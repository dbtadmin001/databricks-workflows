"""Gold: Silver -> Gold in Spark SQL. fact_shipments and programme_monthly_summary.

Silver-accepted shipments and conformed dimensions are registered as temp
views; every Gold table is built with an explicit Spark SQL statement (no
DataFrame API here), matching this project's requirement that Silver->Gold
be Spark SQL.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession

FACT_SHIPMENTS_SQL = """
SELECT
    s.SHIPMENT_ID       AS shipment_id,
    s.WAREHOUSE_ID       AS warehouse_id,
    w.WAREHOUSE_NAME     AS warehouse_name,
    s.PROGRAMME_ID       AS programme_id,
    p.PROGRAMME_NAME     AS programme_name,
    s.ITEM_CODE          AS item_code,
    i.ITEM_NAME           AS item_name,
    s.quantity            AS quantity,
    s.unit_cost            AS unit_cost,
    CAST(s.quantity AS DECIMAL(18,2)) * s.unit_cost AS total_line_cost,
    s.status               AS status,
    s.ship_date             AS ship_date
FROM silver_shipments_accepted s
JOIN silver_warehouses w ON s.WAREHOUSE_ID = w.WAREHOUSE_ID
JOIN silver_programmes p ON s.PROGRAMME_ID = p.PROGRAMME_ID
JOIN silver_items i ON s.ITEM_CODE = i.ITEM_CODE
"""

PROGRAMME_MONTHLY_SUMMARY_SQL = """
SELECT
    programme_name,
    date_format(ship_date, 'yyyy-MM') AS year_month,
    SUM(quantity) AS total_qty,
    SUM(total_line_cost) AS total_cost
FROM gold_fact_shipments_stage
WHERE status != 'cancelled'
GROUP BY programme_name, date_format(ship_date, 'yyyy-MM')
"""


def register_views(
    spark: SparkSession,
    silver_shipments_accepted: DataFrame,
    silver_warehouses: DataFrame,
    silver_programmes: DataFrame,
    silver_items: DataFrame,
) -> None:
    silver_shipments_accepted.createOrReplaceTempView("silver_shipments_accepted")
    silver_warehouses.createOrReplaceTempView("silver_warehouses")
    silver_programmes.createOrReplaceTempView("silver_programmes")
    silver_items.createOrReplaceTempView("silver_items")


def build_fact_shipments(spark: SparkSession) -> DataFrame:
    return spark.sql(FACT_SHIPMENTS_SQL)


def build_programme_monthly_summary(spark: SparkSession, fact_shipments: DataFrame) -> DataFrame:
    fact_shipments.createOrReplaceTempView("gold_fact_shipments_stage")
    return spark.sql(PROGRAMME_MONTHLY_SUMMARY_SQL)
