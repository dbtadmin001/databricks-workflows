from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

# Verified against the real assessment fixture (see REQUIREMENTS.md,
# "Verified-source requirements"): bopis_order_id is set only on
# change_type_id=4 (bopis) records, exactly one ONLINE- leg (store_id=99) and
# one PICKUP- leg (a physical store) per bopis_order_id. store_id=99 also
# carries genuine standalone activity across all four change types with no
# bopis_order_id -- excluding all of store_id=99 would wrongly zero that out.
ONLINE_STORE_ID = 99


def _optional_column(frame: DataFrame, name: str):
    return F.col(name) if name in frame.columns else F.lit(None).cast("string")


def to_bronze_events(source: DataFrame) -> DataFrame:
    """Preserve the raw nested transaction document; stamp ingestion time."""
    return source.withColumn("_ingested_at", F.current_timestamp())


def to_bronze_snapshots(source: DataFrame) -> DataFrame:
    """Preserve the raw snapshot row; stamp ingestion time."""
    return source.withColumn("_ingested_at", F.current_timestamp())


def explode_inventory_changes(bronze_events: DataFrame) -> DataFrame:
    """One row per transaction-item. Grain: trans_id + item_id (pre-dedup)."""
    channel = _optional_column(bronze_events, "channel")
    bopis_order_id = _optional_column(bronze_events, "bopis_order_id")
    return bronze_events.withColumn("item", F.explode("items")).select(
        F.col("trans_id"),
        F.col("store_id"),
        F.col("date_time").cast("timestamp").alias("date_time"),
        F.col("change_type_id"),
        F.col("item.item_id").alias("item_id"),
        F.col("item.quantity").cast("int").alias("quantity"),
        bopis_order_id.alias("bopis_order_id"),
        channel.alias("channel"),
        F.col("_ingested_at"),
    )


def classify_inventory_change(
    exploded: DataFrame,
    store_ref: DataFrame,
    item_ref: DataFrame,
    change_type_ref: DataFrame,
) -> tuple[DataFrame, DataFrame]:
    """Return (accepted, quarantine). Grain: trans_id + item_id, deduplicated.

    DQ rules per REQUIREMENTS.md: required fields non-null; store/item/
    change-type references valid; quantity sign matches
    inventory_change_type.expected_sign. Invalid rows are quarantined with a
    reason code, never silently dropped into Silver.
    """
    valid_stores = store_ref.select(F.col("store_id").alias("_valid_store_id")).distinct()
    valid_items = item_ref.select(F.col("item_id").alias("_valid_item_id")).distinct()
    signs = change_type_ref.select(
        F.col("change_type_id").alias("_ct_id"),
        F.when(F.col("expected_sign") == "positive", F.lit(1))
        .otherwise(F.lit(-1))
        .alias("_expected_sign"),
    )

    checked = (
        exploded.join(valid_stores, exploded["store_id"] == F.col("_valid_store_id"), "left")
        .join(valid_items, exploded["item_id"] == F.col("_valid_item_id"), "left")
        .join(signs, exploded["change_type_id"] == F.col("_ct_id"), "left")
    )

    actual_sign = (
        F.when(F.col("quantity") > 0, F.lit(1))
        .when(F.col("quantity") < 0, F.lit(-1))
        .otherwise(F.lit(None))
    )

    reasons = F.filter(
        F.array(
            F.when(F.col("trans_id").isNull() | (F.col("trans_id") == ""), "missing_trans_id"),
            F.when(F.col("store_id").isNull(), "missing_store_id"),
            F.when(F.col("date_time").isNull(), "missing_date_time"),
            F.when(F.col("item_id").isNull(), "missing_item_id"),
            F.when(F.col("quantity").isNull(), "missing_quantity"),
            F.when(
                F.col("store_id").isNotNull() & F.col("_valid_store_id").isNull(),
                "unknown_store_id",
            ),
            F.when(
                F.col("item_id").isNotNull() & F.col("_valid_item_id").isNull(),
                "unknown_item_id",
            ),
            F.when(
                F.col("change_type_id").isNotNull() & F.col("_ct_id").isNull(),
                "unknown_change_type_id",
            ),
            F.when(
                F.col("_ct_id").isNotNull()
                & actual_sign.isNotNull()
                & (actual_sign != F.col("_expected_sign")),
                "invalid_quantity_sign",
            ),
        ),
        lambda reason: reason.isNotNull(),
    )

    classified = checked.withColumn("quarantine_reasons", reasons).drop(
        "_valid_store_id", "_valid_item_id", "_ct_id", "_expected_sign"
    )
    quarantine = classified.where(F.size("quarantine_reasons") > 0)
    eligible = classified.where(F.size("quarantine_reasons") == 0).drop("quarantine_reasons")

    dedup_window = Window.partitionBy("trans_id", "item_id").orderBy(
        F.col("date_time").desc(), F.col("_ingested_at").desc()
    )
    accepted = (
        eligible.withColumn("_rank", F.row_number().over(dedup_window))
        .filter("_rank = 1")
        .drop("_rank")
    )
    return accepted, quarantine


def classify_inventory_snapshot(
    bronze_snapshot: DataFrame,
    store_ref: DataFrame,
    item_ref: DataFrame,
) -> tuple[DataFrame, DataFrame]:
    """Return (accepted, quarantine) snapshot rows. Grain: one row per file row.

    DQ rules per REQUIREMENTS.md: required fields non-null; store/item
    references valid; quantity non-negative.
    """
    valid_stores = store_ref.select(F.col("store_id").alias("_valid_store_id")).distinct()
    valid_items = item_ref.select(F.col("item_id").alias("_valid_item_id")).distinct()

    typed = bronze_snapshot.withColumn(
        "date_time", F.col("date_time").cast("timestamp")
    ).withColumn("quantity", F.col("quantity").cast("int"))

    checked = typed.join(valid_stores, typed["store_id"] == F.col("_valid_store_id"), "left").join(
        valid_items, typed["item_id"] == F.col("_valid_item_id"), "left"
    )

    reasons = F.filter(
        F.array(
            F.when(F.col("id").isNull(), "missing_id"),
            F.when(F.col("item_id").isNull(), "missing_item_id"),
            F.when(F.col("store_id").isNull(), "missing_store_id"),
            F.when(F.col("date_time").isNull(), "missing_date_time"),
            F.when(F.col("quantity").isNull(), "missing_quantity"),
            F.when(
                F.col("store_id").isNotNull() & F.col("_valid_store_id").isNull(),
                "unknown_store_id",
            ),
            F.when(
                F.col("item_id").isNotNull() & F.col("_valid_item_id").isNull(),
                "unknown_item_id",
            ),
            F.when(
                F.col("quantity").isNotNull() & (F.col("quantity") < 0),
                "negative_snapshot_quantity",
            ),
        ),
        lambda reason: reason.isNotNull(),
    )

    classified = checked.withColumn("quarantine_reasons", reasons).drop(
        "_valid_store_id", "_valid_item_id"
    )
    quarantine = classified.where(F.size("quarantine_reasons") > 0)
    accepted = classified.where(F.size("quarantine_reasons") == 0).drop("quarantine_reasons")
    return accepted, quarantine


def latest_inventory_snapshot(accepted_snapshot: DataFrame) -> DataFrame:
    """One row per store_id + item_id: the most recent valid snapshot by date_time.

    Selection is strictly by date_time (never file arrival order or filename)
    per REQUIREMENTS.md -- this is load-bearing for the incremental release's
    late-arriving-but-older-dated snapshot rows.
    """
    latest_window = Window.partitionBy("store_id", "item_id").orderBy(
        F.col("date_time").desc(), F.col("id").desc()
    )
    return (
        accepted_snapshot.withColumn("_rank", F.row_number().over(latest_window))
        .filter("_rank = 1")
        .drop("_rank")
    )


def to_gold_inventory_current(
    latest_snapshot: DataFrame,
    accepted_inventory_change: DataFrame,
    store_ref: DataFrame,
    item_ref: DataFrame,
) -> DataFrame:
    """Grain: store_id + item_id. See DATA_CONTRACTS.md "Gold" for column meanings."""
    countable_changes = accepted_inventory_change.where(
        ~((F.col("store_id") == F.lit(ONLINE_STORE_ID)) & F.col("bopis_order_id").isNotNull())
    )
    latest_snapshot.createOrReplaceTempView("_latest_snapshot")
    countable_changes.createOrReplaceTempView("_countable_changes")
    store_ref.createOrReplaceTempView("_store_ref")
    item_ref.createOrReplaceTempView("_item_ref")

    return latest_snapshot.sparkSession.sql(
        """
        WITH change_totals AS (
          SELECT c.store_id, c.item_id,
                 SUM(c.quantity) AS inventory_change_quantity,
                 MAX(c.date_time) AS last_change_date_time
          FROM _countable_changes c
          JOIN _latest_snapshot s
            ON c.store_id = s.store_id AND c.item_id = s.item_id
           AND c.date_time >= s.date_time
          GROUP BY c.store_id, c.item_id
        )
        SELECT
          s.store_id,
          st.store_name,
          st.store_type,
          s.item_id,
          it.item_name,
          it.category,
          s.quantity AS snapshot_quantity,
          s.date_time AS snapshot_date_time,
          COALESCE(t.inventory_change_quantity, 0) AS inventory_change_quantity,
          s.quantity + COALESCE(t.inventory_change_quantity, 0) AS current_inventory_quantity,
          it.safety_stock_quantity,
          (s.quantity + COALESCE(t.inventory_change_quantity, 0)) < it.safety_stock_quantity
            AS below_safety_stock,
          GREATEST(s.date_time, COALESCE(t.last_change_date_time, s.date_time))
            AS last_inventory_timestamp
        FROM _latest_snapshot s
        JOIN _store_ref st ON s.store_id = st.store_id
        JOIN _item_ref it ON s.item_id = it.item_id
        LEFT JOIN change_totals t ON s.store_id = t.store_id AND s.item_id = t.item_id
        """
    )
