import pytest

from projects.pos_inventory_analytics.modules.pipeline import (
    classify_inventory_change,
    classify_inventory_snapshot,
    explode_inventory_changes,
    latest_inventory_snapshot,
    to_bronze_events,
    to_bronze_snapshots,
    to_gold_inventory_current,
)

pytestmark = [pytest.mark.component, pytest.mark.docker_compat]

EVENT_SCHEMA = (
    "trans_id string, store_id int, date_time string, change_type_id int, "
    "items array<struct<item_id:int,quantity:int>>, bopis_order_id string"
)
SNAPSHOT_SCHEMA = (
    "id int, item_id int, employee_id int, store_id int, date_time string, quantity int"
)


def _store_ref(spark):
    return spark.createDataFrame(
        [
            (1, "Kampala Central", "physical"),
            (2, "Entebbe Airport", "physical"),
            (3, "Jinja Main", "physical"),
            (99, "Online", "online"),
        ],
        ["store_id", "store_name", "store_type"],
    )


def _item_ref(spark):
    return spark.createDataFrame(
        [(1001, "Rice 2kg", "grocery", 12), (1002, "Maize Flour 2kg", "grocery", 13)],
        ["item_id", "item_name", "category", "safety_stock_quantity"],
    )


def _change_type_ref(spark):
    return spark.createDataFrame(
        [
            (1, "sale", "negative"),
            (2, "restock", "positive"),
            (3, "shrinkage", "negative"),
            (4, "bopis", "negative"),
        ],
        ["change_type_id", "change_type", "expected_sign"],
    )


def test_explode_and_classify_matches_verified_fixture_defects(spark):
    # Mirrors the real embedded defects from data/raw/pos_data/landing/inventory_events
    # (see REQUIREMENTS.md "Verified-source requirements"): one exact-duplicate
    # trans_id, a null date_time, a null store_id, an orphan item_id.
    events = spark.createDataFrame(
        [
            ("TXN-1", 1, "2026-07-01T08:00:00Z", 1, [(1001, -2)], None),
            ("TXN-000026", 3, "2026-07-02T00:48:42Z", 1, [(1002, -4)], None),
            ("TXN-000026", 3, "2026-07-02T00:48:42Z", 1, [(1002, -4)], None),  # exact duplicate
            ("BAD-NULLTIME", 1, None, 1, [(1002, -1)], None),
            ("BAD-NULLSTORE", None, "2026-07-02T10:00:00Z", 1, [(1001, -1)], None),
            ("BAD-UNKNOWNITEM", 1, "2026-07-02T11:00:00Z", 1, [(9999, -1)], None),
        ],
        EVENT_SCHEMA,
    )

    bronze = to_bronze_events(events)
    exploded = explode_inventory_changes(bronze)
    accepted, quarantine = classify_inventory_change(
        exploded, _store_ref(spark), _item_ref(spark), _change_type_ref(spark)
    )

    # TXN-000026 collapses to one accepted row (dedup on trans_id+item_id).
    assert accepted.count() == 2
    assert {row.trans_id for row in accepted.collect()} == {"TXN-1", "TXN-000026"}

    reasons_by_trans = {row.trans_id: set(row.quarantine_reasons) for row in quarantine.collect()}
    assert reasons_by_trans["BAD-NULLTIME"] == {"missing_date_time"}
    # A null store_id is "missing", not "unknown" -- unknown_store_id is reserved
    # for a non-null value that fails to match a reference row.
    assert reasons_by_trans["BAD-NULLSTORE"] == {"missing_store_id"}
    assert reasons_by_trans["BAD-UNKNOWNITEM"] == {"unknown_item_id"}


def test_invalid_sign_is_quarantined(spark):
    events = spark.createDataFrame(
        [
            ("TXN-BADSIGN", 1, "2026-07-01T08:00:00Z", 2, [(1001, -5)], None)
        ],  # restock must be positive
        EVENT_SCHEMA,
    )
    exploded = explode_inventory_changes(to_bronze_events(events))
    accepted, quarantine = classify_inventory_change(
        exploded, _store_ref(spark), _item_ref(spark), _change_type_ref(spark)
    )
    assert accepted.count() == 0
    assert set(quarantine.first().quarantine_reasons) == {"invalid_quantity_sign"}


def test_multi_item_transaction_explodes_to_one_row_per_item(spark):
    events = spark.createDataFrame(
        [("TXN-MULTI", 1, "2026-07-01T08:00:00Z", 1, [(1001, -1), (1002, -2)], None)],
        EVENT_SCHEMA,
    )
    exploded = explode_inventory_changes(to_bronze_events(events))
    assert exploded.count() == 2
    assert set(exploded.select("item_id").rdd.flatMap(lambda r: r).collect()) == {1001, 1002}


def test_snapshot_classification_matches_verified_fixture_defects(spark):
    # Mirrors the real snapshot file: one row with a null store_id (id=202) and
    # one row referencing the orphan item_id=9999.
    snapshots = spark.createDataFrame(
        [
            (1, 1001, 5037, 1, "2026-07-01T06:00:00Z", 51),
            (202, 1001, 5011, None, "2026-07-01T06:00:00Z", 22),
            (203, 9999, 5012, 1, "2026-07-01T06:00:00Z", 5),
            (204, 1002, 5013, 1, "2026-07-01T06:00:00Z", -3),
        ],
        SNAPSHOT_SCHEMA,
    )
    accepted, quarantine = classify_inventory_snapshot(
        to_bronze_snapshots(snapshots), _store_ref(spark), _item_ref(spark)
    )
    assert accepted.count() == 1
    reasons_by_id = {row.id: set(row.quarantine_reasons) for row in quarantine.collect()}
    assert reasons_by_id[202] == {"missing_store_id"}
    assert reasons_by_id[203] == {"unknown_item_id"}
    assert reasons_by_id[204] == {"negative_snapshot_quantity"}


def test_latest_snapshot_selects_by_date_time_not_id_or_arrival_order(spark):
    snapshots = spark.createDataFrame(
        [
            (1, 1001, 1, 1, "2026-07-01T06:00:00Z", 50),
            # Higher id, arrives "later" in a file sense, but an OLDER date_time --
            # must not win (mirrors the incremental release's late-but-older rows).
            (2, 1001, 1, 1, "2026-06-30T06:00:00Z", 999),
            (3, 1001, 1, 1, "2026-07-02T06:00:00Z", 40),
        ],
        SNAPSHOT_SCHEMA,
    )
    latest = latest_inventory_snapshot(snapshots)
    assert latest.count() == 1
    row = latest.first()
    assert row.quantity == 40
    assert row.date_time == "2026-07-02T06:00:00Z"


def test_gold_excludes_online_bopis_leg_but_keeps_standalone_online_activity(spark):
    snapshots = spark.createDataFrame(
        [(1, 1001, 1, 1, "2026-07-01T06:00:00Z", 50), (2, 1001, 1, 99, "2026-07-01T06:00:00Z", 20)],
        SNAPSHOT_SCHEMA,
    )
    latest = latest_inventory_snapshot(snapshots)

    changes = spark.createDataFrame(
        [
            # BOPIS pair: pickup leg (physical store) counts, online leg excluded.
            ("PICKUP-1", 1, "2026-07-01T09:00:00Z", 4, 1001, -3, "BOPIS-1"),
            ("ONLINE-1", 99, "2026-07-01T09:00:00Z", 4, 1001, -3, "BOPIS-1"),
            # Standalone online-store sale, no bopis_order_id -- must still count.
            ("TXN-ONLINE-SALE", 99, "2026-07-01T10:00:00Z", 1, 1001, -2, None),
        ],
        "trans_id string, store_id int, date_time string, change_type_id int, "
        "item_id int, quantity int, bopis_order_id string",
    )

    gold = to_gold_inventory_current(latest, changes, _store_ref(spark), _item_ref(spark))
    by_store = {row.store_id: row for row in gold.collect()}

    assert by_store[1].inventory_change_quantity == -3
    assert by_store[1].current_inventory_quantity == 47
    assert by_store[99].inventory_change_quantity == -2  # only the standalone sale
    assert by_store[99].current_inventory_quantity == 18


def test_gold_left_joins_snapshot_so_items_with_no_changes_remain_visible(spark):
    snapshots = spark.createDataFrame(
        [(1, 1001, 1, 1, "2026-07-01T06:00:00Z", 10)], SNAPSHOT_SCHEMA
    )
    latest = latest_inventory_snapshot(snapshots)
    changes = spark.createDataFrame(
        [],
        "trans_id string, store_id int, date_time string, change_type_id int, "
        "item_id int, quantity int, bopis_order_id string",
    )
    gold = to_gold_inventory_current(latest, changes, _store_ref(spark), _item_ref(spark))
    row = gold.first()
    assert row.inventory_change_quantity == 0
    assert row.current_inventory_quantity == 10


def test_below_safety_stock_flag(spark):
    snapshots = spark.createDataFrame(
        [(1, 1001, 1, 1, "2026-07-01T06:00:00Z", 5)],
        SNAPSHOT_SCHEMA,  # safety stock for 1001 is 12
    )
    latest = latest_inventory_snapshot(snapshots)
    changes = spark.createDataFrame(
        [],
        "trans_id string, store_id int, date_time string, change_type_id int, "
        "item_id int, quantity int, bopis_order_id string",
    )
    gold = to_gold_inventory_current(latest, changes, _store_ref(spark), _item_ref(spark))
    assert gold.first().below_safety_stock is True
