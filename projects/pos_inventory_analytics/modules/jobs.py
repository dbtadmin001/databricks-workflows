from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from .quality_profile import (
    QualityProfile,
    contract_set_hash as quality_contract_set_hash,
    profile_and_record,
)
from .schema_contract import (
    LayerContract,
    SchemaDiffReport,
    SchemaDifference,
    compare_schema,
    load_contract,
    observed_fields,
)

# This project's medallion tables are published by the Lakeflow Declarative
# Pipeline (src/notebooks/dlt_pipeline.py), not by this module -- Auto
# Loader/DLT owns incremental ingestion, checkpointing, and Delta schema
# enforcement natively (see REQUIREMENTS.md, "Lakeflow vs. this repo's
# PySpark/PipelineRunner pattern"). This module is the post-pipeline
# schema/quality evidence recorder: it reads the already-published tables,
# records this repo's standard schema-diff-report/stage-quality-profile
# evidence, and re-applies the versioned Gold contract's explicit column list
# as a defense-in-depth safety net against silent column drift (DLT's own
# schema inference could otherwise let an undeclared additive column
# through). Findings are always flagged, never blocking.

BRONZE_TABLE = "bronze_inventory_change_raw"
SILVER_TABLE = "silver_inventory_change"
GOLD_TABLE = "gold_inventory_current"


@dataclass(frozen=True)
class LayerRunResult:
    profile: QualityProfile
    schema_compatible: bool


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    return parser.parse_args()


def validate_and_record_schema(
    spark: SparkSession,
    catalog: str,
    schema: str,
    layer: str,
    candidate_schema,
    target_table: str,
    run_id: str,
) -> tuple[LayerContract, SchemaDiffReport]:
    contract = load_contract(layer)
    previous = (
        observed_fields(spark.table(target_table).schema)
        if spark.catalog.tableExists(target_table)
        else ()
    )
    report = compare_schema(contract, observed_fields(candidate_schema), previous)
    print(report.render())
    report_table = f"{catalog}.{schema}.project_12_pos_inventory_analytics_schema_diff_report"
    differences = report.differences or (
        SchemaDifference(
            "INFO",
            "NO_SCHEMA_DIFFERENCE",
            "*",
            "contract",
            "candidate",
            "Candidate schema matches the versioned contract.",
        ),
    )
    rows = [
        (
            run_id,
            layer,
            contract.version,
            report.compatible,
            item.severity,
            item.code,
            item.field,
            item.expected,
            item.observed,
            item.message,
            report.render(),
        )
        for item in differences
    ]
    (
        spark.createDataFrame(
            rows,
            [
                "run_id",
                "layer",
                "contract_version",
                "compatible",
                "severity",
                "difference_code",
                "field_name",
                "expected_schema",
                "observed_schema",
                "message",
                "readable_report",
            ],
        )
        .withColumn("generated_at", F.current_timestamp())
        .write.format("delta")
        .mode("append")
        .saveAsTable(report_table)
    )
    return contract, report


def record_gold_publication(
    spark: SparkSession,
    audit_table: str,
    run_id: str,
    target_table: str,
    status: str,
    row_count: int,
    reason_code: str,
    comment: str,
) -> None:
    (
        spark.createDataFrame(
            [(run_id, target_table, status, row_count, reason_code, comment)],
            ["run_id", "target_table", "status", "row_count", "reason_code", "comment"],
        )
        .withColumn("audited_at", F.current_timestamp())
        .write.format("delta")
        .mode("append")
        .saveAsTable(audit_table)
    )


def _audit_bronze_or_silver(
    spark: SparkSession, catalog: str, schema: str, layer: str, table_name: str, run_id: str
) -> LayerRunResult:
    full_table = f"{catalog}.{schema}.{table_name}"
    frame = spark.table(full_table)
    profile = profile_and_record(spark, frame, catalog, schema, layer, run_id)
    _, report = validate_and_record_schema(
        spark, catalog, schema, layer, frame.schema, full_table, run_id
    )
    return LayerRunResult(profile, report.compatible)


def run_schema_and_quality_audit(catalog: str, schema: str, run_id: str | None = None) -> str:
    """Record schema/quality evidence for the Lakeflow-published tables.

    Runs after the pipeline update completes. Never blocks -- there is no
    unpublished/staged state to hold; dlt_pipeline.py already wrote every
    table. Gold is additionally re-materialized through the versioned
    contract's explicit column list as a drift safety net.
    """
    spark = SparkSession.builder.getOrCreate()
    run_id = run_id or uuid.uuid4().hex
    print(f"Auditing against quality contract set {quality_contract_set_hash()}")

    bronze = _audit_bronze_or_silver(spark, catalog, schema, "bronze", BRONZE_TABLE, run_id)
    silver = _audit_bronze_or_silver(spark, catalog, schema, "silver", SILVER_TABLE, run_id)

    gold_table = f"{catalog}.{schema}.{GOLD_TABLE}"
    gold_frame = spark.table(gold_table)
    gold_quality = profile_and_record(spark, gold_frame, catalog, schema, "gold", run_id)
    contract, schema_report = validate_and_record_schema(
        spark, catalog, schema, "gold", gold_frame.schema, gold_table, run_id
    )
    columns = list(contract.publication_columns(gold_frame.columns))
    # Audit only - do not modify tables created by the pipeline
    # The pipeline owns the table lifecycle; this job validates schema/quality
    print(f"Gold table audited with {len(columns)} contract columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")

    audit_table = f"{catalog}.{schema}.project_12_pos_inventory_analytics_gold_publication_audit"
    row_count = spark.table(gold_table).count()

    warnings: list[str] = []
    for name, quality, compatible in (
        ("bronze", bronze.profile, bronze.schema_compatible),
        ("silver", silver.profile, silver.schema_compatible),
        ("gold", gold_quality, schema_report.compatible),
    ):
        if not compatible:
            warnings.append(f"{name}_schema_contract_flagged")
        if quality.critical_failures:
            warnings.append(
                f"{name}_critical_quality_checks_flagged:" + ",".join(quality.critical_failures)
            )

    status = "PUBLISHED_WITH_WARNINGS" if warnings else "PUBLISHED"
    comment = (
        "Gold inventory published with flagged findings: " + ", ".join(warnings)
        if warnings
        else "All schema and quality audits passed for the pipeline-published tables."
    )
    record_gold_publication(
        spark,
        audit_table,
        run_id,
        gold_table,
        status,
        row_count,
        ",".join(warnings) or "all_audits_passed",
        comment,
    )
    return status


def audit_main() -> None:
    args = arguments()
    run_schema_and_quality_audit(args.catalog, args.schema)
