from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType

MONEY = DecimalType(18, 2)
RATE = DecimalType(18, 8)

CONTRIBUTION_COLUMNS = [
    "contribution_id",
    "donor_id",
    "programme_id",
    "fiscal_year_raw",
    "fiscal_year_norm",
    "contribution_date",
    "currency_original",
    "amount_original",
    "exchange_rate_to_usd",
    "amount_usd",
    "status",
    "grant_id",
    "payment_method",
    "notes",
    "source_batch",
]


@dataclass(frozen=True)
class SilverMetrics:
    bronze_contribution_rows: int
    exact_duplicates_removed: int
    conflicting_duplicate_rows: int
    cross_batch_corrections: int
    accepted_rows: int
    quarantined_rows: int


def _trimmed(column: str) -> F.Column:
    return F.trim(F.col(column).cast("string"))


def _fiscal_year(column: F.Column) -> F.Column:
    value = F.trim(column.cast("string"))
    return (
        F.when(value.rlike(r"^[0-9]{4}$"), value.cast("int"))
        .when(
            value.rlike(r"^[0-9]{4}-[0-9]{4}$"),
            F.regexp_extract(value, r"([0-9]{4})$", 1).cast("int"),
        )
        .when(
            value.rlike(r"(?i)^FY[0-9]{2}$"),
            (F.regexp_extract(value, r"([0-9]{2})$", 1).cast("int") + F.lit(2000)),
        )
    )


def _parsed_date(column_name: str) -> F.Column:
    quoted = f"`{column_name}`"
    return F.to_date(
        F.coalesce(
            F.expr(f"try_to_timestamp({quoted}, 'MM/dd/yyyy')"),
            F.expr(f"try_to_timestamp({quoted}, 'dd-MMM-yy')"),
            F.expr(f"try_to_timestamp({quoted}, 'yyyy-MM-dd')"),
            F.expr(f"try_cast((try_cast({quoted} AS BIGINT) / 1000) AS TIMESTAMP)"),
        )
    )


def conform_donors(bronze: DataFrame) -> DataFrame:
    return bronze.select(
        _trimmed("DONOR_ID").alias("donor_id"),
        _trimmed("DONOR_NAME").alias("donor_name"),
        F.lower(_trimmed("DONOR_TYPE")).alias("donor_type"),
        _trimmed("COUNTRY").alias("country"),
    ).dropDuplicates(["donor_id"])


def conform_exchange_rates(bronze: DataFrame) -> DataFrame:
    return bronze.select(
        F.upper(_trimmed("CURRENCY")).alias("currency"),
        _trimmed("RATE_MONTH").alias("rate_month"),
        F.col("RATE_TO_USD").cast(RATE).alias("rate_to_usd"),
    ).dropDuplicates(["currency", "rate_month"])


def conform_grants(bronze: DataFrame) -> DataFrame:
    return bronze.select(
        _trimmed("grant_id").alias("grant_id"),
        _trimmed("grant_reference").alias("grant_reference"),
        _trimmed("donor_id").alias("donor_id"),
        _trimmed("programme_id").alias("programme_id"),
        F.col("amount_committed_usd").cast(MONEY).alias("amount_committed_usd"),
        F.to_date(_trimmed("signed_date"), "yyyy-MM-dd").alias("signed_date"),
        F.col("reporting.frequency").cast("string").alias("reporting_frequency"),
        F.to_date(F.expr("try_cast((reporting.next_due_date_epoch / 1000) AS TIMESTAMP)")).alias(
            "next_due_date"
        ),
        F.concat_ws(",", F.coalesce(F.col("tags"), F.array().cast("array<string>"))).alias(
            "tags_str"
        ),
    ).dropDuplicates(["grant_id"])


def build_programme_scd2(q1: DataFrame, q2: DataFrame) -> DataFrame:
    def conform(df: DataFrame) -> DataFrame:
        return df.select(
            _trimmed("PROGRAMME_ID").alias("programme_id"),
            _trimmed("PROGRAMME_NAME").alias("programme_name"),
            _trimmed("SECTOR").alias("sector"),
            F.col("ANNUAL_BUDGET_USD").cast(MONEY).alias("annual_budget_usd"),
            F.to_date(_trimmed("SNAPSHOT_DATE"), "yyyy-MM-dd").alias("snapshot_date"),
        )

    first = conform(q1)
    second = conform(q2)
    prior = first.select(
        "programme_id",
        F.col("programme_name").alias("prior_name"),
        F.col("sector").alias("prior_sector"),
        F.col("annual_budget_usd").alias("prior_budget"),
    )
    changed_second = (
        second.join(prior, "programme_id", "left")
        .where(
            F.col("prior_budget").isNull()
            | ~F.col("annual_budget_usd").eqNullSafe(F.col("prior_budget"))
            | ~F.col("programme_name").eqNullSafe(F.col("prior_name"))
            | ~F.col("sector").eqNullSafe(F.col("prior_sector"))
        )
        .select(second.columns)
    )
    versions = first.unionByName(changed_second)
    window = Window.partitionBy("programme_id").orderBy("snapshot_date")
    return (
        versions.withColumn("effective_start", F.col("snapshot_date"))
        .withColumn("effective_end", F.lead("snapshot_date").over(window))
        .withColumn("version_rank", F.row_number().over(window))
        .withColumn("is_current", F.col("effective_end").isNull())
        .drop("snapshot_date")
    )


def _normalize_contributions(bronze: DataFrame, source_batch: str) -> DataFrame:
    csv = source_batch == "csv"
    mapping = {
        "contribution_id": "CONTRIBUTION_ID" if csv else "contribution_id",
        "donor_id": "DONOR_ID" if csv else "donor_id",
        "programme_id": "PROGRAMME_ID" if csv else "programme_id",
        "fiscal_year": "FISCAL_YEAR" if csv else "fiscal_year",
        "contribution_date": "CONTRIBUTION_DATE" if csv else "contribution_date",
        "currency_original": "CURRENCY_ORIGINAL" if csv else "currency_original",
        "amount_original": "AMOUNT_ORIGINAL" if csv else "amount_original",
        "status": "STATUS" if csv else "status",
    }
    raw = bronze.select(
        *[_trimmed(source).alias(target) for target, source in mapping.items()],
        (F.col("EXCHANGE_RATE_TO_USD").cast(RATE) if csv else F.lit(None).cast(RATE)).alias(
            "exchange_rate_to_usd"
        ),
        (F.col("AMOUNT_USD").cast(MONEY) if csv else F.lit(None).cast(MONEY)).alias("amount_usd"),
        (F.lit(None).cast("string") if csv else _trimmed("grant_id")).alias("grant_id"),
        (F.lit(None).cast("string") if csv else _trimmed("payment_method")).alias("payment_method"),
        (F.lit(None).cast("string") if csv else _trimmed("notes")).alias("notes"),
    )
    return raw.select(
        "contribution_id",
        "donor_id",
        "programme_id",
        F.col("fiscal_year").alias("fiscal_year_raw"),
        _fiscal_year(F.col("fiscal_year")).alias("fiscal_year_norm"),
        _parsed_date("contribution_date").alias("contribution_date"),
        F.upper(F.col("currency_original")).alias("currency_original"),
        F.col("amount_original").cast(MONEY).alias("amount_original"),
        "exchange_rate_to_usd",
        "amount_usd",
        F.lower(F.trim(F.col("status"))).alias("status"),
        "grant_id",
        "payment_method",
        "notes",
        F.lit(source_batch).alias("source_batch"),
    )


def build_contributions(
    contributions_csv: DataFrame,
    contributions_json: DataFrame,
    donors: DataFrame,
    programmes: DataFrame,
    exchange_rates: DataFrame,
) -> tuple[DataFrame, DataFrame, SilverMetrics]:
    csv_rows = _normalize_contributions(contributions_csv, "csv")
    json_rows = _normalize_contributions(contributions_json, "json")
    csv_distinct = csv_rows.dropDuplicates(CONTRIBUTION_COLUMNS)
    json_distinct = json_rows.dropDuplicates(CONTRIBUTION_COLUMNS)
    exact_removed = (csv_rows.count() - csv_distinct.count()) + (
        json_rows.count() - json_distinct.count()
    )

    def conflicting(df: DataFrame) -> DataFrame:
        ids = df.groupBy("contribution_id").count().where(F.col("count") > 1)
        return df.join(ids.select("contribution_id"), "contribution_id", "inner")

    csv_conflicts = conflicting(csv_distinct)
    json_conflicts = conflicting(json_distinct)
    conflict_rows = csv_conflicts.unionByName(json_conflicts)
    conflict_ids = conflict_rows.select("contribution_id").distinct()
    csv_eligible = csv_distinct.join(conflict_ids, "contribution_id", "left_anti")
    json_eligible = json_distinct.join(conflict_ids, "contribution_id", "left_anti")

    cross_batch = (
        csv_eligible.select("contribution_id")
        .distinct()
        .join(json_eligible.select("contribution_id").distinct(), "contribution_id")
        .count()
    )
    precedence = Window.partitionBy("contribution_id").orderBy(
        F.when(F.col("source_batch") == "json", F.lit(2)).otherwise(F.lit(1)).desc()
    )
    merged = (
        csv_eligible.unionByName(json_eligible)
        .withColumn("_rank", F.row_number().over(precedence))
        .where(F.col("_rank") == 1)
        .drop("_rank")
    )

    rates = exchange_rates.select(
        F.col("currency").alias("_fx_currency"),
        F.col("rate_month").alias("_fx_month"),
        F.col("rate_to_usd").alias("_fx_rate"),
    )
    enriched = (
        merged.withColumn("_rate_month", F.date_format("contribution_date", "yyyy-MM"))
        .join(
            rates,
            (F.col("currency_original") == F.col("_fx_currency"))
            & (F.col("_rate_month") == F.col("_fx_month")),
            "left",
        )
        .withColumn(
            "exchange_rate_to_usd",
            F.coalesce(F.col("exchange_rate_to_usd"), F.col("_fx_rate")).cast(RATE),
        )
        .withColumn(
            "amount_usd",
            F.coalesce(
                F.col("amount_usd"),
                (F.col("amount_original") * F.col("_fx_rate")).cast(MONEY),
            ),
        )
    )
    donor_ref = donors.select(F.col("donor_id").alias("_valid_donor")).distinct()
    programme_ref = programmes.select(F.col("programme_id").alias("_valid_programme")).distinct()
    classified = enriched.join(donor_ref, F.col("donor_id") == F.col("_valid_donor"), "left").join(
        programme_ref, F.col("programme_id") == F.col("_valid_programme"), "left"
    )
    reasons = F.filter(
        F.array(
            F.when(F.col("_valid_donor").isNull(), F.lit("missing_donor")),
            F.when(F.col("_valid_programme").isNull(), F.lit("missing_programme")),
            F.when(F.col("amount_original").isNull(), F.lit("missing_amount")),
            F.when(F.col("amount_original") <= 0, F.lit("non_positive_amount")),
            F.when(F.col("contribution_date").isNull(), F.lit("invalid_date")),
            F.when(
                (F.col("source_batch") == "json")
                & F.col("amount_original").isNotNull()
                & F.col("contribution_date").isNotNull()
                & F.col("_fx_rate").isNull(),
                F.lit("missing_exchange_rate"),
            ),
        ),
        lambda reason: reason.isNotNull(),
    )
    classified = classified.withColumn("quarantine_reasons", reasons)
    accepted = classified.where(F.size("quarantine_reasons") == 0).select(*CONTRIBUTION_COLUMNS)
    quality_quarantine = classified.where(F.size("quarantine_reasons") > 0).select(
        *CONTRIBUTION_COLUMNS, "quarantine_reasons"
    )
    conflict_quarantine = conflict_rows.select(*CONTRIBUTION_COLUMNS).withColumn(
        "quarantine_reasons", F.array(F.lit("conflicting_duplicate"))
    )
    quarantine = conflict_quarantine.unionByName(quality_quarantine).withColumn(
        "quarantine_comment",
        F.array_join(
            F.transform(
                "quarantine_reasons",
                lambda reason: (
                    F.when(reason == "missing_donor", "Donor ID is absent from the donor master.")
                    .when(
                        reason == "missing_programme",
                        "Programme ID is absent from all programme snapshots.",
                    )
                    .when(reason == "missing_amount", "Contribution amount is missing.")
                    .when(reason == "non_positive_amount", "Contribution amount is not positive.")
                    .when(
                        reason == "invalid_date",
                        "Contribution date is missing or cannot be parsed safely.",
                    )
                    .when(
                        reason == "missing_exchange_rate",
                        "No exchange rate exists for the contribution currency and month.",
                    )
                    .when(
                        reason == "conflicting_duplicate",
                        "Multiple rows share this contribution ID with conflicting values.",
                    )
                    .otherwise("Record failed a governed Silver quality rule.")
                ),
            ),
            " ",
        ),
    )
    metrics = SilverMetrics(
        bronze_contribution_rows=contributions_csv.count() + contributions_json.count(),
        exact_duplicates_removed=exact_removed,
        conflicting_duplicate_rows=conflict_rows.count(),
        cross_batch_corrections=cross_batch,
        accepted_rows=accepted.count(),
        quarantined_rows=quarantine.count(),
    )
    return accepted, quarantine, metrics


def merge_accepted_contributions(spark, accepted: DataFrame, target_table: str) -> None:
    """Synchronize the accepted snapshot with an explicit, idempotent Delta MERGE."""
    candidate_view = "_p08_accepted_candidate"
    accepted.createOrReplaceTempView(candidate_view)
    if not spark.catalog.tableExists(target_table):
        accepted.limit(0).write.format("delta").mode("overwrite").saveAsTable(target_table)
    assignments = ", ".join(f"target.`{name}` = source.`{name}`" for name in CONTRIBUTION_COLUMNS)
    columns = ", ".join(f"`{name}`" for name in CONTRIBUTION_COLUMNS)
    values = ", ".join(f"source.`{name}`" for name in CONTRIBUTION_COLUMNS)
    spark.sql(
        f"""
        MERGE INTO {target_table} AS target
        USING {candidate_view} AS source
        ON target.contribution_id = source.contribution_id
        WHEN MATCHED THEN UPDATE SET {assignments}
        WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values})
        WHEN NOT MATCHED BY SOURCE THEN DELETE
        """
    )


def transform_silver(bronze: dict[str, DataFrame]) -> tuple[dict[str, DataFrame], SilverMetrics]:
    donors = conform_donors(bronze["donors"])
    programmes = build_programme_scd2(bronze["programmes_q1"], bronze["programmes_q2"])
    exchange_rates = conform_exchange_rates(bronze["exchange_rates"])
    grants = conform_grants(bronze["grants"])
    accepted, quarantine, metrics = build_contributions(
        bronze["contributions_csv"],
        bronze["contributions_json"],
        donors,
        programmes,
        exchange_rates,
    )
    return (
        {
            "donors": donors,
            "dim_programme": programmes,
            "exchange_rates": exchange_rates,
            "grants": grants,
            "contributions_accepted": accepted,
            "contributions_quarantine": quarantine,
        },
        metrics,
    )
