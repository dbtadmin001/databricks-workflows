"""Silver: clean, conform, dedupe, validate referential integrity, quarantine.

Transform order matches DATA_CONTRACTS.md exactly:
1. Parse SHIP_DATE (3 known formats), normalize STATUS, clean UNIT_COST.
2. Drop exact full-row duplicates.
3. Classify remaining SHIPMENT_ID collisions as conflicting_duplicate.
4. Validate referential integrity against conformed dimensions.
5. Validate quantity (missing / non-positive).
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

STATUS_MAP = {
    "cancelled": "cancelled",
    "delivered": "delivered",
    "in transit": "in_transit",
    "pending": "pending",
}


def conform_dimension(bronze: DataFrame, *, business_key: str) -> DataFrame:
    """Pass-through conformed dimension: trim strings, drop metadata cols."""
    columns = [c for c in bronze.columns if not c.startswith("_")]
    trimmed = bronze.select(*[F.trim(F.col(c)).alias(c) for c in columns])
    return trimmed.dropDuplicates([business_key])


def _parse_ship_date(col: str):
    return F.coalesce(
        F.try_to_timestamp(F.col(col), F.lit("yyyy-MM-dd")).cast("date"),
        F.try_to_timestamp(F.col(col), F.lit("MM/dd/yyyy")).cast("date"),
        F.try_to_timestamp(F.col(col), F.lit("dd-MMM-yy")).cast("date"),
    )


def _normalize_status(col: str):
    normalized = F.trim(F.lower(F.col(col)))
    mapping = F.create_map(
        *[item for pair in STATUS_MAP.items() for item in (F.lit(pair[0]), F.lit(pair[1]))]
    )
    return mapping[normalized]


def _clean_cost(col: str):
    return F.regexp_replace(F.col(col), r"[$,]", "").cast("decimal(10,2)")


def clean_shipments(bronze_shipments: DataFrame) -> DataFrame:
    """Apply cleaning transforms; keep original raw columns alongside cleaned ones."""
    return bronze_shipments.select(
        "SHIPMENT_ID",
        "WAREHOUSE_ID",
        "PROGRAMME_ID",
        "ITEM_CODE",
        F.trim(F.col("QUANTITY")).alias("quantity_raw"),
        F.col("QUANTITY").cast("int").alias("quantity"),
        _parse_ship_date("SHIP_DATE").alias("ship_date"),
        F.col("SHIP_DATE").alias("ship_date_raw"),
        _normalize_status("STATUS").alias("status"),
        F.col("STATUS").alias("status_raw"),
        _clean_cost("UNIT_COST").alias("unit_cost"),
        "_ingest_ts",
        "_source_file",
        "_run_id",
    )


def _reason(condition, message: str):
    return F.when(condition, F.lit(message))


def normalize_and_quarantine(
    bronze_shipments: DataFrame,
    silver_warehouses: DataFrame,
    silver_programmes: DataFrame,
    silver_items: DataFrame,
) -> tuple[DataFrame, DataFrame]:
    cleaned = clean_shipments(bronze_shipments)

    # Step 2: drop exact full-row duplicates (compare on the raw+cleaned business columns).
    dedup_cols = [
        "SHIPMENT_ID",
        "WAREHOUSE_ID",
        "PROGRAMME_ID",
        "ITEM_CODE",
        "quantity_raw",
        "ship_date_raw",
        "status_raw",
        "_source_file",
    ]
    deduped = cleaned.dropDuplicates(dedup_cols)

    # Step 3: classify remaining SHIPMENT_ID collisions as conflicting duplicates.
    collision_window = Window.partitionBy("SHIPMENT_ID")
    with_collision_count = deduped.withColumn(
        "_collision_count", F.count("*").over(collision_window)
    )

    valid_warehouses = silver_warehouses.select(F.col("WAREHOUSE_ID").alias("_wh"))
    valid_programmes = silver_programmes.select(F.col("PROGRAMME_ID").alias("_prg"))
    valid_items = silver_items.select(F.col("ITEM_CODE").alias("_itm"))

    joined = (
        with_collision_count.join(valid_warehouses, F.col("WAREHOUSE_ID") == F.col("_wh"), "left")
        .join(valid_programmes, F.col("PROGRAMME_ID") == F.col("_prg"), "left")
        .join(valid_items, F.col("ITEM_CODE") == F.col("_itm"), "left")
    )

    classified = joined.withColumn(
        "quarantine_reason",
        F.concat_ws(
            "; ",
            _reason(F.col("_collision_count") > 1, "conflicting_duplicate"),
            _reason(F.col("_wh").isNull(), "missing_warehouse"),
            _reason(F.col("_prg").isNull(), "missing_programme"),
            _reason(F.col("_itm").isNull(), "missing_item"),
            _reason(
                F.col("quantity_raw").isNull() | (F.col("quantity_raw") == ""),
                "missing_quantity",
            ),
            _reason(
                (F.col("quantity_raw").isNotNull())
                & (F.col("quantity_raw") != "")
                & (F.col("quantity") <= 0),
                "non_positive_quantity",
            ),
            _reason(
                F.col("ship_date_raw").isNotNull()
                & (F.trim(F.col("ship_date_raw")) != "")
                & F.col("ship_date").isNull(),
                "invalid_ship_date",
            ),
        ),
    )

    quarantine = classified.filter(F.col("quarantine_reason") != "").select(
        "SHIPMENT_ID",
        "WAREHOUSE_ID",
        "PROGRAMME_ID",
        "ITEM_CODE",
        F.col("quantity_raw").alias("QUANTITY"),
        F.col("ship_date_raw").alias("SHIP_DATE"),
        F.col("status_raw").alias("STATUS"),
        "unit_cost",
        "quarantine_reason",
        "_source_file",
        "_ingest_ts",
        "_run_id",
    )

    accepted = classified.filter(F.col("quarantine_reason") == "").select(
        "SHIPMENT_ID",
        "WAREHOUSE_ID",
        "PROGRAMME_ID",
        "ITEM_CODE",
        "quantity",
        "ship_date",
        "status",
        "unit_cost",
        "_source_file",
        "_ingest_ts",
        "_run_id",
    )

    return accepted, quarantine
