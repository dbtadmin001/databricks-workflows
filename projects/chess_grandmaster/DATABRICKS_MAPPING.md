# Databricks Mapping — Chess.com Grandmaster and User Analytics

## Recommended platform mapping

| Concern | Databricks implementation |
|---|---|
| Source ingestion | PySpark adapters, Auto Loader, JDBC, or Kafka/Event Hubs |
| Bronze | Delta managed tables with raw payload and audit metadata |
| Silver | PySpark transformations, explicit schema contracts, Delta MERGE |
| Gold | Spark SQL tables/materialized views; optional dbt |
| Orchestration | Lakeflow Jobs / Declarative Automation Bundles |
| Testing | Pytest, Chispa, mocked source tests, remote smoke tests |
| Governance | Unity Catalog catalogs, schemas, grants, tags and masks where supported |
| Infrastructure | Terraform, separated from application deployment |
| Observability | job run output, quality tables, event logs, reconciliation tables |
| BI | Databricks SQL dashboard or optional external dashboard |

## Suggested medallion objects

- Catalog: `${catalog}`
- Schemas: `bronze`, `silver`, `gold`, `quarantine`, `governance`
- Bronze source table: `${catalog}.bronze.chess_grandmaster_raw`
- Silver core table: `${catalog}.silver.chess_grandmaster_clean`
- Gold products:
  - `${catalog}.gold.player_activity_daily`
  - `${catalog}.gold.player_segment`
  - `${catalog}.gold.opening_performance`
  - `${catalog}.gold.rating_progression`
  - `${catalog}.gold.grandmaster_game_summary`

## Optional components

- dbt for Gold dependency management and tests
- MLflow for analytical/model workflows
- Docker for external producers or extractors
- Airflow only when orchestration spans systems outside Databricks
