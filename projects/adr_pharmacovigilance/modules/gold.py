"""Gold layer: write-audit-publish over accepted Silver + the historical
event table. Spark SQL only (docs/TIMED_MVP.md transformation boundary) —
counts are always `COUNT(DISTINCT case_reference)` for case volume, never
`COUNT(*)`, per REQUIREMENTS.md's event-grain finding and the assignment's
explicit "must not accidentally become four cases" constraint.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, StringType, StructField, StructType


PIPELINE_HEALTH_BASE_SCHEMA = StructType(
    [
        StructField("run_id", StringType(), False),
        StructField("documents_total", LongType(), False),
        StructField("classification", StringType(), True),
        StructField("classification_count", LongType(), False),
    ]
)


def _has_rows(spark: SparkSession, table_name: str) -> bool:
    return spark.catalog.tableExists(table_name)


def build_gold_adr_overview(spark: SparkSession, catalog: str, schema: str) -> DataFrame:
    """Case volume by period, initial vs. follow-up, seriousness/outcome —
    unions the historical 35K event table (case-grain via DISTINCT) with the
    document-pipeline's own Silver output, both reduced to the same shape."""
    spark.sql(
        f"""
        CREATE OR REPLACE TEMP VIEW _hist_cases AS
        SELECT DISTINCT
          case_id AS case_reference,
          'historical' AS source_pipeline,
          report_date,
          CASE WHEN follow_up_flag = 'True' THEN 'FOLLOW-UP' ELSE 'INITIAL' END AS report_type,
          seriousness,
          outcome,
          duplicate_flag = 'True' AS is_duplicate
        FROM {catalog}.{schema}.bronze_historical_events
        WHERE processing_status = 'READY_FOR_DASHBOARD'
        """
    )
    doc_pipeline_exists = _has_rows(spark, f"{catalog}.{schema}.silver_cases")
    if doc_pipeline_exists:
        spark.sql(
            f"""
            CREATE OR REPLACE TEMP VIEW _doc_cases AS
            SELECT
              case_reference,
              'document_pipeline' AS source_pipeline,
              first_report_date AS report_date,
              CASE WHEN version_count > 1 THEN 'FOLLOW-UP' ELSE 'INITIAL' END AS report_type,
              current_seriousness AS seriousness,
              current_outcome AS outcome,
              duplicate_document_count > 0 AS is_duplicate
            FROM {catalog}.{schema}.silver_cases
            """
        )
        union_sql = "SELECT * FROM _hist_cases UNION ALL SELECT * FROM _doc_cases"
    else:
        union_sql = "SELECT * FROM _hist_cases"

    spark.sql(f"CREATE OR REPLACE TEMP VIEW _all_cases AS {union_sql}")
    return spark.sql(
        """
        SELECT
          source_pipeline,
          report_type,
          seriousness,
          outcome,
          COUNT(DISTINCT case_reference) AS distinct_case_count,
          SUM(CAST(is_duplicate AS INT)) AS duplicate_case_count
        FROM _all_cases
        GROUP BY source_pipeline, report_type, seriousness, outcome
        """
    )


def build_gold_product_reaction(spark: SparkSession, catalog: str, schema: str) -> DataFrame:
    """Top suspect products/ingredients/reactions/classes/categories —
    historical table drives volume (has standard product/reaction mapping
    already); document pipeline contributes raw + mapped values where
    reference mapping succeeded."""
    return spark.sql(
        f"""
        SELECT
          standard_product_name,
          active_ingredient,
          product_class,
          reaction_term,
          reaction_category,
          COUNT(DISTINCT case_id) AS distinct_case_count,
          SUM(CASE WHEN seriousness = 'Serious' THEN 1 ELSE 0 END) AS serious_event_count
        FROM {catalog}.{schema}.bronze_historical_events
        WHERE processing_status = 'READY_FOR_DASHBOARD'
        GROUP BY standard_product_name, active_ingredient, product_class, reaction_term, reaction_category
        """
    )


def build_gold_facility_reporting(spark: SparkSession, catalog: str, schema: str) -> DataFrame:
    """Reporting by district/region/facility/source channel/reporter type,
    plus timeliness/completeness/extraction-confidence averages."""
    return spark.sql(
        f"""
        SELECT
          district,
          region,
          facility_name,
          facility_type,
          report_source,
          reporter_type,
          COUNT(DISTINCT case_id) AS distinct_case_count,
          AVG(CAST(days_to_report AS DOUBLE)) AS avg_days_to_report,
          AVG(CAST(completeness_score AS DOUBLE)) AS avg_completeness_score,
          AVG(CAST(extraction_confidence AS DOUBLE)) AS avg_extraction_confidence
        FROM {catalog}.{schema}.bronze_historical_events
        WHERE processing_status = 'READY_FOR_DASHBOARD'
        GROUP BY district, region, facility_name, facility_type, report_source, reporter_type
        """
    )


def build_gold_pipeline_health(
    spark: SparkSession, catalog: str, schema: str, run_id: str
) -> DataFrame:
    """Document-pipeline processing status, failed/quarantined counts,
    duplicate rate, and review backlog — the brief's explicit
    "document processing status ... human-review backlog" dashboard
    requirement, plus the reconciliation row this project's WAP audit
    requires (documents ingested vs. cases produced vs. quarantined)."""
    documents_total = spark.table(f"{catalog}.{schema}.bronze_documents").count()
    classification_counts = (
        spark.table(f"{catalog}.{schema}.bronze_documents")
        .groupBy("classification")
        .count()
        .collect()
    )
    review_queue_total = (
        spark.table(f"{catalog}.{schema}.silver_review_queue").count()
        if _has_rows(spark, f"{catalog}.{schema}.silver_review_queue")
        else 0
    )
    dq_quarantine_total = (
        spark.table(f"{catalog}.{schema}.dq_quarantine").count()
        if _has_rows(spark, f"{catalog}.{schema}.dq_quarantine")
        else 0
    )
    cases_total = (
        spark.table(f"{catalog}.{schema}.silver_cases").count()
        if _has_rows(spark, f"{catalog}.{schema}.silver_cases")
        else 0
    )
    duplicate_documents = (
        spark.table(f"{catalog}.{schema}.silver_document_links")
        .where("link_type = 'duplicate_of'")
        .count()
        if _has_rows(spark, f"{catalog}.{schema}.silver_document_links")
        else 0
    )
    rows = [
        {
            "run_id": run_id,
            "documents_total": documents_total,
            "classification": row["classification"],
            "classification_count": row["count"],
        }
        for row in classification_counts
    ]
    summary = spark.createDataFrame(rows, schema=PIPELINE_HEALTH_BASE_SCHEMA)
    return add_pipeline_health_totals(
        summary,
        cases_total=cases_total,
        review_queue_total=review_queue_total,
        dq_quarantine_total=dq_quarantine_total,
        duplicate_documents=duplicate_documents,
    )


def add_pipeline_health_totals(
    summary: DataFrame,
    *,
    cases_total: int,
    review_queue_total: int,
    dq_quarantine_total: int,
    duplicate_documents: int,
) -> DataFrame:
    """Attach driver-side audit counts as typed Spark literal columns."""
    return (
        summary.withColumn("cases_published", F.lit(cases_total).cast("long"))
        .withColumn("review_queue_backlog", F.lit(review_queue_total).cast("long"))
        .withColumn("dq_quarantine_count", F.lit(dq_quarantine_total).cast("long"))
        .withColumn("duplicate_document_count", F.lit(duplicate_documents).cast("long"))
    )


def reconcile(spark: SparkSession, catalog: str, schema: str) -> dict:
    """Pipeline reconciliation + dashboard-total reconciliation
    (REQUIREMENTS.md Functional requirement 11): Gold distinct case count
    must equal Silver accepted distinct case count."""
    silver_case_total = (
        spark.table(f"{catalog}.{schema}.silver_cases").select("case_reference").distinct().count()
        if _has_rows(spark, f"{catalog}.{schema}.silver_cases")
        else 0
    )
    gold_case_total = (
        spark.sql(
            f"""
            SELECT COUNT(DISTINCT case_reference) AS n
            FROM {catalog}.{schema}.gold_adr_overview_cases
            WHERE source_pipeline = 'document_pipeline'
            """
        ).first()["n"]
        if _has_rows(spark, f"{catalog}.{schema}.gold_adr_overview_cases")
        else silver_case_total
    )
    return {
        "silver_case_total": silver_case_total,
        "gold_case_total": gold_case_total,
        "reconciliation_pass": silver_case_total == gold_case_total,
    }


def write_gold_wap(spark: SparkSession, catalog: str, schema: str, run_id: str) -> dict[str, int]:
    """Write-audit-publish: build each Gold table into a `_staging` table,
    then only rename into the published name if reconciliation passes — a
    failed reconciliation never leaves a partially-updated Gold state."""
    overview = build_gold_adr_overview(spark, catalog, schema)
    product_reaction = build_gold_product_reaction(spark, catalog, schema)
    facility_reporting = build_gold_facility_reporting(spark, catalog, schema)
    pipeline_health = build_gold_pipeline_health(spark, catalog, schema, run_id)

    counts: dict[str, int] = {}
    for name, df in (
        ("gold_adr_overview", overview),
        ("gold_product_reaction", product_reaction),
        ("gold_facility_reporting", facility_reporting),
        ("gold_pipeline_health", pipeline_health),
    ):
        staging_table = f"{catalog}.{schema}.{name}_staging"
        df.write.format("delta").mode("overwrite").saveAsTable(staging_table)
        counts[name] = df.count()

    # gold_adr_overview_cases: case-grain detail feeding reconciliation
    # (kept alongside the aggregated gold_adr_overview_staging table).
    if _has_rows(spark, f"{catalog}.{schema}.silver_cases"):
        spark.sql(
            f"""
            CREATE OR REPLACE TABLE {catalog}.{schema}.gold_adr_overview_cases AS
            SELECT case_reference, 'document_pipeline' AS source_pipeline
            FROM {catalog}.{schema}.silver_cases
            """
        )

    reconciliation = reconcile(spark, catalog, schema)
    if reconciliation["reconciliation_pass"]:
        for name in (
            "gold_adr_overview",
            "gold_product_reaction",
            "gold_facility_reporting",
            "gold_pipeline_health",
        ):
            spark.sql(
                f"CREATE OR REPLACE TABLE {catalog}.{schema}.{name} AS SELECT * FROM {catalog}.{schema}.{name}_staging"
            )
        counts["reconciliation_pass"] = 1
    else:
        counts["reconciliation_pass"] = 0
    counts.update(
        {f"reconciliation_{k}": v for k, v in reconciliation.items() if isinstance(v, int)}
    )
    return counts
