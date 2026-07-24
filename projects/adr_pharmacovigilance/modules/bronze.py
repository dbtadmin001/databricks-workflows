"""Bronze layer: idempotent document registry + content capture, plus the
historical event CSV and reference-table loads. Document-level extraction
runs driver-side over the (small, 140-document) synthetic set — the
production equivalent is Auto Loader (`cloudFiles`) landing files into a
Unity Catalog volume and a `foreachBatch`/UDF call to `ai_parse_document()`;
see REQUIREMENTS.md Decision 3 for why Auto Loader is the justified choice
for the real document stream even though this MVP walks a static directory.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
)

from projects.adr_pharmacovigilance.modules.extraction import (
    TextExtractor,
    classify_and_extract,
    default_extractor,
)

MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def discover_documents(documents_dir: str) -> list[Path]:
    root = Path(documents_dir)
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MIME_BY_EXTENSION
    )


def load_arrival_manifest(manifest_csv_path: str) -> dict[str, dict[str, str]]:
    """file_name -> arrival metadata row, keyed for O(1) join during
    registration (REQUIREMENTS.md: manifest is the authoritative arrival
    source for the assignment document set, verified 1:1 against disk)."""
    import csv

    with open(manifest_csv_path, newline="", encoding="utf-8-sig") as handle:
        return {row["file_name"]: row for row in csv.DictReader(handle)}


def register_and_extract_documents(
    documents_dir: str,
    manifest_by_file: dict[str, dict[str, str]],
    run_id: str,
    extractor: TextExtractor | None = None,
) -> list[dict]:
    """Walk the document directory once, computing registry metadata and
    running extraction for every file. Returns plain dicts (not a DataFrame)
    so this function stays testable without a SparkSession."""
    extractor = extractor or default_extractor()
    rows: list[dict] = []
    for path in discover_documents(documents_dir):
        raw_bytes = path.read_bytes()
        checksum = _sha256(raw_bytes)
        mime_type = MIME_BY_EXTENSION[path.suffix.lower()]
        arrival = manifest_by_file.get(path.name, {})
        outcome = classify_and_extract(raw_bytes, mime_type, extractor)
        rows.append(
            {
                "document_id": checksum,  # content-addressed: identical bytes -> identical document_id
                "file_name": path.name,
                "file_path": str(path),
                "relative_path": arrival.get("relative_path", path.name),
                "extension": path.suffix.lower(),
                "mime_type": mime_type,
                "size_bytes": float(path.stat().st_size),
                "checksum_sha256": checksum,
                "modification_time": float(path.stat().st_mtime),
                "arrival_timestamp": arrival.get("arrival_timestamp"),
                "arrival_batch": arrival.get("arrival_batch"),
                "source_system": arrival.get("source_system"),
                "ingestion_timestamp": None,  # filled by add_bronze_metadata (Spark side, deterministic per run)
                "run_id": run_id,
                "classification": outcome.classification,
                "extraction_confidence": outcome.confidence,
                "extraction_method": outcome.text_extraction.method,
                "extraction_error": outcome.text_extraction.error,
                "raw_text": outcome.text_extraction.text,
                "parsed_fields_json": json.dumps(_parsed_fields_to_json(outcome.fields)),
            }
        )
    return rows


def dedupe_by_checksum(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split the full per-file arrival list (every physical file, always
    written verbatim to `bronze_document_arrivals`) into a checksum-deduped
    registry (`bronze_documents` — one row per distinct content, keyed by
    `document_id`) and the duplicate-arrival records.

    Confirmed necessary by testing against the real fixture set: the
    assignment's `duplicate_116_ADR-2026-0031_CIOMS_initial.pdf` is
    byte-identical to `ADR-2026-0031_CIOMS_initial.pdf` (verified sha256
    match), so relying only on the cross-run MERGE in
    `write_bronze_documents` was not enough — a single ingestion batch can
    itself contain two files with the same checksum, which a plain
    `df.write.saveAsTable(...)` on first run would have written as two rows
    sharing one `document_id`, violating the registry's key. Canonical row
    per checksum is chosen deterministically by `file_name` order."""
    by_checksum: dict[str, list[dict]] = {}
    for row in rows:
        by_checksum.setdefault(row["document_id"], []).append(row)

    deduped: list[dict] = []
    duplicate_arrivals: list[dict] = []
    for checksum, group in by_checksum.items():
        ordered = sorted(group, key=lambda r: r["file_name"])
        canonical, *duplicates = ordered
        deduped.append(canonical)
        for dup in duplicates:
            duplicate_arrivals.append(
                {
                    "document_id": checksum,
                    "duplicate_file_name": dup["file_name"],
                    "duplicate_relative_path": dup["relative_path"],
                    "canonical_file_name": canonical["file_name"],
                    "arrival_timestamp": dup["arrival_timestamp"],
                }
            )
    return deduped, duplicate_arrivals


def _parsed_fields_to_json(fields) -> dict:
    payload = asdict(fields)
    return payload


BRONZE_DOCUMENTS_SCHEMA = StructType(
    [
        StructField("document_id", StringType(), False),
        StructField("file_name", StringType(), False),
        StructField("file_path", StringType(), False),
        StructField("relative_path", StringType(), True),
        StructField("extension", StringType(), True),
        StructField("mime_type", StringType(), True),
        StructField("size_bytes", DoubleType(), True),
        StructField("checksum_sha256", StringType(), False),
        StructField("modification_time", DoubleType(), True),
        StructField("arrival_timestamp", StringType(), True),
        StructField("arrival_batch", StringType(), True),
        StructField("source_system", StringType(), True),
        StructField("run_id", StringType(), False),
        StructField("classification", StringType(), False),
        StructField("extraction_confidence", DoubleType(), False),
        StructField("extraction_method", StringType(), True),
        StructField("extraction_error", StringType(), True),
    ]
)


def build_bronze_documents_df(spark: SparkSession, rows: list[dict]) -> DataFrame:
    """Registry table: one row per distinct document checksum. Re-running
    ingestion over the same files produces the same `document_id` values, so
    a `MERGE ... WHEN NOT MATCHED THEN INSERT` (see `write_bronze_documents`)
    keeps re-ingestion idempotent without inflating the registry."""
    slim_rows = [
        {k: v for k, v in row.items() if k in BRONZE_DOCUMENTS_SCHEMA.fieldNames()} for row in rows
    ]
    df = spark.createDataFrame(slim_rows, schema=BRONZE_DOCUMENTS_SCHEMA)
    return df.withColumn("ingestion_timestamp", F.current_timestamp()).withColumn(
        "processing_status", F.lit("REGISTERED")
    )


def build_bronze_document_content_df(spark: SparkSession, rows: list[dict]) -> DataFrame:
    """Raw extracted text per document, kept separate from the registry so
    the (much larger) text payload doesn't bloat registry scans."""
    slim = [{"document_id": r["document_id"], "raw_text": r["raw_text"]} for r in rows]
    schema = StructType(
        [
            StructField("document_id", StringType(), False),
            StructField("raw_text", StringType(), True),
        ]
    )
    return spark.createDataFrame(slim, schema=schema)


def build_bronze_extraction_payloads_df(spark: SparkSession, rows: list[dict]) -> DataFrame:
    """Raw extraction-service response per document (parsed fields as JSON),
    preserved verbatim per docs/TIMED_MVP.md's Bronze source-fidelity
    contract, independent of whatever Silver later does with these fields."""
    slim = [
        {"document_id": r["document_id"], "parsed_fields_json": r["parsed_fields_json"]}
        for r in rows
    ]
    schema = StructType(
        [
            StructField("document_id", StringType(), False),
            StructField("parsed_fields_json", StringType(), False),
        ]
    )
    return spark.createDataFrame(slim, schema=schema)


def write_bronze_documents(spark: SparkSession, df: DataFrame, catalog: str, schema: str) -> int:
    """Idempotent MERGE on `document_id` (content checksum): re-ingesting an
    unchanged file is a no-op, matching the assignment's explicit
    'exact duplicate files must not create duplicate cases' constraint at
    the Bronze layer (Silver handles near-duplicate, different-checksum
    resubmissions separately — see silver.py)."""
    table_name = f"{catalog}.{schema}.bronze_documents"
    if not spark.catalog.tableExists(table_name):
        df.write.format("delta").saveAsTable(table_name)
        return df.count()

    df.createOrReplaceTempView("_bronze_documents_incoming")
    spark.sql(
        f"""
        MERGE INTO {table_name} AS target
        USING _bronze_documents_incoming AS source
        ON target.document_id = source.document_id
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    return spark.table(table_name).count()


def ingest_historical_events(
    spark: SparkSession, historical_csv_path: str, catalog: str, schema: str
) -> int:
    """Batch-load the 35,000-row historical event CSV (event grain: one row
    per case x product x reaction, per REQUIREMENTS.md profiling)."""
    df = (
        spark.read.option("header", "true")
        .option("inferSchema", "false")
        .csv(historical_csv_path)
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.lit(os.path.basename(historical_csv_path)))
    )
    table_name = f"{catalog}.{schema}.bronze_historical_events"
    df.write.format("delta").mode("overwrite").saveAsTable(table_name)
    return df.count()


REFERENCE_TABLES = {
    "facility_master": "reference/facility_master.csv",
    "district_master": "reference/district_master.csv",
    "product_dictionary": "reference/product_dictionary.csv",
    "reaction_dictionary": "reference/reaction_dictionary.csv",
    "seriousness_rules": "reference/seriousness_rules.csv",
    "pipeline_status_reference": "reference/pipeline_status_reference.csv",
    "arrival_manifest": "reference/arrival_manifest.csv",
}


def ingest_reference_tables(
    spark: SparkSession, raw_dir: str, catalog: str, schema: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table, relative_path in REFERENCE_TABLES.items():
        path = str(Path(raw_dir) / relative_path)
        df = spark.read.option("header", "true").csv(path)
        table_name = f"{catalog}.{schema}.ref_{table}"
        df.write.format("delta").mode("overwrite").saveAsTable(table_name)
        counts[table] = df.count()
    return counts
