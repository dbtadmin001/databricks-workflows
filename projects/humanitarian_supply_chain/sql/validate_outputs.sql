SELECT category, record_count, metric_total, metric_average, latest_event_ts
FROM ${var.catalog}.${var.schema}.project_07_unicef_supply_chain_gold_metrics
ORDER BY metric_total DESC;
