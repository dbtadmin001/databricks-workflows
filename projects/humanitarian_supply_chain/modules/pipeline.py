"""End-to-end orchestration: Bronze -> Silver -> WAP -> Gold (Spark SQL) -> WAP.

Catalog/schema are always passed in by the caller (from databricks.yml /
delivery.json's per-environment values) -- never hardcoded here, so dev and
prod stay on their Terraform-managed dedicated catalogs.
"""

from __future__ import annotations

import re
import uuid

from pyspark.sql import DataFrame, SparkSession

from projects.humanitarian_supply_chain.modules.bronze import ingest_all
from projects.humanitarian_supply_chain.modules.gold import (
    build_fact_shipments,
    build_programme_monthly_summary,
    register_views,
)
from projects.humanitarian_supply_chain.modules.silver import conform_dimension, normalize_and_quarantine

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def qualified(catalog: str, schema: str, table: str) -> str:
    if not all(IDENTIFIER.fullmatch(v) for v in (catalog, schema, table)):
        raise ValueError("catalog, schema, and table must be simple identifiers")
    return f"{catalog}.{schema}.{table}"


def table_names(catalog: str, schema: str) -> dict[str, str]:
    names = {
        "bronze_warehouses": "bronze_warehouses",
        "bronze_programmes": "bronze_programmes",
        "bronze_items": "bronze_items",
        "bronze_shipments": "bronze_shipments",
        "silver_warehouses": "silver_warehouses",
        "silver_programmes": "silver_programmes",
        "silver_items": "silver_items",
        "silver_shipments_accepted": "silver_shipments_accepted",
        "silver_shipments_quarantine": "silver_shipments_quarantine",
        "gold_fact_shipments": "fact_shipments",
        "gold_programme_monthly_summary": "programme_monthly_summary",
    }
    return {key: qualified(catalog, schema, table) for key, table in names.items()}


def _write_wap(
    spark: SparkSession,
    dataframe: DataFrame,
    target: str,
    run_id: str,
    *,
    reject_empty: bool = True,
) -> None:
    """Write-audit-publish: stage -> reject-empty (unless allowed) -> atomic replace."""
    stage = f"{target.replace('.', '_')}_wap_{run_id.replace('-', '')}"
    dataframe.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        stage
    )
    if reject_empty and dataframe.limit(1).count() == 0:
        spark.sql(f"DROP TABLE IF EXISTS {stage}")
        raise RuntimeError(f"WAP quality gate rejected empty publication for {target}")
    columns = ", ".join(f"`{name}`" for name in dataframe.columns)
    spark.sql(f"CREATE OR REPLACE TABLE {target} USING DELTA AS SELECT {columns} FROM {stage}")
    spark.sql(f"DROP TABLE IF EXISTS {stage}")


def run_pipeline(spark: SparkSession, raw_dir: str, catalog: str, schema: str) -> dict:
    run_id = str(uuid.uuid4())
    names = table_names(catalog, schema)

    # Bronze: idempotent overwrite-by-file, no WAP gate (Bronze intentionally accepts everything).
    bronze_counts = ingest_all(
        spark,
        raw_dir,
        {
            "warehouses": names["bronze_warehouses"],
            "programmes": names["bronze_programmes"],
            "items": names["bronze_items"],
            "shipments": names["bronze_shipments"],
        },
    )

    # Silver dimensions: pass-through conform, WAP-published (idempotent replace).
    silver_warehouses = conform_dimension(
        spark.table(names["bronze_warehouses"]), business_key="WAREHOUSE_ID"
    )
    silver_programmes = conform_dimension(
        spark.table(names["bronze_programmes"]), business_key="PROGRAMME_ID"
    )
    silver_items = conform_dimension(spark.table(names["bronze_items"]), business_key="ITEM_CODE")
    _write_wap(spark, silver_warehouses, names["silver_warehouses"], run_id)
    _write_wap(spark, silver_programmes, names["silver_programmes"], run_id)
    _write_wap(spark, silver_items, names["silver_items"], run_id)

    # Silver shipments: full transform + quarantine classification, WAP-published.
    accepted, quarantine = normalize_and_quarantine(
        spark.table(names["bronze_shipments"]),
        silver_warehouses,
        silver_programmes,
        silver_items,
    )
    _write_wap(spark, accepted, names["silver_shipments_accepted"], run_id)
    _write_wap(spark, quarantine, names["silver_shipments_quarantine"], run_id, reject_empty=False)

    # WAP gate between Silver and Gold: Gold is only built from the just-published,
    # WAP-verified Silver tables -- re-read them from the catalog, not from the
    # in-memory accepted/quarantine frames, so Gold always reflects what was
    # actually published, not an intermediate in-flight computation.
    published_accepted = spark.table(names["silver_shipments_accepted"])
    published_warehouses = spark.table(names["silver_warehouses"])
    published_programmes = spark.table(names["silver_programmes"])
    published_items = spark.table(names["silver_items"])

    # Gold (Spark SQL): fact + aggregate, WAP-published.
    register_views(
        spark, published_accepted, published_warehouses, published_programmes, published_items
    )
    fact_shipments = build_fact_shipments(spark)
    _write_wap(spark, fact_shipments, names["gold_fact_shipments"], run_id)

    programme_monthly_summary = build_programme_monthly_summary(spark, fact_shipments)
    _write_wap(spark, programme_monthly_summary, names["gold_programme_monthly_summary"], run_id)

    return {
        "run_id": run_id,
        "bronze": bronze_counts,
        "silver_accepted": accepted.count(),
        "silver_quarantine": quarantine.count(),
        "gold_fact_shipments": fact_shipments.count(),
        "gold_programme_monthly_summary": programme_monthly_summary.count(),
        "tables": names,
    }


def default_raw_dir(catalog: str, schema: str) -> str:
    """Unity Catalog Volume path convention recorded in milestones/P07-M02.md."""
    return f"/Volumes/{catalog}/{schema}/landing"


def run_bronze_phase(
    spark: SparkSession, catalog: str, schema: str, *, raw_dir: str | None = None
) -> dict:
    names = table_names(catalog, schema)
    counts = ingest_all(
        spark,
        raw_dir or default_raw_dir(catalog, schema),
        {
            "warehouses": names["bronze_warehouses"],
            "programmes": names["bronze_programmes"],
            "items": names["bronze_items"],
            "shipments": names["bronze_shipments"],
        },
    )
    return {"bronze": counts, "tables": names}


def run_silver_phase(spark: SparkSession, catalog: str, schema: str) -> dict:
    run_id = str(uuid.uuid4())
    names = table_names(catalog, schema)
    silver_warehouses = conform_dimension(
        spark.table(names["bronze_warehouses"]), business_key="WAREHOUSE_ID"
    )
    silver_programmes = conform_dimension(
        spark.table(names["bronze_programmes"]), business_key="PROGRAMME_ID"
    )
    silver_items = conform_dimension(spark.table(names["bronze_items"]), business_key="ITEM_CODE")
    _write_wap(spark, silver_warehouses, names["silver_warehouses"], run_id)
    _write_wap(spark, silver_programmes, names["silver_programmes"], run_id)
    _write_wap(spark, silver_items, names["silver_items"], run_id)

    accepted, quarantine = normalize_and_quarantine(
        spark.table(names["bronze_shipments"]), silver_warehouses, silver_programmes, silver_items
    )
    _write_wap(spark, accepted, names["silver_shipments_accepted"], run_id)
    _write_wap(spark, quarantine, names["silver_shipments_quarantine"], run_id, reject_empty=False)
    return {
        "silver_accepted": accepted.count(),
        "silver_quarantine": quarantine.count(),
        "tables": names,
    }


def run_gold_phase(spark: SparkSession, catalog: str, schema: str) -> dict:
    run_id = str(uuid.uuid4())
    names = table_names(catalog, schema)
    # WAP gate between Silver and Gold: build Gold only from tables already
    # published by run_silver_phase, re-read from the catalog.
    published_accepted = spark.table(names["silver_shipments_accepted"])
    published_warehouses = spark.table(names["silver_warehouses"])
    published_programmes = spark.table(names["silver_programmes"])
    published_items = spark.table(names["silver_items"])

    register_views(
        spark, published_accepted, published_warehouses, published_programmes, published_items
    )
    fact_shipments = build_fact_shipments(spark)
    _write_wap(spark, fact_shipments, names["gold_fact_shipments"], run_id)

    programme_monthly_summary = build_programme_monthly_summary(spark, fact_shipments)
    _write_wap(spark, programme_monthly_summary, names["gold_programme_monthly_summary"], run_id)
    return {
        "gold_fact_shipments": fact_shipments.count(),
        "gold_programme_monthly_summary": programme_monthly_summary.count(),
        "tables": names,
    }
