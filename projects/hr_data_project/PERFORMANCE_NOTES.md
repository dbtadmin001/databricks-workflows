# Performance Notes - HR Data Workforce Planning

MVP performance evidence status: COMPLETE

## Baseline Controls

- Runtime target: Databricks serverless environment version `2`, Python 3.11.
- Source snapshot: bounded assessment pack under `data/raw`; all files are registered
  once and reused.
- Bronze: parse each workbook/document once, persist source register and structured row
  staging.
- Silver: filter/project by sheet key before aggregating supply; no Python UDFs.
- Gold: Spark SQL CTEs over accepted Silver signals and aggregate supply; explicit
  office/skill grain.
- WAP: one compact audit query validates row count, null business keys, duplicate
  office/skill grain, and nonnegative scores.

## Explain Evidence

Local formatted explain and Databricks execution-plan evidence are `NOT_RUN` until the
first Spark compatibility/dev run. The implementation avoids Cartesian joins except the
bounded skill-reference match against document evidence, which is intentionally small.
