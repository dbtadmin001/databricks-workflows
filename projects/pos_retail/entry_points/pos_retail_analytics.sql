-- Databricks notebook source
-- MAGIC %md
-- MAGIC # POS Retail — Analytics
-- MAGIC Bakehouse franchise POS analytics over the `workspace.default` gold and silver layers.

-- COMMAND ----------
-- MAGIC %sql
SELECT
  COUNT(DISTINCT transactionID) AS total_transactions,
  COUNT(DISTINCT customerID) AS unique_customers,
  COUNT(DISTINCT franchiseID) AS active_franchises,
  ROUND(SUM(totalPrice), 2) AS total_revenue,
  ROUND(AVG(totalPrice), 2) AS avg_basket_size,
  ROUND(SUM(totalPrice) / COUNT(DISTINCT DATE(dateTime)), 2) AS avg_daily_revenue
FROM workspace.default.silver_transactions_enriched;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  transaction_date,
  SUM(total_revenue) AS daily_revenue,
  SUM(total_units_sold) AS daily_units,
  SUM(transaction_count) AS daily_transactions
FROM workspace.default.gold_daily_revenue
GROUP BY transaction_date
ORDER BY transaction_date;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  product,
  total_revenue,
  total_units_sold,
  avg_unit_price,
  avg_transaction_value,
  unique_customers,
  ROUND(revenue_share * 100, 2) AS revenue_share_pct
FROM workspace.default.gold_product_performance
ORDER BY total_revenue DESC;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  revenue_rank,
  franchise_name,
  city,
  country,
  store_size,
  total_revenue,
  transaction_count,
  unique_customers,
  ROUND(avg_basket_size, 2) AS avg_basket_size
FROM workspace.default.gold_franchise_ranking
ORDER BY revenue_rank
LIMIT 10;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  country,
  COUNT(DISTINCT franchiseID) AS franchise_count,
  SUM(total_revenue) AS total_revenue,
  SUM(transaction_count) AS total_transactions,
  ROUND(AVG(avg_basket_size), 2) AS avg_basket_size
FROM workspace.default.gold_franchise_ranking
GROUP BY country
ORDER BY total_revenue DESC;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  store_size,
  COUNT(DISTINCT franchiseID) AS store_count,
  SUM(total_revenue) AS total_revenue,
  SUM(transaction_count) AS total_transactions,
  ROUND(AVG(avg_basket_size), 2) AS avg_basket_size
FROM workspace.default.gold_franchise_ranking
GROUP BY store_size
ORDER BY total_revenue DESC;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  spend_tier,
  COUNT(customerID) AS customer_count,
  ROUND(AVG(total_spend), 2) AS avg_spend,
  ROUND(AVG(visit_count), 1) AS avg_visits,
  ROUND(AVG(active_days), 1) AS avg_active_days,
  ROUND(AVG(stores_visited), 1) AS avg_stores_visited
FROM workspace.default.gold_customer_segments
GROUP BY spend_tier
ORDER BY avg_spend DESC;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  gender,
  favourite_product,
  COUNT(*) AS customer_count,
  ROUND(AVG(total_spend), 2) AS avg_spend
FROM workspace.default.gold_customer_segments
GROUP BY gender, favourite_product
ORDER BY gender, customer_count DESC;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  transaction_hour,
  COUNT(transactionID) AS transaction_count,
  ROUND(SUM(totalPrice), 2) AS total_revenue,
  ROUND(AVG(totalPrice), 2) AS avg_basket_size
FROM workspace.default.silver_transactions_enriched
GROUP BY transaction_hour
ORDER BY transaction_hour;

-- COMMAND ----------
-- MAGIC %sql
SELECT
  paymentMethod,
  COUNT(transactionID) AS transaction_count,
  ROUND(SUM(totalPrice), 2) AS total_revenue,
  ROUND(AVG(totalPrice), 2) AS avg_basket_size,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_transactions
FROM workspace.default.silver_transactions_enriched
GROUP BY paymentMethod
ORDER BY transaction_count DESC;
