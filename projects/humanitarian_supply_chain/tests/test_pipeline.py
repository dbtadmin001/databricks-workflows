"""Component test: Bronze -> Silver -> Gold transformation logic against the
real data/raw/*.csv, asserting the exact reconciliation baseline in
ACCEPTANCE_CRITERIA.md.

Exercises the transformation functions directly on DataFrames/temp views
rather than through run_pipeline()'s saveAsTable/WAP writes: local Windows
Spark requires a winutils.exe binary for Delta table writes that isn't
available in this environment (a Windows-local-only limitation, not present
on a real Databricks cluster, where run_pipeline()'s WAP path is what
actually executes). This still proves the transformation logic itself --
cleaning, dedup, conflicting-duplicate detection, referential integrity,
quarantine classification, and the Gold SQL joins/aggregation -- is correct.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from projects.humanitarian_supply_chain.modules.bronze import RAW_FILES, read_raw_csv
from projects.humanitarian_supply_chain.modules.gold import (
    build_fact_shipments,
    build_programme_monthly_summary,
    register_views,
)
from projects.humanitarian_supply_chain.modules.silver import conform_dimension, normalize_and_quarantine

pytestmark = pytest.mark.component

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


@pytest.fixture(scope="module")
def bronze_frames(spark):
    return {
        key: read_raw_csv(spark, str(RAW_DIR / filename), filename)
        for key, filename in RAW_FILES.items()
    }


@pytest.fixture(scope="module")
def silver_dimensions(bronze_frames):
    return {
        "warehouses": conform_dimension(bronze_frames["warehouses"], business_key="WAREHOUSE_ID"),
        "programmes": conform_dimension(bronze_frames["programmes"], business_key="PROGRAMME_ID"),
        "items": conform_dimension(bronze_frames["items"], business_key="ITEM_CODE"),
    }


@pytest.fixture(scope="module")
def silver_shipments(bronze_frames, silver_dimensions):
    return normalize_and_quarantine(
        bronze_frames["shipments"],
        silver_dimensions["warehouses"],
        silver_dimensions["programmes"],
        silver_dimensions["items"],
    )


def test_bronze_row_counts(bronze_frames):
    assert bronze_frames["warehouses"].count() == 6
    assert bronze_frames["programmes"].count() == 5
    assert bronze_frames["items"].count() == 7
    assert bronze_frames["shipments"].count() == 167


def test_silver_reconciles_to_acceptance_baseline(silver_shipments):
    accepted, quarantine = silver_shipments
    assert accepted.count() == 137
    assert quarantine.count() == 24

    reasons = "; ".join(
        row["quarantine_reason"]
        for row in quarantine.select("quarantine_reason").distinct().collect()
    )
    assert "conflicting_duplicate" in reasons
    assert "missing_warehouse" in reasons
    assert "missing_programme" in reasons
    assert "missing_quantity" in reasons
    assert "non_positive_quantity" in reasons

    shp5011 = quarantine.filter("SHIPMENT_ID = 'SHP5011'")
    assert shp5011.count() == 2
    assert accepted.filter("SHIPMENT_ID = 'SHP5011'").count() == 0


def test_silver_date_parsing_is_tolerant_in_ansi_mode(spark):
    previous_ansi = spark.conf.get("spark.sql.ansi.enabled")
    spark.conf.set("spark.sql.ansi.enabled", "true")
    try:
        rows = [
            ("ISO", "2024-01-15"),
            ("US", "06/23/2025"),
            ("ORACLE", "10-SEP-24"),
            ("INVALID", "not-a-date"),
        ]
        bronze = spark.createDataFrame(
            [
                (
                    shipment_id,
                    "WH001",
                    "PRG001",
                    "ITM001",
                    "1",
                    ship_date,
                    "DELIVERED",
                    "10.00",
                    datetime(2026, 7, 16),
                    "SHIPMENTS.csv",
                    "ansi-date-test",
                )
                for shipment_id, ship_date in rows
            ],
            [
                "SHIPMENT_ID",
                "WAREHOUSE_ID",
                "PROGRAMME_ID",
                "ITEM_CODE",
                "QUANTITY",
                "SHIP_DATE",
                "STATUS",
                "UNIT_COST",
                "_ingest_ts",
                "_source_file",
                "_run_id",
            ],
        )
        warehouses = spark.createDataFrame([("WH001",)], ["WAREHOUSE_ID"])
        programmes = spark.createDataFrame([("PRG001",)], ["PROGRAMME_ID"])
        items = spark.createDataFrame([("ITM001",)], ["ITEM_CODE"])

        accepted, quarantine = normalize_and_quarantine(bronze, warehouses, programmes, items)

        parsed = {
            row.SHIPMENT_ID: row.ship_date.isoformat()
            for row in accepted.select("SHIPMENT_ID", "ship_date").collect()
        }
        assert parsed == {
            "ISO": "2024-01-15",
            "US": "2025-06-23",
            "ORACLE": "2024-09-10",
        }
        invalid = quarantine.select("SHIPMENT_ID", "quarantine_reason").collect()
        assert [(row.SHIPMENT_ID, row.quarantine_reason) for row in invalid] == [
            ("INVALID", "invalid_ship_date")
        ]
    finally:
        spark.conf.set("spark.sql.ansi.enabled", previous_ansi)


def test_silver_is_idempotent(bronze_frames, silver_dimensions):
    """Running the same transform twice on the same input yields identical counts."""
    accepted1, quarantine1 = normalize_and_quarantine(
        bronze_frames["shipments"],
        silver_dimensions["warehouses"],
        silver_dimensions["programmes"],
        silver_dimensions["items"],
    )
    accepted2, quarantine2 = normalize_and_quarantine(
        bronze_frames["shipments"],
        silver_dimensions["warehouses"],
        silver_dimensions["programmes"],
        silver_dimensions["items"],
    )
    assert accepted1.count() == accepted2.count() == 137
    assert quarantine1.count() == quarantine2.count() == 24


def test_gold_fact_and_summary(spark, silver_shipments, silver_dimensions):
    accepted, _ = silver_shipments
    register_views(
        spark,
        accepted,
        silver_dimensions["warehouses"],
        silver_dimensions["programmes"],
        silver_dimensions["items"],
    )
    fact = build_fact_shipments(spark)
    assert fact.count() == 137

    summary = build_programme_monthly_summary(spark, fact)
    cancelled_in_summary = summary.filter("year_month IS NULL").count()
    assert cancelled_in_summary == 0

    total_qty_fact = fact.filter("status != 'cancelled'").agg({"quantity": "sum"}).collect()[0][0]
    total_qty_summary = summary.agg({"total_qty": "sum"}).collect()[0][0]
    assert int(total_qty_fact) == int(total_qty_summary)
