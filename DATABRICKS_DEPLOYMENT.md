# Databricks Deployment Guide

## Prerequisites

1. **Databricks CLI installed**: `curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh`
2. **Authenticated**: Configure with `databricks configure` or set environment variables
3. **Warehouse ID**: Get from Databricks SQL → SQL Warehouses

## Environment Variables

Create a `.env` file (or export in your shell):

```bash
# Databricks
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-personal-access-token"
export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"

# AWS (if using S3 sources)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

## Deploy to Dev Environment

### Step 1: Navigate to Bundle Directory

```bash
cd platforms/databricks/bundles/
```

### Step 2: Validate Bundle

```bash
databricks bundle validate -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

**Expected output**: Validation successful

### Step 3: Deploy Bundle

```bash
databricks bundle deploy -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

**Expected output**:
- Creates/updates pipeline: `pos_retail_medallion_dev`
- Creates/updates dashboard: `[dev] POS Retail Bakehouse Analytics`
- Syncs transformation code to workspace

### Step 4: Verify Resources

```bash
# List deployed resources
databricks bundle summary -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

### Step 5: Run Pipeline

#### Option A: Via CLI

```bash
databricks pipelines start-update <pipeline-id> --full-refresh
```

#### Option B: Via UI

1. Navigate to **Delta Live Tables** (or **Workflows** → **Delta Live Tables**)
2. Find pipeline: `pos_retail_medallion_dev`
3. Click **Start** → **Full refresh**

### Step 6: Monitor Pipeline Execution

Watch the pipeline progress through:
- **Bronze**: Ingest raw transactions
- **Silver**: Enrich with dim tables, apply DQ rules
- **Gold**: Aggregate metrics (daily revenue, product performance, etc.)

**Expected duration**: 3-5 minutes for full refresh

### Step 7: View Dashboard

1. Navigate to **Dashboards**
2. Find: `[dev] POS Retail Bakehouse Analytics`
3. Click to open (should show 2 pages with 14+ widgets)

## Deploy to Production

Same steps, but use `-t prod`:

```bash
cd platforms/databricks/bundles/
databricks bundle validate -t prod --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
databricks bundle deploy -t prod --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

**Resources created**:
- Pipeline: `pos_retail_medallion_prod`
- Dashboard: `[prod] POS Retail Bakehouse Analytics`

## Troubleshooting

### Bundle Validation Fails

**Symptom**: `Error: unable to locate file or directory`

**Solution**: Check that `databricks.yml` paths reference the correct locations:
- Libraries: `../../../src/core/transformations/**`
- Notebook: `../../../projects/pos_retail/entry_points/pos_retail_analytics.sql`

### Pipeline Start Fails

**Symptom**: `Error: source data not found`

**Solution**: Check that:
1. S3 bucket exists and is accessible
2. AWS credentials are correct in environment config
3. Source paths in `projects/pos_retail/config/project.yml` are correct

### Dashboard Shows No Data

**Symptom**: Dashboard opens but widgets show "No data"

**Solution**:
1. Verify pipeline ran successfully (check Update History)
2. Check that Gold tables exist: `workspace.default.gold_*`
3. Refresh dashboard data

## CI/CD Deployment (GitHub Actions)

Push to `main` branch triggers automatic deployment to prod:

```bash
git push origin main
```

Monitor progress: **Actions** tab in GitHub

## Rollback

To roll back to a previous version:

```bash
git checkout <previous-commit-sha>
cd platforms/databricks/bundles/
databricks bundle deploy -t prod --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

## Next Steps

- [ ] Deploy to dev and verify end-to-end
- [ ] Add monitoring and alerting
- [ ] Set up scheduled pipeline runs
- [ ] Configure dashboard permissions
- [ ] Add data quality monitoring
