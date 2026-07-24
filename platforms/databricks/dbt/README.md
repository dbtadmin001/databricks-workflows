# dbt Project — Gold Layer Testing & Documentation

## Purpose

This dbt project provides **testing, documentation, and lineage** for Gold layer tables produced by the PySpark Lakeflow pipeline.

**IMPORTANT**: This project does NOT create or transform data. It only:
* **Tests** Gold tables (schema tests + custom business logic tests)
* **Documents** Gold tables (via dbt docs)
* **Tracks lineage** (via dbt's DAG visualization)

## What dbt Does

✅ **Schema tests** — Validate columns (not_null, unique, accepted_values, relationships)  
✅ **Custom tests** — Business logic assertions (revenue consistency, no negatives, etc.)  
✅ **Documentation** — Generate browsable docs with column descriptions and lineage  
✅ **Sources** — Define Gold tables as dbt sources (not models)  

## What dbt Does NOT Do

❌ **Transform data** — Bronze/Silver/Gold transformations live in `src/core/transformations/` (PySpark)  
❌ **Create tables** — Gold tables are materialized by the Lakeflow pipeline  
❌ **Replace PySpark** — dbt is a testing/docs layer on top of PySpark-created tables  

## Directory Structure

```
platforms/databricks/dbt/
├── dbt_project.yml           # Project configuration
├── profiles.yml.example      # Connection profile template
├── packages.yml              # dbt-utils dependency
├── models/
│   └── sources/
│       └── sources.yml       # Gold table definitions + schema tests
├── tests/                    # Custom singular tests (SQL assertions)
│   ├── test_revenue_consistency_across_gold_tables.sql
│   ├── test_no_negative_revenue_amounts.sql
│   ├── test_revenue_share_sums_to_one.sql
│   └── test_spend_tier_thresholds_match_amounts.sql
├── macros/                   # Custom Jinja macros (if needed)
├── seeds/                    # Static CSV data (if needed)
└── snapshots/                # SCD2 snapshots (currently unused)
```

## Setup

### 1. Install dbt-databricks

```bash
pip install dbt-databricks
```

### 2. Configure Profile

Copy `profiles.yml.example` to `~/.dbt/profiles.yml` and set environment variables:

```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/<warehouse-id>"
export DATABRICKS_TOKEN="dapi..."
```

Get `DATABRICKS_HTTP_PATH` from:  
Databricks UI → SQL Warehouses → [your warehouse] → Connection Details → HTTP Path

### 3. Install Dependencies

```bash
cd platforms/databricks/dbt
dbt deps
```

This installs `dbt_utils` package.

## Usage

### Run Tests

```bash
cd platforms/databricks/dbt

# Test all Gold tables
dbt test

# Test specific source
dbt test --select source:gold

# Test specific table
dbt test --select source:gold.gold_daily_revenue
```

### Generate Documentation

```bash
# Generate docs
dbt docs generate

# Serve docs locally
dbt docs serve
```

Navigate to `http://localhost:8080` to browse the documentation.

### Debug Connection

```bash
dbt debug
```

This validates your profile configuration and connection to Databricks.

## Tests Included

### Schema Tests (in `sources.yml`)

For each Gold table:
* **not_null** — Key columns must not be null
* **unique** — Primary keys must be unique
* **accepted_values** — Categorical columns have valid values
* **expression_is_true** — Numeric constraints (e.g., revenue >= 0, lat/lon bounds)

### Custom Tests (in `tests/`)

1. **Revenue consistency** — Total revenue matches across gold_daily_revenue and gold_product_performance
2. **No negative amounts** — All revenue/spend columns are non-negative
3. **Revenue share sums to 1.0** — Product revenue shares sum to 100% (within rounding tolerance)
4. **Spend tier consistency** — Customer spend_tier matches thresholds (High >= 500, Medium >= 200, Low < 200)

## CI Integration

dbt tests run automatically in CI after the Databricks pipeline completes.

See `.github/workflows/deploy-databricks.yml` for the integration.

## Adding New Tests

### Schema Test

Add to `models/sources/sources.yml` under the relevant column:

```yaml
columns:
  - name: my_column
    tests:
      - not_null
      - unique
```

### Custom Test

Create a new `.sql` file in `tests/`:

```sql
-- tests/test_my_business_rule.sql
-- Test should return 0 rows if passing

select *
from {{ source('gold', 'my_table') }}
where [condition that should never be true]
```

## Relationship to PySpark Pipeline

```
┌─────────────────────────────────────┐
│ src/core/transformations/           │
│   ├── bronze/                       │
│   ├── silver/                       │
│   └── gold/  ← Creates Gold tables  │
└─────────────────────────────────────┘
             ↓
   Databricks Lakeflow Pipeline
             ↓
┌─────────────────────────────────────┐
│ workspace.default.gold_*            │
│   (Gold tables exist)               │
└─────────────────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│ platforms/databricks/dbt/           │
│   Tests + Documents Gold tables →   │
└─────────────────────────────────────┘
```

**Key principle**: PySpark creates the tables, dbt validates them.

## Questions?

See `MIGRATION.md` for architecture details or `DATABRICKS_DEPLOYMENT.md` for deployment process.
