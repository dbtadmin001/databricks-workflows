# Databricks Platform Adapter

**Deploy POS Retail project to Databricks using Declarative Automation Bundles**

## Structure

```
bundles/       Databricks Asset Bundle configurations (databricks.yml)
resources/     Pipeline and dashboard resource definitions
dashboards/    Lakeview dashboard JSON exports
```

## Prerequisites

- Databricks CLI ≥ 0.232.0
- Workspace with Unity Catalog enabled
- SQL warehouse for dashboard queries

## Deployment

From the bundles directory, authenticate and deploy:

```bash
cd platforms/databricks/bundles
export DATABRICKS_HOST=<your-workspace-url>
export DATABRICKS_TOKEN=<your-token>
```

Then run deployment commands for dev or prod targets.

## What Gets Deployed

1. **Pipeline**: Lakeflow Spark Declarative Pipeline
   - Bronze ingestion tables (4)
   - Silver enriched tables (2)
   - Gold aggregation views (4)
   - Serverless compute with Photon enabled

2. **Dashboard**: Lakeview dashboard (2 pages, 14+ widgets)
   - Embedded credentials for published viewers
   - CAN_VIEW permissions for all workspace users

3. **Notebooks**: SQL analytics notebook in entry_points/

## Customization

Edit `databricks.yml` variables to change target catalog/schema, or override at deploy time.

## References

- Business logic: `src/core/transformations/`
- Project config: `projects/pos_retail/`
- Databricks Asset Bundles documentation online
