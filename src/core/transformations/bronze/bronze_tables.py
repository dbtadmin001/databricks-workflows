# Bronze Layer — raw ingestion from samples.bakehouse.*
# Adds audit columns; no transformations applied.

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(
    name="bronze_transactions",
    comment="Raw POS transactions from samples.bakehouse.sales_transactions",
    table_properties={"quality": "bronze"}
)
def bronze_transactions():
    return (
        spark.read.table("samples.bakehouse.sales_transactions")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("samples.bakehouse.sales_transactions"))
    )


@dp.table(
    name="bronze_franchises",
    comment="Raw franchise/store dimension from samples.bakehouse.sales_franchises",
    table_properties={"quality": "bronze"}
)
def bronze_franchises():
    return (
        spark.read.table("samples.bakehouse.sales_franchises")
        .withColumn("_ingested_at", F.current_timestamp())
    )


@dp.table(
    name="bronze_customers",
    comment="Raw customer dimension from samples.bakehouse.sales_customers",
    table_properties={"quality": "bronze"}
)
def bronze_customers():
    return (
        spark.read.table("samples.bakehouse.sales_customers")
        .withColumn("_ingested_at", F.current_timestamp())
    )


@dp.table(
    name="bronze_suppliers",
    comment="Raw supplier dimension from samples.bakehouse.sales_suppliers",
    table_properties={"quality": "bronze"}
)
def bronze_suppliers():
    return (
        spark.read.table("samples.bakehouse.sales_suppliers")
        .withColumn("_ingested_at", F.current_timestamp())
    )
