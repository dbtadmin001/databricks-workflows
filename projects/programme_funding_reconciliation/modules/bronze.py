from __future__ import annotations

import os
import re
import uuid
from pathlib import PurePosixPath
from typing import Protocol

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

SOURCES = {
    "donors": ("DONORS.csv", "csv"),
    "programmes_q1": ("PROGRAMMES_SNAPSHOT_2025Q1.csv", "csv"),
    "programmes_q2": ("PROGRAMMES_SNAPSHOT_2025Q2.csv", "csv"),
    "contributions_csv": ("CONTRIBUTIONS.csv", "csv"),
    "contributions_json": ("CONTRIBUTIONS_2025Q3.json", "json"),
    "grants": ("GRANTS.json", "json"),
    "exchange_rates": ("EXCHANGE_RATES.parquet", "parquet"),
    "legacy_oracle_summary": ("LEGACY_ORACLE_SUMMARY.csv", "csv"),
}

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class FileSystem(Protocol):
    def mkdirs(self, path: str) -> object: ...

    def cp(self, source: str, destination: str, recurse: bool = False) -> object: ...


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


def volume_raw_path(catalog: str, schema: str, volume: str) -> str:
    for value, label in ((catalog, "catalog"), (schema, "schema"), (volume, "volume")):
        validate_identifier(value, label)
    return f"/Volumes/{catalog}/{schema}/{volume}/raw"


def stage_raw_files(
    fs: FileSystem,
    bundle_raw_dir: str,
    catalog: str,
    schema: str,
    volume: str,
) -> str:
    """Copy the immutable assignment snapshot into the governed UC landing volume."""
    destination_root = volume_raw_path(catalog, schema, volume)
    fs.mkdirs(destination_root)
    for filename, _ in SOURCES.values():
        source = str(PurePosixPath(bundle_raw_dir.replace("\\", "/")) / filename)
        source_uri = source if ":" in source[:8] else f"file:{source}"
        destination = f"dbfs:{destination_root}/{filename}"
        fs.cp(source_uri, destination, False)
    return destination_root


def load_source_df(spark: SparkSession, source_path: str, source_format: str) -> DataFrame:
    """Reads a source file using the appropriate format-specific reader."""
    reader = spark.read
    if source_format == "csv":
        return reader.option("header", "true").option("inferSchema", "false").csv(source_path)
    if source_format == "json":
        return reader.option("multiLine", "true").json(source_path)
    if source_format == "parquet":
        return reader.parquet(source_path)
    raise ValueError(f"Unsupported format: {source_format}")


def add_bronze_metadata(df: DataFrame, source_path: str, run_id: str) -> DataFrame:
    """Adds standard Bronze metadata columns to a DataFrame."""
    return (
        df.withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.lit(os.path.basename(source_path)))
        .withColumn("_run_id", F.lit(run_id))
    )


def ingest_all_bronze(
    spark: SparkSession,
    raw_data_dir: str,
    catalog: str,
    schema: str,
    run_id: str | None = None,
) -> dict[str, int]:
    """Ingests all eight static sources into Bronze Delta tables and returns their row counts."""
    validate_identifier(catalog, "catalog")
    validate_identifier(schema, "schema")
    if not run_id:
        run_id = str(uuid.uuid4())

    row_counts: dict[str, int] = {}
    for key, (filename, source_format) in SOURCES.items():
        source_path = str(PurePosixPath(raw_data_dir.replace("\\", "/")) / filename)
        table_name = f"{catalog}.{schema}.bronze_{key}"

        df = load_source_df(spark, source_path, source_format)
        bronze_df = add_bronze_metadata(df, source_path, run_id)

        bronze_df.write.format("delta").mode("overwrite").saveAsTable(table_name)
        row_counts[key] = bronze_df.count()

    return row_counts
