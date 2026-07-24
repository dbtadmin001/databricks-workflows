from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql.types import StructType


@dataclass(frozen=True)
class GoldAudit:
    fact_rows: int
    summary_rows: int
    null_keys: int
    duplicate_keys: int
    accepted_rows: int

    @property
    def passed(self) -> bool:
        return (
            self.fact_rows > 0
            and self.fact_rows == self.accepted_rows
            and self.null_keys == 0
            and self.duplicate_keys == 0
        )


@dataclass(frozen=True)
class PublicationDecision:
    status: str
    reason_code: str
    comment: str

    @property
    def published(self) -> bool:
        return self.status in {"PUBLISHED", "PUBLISHED_WITH_WARNINGS"}


def build_fact(
    spark,
    accepted: DataFrame,
    donors: DataFrame,
    programmes: DataFrame,
    grants: DataFrame,
) -> DataFrame:
    accepted.createOrReplaceTempView("_p08_accepted")
    donors.createOrReplaceTempView("_p08_donors")
    programmes.createOrReplaceTempView("_p08_programmes")
    grants.createOrReplaceTempView("_p08_grants")
    return spark.sql(
        """
        WITH projected_contributions AS (
          SELECT contribution_id, contribution_date, fiscal_year_norm, donor_id,
                 programme_id, currency_original, amount_original, exchange_rate_to_usd,
                 amount_usd, status, grant_id, payment_method, source_batch
          FROM _p08_accepted
        ), point_in_time_programme AS (
          SELECT c.contribution_id, p.programme_name, p.sector,
                 ROW_NUMBER() OVER (
                   PARTITION BY c.contribution_id
                   ORDER BY CASE WHEN c.contribution_date >= p.effective_start THEN 0 ELSE 1 END,
                            p.effective_start DESC
                 ) AS programme_rank
          FROM projected_contributions c
          INNER JOIN _p08_programmes p
            ON c.programme_id = p.programme_id
           AND (c.contribution_date >= p.effective_start OR p.version_rank = 1)
           AND (p.effective_end IS NULL OR c.contribution_date < p.effective_end)
        )
        SELECT c.contribution_id, c.contribution_date, c.fiscal_year_norm,
               c.donor_id, d.donor_name, d.donor_type,
               c.programme_id, p.programme_name, p.sector,
               c.currency_original, c.amount_original, c.exchange_rate_to_usd,
               c.amount_usd, c.status, c.grant_id, g.grant_reference,
               g.reporting_frequency, g.next_due_date, c.payment_method, c.source_batch
        FROM projected_contributions c
        INNER JOIN _p08_donors d ON c.donor_id = d.donor_id
        INNER JOIN point_in_time_programme p
          ON c.contribution_id = p.contribution_id AND p.programme_rank = 1
        LEFT JOIN _p08_grants g ON c.grant_id = g.grant_id
        """
    )


def build_programme_summary(spark, fact: DataFrame) -> DataFrame:
    fact.createOrReplaceTempView("_p08_gold_fact_candidate")
    return spark.sql(
        """
        WITH projected_fact AS (
          SELECT programme_id, fiscal_year_norm, status, amount_usd
          FROM _p08_gold_fact_candidate
        )
        SELECT programme_id, fiscal_year_norm,
               SUM(CASE WHEN status = 'committed' THEN amount_usd ELSE 0 END)
                 AS total_committed_usd,
               SUM(CASE WHEN status = 'received' THEN amount_usd ELSE 0 END)
                 AS total_received_usd,
               COUNT(*) AS contribution_count
        FROM projected_fact
        GROUP BY programme_id, fiscal_year_norm
        """
    )


def validate_schema_evolution(candidate: StructType, existing: StructType | None) -> None:
    if existing is None:
        return
    candidate_types = {field.name: field.dataType.simpleString() for field in candidate.fields}
    existing_types = {field.name: field.dataType.simpleString() for field in existing.fields}
    dropped = sorted(set(existing_types) - set(candidate_types))
    changed = {
        name: (existing_types[name], candidate_types[name])
        for name in set(existing_types) & set(candidate_types)
        if existing_types[name] != candidate_types[name]
    }
    if dropped or changed:
        raise ValueError(
            f"Gold schema evolution must be additive: dropped={dropped}, types={changed}"
        )


def validate_additive_schema(candidate: StructType, existing: StructType | None = None) -> None:
    required = {
        "contribution_id": "string",
        "contribution_date": "date",
        "fiscal_year_norm": "int",
        "donor_id": "string",
        "programme_id": "string",
        "amount_usd": "decimal(18,2)",
        "status": "string",
    }
    candidate_types = {field.name: field.dataType.simpleString() for field in candidate.fields}
    missing = sorted(set(required) - set(candidate_types))
    mismatched = {
        name: (required[name], candidate_types.get(name))
        for name in required
        if name in candidate_types and candidate_types[name] != required[name]
    }
    if missing or mismatched:
        raise ValueError(f"Gold schema contract failed: missing={missing}, types={mismatched}")
    validate_schema_evolution(candidate, existing)


def audit_gold(fact: DataFrame, summary: DataFrame, accepted_rows: int) -> GoldAudit:
    from pyspark.sql import functions as F

    fact_rows = fact.count()
    null_keys = fact.where(F.col("contribution_id").isNull()).count()
    duplicate_keys = fact.groupBy("contribution_id").count().where(F.col("count") > 1).count()
    return GoldAudit(
        fact_rows=fact_rows,
        summary_rows=summary.count(),
        null_keys=null_keys,
        duplicate_keys=duplicate_keys,
        accepted_rows=accepted_rows,
    )


def decide_publication(audit: GoldAudit, schema_error: str | None = None) -> PublicationDecision:
    if schema_error:
        return PublicationDecision(
            "PUBLICATION_HELD",
            "SCHEMA_INCOMPATIBLE",
            f"Gold candidate was not published because its schema is incompatible: {schema_error}",
        )
    if audit.fact_rows == 0:
        return PublicationDecision(
            "PUBLICATION_HELD",
            "EMPTY_GOLD",
            "Gold candidate is empty; the current published tables were left unchanged.",
        )
    if audit.fact_rows != audit.accepted_rows:
        return PublicationDecision(
            "PUBLICATION_HELD",
            "RECONCILIATION_MISMATCH",
            "Gold fact rows do not reconcile to accepted Silver rows; current Gold is unchanged.",
        )
    if audit.null_keys:
        return PublicationDecision(
            "PUBLICATION_HELD",
            "NULL_BUSINESS_KEY",
            "Gold candidate contains null contribution IDs; current Gold is unchanged.",
        )
    if audit.duplicate_keys:
        return PublicationDecision(
            "PUBLICATION_HELD",
            "DUPLICATE_GRAIN",
            "Gold candidate contains duplicate contribution IDs; current Gold is unchanged.",
        )
    return PublicationDecision(
        "PUBLISHED",
        "ALL_CHECKS_PASSED",
        "Gold candidate passed schema, grain, key, and reconciliation audits.",
    )


def quote_identifier(value: str) -> str:
    return f"`{value.replace('`', '``')}`"


def publish_staged_table(spark, staging_table: str, target_table: str, columns: list[str]) -> None:
    explicit_columns = ", ".join(quote_identifier(column) for column in columns)
    spark.sql(
        f"CREATE OR REPLACE TABLE {target_table} AS SELECT {explicit_columns} FROM {staging_table}"
    )
