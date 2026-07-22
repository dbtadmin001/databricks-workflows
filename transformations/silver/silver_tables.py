# Silver Layer — cleaned, enriched, DQ-validated

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.expect_or_drop("valid_transaction_id", "transactionID IS NOT NULL")
@dp.expect_or_drop("valid_total_price",    "totalPrice > 0")
@dp.expect_or_drop("valid_quantity",       "quantity > 0")
@dp.expect(        "valid_unit_price",     "unitPrice > 0")  # warn only
@dp.table(
    name="silver_transactions_enriched",
    comment="Transactions joined with franchise & customer dims; DQ-enforced",
    table_properties={"quality": "silver"}
)
def silver_transactions_enriched():
    txn = spark.read.table("bronze_transactions")
    fran = spark.read.table("bronze_franchises").select(
        "franchiseID",
        F.col("name").alias("franchise_name"),
        "city", "district", "country",
        F.col("size").alias("store_size"),
        "longitude", "latitude"
    )
    cust = spark.read.table("bronze_customers").select(
        "customerID",
        F.concat_ws(" ", F.col("first_name"), F.col("last_name")).alias("customer_name"),
        "gender",
        F.col("country").alias("customer_country"),
        F.col("continent").alias("customer_continent")
    )
    return (
        txn
        .join(fran, on="franchiseID", how="left")
        .join(cust, on="customerID",  how="left")
        .withColumn("transaction_date",  F.to_date("dateTime"))
        .withColumn("transaction_hour",  F.hour("dateTime"))
        .withColumn("transaction_month", F.date_format("dateTime", "yyyy-MM"))
        .drop("_ingested_at", "_source")
    )


@dp.table(
    name="silver_franchise_details",
    comment="Franchise stores enriched with approved supplier info",
    table_properties={"quality": "silver"}
)
def silver_franchise_details():
    fran = spark.read.table("bronze_franchises")
    supp = spark.read.table("bronze_suppliers").select(
        "supplierID",
        F.col("name").alias("supplier_name"),
        "ingredient", "continent", "approved"
    )
    return (
        fran
        .join(supp, on="supplierID", how="left")
        .drop("_ingested_at")
    )
