# Test Plan — Chess.com Grandmaster and User Analytics

## Unit tests

- source configuration validation
- parsing and normalization
- deterministic deduplication
- null/type handling
- KPI calculations
- schema comparison and drift classification

## Chispa tests

- Bronze-to-Silver expected DataFrames
- duplicate-resolution logic
- window calculations
- SCD or history logic where applicable
- quarantine routing

## Mocked integration tests

- API pagination, retries and rate limits
- JDBC options without a real database
- file arrival and malformed input
- streaming micro-batches where applicable

## Remote Databricks tests

- package import
- Spark session and transformation smoke test
- Delta table write/read
- Bundle job execution
- optional materialized-view refresh

## Reconciliation

Validate:

- row count
- distinct business keys
- duplicate count
- null rates
- date/time bounds
- categorical distributions
- key aggregates
- unmatched records

## UAT

Show that unchanged API resources are skipped, changed archives are loaded once, and bad data cannot be published.
