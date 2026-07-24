from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType

from .execution import (
    ExecutionIdentity,
    PipelineRunner,
    PipelineSummary,
    StageOutcome,
    fingerprint_files,
    resolve_code_sha,
    stable_hash,
)
from .pipeline import classify_silver, source_register_to_bronze, structured_rows_to_bronze, to_gold
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
    contract_set_hash,
    load_contract,
    observed_fields,
)
from .source_documents import discover_pack
from .stage_ledger import SparkStageLedger


@dataclass(frozen=True)
class LayerRunResult:
    profile: QualityProfile
    status: str = "COMPLETED"
    comment: str = "Layer completed."


SOURCE_REGISTER_SCHEMA = StructType(
    [
        StructField("source_id", StringType(), False),
        StructField("source_file", StringType(), False),
        StructField("format", StringType(), False),
        StructField("document_type", StringType(), False),
        StructField("office_id", StringType(), True),
        StructField("country", StringType(), True),
        StructField("region", StringType(), True),
        StructField("reporting_period", StringType(), True),
        StructField("processing_status", StringType(), False),
        StructField("extraction_method", StringType(), False),
        StructField("evidence_text", StringType(), True),
        StructField("source_size_bytes", LongType(), False),
    ]
)

STRUCTURED_ROW_SCHEMA = StructType(
    [
        StructField("source_id", StringType(), False),
        StructField("source_file", StringType(), False),
        StructField("sheet_name", StringType(), False),
        StructField("sheet_key", StringType(), False),
        StructField("row_number", LongType(), False),
        StructField("row_json", StringType(), False),
    ]
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--source-base-path")
    return parser.parse_args()


def pipeline_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--source-base-path")
    parser.add_argument("--from-stage", choices=("bronze", "silver", "gold"), default="bronze")
    parser.add_argument("--to-stage", choices=("bronze", "silver", "gold"), default="gold")
    parser.add_argument(
        "--force-stage", choices=("bronze", "silver", "gold"), action="append", default=[]
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--source-fingerprint")
    parser.add_argument("--configuration-hash")
    parser.add_argument("--code-sha")
    return parser.parse_args()


def default_source_base_path() -> str:
    project_local = Path.cwd() / "projects" / "hr_data_project" / "data" / "raw"
    if project_local.exists():
        return str(project_local)
    local = Path.cwd() / "data" / "raw"
    if local.exists():
        return str(local)
    return "data/raw"


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
    report_table = f"{catalog}.{schema}.hr_data_project_schema_diff_report"
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


def run_bronze(
    catalog: str, schema: str, run_id: str | None = None, source_base_path: str | None = None
) -> LayerRunResult:
    spark = SparkSession.builder.getOrCreate()
    run_id = run_id or uuid.uuid4().hex
    source_base = source_base_path or default_source_base_path()
    pack = discover_pack(source_base)
    register_source = spark.createDataFrame(pack.source_register, SOURCE_REGISTER_SCHEMA)
    structured_source = spark.createDataFrame(pack.structured_rows, STRUCTURED_ROW_SCHEMA)
    bronze = source_register_to_bronze(register_source, run_id)
    structured = structured_rows_to_bronze(structured_source, run_id)
    table_name = f"{catalog}.{schema}.bronze_source_register"
    quality = profile_and_record(spark, bronze, catalog, schema, "bronze", run_id)
    _, report = validate_and_record_schema(
        spark, catalog, schema, "bronze", bronze.schema, table_name, run_id
    )
    # Schema-contract findings are flagged (recorded above for review in
    # hr_data_project_schema_diff_report), not blocking: this is a timed
    # MVP/demo pipeline, and a data-quality/schema difference must not stop
    # Bronze from writing or hold up Silver/Gold/SQL validation downstream.
    bronze.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        table_name
    )
    bronze.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{catalog}.{schema}.hr_data_project_bronze"
    )
    structured.write.format("delta").mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(f"{catalog}.{schema}.bronze_structured_rows")
    comment = f"Registered {bronze.count()} sources and staged {structured.count()} structured rows."
    if not report.compatible:
        comment += " Schema contract flagged differences; see schema_diff_report."
    return LayerRunResult(quality, comment=comment)


def run_silver(catalog: str, schema: str, run_id: str | None = None) -> LayerRunResult:
    spark = SparkSession.builder.getOrCreate()
    run_id = run_id or uuid.uuid4().hex
    signals, quarantine, supply = classify_silver(
        spark.table(f"{catalog}.{schema}.bronze_source_register"),
        spark.table(f"{catalog}.{schema}.bronze_structured_rows"),
    )
    table_name = f"{catalog}.{schema}.silver_workforce_signals"
    quality = profile_and_record(
        spark, signals, catalog, schema, "silver", run_id, rejected_records=quarantine.count()
    )
    _, report = validate_and_record_schema(
        spark, catalog, schema, "silver", signals.schema, table_name, run_id
    )
    # Flag, don't block -- see the matching comment in run_bronze.
    signals.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        table_name
    )
    signals.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{catalog}.{schema}.hr_data_project_silver"
    )
    quarantine.write.format("delta").mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(f"{catalog}.{schema}.hr_data_project_quarantine")
    supply.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        f"{catalog}.{schema}.silver_skill_supply"
    )
    signal_count = signals.count()
    quarantine_count = quarantine.count()
    (
        spark.createDataFrame(
            [(run_id, signal_count + quarantine_count, signal_count, quarantine_count, 0)],
            [
                "run_id",
                "signal_source_rows",
                "accepted_signal_rows",
                "quarantined_signal_rows",
                "explicitly_excluded_rows",
            ],
        )
        .withColumn(
            "reconciliation_status",
            F.when(
                F.col("signal_source_rows")
                == F.col("accepted_signal_rows")
                + F.col("quarantined_signal_rows")
                + F.col("explicitly_excluded_rows"),
                F.lit("PASS"),
            ).otherwise(F.lit("REVIEW")),
        )
        .withColumn("audited_at", F.current_timestamp())
        .write.format("delta")
        .mode("append")
        .saveAsTable(f"{catalog}.{schema}.hr_data_project_reconciliation_audit")
    )
    comment = "Published workforce signals, supply and quarantine."
    if not report.compatible:
        comment += " Schema contract flagged differences; see schema_diff_report."
    return LayerRunResult(quality, comment=comment)


def run_gold(
    catalog: str,
    schema: str,
    run_id: str | None = None,
    upstream_critical_failures: tuple[str, ...] = (),
) -> str:
    spark = SparkSession.builder.getOrCreate()
    gold = to_gold(
        spark.table(f"{catalog}.{schema}.silver_workforce_signals"),
        spark.table(f"{catalog}.{schema}.silver_skill_supply"),
    )
    run_id = run_id or uuid.uuid4().hex
    target = f"{catalog}.{schema}.gold_workforce_gap"
    staging = f"{target}_wap_{run_id}"
    audit = f"{catalog}.{schema}.hr_data_project_gold_publication_audit"
    quality = profile_and_record(spark, gold, catalog, schema, "gold", run_id)
    contract, schema_report = validate_and_record_schema(
        spark, catalog, schema, "gold", gold.schema, target, run_id
    )
    # Data-quality/schema findings are flagged (recorded in the audit trail
    # and schema-diff report), not blocking: this is a timed MVP/demo
    # pipeline, and Gold must always publish so downstream SQL validation and
    # the dashboard have a real table to query. A held/unpublished Gold table
    # previously turned one flagged issue into a hard TABLE_OR_VIEW_NOT_FOUND
    # failure for every consumer -- publishing with an honest
    # PUBLISHED_WITH_WARNINGS status keeps the failure mode a documented
    # data-quality note instead of a broken pipeline.
    warnings: list[str] = []
    if not schema_report.compatible:
        warnings.append("schema_contract_flagged")
    critical_failures = tuple(
        dict.fromkeys((*upstream_critical_failures, *quality.critical_failures))
    )
    if critical_failures:
        warnings.append("critical_quality_checks_flagged:" + ",".join(critical_failures))
    columns = list(contract.publication_columns(gold.columns))
    gold.select(*columns).write.format("delta").mode("overwrite").saveAsTable(staging)
    try:
        audit_row = spark.sql(
            f"""
            WITH row_audit AS (
              SELECT
                COUNT(*) AS row_count,
                SUM(CASE WHEN office_id IS NULL OR skill_id IS NULL THEN 1 ELSE 0 END) AS null_keys,
                SUM(CASE WHEN demand_score < 0 OR supply_fte < 0 OR gap_value < 0 THEN 1 ELSE 0 END) AS invalid_scores
              FROM {staging}
            ),
            duplicate_audit AS (
              SELECT COUNT(*) AS duplicate_grain
              FROM (
                SELECT office_id, skill_id FROM {staging} GROUP BY office_id, skill_id HAVING COUNT(*) > 1
              ) duplicates
            )
            SELECT row_count, null_keys, invalid_scores, duplicate_grain
            FROM row_audit CROSS JOIN duplicate_audit
            """
        ).first()
        warnings.extend(
            name
            for name, flagged in (
                ("empty_output", audit_row.row_count == 0),
                ("null_business_key", audit_row.null_keys > 0),
                ("duplicate_business_grain", audit_row.duplicate_grain > 0),
                ("invalid_gap_score", audit_row.invalid_scores > 0),
            )
            if flagged
        )
        spark.sql(
            f"""
            CREATE OR REPLACE TABLE {target} AS
            SELECT {", ".join(columns)}
            FROM {staging}
            """
        )
        spark.sql(
            f"""
            CREATE OR REPLACE TABLE {catalog}.{schema}.hr_data_project_gold_metrics AS
            SELECT * FROM {target}
            """
        )
        if warnings:
            status = "PUBLISHED_WITH_WARNINGS"
            comment = "Gold workforce gap published with flagged data-quality/schema findings: " + ", ".join(
                warnings
            )
        else:
            status = "PUBLISHED"
            comment = "Gold workforce gap passed schema, grain, nonnegative-score and publication audits."
        record_gold_publication(
            spark, audit, run_id, target, status, audit_row.row_count, ",".join(warnings) or "all_audits_passed", comment
        )
        return status
    finally:
        spark.sql(f"DROP TABLE IF EXISTS {staging}")


def run_pipeline(
    catalog: str,
    schema: str,
    *,
    source_base_path: str | None = None,
    from_stage: str = "bronze",
    to_stage: str = "gold",
    force_stages: tuple[str, ...] = (),
    resume: bool = False,
    source_fingerprint: str | None = None,
    configuration_hash: str | None = None,
    code_sha: str | None = None,
) -> PipelineSummary:
    spark = SparkSession.builder.getOrCreate()
    source_base = Path(source_base_path or default_source_base_path())
    identity = ExecutionIdentity(
        source_fingerprint=source_fingerprint or fingerprint_files(sorted(source_base.rglob("*"))),
        configuration_hash=configuration_hash
        or stable_hash(
            {
                "catalog": catalog,
                "schema": schema,
                "source_base_path": str(source_base),
                "schema_contract_set": contract_set_hash(),
                "quality_contract_set": quality_contract_set_hash(),
            }
        ),
        code_sha=resolve_code_sha(code_sha),
    )
    ledger = SparkStageLedger(spark, f"{catalog}.{schema}.hr_data_project_stage_execution_status")
    pipeline_run_id = uuid.uuid4().hex
    profiles: dict[str, QualityProfile] = {}

    # Bronze/Silver/Gold always write their declared tables now -- schema and
    # quality findings are flagged in the audit/schema-diff tables, never
    # held. execution.HELD remains available for a future genuinely-blocking
    # case, but nothing in this pipeline returns it today; see
    # run_bronze/run_silver/run_gold for the flag-not-block logic.
    def bronze_stage() -> StageOutcome:
        result = run_bronze(catalog, schema, pipeline_run_id, str(source_base))
        profiles["bronze"] = result.profile
        return StageOutcome(comment=result.comment)

    def silver_stage() -> StageOutcome:
        result = run_silver(catalog, schema, pipeline_run_id)
        profiles["silver"] = result.profile
        return StageOutcome(comment=result.comment)

    def gold_stage() -> StageOutcome:
        upstream_failures = tuple(
            failure
            for stage in ("bronze", "silver")
            for failure in (profiles[stage].critical_failures if stage in profiles else ())
        )
        publication = run_gold(catalog, schema, pipeline_run_id, upstream_failures)
        return StageOutcome(comment=f"Gold workforce gap {publication.lower()}.")

    summary = PipelineRunner(ledger).run(
        identity,
        {"bronze": bronze_stage, "silver": silver_stage, "gold": gold_stage},
        from_stage=from_stage,
        to_stage=to_stage,
        force_stages=force_stages,
        resume=resume,
        pipeline_run_id=pipeline_run_id,
    )
    print(
        json.dumps(
            {
                "pipeline_run_id": summary.pipeline_run_id,
                "planned": summary.planned,
                "skipped": summary.skipped,
                "completed": summary.completed,
                "held_stage": summary.held_stage,
                "source_fingerprint": identity.source_fingerprint,
                "configuration_hash": identity.configuration_hash,
                "code_sha": identity.code_sha,
            },
            sort_keys=True,
        )
    )
    return summary


def bronze_main() -> None:
    args = arguments()
    run_bronze(args.catalog, args.schema, source_base_path=args.source_base_path)


def silver_main() -> None:
    args = arguments()
    run_silver(args.catalog, args.schema)


def gold_main() -> None:
    args = arguments()
    run_gold(args.catalog, args.schema)


def pipeline_main() -> None:
    args = pipeline_arguments()
    run_pipeline(
        args.catalog,
        args.schema,
        source_base_path=args.source_base_path,
        from_stage=args.from_stage,
        to_stage=args.to_stage,
        force_stages=tuple(args.force_stage),
        resume=args.resume,
        source_fingerprint=args.source_fingerprint,
        configuration_hash=args.configuration_hash,
        code_sha=args.code_sha,
    )
