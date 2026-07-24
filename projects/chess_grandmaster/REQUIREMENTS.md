# Requirements — Chess.com Grandmaster and User Analytics

## Functional requirements

1. Support deterministic local fixtures and at least one configurable live or development source.
2. Ingest source data into a Bronze Delta table with `_ingested_at`, `_source`, `_run_id`, and source-specific metadata.
3. Preserve malformed or unexpected content through a rescued-data or quarantine mechanism.
4. Transform data into explicit Silver contracts with deterministic deduplication and idempotent writes.
5. Produce the following Gold products:
   - `player_activity_daily`
   - `player_segment`
   - `opening_performance`
   - `rating_progression`
   - `grandmaster_game_summary`
6. Calculate and test the following analytical outcomes:
   - Daily active players
   - Games per user
   - Win/draw/loss rate
   - Rating change
   - Opening success
   - Power-user segmentation
7. Provide a Databricks Job or Pipeline definition deployable through a Bundle.
8. Provide optional Terraform resources for catalog, schemas, grants, and supporting infrastructure.
9. Provide automated unit, schema, reconciliation, and smoke tests.
10. Provide a reproducible UAT scenario.

## Non-functional requirements

- No secrets in source control or logs.
- Re-runs must be idempotent.
- All production-facing tables must use explicit three-part names.
- Silver and Gold must avoid `SELECT *`.
- All schema changes must be detected and classified.
- Source/API failure must produce actionable diagnostics.
- Optional components must not break the minimum stack when disabled.
- Pipeline logic must be reusable outside notebooks.

## Project-specific requirements

- ETag incremental ingestion
- Large-scale flattening
- WAP data quality pattern
- SCD Type 2 player profile history
- Chispa tests
- Optional dbt marts


## Verified-source requirements

- The default source and every optional provider must be declared in `DATA_SOURCES.md`.
- Live ingestion must be disabled in CI unless an explicitly approved integration environment is used.
- Undocumented or unapproved scraping endpoints must not be production dependencies.
- Every live adapter must have deterministic fixtures and contract tests.
- Source credentials must be referenced by environment/secret name only.
