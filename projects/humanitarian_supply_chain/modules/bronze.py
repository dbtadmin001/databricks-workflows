"""Bronze ingestion: load raw CSVs unmodified, idempotent per source file."""

from __future__ import annotations

import uuid

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

RAW_FILES = {
    "warehouses": "WAREHOUSES.csv",
    "programmes": "PROGRAMMES.csv",
    "items": "ITEMS.csv",
    "shipments": "SHIPMENTS.csv",
}


def read_raw_csv(spark: SparkSession, path: str, source_file: str) -> DataFrame:
    """Read one raw CSV as strings only, no cleaning, plus ingestion metadata."""
    run_id = str(uuid.uuid4())
    return (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .csv(path)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.lit(source_file))
        .withColumn("_run_id", F.lit(run_id))
    )


def write_bronze_table(dataframe: DataFrame, target: str) -> None:
    """Idempotent overwrite-by-source-file: replacing Bronze for a full static
    extract is safe to re-run any number of times without duplicating rows,
    since the whole file is the unit of ingestion (no incremental cursor)."""
    dataframe.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        target
    )


def ingest_all(spark: SparkSession, raw_dir: str, table_names: dict[str, str]) -> dict[str, int]:
    """Load all four raw CSVs into their Bronze tables. Returns row counts."""
    counts: dict[str, int] = {}
    for key, filename in RAW_FILES.items():
        frame = read_raw_csv(spark, f"{raw_dir}/{filename}", filename)
        write_bronze_table(frame, table_names[key])
        counts[key] = frame.count()
    return counts
