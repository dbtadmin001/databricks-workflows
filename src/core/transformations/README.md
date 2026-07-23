# Core Transformations

**Platform-agnostic business logic for the POS Retail medallion pipeline.**

This directory contains pure PySpark/SQL transformation code that runs identically across:
- Databricks (Lakeflow Spark Declarative Pipelines)
- Microsoft Fabric (Notebooks + Lakehouses)
- AWS (Glue/EMR + S3)

## Structure

```
bronze/    Raw ingestion with audit columns (_ingested_at, _source)
silver/    Cleaned, enriched, DQ-validated business entities
gold/      Business-ready aggregations and materialized views
```

## Design Principles

1. **No platform-specific imports** — Use only `pyspark.sql`, `pyspark.sql.functions`, standard PySpark APIs
2. **Declarative** — Use `@dp.table` / `@dp.materialized_view` decorators for Databricks; adapters exist for other platforms
3. **Testable** — All transforms can be unit-tested with local Spark (no Databricks workspace required)
4. **Idempotent** — Safe to re-run; produces identical results given identical inputs

## Dependencies

- PySpark 3.3+
- No external libraries required for core logic
- Platform adapters handle orchestration, scheduling, and storage

## Testing

See `tests/unit/` for unit tests of these transforms.
