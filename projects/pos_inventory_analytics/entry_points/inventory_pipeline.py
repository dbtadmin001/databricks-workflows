# Databricks notebook source
# MAGIC %md
# MAGIC # Real-time POS inventory Lakeflow Declarative Pipeline
# MAGIC
# MAGIC **Purpose:** Incrementally ingest inventory events and snapshots, produce clean
# MAGIC Silver inventory-change/snapshot data, and calculate current inventory with a
# MAGIC safety-stock alert, per `REQUIREMENTS.md`/`DATA_CONTRACTS.md`.
# MAGIC
# MAGIC **Inputs:** The `source_base_path` pipeline configuration value (a configurable
# MAGIC Unity Catalog Volume path, never hardcoded), pointing at
# MAGIC `reference/*.csv` and `landing/{inventory_events,inventory_snapshots}/*`.
# MAGIC
# MAGIC **Processing:** Every table function here is a thin Lakeflow wrapper: reference
# MAGIC files become materialized tables; events/snapshots are ingested incrementally via
# MAGIC Auto Loader into streaming Bronze tables; Silver/Gold call the same plain,
# MAGIC unit-tested functions in `pipeline.py` used by `tests/test_pipeline.py` --
# MAGIC business logic lives there, not here, so it is exercised by local/CI tests even
# MAGIC though this file's own `@dlt.table`/Auto Loader wiring can only be proven by a
# MAGIC real deployed pipeline update (see REQUIREMENTS.md, "Lakeflow vs. this repo's
# MAGIC PySpark/PipelineRunner pattern").
# MAGIC
# MAGIC **Key optimizations:** Auto Loader incremental file discovery/checkpointing
# MAGIC (no full-directory rescans); an explicit fixed schema (including the optional
# MAGIC `channel` field from day one) so the incremental batch's new field never
# MAGIC triggers a schema-evolution restart; Silver/Gold read Bronze via `dlt.read`
# MAGIC (batch snapshot of the accumulated Delta table) rather than `dlt.read_stream`,
# MAGIC because the required dedup/latest-snapshot window functions are not valid on an
# MAGIC unbounded streaming DataFrame -- data volume here is small enough that a full
# MAGIC Silver/Gold recompute per pipeline update is the correct, simple choice.
# MAGIC
# MAGIC **Expected outputs:** `bronze_inventory_change_raw`, `bronze_inventory_snapshot_raw`,
# MAGIC `silver_inventory_change` (+ `_quarantine`), `silver_inventory_snapshot`
# MAGIC (+ `_quarantine`), `silver_latest_inventory_snapshot`, `gold_inventory_current`,
# MAGIC and the four reference tables. At least 5 explicit Lakeflow expectations on the
# MAGIC two Bronze streaming tables.

# COMMAND ----------
# MAGIC %md
# MAGIC ## 1. Load the tested pipeline logic and resolve the configurable base path
# MAGIC
# MAGIC The pipeline's `configuration` block (declared in the Bundle pipeline resource)
# MAGIC supplies `source_base_path` -- never a hardcoded Workspace or Bundle deployment
# MAGIC directory, per the brief's explicit constraint.

# COMMAND ----------
# ruff: noqa: F821
# Fix for editable install issue: explicitly add src to sys.path
import sys
import os

# Get the bundle base path and add src to Python path
# Repo base path
repo_base = "/Workspace/Repos/albertraviss@gmail.com/databricks-workflows"
# Add projects directory to Python path
projects_path = f"{repo_base}/projects"
if projects_path not in sys.path:
    sys.path.insert(0, projects_path)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType, StringType, StructField, StructType

from projects.pos_inventory_analytics.modules.pipeline import (
    classify_inventory_change,
    classify_inventory_snapshot,
    explode_inventory_changes,
    latest_inventory_snapshot,
    to_bronze_events,
    to_bronze_snapshots,
    to_gold_inventory_current,
)

BASE_PATH = spark.conf.get("source_base_path")
EVENTS_PATH = f"{BASE_PATH}/landing/inventory_events"
SNAPSHOTS_PATH = f"{BASE_PATH}/landing/inventory_snapshots"
REFERENCE_PATH = f"{BASE_PATH}/reference"

# Fixed explicit schema, channel included from day one: batch01 simply has it
# always NULL, so the incremental batch introducing populated channel values
# is an ordinary data change, never a schema-evolution event.
_ITEM_LINE_SCHEMA = StructType(
    [
        StructField("item_id", IntegerType(), True),
        StructField("quantity", IntegerType(), True),
    ]
)
EVENT_SCHEMA = StructType(
    [
        StructField("trans_id", StringType(), True),
        StructField("store_id", IntegerType(), True),
        StructField("date_time", StringType(), True),
        StructField("change_type_id", IntegerType(), True),
        StructField("items", ArrayType(_ITEM_LINE_SCHEMA), True),
        StructField("bopis_order_id", StringType(), True),
        StructField("channel", StringType(), True),
    ]
)
SNAPSHOT_SCHEMA = StructType(
    [
        StructField("id", IntegerType(), True),
        StructField("item_id", IntegerType(), True),
        StructField("employee_id", IntegerType(), True),
        StructField("store_id", IntegerType(), True),
        StructField("date_time", StringType(), True),
        StructField("quantity", IntegerType(), True),
    ]
)
EVENT_SCHEMA = StructType(
    [
        StructField("trans_id", StringType(), True),
        StructField("store_id", IntegerType(), True),
        StructField("date_time", StringType(), True),
        StructField("change_type_id", IntegerType(), True),
        StructField("items", ArrayType(_ITEM_LINE_SCHEMA), True),
        StructField("bopis_order_id", StringType(), True),
        StructField("channel", StringType(), True),
    ]
)
SNAPSHOT_SCHEMA = StructType(
    [
        StructField("id", IntegerType(), True),
        StructField("item_id", IntegerType(), True),
        StructField("employee_id", IntegerType(), True),
        StructField("store_id", IntegerType(), True),
        StructField("date_time", StringType(), True),
        StructField("quantity", IntegerType(), True),
    ]
)

# COMMAND ----------
# MAGIC %md
# MAGIC ## 2. Reference tables
# MAGIC
# MAGIC Static files materialized as tables, per the brief ("Static reference files may
# MAGIC be materialized views or tables"). Numeric columns are cast explicitly; CSV
# MAGIC reads otherwise default every column to string.


# COMMAND ----------
@dlt.table(name="store_ref", comment="Store reference: id, name, type, city.")
def store_ref():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .load(f"{REFERENCE_PATH}/store.csv")
        .withColumn("store_id", F.col("store_id").cast("int"))
    )


@dlt.table(
    name="item_ref", comment="Item reference: id, name, supplier, category, price, safety stock."
)
def item_ref():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .load(f"{REFERENCE_PATH}/item.csv")
        .withColumn("item_id", F.col("item_id").cast("int"))
        .withColumn("supplier_id", F.col("supplier_id").cast("int"))
        .withColumn("unit_price", F.col("unit_price").cast("double"))
        .withColumn("safety_stock_quantity", F.col("safety_stock_quantity").cast("int"))
    )


@dlt.table(
    name="change_type_ref",
    comment="Inventory change type reference: sale/restock/shrinkage/bopis and expected sign.",
)
def change_type_ref():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .load(f"{REFERENCE_PATH}/inventory_change_type.csv")
        .withColumn("change_type_id", F.col("change_type_id").cast("int"))
    )


@dlt.table(
    name="supplier_ref",
    comment="Supplier reference: id, name, lead time. Optional for the core solution.",
)
def supplier_ref():
    return (
        spark.read.format("csv")
        .option("header", "true")
        .load(f"{REFERENCE_PATH}/supplier.csv")
        .withColumn("supplier_id", F.col("supplier_id").cast("int"))
        .withColumn("lead_time_days", F.col("lead_time_days").cast("int"))
    )


# COMMAND ----------
# MAGIC %md
# MAGIC ## 3. Bronze: incremental Auto Loader ingestion
# MAGIC
# MAGIC Streaming tables preserve the raw nested event structure and the raw snapshot
# MAGIC row, plus source filename and ingestion timestamp. At least three explicit
# MAGIC expectations per the brief are declared here (five total, across both tables).


# COMMAND ----------
@dlt.table(
    name="bronze_inventory_change_raw",
    comment="Raw nested transaction events, Auto Loader incremental ingestion, source metadata preserved.",
)
@dlt.expect("has_trans_id", "trans_id IS NOT NULL")
@dlt.expect("has_store_id", "store_id IS NOT NULL")
@dlt.expect("has_date_time", "date_time IS NOT NULL")
def bronze_inventory_change_raw():
    raw = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .schema(EVENT_SCHEMA)
        .load(EVENTS_PATH)
        .withColumn("_source_file", F.col("_metadata.file_name"))
    )
    return to_bronze_events(raw)


@dlt.table(
    name="bronze_inventory_snapshot_raw",
    comment="Raw snapshot rows, Auto Loader incremental ingestion, source metadata preserved.",
)
@dlt.expect("has_id", "id IS NOT NULL")
@dlt.expect("has_item_id", "item_id IS NOT NULL")
def bronze_inventory_snapshot_raw():
    raw = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .schema(SNAPSHOT_SCHEMA)
        .load(SNAPSHOTS_PATH)
        .withColumn("_source_file", F.col("_metadata.file_name"))
    )
    return to_bronze_snapshots(raw)


# COMMAND ----------
# MAGIC %md
# MAGIC ## 4. Silver: explode, deduplicate, apply data-quality rules
# MAGIC
# MAGIC Calls the same `pipeline.py` functions `tests/test_pipeline.py` exercises
# MAGIC against the real verified fixture defects (duplicate `trans_id`, null required
# MAGIC fields, orphan references). Invalid records are quarantined with a reason code,
# MAGIC never silently dropped.


# COMMAND ----------
@dlt.table(
    name="silver_inventory_change",
    comment="Accepted, exploded, deduplicated item-level inventory changes. Grain: trans_id + item_id.",
)
def silver_inventory_change():
    exploded = explode_inventory_changes(dlt.read("bronze_inventory_change_raw"))
    accepted, _ = classify_inventory_change(
        exploded, dlt.read("store_ref"), dlt.read("item_ref"), dlt.read("change_type_ref")
    )
    return accepted


@dlt.table(
    name="silver_inventory_change_quarantine",
    comment="Reason-coded rejected inventory-change records.",
)
def silver_inventory_change_quarantine():
    exploded = explode_inventory_changes(dlt.read("bronze_inventory_change_raw"))
    _, quarantine = classify_inventory_change(
        exploded, dlt.read("store_ref"), dlt.read("item_ref"), dlt.read("change_type_ref")
    )
    return quarantine


@dlt.table(name="silver_inventory_snapshot", comment="Complete valid snapshot history.")
def silver_inventory_snapshot():
    accepted, _ = classify_inventory_snapshot(
        dlt.read("bronze_inventory_snapshot_raw"), dlt.read("store_ref"), dlt.read("item_ref")
    )
    return accepted


@dlt.table(
    name="silver_inventory_snapshot_quarantine", comment="Reason-coded rejected snapshot rows."
)
def silver_inventory_snapshot_quarantine():
    _, quarantine = classify_inventory_snapshot(
        dlt.read("bronze_inventory_snapshot_raw"), dlt.read("store_ref"), dlt.read("item_ref")
    )
    return quarantine


@dlt.table(
    name="silver_latest_inventory_snapshot",
    comment="Latest valid snapshot per store x item, selected strictly by date_time.",
)
def silver_latest_inventory_snapshot():
    return latest_inventory_snapshot(dlt.read("silver_inventory_snapshot"))


# COMMAND ----------
# MAGIC %md
# MAGIC ## 5. Gold: current inventory and safety-stock flag
# MAGIC
# MAGIC Left join from the latest snapshot so items with no subsequent transaction
# MAGIC remain visible; excludes only the online-store leg of a BOPIS pair, not all
# MAGIC online-store activity (see `REQUIREMENTS.md`, "Correction to a naive
# MAGIC 'exclude store_id=99' reading").


# COMMAND ----------
@dlt.table(
    name="gold_inventory_current",
    comment="Current inventory per store x item with safety-stock flag. See DATA_CONTRACTS.md.",
)
def gold_inventory_current():
    return to_gold_inventory_current(
        dlt.read("silver_latest_inventory_snapshot"),
        dlt.read("silver_inventory_change"),
        dlt.read("store_ref"),
        dlt.read("item_ref"),
    )
