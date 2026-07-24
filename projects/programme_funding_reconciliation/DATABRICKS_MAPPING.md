# Databricks Mapping - Programme Funding & Parallel-Run Reconciliation

## Approved development environment

- Profile: `db-blueprints-dev`.
- Catalog: `project_08_programme_funding_reconciliation_dev`.
- Schema: `medallion`.
- SQL warehouse mode: `existing`.
- SQL warehouse ID: `cc91c315736f92f8`.
- Python: 3.11.

The single approved schema uses physical layer prefixes. Logical
`bronze.contributions_csv`, for example, maps to
`project_08_programme_funding_reconciliation_dev.medallion.bronze_contributions_csv`.
No workload may fall back to `workspace`, `main`, or `default`.

## Component mapping

| Requirement | Databricks implementation |
|---|---|
| Static CSV/JSON/Parquet ingestion | PySpark notebook task calling importable Bronze functions and format-specific readers |
| Raw fidelity | Delta `bronze_*` tables with source columns plus `_ingest_ts`, `_source_file`, `_run_id` |
| Schema drift and data quality | PySpark Silver module using explicit schema alignment, ANSI-safe parsing, typed columns, exact/conflicting duplicate classification, quarantine and FX enrichment |
| Cross-batch corrections | Delta `MERGE INTO` keyed by `contribution_id`, with Q3 as the later source |
| Programme history | `silver_dim_programme` SCD2 table and point-in-time fact join |
| Gold products | Explicit Spark SQL creating staged Gold fact and programme/fiscal-year summary outputs |
| WAP | Run-scoped Delta staging tables, audit record, explicit-column atomic replacement, and safe staging cleanup |
| Reconciliation | SQL warehouse task using the declared warehouse ID and explicit three-part names |
| Deployment | Databricks Asset Bundle notebook tasks; validation, deployment and execution remain separate controls |
| Catalog/schema/grants | Project Terraform module; Free Edition default-storage bootstrap followed by immediate import when needed |

## Governed object names

Bronze: `bronze_donors`, `bronze_programmes_q1`, `bronze_programmes_q2`,
`bronze_contributions_csv`, `bronze_contributions_json`, `bronze_grants`,
`bronze_exchange_rates`, and `bronze_legacy_oracle_summary`.

Silver: `silver_donors`, `silver_dim_programme`, `silver_exchange_rates`,
`silver_grants`, `silver_contributions_accepted`, and
`silver_contributions_quarantine`.

Gold: `gold_fact_contributions`, `gold_programme_fy_summary`, and
`gold_publication_audit`. Staging names include a sanitized run ID and are not
consumer-facing contracts.

## Infrastructure fallback boundary

Terraform declaration and state synchronization are mandatory. A Terraform apply or
import defect may be recorded as nonblocking for the timed MVP only when read-only
preflight proves the dedicated catalog and schema already exist and the deployment
identity can use them. Missing catalog/schema access blocks Bundle execution; ad hoc
catalog/schema/grant SQL from notebooks is prohibited.

## Branch mapping

`main` is the development integration branch and must trigger automatic development
Terraform/Bundle delivery after PR approval. `production` is protected and triggers
production delivery only after an approved promotion PR from `main`. The shared
workflow correction is a separate template-governance change and must land before a
Project 8 merge can be relied on for automatic development deployment.
