# POS Retail — Medallion Analytics

Databricks Declarative Automation Bundle for the Bakehouse franchise POS retail pipeline.

## What's in here

```
databricks.yml              Bundle root — dev & prod targets
resources/
  pipeline.yml              Lakeflow Spark Declarative Pipeline (bronze → silver → gold)
  dashboard.yml             AI/BI Bakehouse Analytics dashboard
notebooks/
  pos_retail_analytics.sql  Analytics notebook (SQL source)
dashboards/
  pos_retail_bakehouse_analytics.lvdash.json  Dashboard definition (edit with VS Code / any editor)
transformations/
  bronze/                   Raw ingestion tables
  silver/                   Enriched transactions
  gold/                     Aggregated reporting tables
.github/workflows/
  pr-checks.yml             CI checks on every PR to main
  deploy.yml                Auto-deploy to prod on merge to main
.devcontainer/              Dev container for local editing
docker-compose.yml          Local CI runner (offline, no Databricks compute needed)
scripts/
  local_ci.sh               One-shot local validation script
  validate_project.py       Structural checks (YAML, SQL, file presence)
tests/
  test_project_structure.py pytest suite for offline PR gating
```

## CI/CD flow

```
feature-branch  →  PR to main  →  pr-checks.yml  →  merge  →  deploy.yml → bundle deploy -t prod
```

All merges to `main` require PR review (enforce via GitHub branch protection rules) and passing CI.

## Deploying manually

```bash
# Install Databricks CLI ≥ 0.232.0
pip install databricks-cli

# Authenticate
export DATABRICKS_HOST=https://dbc-94db375b-4c4c.cloud.databricks.com
export DATABRICKS_TOKEN=<your-pat>

# Validate
databricks bundle validate -t prod --var warehouse_id=<warehouse-id>

# Deploy
databricks bundle deploy -t prod --var warehouse_id=<warehouse-id>
```

## Editing the dashboard externally

Open `dashboards/pos_retail_bakehouse_analytics.lvdash.json` in any editor (VS Code, etc.).  
After editing, open a PR. On merge, `deploy.yml` redeploys it automatically.  
To pull live workspace edits back into the file:

```bash
databricks bundle generate dashboard --resource pos_retail_bakehouse_analytics --force
```

## Required GitHub secrets / variables

| Name | Where | Description |
|------|-------|-------------|
| `DATABRICKS_HOST` | Secret | Workspace URL |
| `DATABRICKS_TOKEN` | Secret | Service-principal or user PAT |
| `DATABRICKS_WAREHOUSE_ID` | Variable | SQL warehouse ID for dashboards |
