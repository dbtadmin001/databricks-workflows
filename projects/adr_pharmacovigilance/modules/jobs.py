"""Orchestration entrypoints called by the Bundle job tasks / notebooks
(see resources/10_adr_pharmacovigilance.job.yml and src/notebooks/*.py).
Each `run_*` function is idempotent and independently re-runnable, matching
this repo's standard Bronze -> Silver -> Gold WAP -> SQL validation -> dashboard
job chain (see projects/09_github_sentiment_analytics for the established
pattern this mirrors).
"""

from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from pyspark.sql import SparkSession

from projects.adr_pharmacovigilance.modules import bronze, gold, silver


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--raw-dir", required=True)
    return parser.parse_args()


def _load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def run_bronze(
    spark: SparkSession, raw_dir: str, catalog: str, schema: str, run_id: str | None = None
) -> dict:
    run_id = run_id or str(uuid.uuid4())
    manifest = bronze.load_arrival_manifest(
        str(Path(raw_dir) / "reference" / "arrival_manifest.csv")
    )
    all_arrivals = bronze.register_and_extract_documents(
        str(Path(raw_dir) / "documents" / "synthetic"), manifest, run_id
    )
    rows, duplicate_arrivals = bronze.dedupe_by_checksum(all_arrivals)

    arrivals_df = spark.createDataFrame(
        [
            {k: v for k, v in r.items() if k in bronze.BRONZE_DOCUMENTS_SCHEMA.fieldNames()}
            for r in all_arrivals
        ],
        schema=bronze.BRONZE_DOCUMENTS_SCHEMA,
    )
    arrivals_df.write.format("delta").mode("overwrite").saveAsTable(
        f"{catalog}.{schema}.bronze_document_arrivals"
    )
    if duplicate_arrivals:
        spark.createDataFrame(duplicate_arrivals).write.format("delta").mode(
            "overwrite"
        ).saveAsTable(f"{catalog}.{schema}.bronze_duplicate_arrivals")

    documents_df = bronze.build_bronze_documents_df(spark, rows)
    content_df = bronze.build_bronze_document_content_df(spark, rows)
    payloads_df = bronze.build_bronze_extraction_payloads_df(spark, rows)

    document_count = bronze.write_bronze_documents(spark, documents_df, catalog, schema)
    content_df.write.format("delta").mode("overwrite").saveAsTable(
        f"{catalog}.{schema}.bronze_document_content"
    )
    payloads_df.write.format("delta").mode("overwrite").saveAsTable(
        f"{catalog}.{schema}.bronze_extraction_payloads"
    )

    historical_count = bronze.ingest_historical_events(
        spark,
        str(Path(raw_dir) / "historical" / "historical_adr_events_35000.csv"),
        catalog,
        schema,
    )
    reference_counts = bronze.ingest_reference_tables(spark, raw_dir, catalog, schema)

    return {
        "run_id": run_id,
        "documents_registered": document_count,
        "documents_this_run": len(rows),
        "historical_events": historical_count,
        **{f"ref_{k}": v for k, v in reference_counts.items()},
    }


def run_silver(
    spark: SparkSession, raw_dir: str, catalog: str, schema: str, run_id: str | None = None
) -> dict:
    run_id = run_id or str(uuid.uuid4())
    manifest = bronze.load_arrival_manifest(
        str(Path(raw_dir) / "reference" / "arrival_manifest.csv")
    )
    all_arrivals = bronze.register_and_extract_documents(
        str(Path(raw_dir) / "documents" / "synthetic"), manifest, run_id
    )
    rows, _duplicate_arrivals = bronze.dedupe_by_checksum(all_arrivals)
    build = silver.build_silver(rows)

    product_dictionary = _load_csv(str(Path(raw_dir) / "reference" / "product_dictionary.csv"))
    reaction_dictionary = _load_csv(str(Path(raw_dir) / "reference" / "reaction_dictionary.csv"))
    facility_master = _load_csv(str(Path(raw_dir) / "reference" / "facility_master.csv"))
    district_master = _load_csv(str(Path(raw_dir) / "reference" / "district_master.csv"))

    mapped_build, exceptions = silver.apply_reference_mapping(
        build, product_dictionary, reaction_dictionary, facility_master, district_master
    )
    accepted_versions, quarantined_versions = silver.classify_dq_quarantine(mapped_build)

    tables = silver.to_spark_tables(spark, mapped_build, exceptions, quarantined_versions)
    counts = silver.write_silver_tables(spark, tables, catalog, schema)
    counts["run_id"] = run_id
    counts["accepted_case_versions"] = len(accepted_versions)
    counts["quarantined_case_versions"] = len(quarantined_versions)
    return counts


def run_gold_wap(spark: SparkSession, catalog: str, schema: str, run_id: str | None = None) -> dict:
    run_id = run_id or str(uuid.uuid4())
    return gold.write_gold_wap(spark, catalog, schema, run_id)


def run_sql_validation(spark: SparkSession, catalog: str, schema: str) -> dict:
    return gold.reconcile(spark, catalog, schema)


def bronze_main() -> None:
    args = arguments()
    spark = SparkSession.builder.getOrCreate()
    print(run_bronze(spark, args.raw_dir, args.catalog, args.schema))


def silver_main() -> None:
    args = arguments()
    spark = SparkSession.builder.getOrCreate()
    print(run_silver(spark, args.raw_dir, args.catalog, args.schema))


def gold_main() -> None:
    args = arguments()
    spark = SparkSession.builder.getOrCreate()
    print(run_gold_wap(spark, args.catalog, args.schema))
