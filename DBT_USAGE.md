# dbt Usage & Architecture Boundary

## Overview

This repository uses **dbt** (data build tool) for a **narrow, specific purpose**: testing, documenting, and tracking lineage for Gold layer tables.

**Key principle**: dbt is a **testing and documentation layer**, not a transformation engine.

## What dbt Does

### ✅ Testing
* **Schema tests** — Validate data contracts (not_null, unique, accepted_values, relationships)
* **Custom tests** — Business logic assertions (revenue consistency, no negative values, etc.)
* **Automated validation** — Runs in CI after each deployment

### ✅ Documentation
* **Column descriptions** — Documents Gold table schemas
* **Test coverage** — Shows which tests apply to which columns
* **Lineage visualization** — DAG of sources and exposures

### ✅ Sources & Exposures
* **Sources** — Formally declares Gold tables as dbt sources
* **Exposures** — (Future) Documents dashboards/apps consuming Gold tables

## What dbt Does NOT Do

### ❌ Data Transformation
**All** Bronze, Silver, and Gold transformations live in `src/core/transformations/` as **PySpark code**.

**Rationale**: Transformation logic must be platform-agnostic and produce byte-identical results across Databricks, Fabric, and AWS. dbt's SQL dialect and adapter behavior differ across platforms (dbt-databricks, dbt-fabric, dbt-athena/dbt-spark), which would create cross-platform parity risks.

### ❌ Table Materialization
dbt does NOT create Gold tables. They are materialized by the **Lakeflow Spark Declarative Pipeline** defined in `src/core/transformations/gold/`.

### ❌ SCD2 Logic
SCD2 (Slowly Changing Dimension Type 2) logic, if needed, should be implemented in `src/core/` PySpark, not dbt snapshots.

**Rationale**: Same as transformation — must be portable and parity-testable across platforms.

### ❌ Bronze/Silver Testing
dbt is scoped to **Gold layer only**. Bronze and Silver layer testing remains in `src/core/` pytest tests.

## Architecture Boundary

```
┌─────────────────────────────────────────────────────────────┐
│ src/core/transformations/  (PySpark — Platform-Agnostic)    │
│                                                              │
│  Bronze Layer                                                │
│    ├── Ingestion from sources                               │
│    └── Audit columns                                         │
│                                                              │
│  Silver Layer                                                │
│    ├── Enrichment (joins)                                   │
│    ├── Data quality rules (@dp.expect)                       │
│    └── Current-state dimensions                             │
│                                                              │
│  Gold Layer                                                  │
│    ├── Aggregations                                          │
│    ├── Window functions                                      │
│    └── Business-ready tables                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
              Databricks Pipeline Runs
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ workspace.default.gold_*  (Materialized Tables)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ platforms/databricks/dbt/  (dbt — Platform-Specific)        │
│                                                              │
│  Sources                                                     │
│    └── Define gold_* as dbt sources                         │
│                                                              │
│  Tests                                                       │
│    ├── Schema tests (not_null, unique, etc.)                │
│    └── Custom tests (business logic SQL assertions)         │
│                                                              │
│  Documentation                                               │
│    └── dbt docs generate                                    │
└─────────────────────────────────────────────────────────────┘
```

## Platform Scope

### Databricks
* **Status**: ✅ Implemented
* **Adapter**: `dbt-databricks`
* **Compute**: SQL Warehouse (serverless)
* **Location**: `platforms/databricks/dbt/`

### Microsoft Fabric
* **Status**: ❌ Not implemented (deferred)
* **Future**: When Fabric adapter is fleshed out, add `platforms/fabric/dbt/` with `dbt-fabric`

### AWS
* **Status**: ❌ Not implemented (deferred)
* **Future**: When AWS adapter is fleshed out, add `platforms/aws/dbt/` with `dbt-athena` or `dbt-spark`

## When to Use dbt vs. PySpark

| Task | Tool | Location | Rationale |
|------|------|----------|-----------|
| Ingest raw data | PySpark | `src/core/transformations/bronze/` | Must be portable |
| Join tables | PySpark | `src/core/transformations/silver/` | Must be portable |
| Apply DQ rules | PySpark | `src/core/transformations/silver/` | Must be portable |
| Aggregate metrics | PySpark | `src/core/transformations/gold/` | Must be portable |
| SCD2 logic | PySpark | `src/core/transformations/silver/` (if added) | Must be portable |
| Test Gold schema | dbt | `platforms/databricks/dbt/` | Platform-specific is OK |
| Test business logic | dbt | `platforms/databricks/dbt/tests/` | Platform-specific is OK |
| Document tables | dbt | `platforms/databricks/dbt/` | Platform-specific is OK |

## Decision Tree

**I need to add new transformation logic. Should I use dbt or PySpark?**

```
Is the logic platform-agnostic (Bronze/Silver/Gold transforms)?
  ├─ YES → Use PySpark in src/core/transformations/
  └─ NO  → Is it testing/documentation of existing Gold tables?
            ├─ YES → Use dbt in platforms/databricks/dbt/
            └─ NO  → Re-evaluate; may not belong in dbt or src/core
```

## Example: When NOT to Use dbt

### ❌ Bad: Adding Gold Aggregation in dbt

```sql
-- platforms/databricks/dbt/models/gold/gold_new_metric.sql
-- ❌ DON'T DO THIS

select
  date,
  product,
  sum(revenue) as total_revenue
from {{ source('silver', 'silver_transactions') }}
group by date, product
```

**Problem**: This creates Gold logic in dbt, which is Databricks-specific SQL. The AWS and Fabric adapters won't have this logic, breaking cross-platform parity.

### ✅ Good: Adding Gold Aggregation in PySpark

```python
# src/core/transformations/gold/gold_new_metric.py
# ✅ DO THIS

@dp.materialized_view(
    name="gold_new_metric",
    comment="New metric aggregation"
)
def gold_new_metric():
    return (
        spark.read.table("silver_transactions")
        .groupBy("date", "product")
        .agg(F.sum("revenue").alias("total_revenue"))
    )
```

Then add dbt tests for `gold_new_metric` in `platforms/databricks/dbt/models/sources/sources.yml`.

**Why**: PySpark logic is portable to all platforms. dbt tests are platform-specific but that's acceptable for validation.

## CI Integration

dbt tests run automatically in `deploy-databricks.yml` after pipeline deployment:

1. Pipeline deploys → Gold tables materialized
2. dbt tests run → Validate Gold tables
3. Deployment summary shows test results

Tests are **non-blocking** (`continue-on-error: true`) to avoid blocking deployments on test failures, but failures are surfaced in CI output.

## Adding New Tests

### Schema Test (in sources.yml)

```yaml
sources:
  - name: gold
    tables:
      - name: gold_my_new_table
        columns:
          - name: my_column
            tests:
              - not_null
              - unique
```

### Custom Test (in tests/)

```sql
-- tests/test_my_business_rule.sql
-- Should return 0 rows if passing

select *
from {{ source('gold', 'gold_my_table') }}
where [condition that should never be true]
```

## Questions?

* **dbt project setup**: See `platforms/databricks/dbt/README.md`
* **Architecture overview**: See `MIGRATION.md`
* **Deployment process**: See `DATABRICKS_DEPLOYMENT.md`
* **Adding new projects**: See `ADDING_PROJECTS.md`
