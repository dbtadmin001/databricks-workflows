-- PURPOSE
-- Confirm that the published Gold inventory table is queryable through the approved
-- SQL warehouse and exposes the exact analytical contract expected by the dashboard.
--
-- INPUTS
-- :catalog and :schema are named SQL-task parameters supplied by the Bundle. IDENTIFIER
-- resolves the dedicated environment-specific Unity Catalog table without hardcoding it.
--
-- PROCESSING
-- Project only the governed Gold columns. This is a read-only serving validation; row,
-- key, duplicate, and reference checks already ran against Bronze/Silver via the schema
-- and quality contracts during the Lakeflow pipeline update and the post-pipeline audit,
-- before this task was allowed to execute.
--
-- KEY OPTIMIZATIONS
-- Column projection limits data read and transferred to the SQL result. No join, Python
-- UDF, or unnecessary intermediate materialization is used. ORDER BY is retained only to
-- produce a deterministic, replenishment-risk-first presentation ranking.
--
-- EXPECTED OUTPUTS
-- One row per published store x item, ordered so items below safety stock surface first.
-- Successful query execution proves warehouse connectivity, catalog resolution, table
-- publication, and the expected output columns; it does not replace the pipeline's own
-- schema/quality audit.

WITH published_gold AS (
  SELECT
    store_id,
    store_name,
    store_type,
    item_id,
    item_name,
    category,
    snapshot_quantity,
    snapshot_date_time,
    inventory_change_quantity,
    current_inventory_quantity,
    safety_stock_quantity,
    below_safety_stock,
    last_inventory_timestamp
  FROM IDENTIFIER(:catalog || '.' || :schema || '.gold_inventory_current')
)
SELECT
  store_id,
  store_name,
  store_type,
  item_id,
  item_name,
  category,
  snapshot_quantity,
  snapshot_date_time,
  inventory_change_quantity,
  current_inventory_quantity,
  safety_stock_quantity,
  below_safety_stock,
  last_inventory_timestamp
FROM published_gold
ORDER BY below_safety_stock DESC, current_inventory_quantity ASC;
