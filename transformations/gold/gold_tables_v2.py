# Gold Layer — business-ready aggregations
# All tables publish to workspace.default.* (pipeline schema = default)

from pyspark import pipelines as dp
from pyspark.sql import functions as F
from pyspark.sql.window import Window


@dp.materialized_view(
    name="gold_daily_revenue",
    comment="Daily revenue by franchise and product — used for trend dashboards",
    table_properties={"quality": "gold"}
)
def gold_daily_revenue():
    return (
        spark.read.table("silver_transactions_enriched")
        .groupBy(
            "transaction_date", "transaction_month",
            "franchiseID", "franchise_name", "city", "country", "store_size",
            "product"
        )
        .agg(
            F.sum("totalPrice").alias("total_revenue"),
            F.sum("quantity").alias("total_units_sold"),
            F.count("transactionID").alias("transaction_count"),
            F.round(F.avg("totalPrice"), 2).alias("avg_transaction_value")
        )
    )


@dp.materialized_view(
    name="gold_product_performance",
    comment="Product-level revenue, volume, and unique customer reach",
    table_properties={"quality": "gold"}
)
def gold_product_performance():
    w_all = Window.partitionBy(F.lit(1))
    return (
        spark.read.table("silver_transactions_enriched")
        .groupBy("product")
        .agg(
            F.sum("totalPrice").alias("total_revenue"),
            F.sum("quantity").alias("total_units_sold"),
            F.count("transactionID").alias("transaction_count"),
            F.round(F.avg("unitPrice"), 2).alias("avg_unit_price"),
            F.round(F.avg("totalPrice"), 2).alias("avg_transaction_value"),
            F.countDistinct("customerID").alias("unique_customers")
        )
        .withColumn(
            "revenue_share",
            F.round(
                F.col("total_revenue") / F.sum("total_revenue").over(w_all), 4
            )
        )
    )


@dp.materialized_view(
    name="gold_franchise_ranking",
    comment="Franchise performance ranked by total revenue with geo coords for mapping",
    table_properties={"quality": "gold"}
)
def gold_franchise_ranking():
    w_rank = Window.orderBy(F.desc("total_revenue"))
    return (
        spark.read.table("silver_transactions_enriched")
        .groupBy(
            "franchiseID", "franchise_name", "city",
            "district", "country", "store_size",
            "longitude", "latitude"
        )
        .agg(
            F.sum("totalPrice").alias("total_revenue"),
            F.sum("quantity").alias("total_units_sold"),
            F.count("transactionID").alias("transaction_count"),
            F.round(F.avg("totalPrice"), 2).alias("avg_basket_size"),
            F.countDistinct("customerID").alias("unique_customers")
        )
        .withColumn("revenue_rank", F.rank().over(w_rank))
    )


@dp.materialized_view(
    name="gold_customer_segments",
    comment="Customer spend tiers, visit frequency, and favourite product",
    table_properties={"quality": "gold"}
)
def gold_customer_segments():
    enriched = spark.read.table("silver_transactions_enriched")

    w_fav = Window.partitionBy("customerID").orderBy(F.desc("product_spend"))
    fav = (
        enriched
        .groupBy("customerID", "product")
        .agg(F.sum("totalPrice").alias("product_spend"))
        .withColumn("rn", F.row_number().over(w_fav))
        .filter(F.col("rn") == 1)
        .select("customerID", F.col("product").alias("favourite_product"))
    )

    base = (
        enriched
        .groupBy(
            "customerID", "customer_name", "gender",
            "customer_country", "customer_continent"
        )
        .agg(
            F.sum("totalPrice").alias("total_spend"),
            F.count("transactionID").alias("visit_count"),
            F.round(F.avg("totalPrice"), 2).alias("avg_spend_per_visit"),
            F.countDistinct("franchiseID").alias("stores_visited"),
            F.countDistinct("transaction_date").alias("active_days")
        )
        .withColumn(
            "spend_tier",
            F.when(F.col("total_spend") >= 500, "High")
             .when(F.col("total_spend") >= 200, "Medium")
             .otherwise("Low")
        )
    )
    return base.join(fav, on="customerID", how="left")
