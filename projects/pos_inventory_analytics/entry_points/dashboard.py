# Databricks notebook source
# MAGIC %md
# MAGIC # Real-Time POS Inventory Analytics dashboard
# MAGIC
# MAGIC **Purpose:** Publish the decision view after the Lakeflow pipeline and schema/
# MAGIC quality audit succeed: products below safety stock by store, current inventory
# MAGIC by category, and a pipeline/quality trust panel.
# MAGIC
# MAGIC **Inputs:** `gold_inventory_current`, the Gold publication audit, stage quality
# MAGIC profile, and the Bronze/Silver/quarantine tables from the dedicated project
# MAGIC schema (see `DATA_CONTRACTS.md`).
# MAGIC
# MAGIC **Processing:** The notebook reads governed tables, computes KPI and data-trust
# MAGIC values, applies a store/category filter, and renders compact Plotly-backed
# MAGIC analytical pages as HTML.
# MAGIC
# MAGIC **Key optimizations:** Read only the compact Gold/audit/quality tables needed for
# MAGIC the active dashboard, aggregate in SQL, avoid raw record details, and render
# MAGIC ordered dashboard sections without intermediate notebook noise.
# MAGIC
# MAGIC **Expected outputs:** A Plotly HTML dashboard with Gold KPIs, latest successful
# MAGIC run, source/accepted/quarantined counts, reconciliation status, candidate
# MAGIC publication status, Gold refresh timestamp, active-filter context, and
# MAGIC analytical annotations.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Load dashboard dependencies
# MAGIC
# MAGIC Import rendering helpers and Spark functions for the dashboard. No governed table
# MAGIC is read in this setup cell.

# COMMAND ----------

# ruff: noqa: F821
# Fix for editable install issue: explicitly add src to sys.path
import sys
import os

bundle_base = "/Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/project_12_pos_inventory_analytics/dev/files"
src_path = f"{bundle_base}/src"
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import html
import re

import plotly.express as px
from IPython.display import HTML, clear_output, display as ipy_display
from pyspark.sql import functions as F

from projects.pos_inventory_analytics.modules.dashboard import render_dashboard_html

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Resolve filters and governed inputs
# MAGIC
# MAGIC Widgets bind the project catalog/schema and the active store filter. The notebook
# MAGIC validates identifiers before reading Gold, the publication audit, quality
# MAGIC profile, quarantine, Bronze, and Silver tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Catalog")
dbutils.widgets.text("schema", "medallion", "Schema")
dbutils.widgets.text("store_filter", "All", "Store filter")
dbutils.widgets.text("category_filter", "All", "Category filter")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
store_filter = dbutils.widgets.get("store_filter").strip()
category_filter = dbutils.widgets.get("category_filter").strip()
safe_identifier = re.compile(r"^[a-z][a-z0-9_]*$")
if not safe_identifier.fullmatch(catalog) or not safe_identifier.fullmatch(schema):
    raise ValueError("A safe dedicated catalog and schema are required")

gold_table = f"{catalog}.{schema}.gold_inventory_current"
audit_table = f"{catalog}.{schema}.project_12_pos_inventory_analytics_gold_publication_audit"
quality_table = f"{catalog}.{schema}.project_12_pos_inventory_analytics_stage_quality_profile"
change_quarantine_table = f"{catalog}.{schema}.silver_inventory_change_quarantine"
snapshot_quarantine_table = f"{catalog}.{schema}.silver_inventory_snapshot_quarantine"
bronze_table = f"{catalog}.{schema}.bronze_inventory_change_raw"
silver_table = f"{catalog}.{schema}.silver_inventory_change"

gold = spark.table(gold_table)
filtered_gold = gold
if store_filter and store_filter.lower() != "all":
    filtered_gold = filtered_gold.where(F.lower("store_name") == store_filter.lower())
if category_filter and category_filter.lower() != "all":
    filtered_gold = filtered_gold.where(F.lower("category") == category_filter.lower())
filtered_gold.createOrReplaceTempView("_dashboard_gold")

audit = spark.table(audit_table)
quality = spark.table(quality_table)
change_quarantine = spark.table(change_quarantine_table)
snapshot_quarantine = spark.table(snapshot_quarantine_table)
source_rows = spark.table(bronze_table).count()
accepted_rows = spark.table(silver_table).count()
change_quarantine_rows = change_quarantine.count()
snapshot_quarantine_rows = snapshot_quarantine.count()
quarantine_rows = change_quarantine_rows + snapshot_quarantine_rows

latest_audit_rows = audit.orderBy(F.desc("audited_at")).limit(1).collect()
successful_audit = audit.where(F.col("status").isin("PUBLISHED", "PUBLISHED_WITH_WARNINGS"))
latest_success_rows = successful_audit.orderBy(F.desc("audited_at")).limit(1).collect()
latest_audit = latest_audit_rows[0] if latest_audit_rows else None
latest_success = latest_success_rows[0] if latest_success_rows else None

kpis = spark.sql(
    """
    SELECT
      SUM(current_inventory_quantity) AS total_inventory,
      COUNT(*) AS item_store_rows,
      COUNT(DISTINCT category) AS categories,
      SUM(CASE WHEN below_safety_stock THEN 1 ELSE 0 END) AS below_safety_stock_count
    FROM _dashboard_gold
    """
).collect()[0]

below_safety_by_store = spark.sql(
    """
    SELECT store_name, COUNT(*) AS below_safety_stock_count
    FROM _dashboard_gold
    WHERE below_safety_stock
    GROUP BY store_name
    ORDER BY below_safety_stock_count DESC
    """
).toPandas()

inventory_by_category = spark.sql(
    """
    SELECT category, SUM(current_inventory_quantity) AS current_inventory_quantity
    FROM _dashboard_gold
    GROUP BY category
    ORDER BY current_inventory_quantity DESC
    """
).toPandas()

inventory_by_store = spark.sql(
    """
    SELECT store_name, SUM(current_inventory_quantity) AS current_inventory_quantity
    FROM _dashboard_gold
    GROUP BY store_name
    ORDER BY current_inventory_quantity DESC
    """
).toPandas()

exploded_total_rows = accepted_rows + change_quarantine_rows
change_quarantine_rate = (
    change_quarantine_rows / exploded_total_rows if exploded_total_rows else 0.0
)
reconciliation_status = "PASS" if exploded_total_rows > 0 else "REVIEW"

freshness_rows = successful_audit.agg(
    F.max("audited_at").alias("gold_refreshed_at"),
    F.floor(
        (F.unix_timestamp(F.current_timestamp()) - F.unix_timestamp(F.max("audited_at"))) / 60
    ).alias("freshness_minutes"),
).collect()
gold_refreshed_at = freshness_rows[0].gold_refreshed_at if freshness_rows else None
freshness_minutes = int(freshness_rows[0].freshness_minutes or 0) if freshness_rows else 0

quality_trend = (
    quality.where(F.col("layer") == "silver")
    .select("run_id", "profiled_at", "rejected_records", "rejected_rate")
    .orderBy("profiled_at")
    .toPandas()
)
failed_rules = (
    change_quarantine.select(F.explode("quarantine_reasons").alias("quality_rule"))
    .unionByName(snapshot_quarantine.select(F.explode("quarantine_reasons").alias("quality_rule")))
    .groupBy("quality_rule")
    .count()
    .orderBy(F.desc("count"), "quality_rule")
    .limit(10)
    .toPandas()
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build trusted metrics and visuals
# MAGIC
# MAGIC Metrics come from governed Gold, publication-audit, and quality-profile
# MAGIC metadata, never hardcoded values. The data-trust panel is prepared beside the
# MAGIC business visuals so publication state and reconciliation remain visible.

# COMMAND ----------

filter_context = (
    f"Active store filter: {store_filter or 'All'}, category filter: {category_filter or 'All'}"
)


def annotate(figure, message):
    figure.add_annotation(
        text=message,
        x=0,
        y=1.12,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
        font={"size": 12, "color": "#52616f"},
    )


below_safety_figure = px.bar(
    below_safety_by_store,
    x="store_name",
    y="below_safety_stock_count",
    title="Products below safety stock, by store",
    labels={"store_name": "Store", "below_safety_stock_count": "Items below safety stock"},
    color_discrete_sequence=["#c43d4b"],
)
annotate(below_safety_figure, f"Replenishment risk by store. {filter_context}.")

inventory_category_figure = px.bar(
    inventory_by_category,
    x="category",
    y="current_inventory_quantity",
    title="Current inventory by category",
    labels={"category": "Category", "current_inventory_quantity": "Current inventory"},
    color_discrete_sequence=["#007f73"],
)
annotate(
    inventory_category_figure,
    f"Snapshot plus valid changes on/after the snapshot. {filter_context}.",
)

inventory_store_figure = px.bar(
    inventory_by_store,
    x="store_name",
    y="current_inventory_quantity",
    title="Current inventory by store",
    labels={"store_name": "Store", "current_inventory_quantity": "Current inventory"},
    color_discrete_sequence=["#2b6cb0"],
)
annotate(
    inventory_store_figure,
    f"Includes the online store's own standalone activity. {filter_context}.",
)

quality_trend_figure = px.line(
    quality_trend,
    x="profiled_at",
    y="rejected_records",
    markers=True,
    title="Silver quarantine trend by pipeline run",
    labels={"profiled_at": "Profile timestamp", "rejected_records": "Quarantined rows"},
)
annotate(
    quality_trend_figure,
    "Track whether rejected inventory-change records are increasing across pipeline runs.",
)

failed_rules_figure = px.bar(
    failed_rules,
    x="count",
    y="quality_rule",
    orientation="h",
    title="Top failed quality rules",
    labels={"count": "Rejected rows", "quality_rule": "Quality rule"},
)
if failed_rules.empty:
    failed_rules_figure.add_annotation(
        text="No quarantine rules failed in the current governed dataset.",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
    )


def card(label, value):
    return (
        '<div class="dashboard-card"><div class="dashboard-label">'
        + html.escape(label)
        + '</div><div class="dashboard-value">'
        + html.escape(str(value))
        + "</div></div>"
    )


summary_html = (
    '<div class="dashboard-grid">'
    + "".join(
        (
            card("Current inventory", f"{float(kpis.total_inventory or 0):,.0f}"),
            card("Store x item rows", f"{int(kpis.item_store_rows or 0):,}"),
            card("Categories", f"{int(kpis.categories or 0):,}"),
            card("Below safety stock", f"{int(kpis.below_safety_stock_count or 0):,}"),
        )
    )
    + "</div>"
)

trust_values = (
    ("Latest successful run", latest_success.run_id if latest_success else "NOT_AVAILABLE"),
    ("Source records", f"{source_rows:,}"),
    ("Accepted records", f"{accepted_rows:,}"),
    ("Quarantined records", f"{quarantine_rows:,}"),
    ("Reconciliation", reconciliation_status),
    ("Candidate publication", latest_audit.status if latest_audit else "NOT_AVAILABLE"),
    ("Gold refreshed", str(gold_refreshed_at or "NOT_AVAILABLE")),
)
trust_html = (
    '<section class="dashboard-trust"><div class="dashboard-label">Data trust</div>'
    '<div class="dashboard-trust-grid">'
    + "".join(
        '<div class="dashboard-trust-item"><div class="dashboard-label">'
        + html.escape(label)
        + '</div><div class="dashboard-trust-value">'
        + html.escape(str(value))
        + "</div></div>"
        for label, value in trust_values
    )
    + "</div></section>"
)

quality_cards_html = (
    '<div class="dashboard-grid">'
    + "".join(
        (
            card("Bronze transactions", f"{source_rows:,}"),
            card("Accepted transaction-items", f"{accepted_rows:,}"),
            card("Quarantined transaction-items", f"{change_quarantine_rows:,}"),
            card("Quarantined snapshot rows", f"{snapshot_quarantine_rows:,}"),
            card("Quarantine rate", f"{change_quarantine_rate:.2%}"),
            card("Freshness", f"{freshness_minutes:,} minutes"),
        )
    )
    + "</div>"
)

dashboard_registry = [
    {
        "name": "Overview & trust",
        "visuals": [
            {
                "id": "below-safety-stock-by-store",
                "figure": below_safety_figure,
                "annotation": f"Replenishment risk by store. {filter_context}.",
            }
        ],
    },
    {
        "name": "Inventory",
        "visuals": [
            {
                "id": "inventory-by-category",
                "figure": inventory_category_figure,
                "annotation": f"Current inventory by category. {filter_context}.",
            },
            {
                "id": "inventory-by-store",
                "figure": inventory_store_figure,
                "annotation": f"Current inventory by store. {filter_context}.",
            },
        ],
    },
    {
        "name": "Data Quality",
        "content_html": quality_cards_html,
        "visuals": [
            {
                "id": "data-quality-quarantine-trend",
                "figure": quality_trend_figure,
                "annotation": "Quarantine history comes from persisted Silver quality profiles.",
            },
            {
                "id": "data-quality-failed-rules",
                "figure": failed_rules_figure,
                "annotation": "Rule counts come from reason-coded quarantine records.",
            },
        ],
    },
]

dashboard_html = render_dashboard_html(
    title="Real-Time POS Inventory Analytics",
    subtitle=f"Governed Gold inventory - {catalog}.{schema}",
    summary_html=summary_html,
    trust_html=trust_html,
    pages=dashboard_registry,
)

# COMMAND ----------

# Sales metrics from inventory change transactions
sales_by_product = spark.sql(
    """
    SELECT 
      i.item_name,
      i.category,
      COUNT(DISTINCT c.trans_id) as transactions,
      SUM(ABS(c.quantity)) as units_sold,
      SUM(ABS(c.quantity) * i.unit_price) as total_revenue,
      AVG(i.unit_price) as avg_price
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    GROUP BY i.item_name, i.category
    ORDER BY total_revenue DESC
    LIMIT 15
    """
).toPandas()

sales_by_store = spark.sql(
    """
    SELECT 
      s.store_name,
      COUNT(DISTINCT c.trans_id) as transactions,
      SUM(ABS(c.quantity)) as units_sold,
      SUM(ABS(c.quantity) * i.unit_price) as total_revenue,
      SUM(ABS(c.quantity) * i.unit_price) / COUNT(DISTINCT c.trans_id) as avg_transaction_value
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.store_ref s ON c.store_id = s.store_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    GROUP BY s.store_name
    ORDER BY total_revenue DESC
    """
).toPandas()

sales_by_category = spark.sql(
    """
    SELECT 
      i.category,
      COUNT(DISTINCT c.trans_id) as transactions,
      SUM(ABS(c.quantity)) as units_sold,
      SUM(ABS(c.quantity) * i.unit_price) as total_revenue
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    GROUP BY i.category
    ORDER BY total_revenue DESC
    """
).toPandas()

sales_by_channel = spark.sql(
    """
    SELECT 
      ct.change_type as channel,
      COUNT(DISTINCT c.trans_id) as transactions,
      SUM(ABS(c.quantity)) as units_sold,
      SUM(ABS(c.quantity) * i.unit_price) as total_revenue
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    GROUP BY ct.change_type
    ORDER BY total_revenue DESC
    """
).toPandas()

sales_daily_trend = spark.sql(
    """
    SELECT 
      DATE(c.date_time) as sale_date,
      COUNT(DISTINCT c.trans_id) as transactions,
      SUM(ABS(c.quantity)) as units_sold,
      SUM(ABS(c.quantity) * i.unit_price) as total_revenue
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    GROUP BY DATE(c.date_time)
    ORDER BY sale_date
    """
).toPandas()

# Overall sales KPIs
total_sales_kpis = spark.sql(
    """
    SELECT
      COUNT(DISTINCT c.trans_id) AS total_transactions,
      SUM(ABS(c.quantity)) AS total_units_sold,
      SUM(ABS(c.quantity) * i.unit_price) AS total_revenue,
      SUM(ABS(c.quantity) * i.unit_price) / COUNT(DISTINCT c.trans_id) AS avg_transaction_value,
      COUNT(DISTINCT c.item_id) AS distinct_products_sold
    FROM project_12_pos_inventory_analytics_dev.medallion.silver_inventory_change c
    JOIN project_12_pos_inventory_analytics_dev.medallion.item_ref i ON c.item_id = i.item_id
    JOIN project_12_pos_inventory_analytics_dev.medallion.change_type_ref ct ON c.change_type_id = ct.change_type_id
    WHERE ct.change_type IN ('sale', 'bopis')
    """
).collect()[0]

# COMMAND ----------

# Sales visualizations
top_products_figure = px.bar(
    sales_by_product.head(10),
    x="total_revenue",
    y="item_name",
    orientation="h",
    title="Top 10 Products by Revenue",
    labels={"total_revenue": "Total Revenue ($)", "item_name": "Product"},
    color_discrete_sequence=["#1f77b4"],
)
annotate(
    top_products_figure,
    "Based on in-store sales and BOPIS transactions. Includes all fulfilled orders.",
)

store_revenue_figure = px.bar(
    sales_by_store,
    x="store_name",
    y="total_revenue",
    title="Revenue by Store",
    labels={"store_name": "Store", "total_revenue": "Total Revenue ($)"},
    color_discrete_sequence=["#2ca02c"],
)
annotate(
    store_revenue_figure,
    "Store-level sales performance including BOPIS fulfillment.",
)

category_revenue_figure = px.pie(
    sales_by_category,
    values="total_revenue",
    names="category",
    title="Revenue Distribution by Category",
    hole=0.4,
)

channel_comparison_figure = px.bar(
    sales_by_channel,
    x="channel",
    y="total_revenue",
    title="Sales by Channel",
    labels={"channel": "Channel", "total_revenue": "Total Revenue ($)"},
    color_discrete_sequence=["#ff7f0e"],
)
annotate(
    channel_comparison_figure,
    "In-store sales vs. Buy Online Pickup In Store (BOPIS) transactions.",
)

daily_trend_figure = px.line(
    sales_daily_trend,
    x="sale_date",
    y="total_revenue",
    markers=True,
    title="Daily Sales Trend",
    labels={"sale_date": "Date", "total_revenue": "Revenue ($)"},
    color_discrete_sequence=["#d62728"],
)
annotate(
    daily_trend_figure,
    "Revenue trend across the reporting period.",
)

transactions_trend_figure = px.line(
    sales_daily_trend,
    x="sale_date",
    y="transactions",
    markers=True,
    title="Daily Transaction Volume",
    labels={"sale_date": "Date", "transactions": "Number of Transactions"},
    color_discrete_sequence=["#9467bd"],
)
annotate(
    transactions_trend_figure,
    "Transaction count by day, including both in-store and BOPIS orders.",
)

# COMMAND ----------

# Combined inventory and sales summary
summary_html = (
    '<div class="dashboard-grid">'
    + "".join(
        (
            card("Total Revenue", f"${float(total_sales_kpis.total_revenue or 0):,.2f}"),
            card("Total Transactions", f"{int(total_sales_kpis.total_transactions or 0):,}"),
            card("Avg Transaction Value", f"${float(total_sales_kpis.avg_transaction_value or 0):,.2f}"),
            card("Units Sold", f"{int(total_sales_kpis.total_units_sold or 0):,}"),
            card("Current Inventory", f"{float(kpis.total_inventory or 0):,.0f}"),
            card("Below Safety Stock", f"{int(kpis.below_safety_stock_count or 0):,}"),
        )
    )
    + "</div>"
)

# COMMAND ----------

dashboard_registry = [
    {
        "name": "Overview & trust",
        "visuals": [
            {
                "id": "below-safety-stock-by-store",
                "figure": below_safety_figure,
                "annotation": f"Replenishment risk by store. {filter_context}.",
            }
        ],
    },
    {
        "name": "Sales Performance",
        "visuals": [
            {
                "id": "top-products-revenue",
                "figure": top_products_figure,
                "annotation": "Top-selling products ranked by total revenue generated.",
            },
            {
                "id": "revenue-by-store",
                "figure": store_revenue_figure,
                "annotation": "Compare sales performance across store locations.",
            },
            {
                "id": "revenue-by-category",
                "figure": category_revenue_figure,
                "annotation": "Category mix and contribution to total revenue.",
            },
        ],
    },
    {
        "name": "Sales Trends",
        "visuals": [
            {
                "id": "daily-revenue-trend",
                "figure": daily_trend_figure,
                "annotation": "Revenue performance over time.",
            },
            {
                "id": "daily-transactions-trend",
                "figure": transactions_trend_figure,
                "annotation": "Transaction volume trends help identify peak periods.",
            },
            {
                "id": "channel-comparison",
                "figure": channel_comparison_figure,
                "annotation": "In-store vs BOPIS channel performance.",
            },
        ],
    },
    {
        "name": "Inventory",
        "visuals": [
            {
                "id": "inventory-by-category",
                "figure": inventory_category_figure,
                "annotation": f"Current inventory by category. {filter_context}.",
            },
            {
                "id": "inventory-by-store",
                "figure": inventory_store_figure,
                "annotation": f"Current inventory by store. {filter_context}.",
            },
        ],
    },
    {
        "name": "Data Quality",
        "content_html": quality_cards_html,
        "visuals": [
            {
                "id": "data-quality-quarantine-trend",
                "figure": quality_trend_figure,
                "annotation": "Quarantine history comes from persisted Silver quality profiles.",
            },
            {
                "id": "data-quality-failed-rules",
                "figure": failed_rules_figure,
                "annotation": "Rule counts come from reason-coded quarantine records.",
            },
        ],
    },
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Render the ordered dashboard
# MAGIC
# MAGIC The final output places the Gold KPI summary first, data trust second, then
# MAGIC navigation/filter context and the analytical visuals with annotations.

# COMMAND ----------

clear_output(wait=True)
try:
    displayHTML(dashboard_html)
except NameError:
    ipy_display(HTML(dashboard_html))