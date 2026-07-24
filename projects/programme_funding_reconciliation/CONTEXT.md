# Project 8 Context

## Delivery target

- Project: `08_programme_funding_reconciliation`
- Branch: `feature/project-08-timed-benchmark`
- Profile: `TIMED_MVP`
- Runtime: Python 3.11, Databricks serverless environment version 2
- Dev catalog/schema: `project_08_programme_funding_reconciliation_dev.medallion`
- SQL warehouse: approved existing warehouse declared in `delivery.json`
- Automation owner: `data-automation-services`

## Current vertical slice

- Eight immutable CSV, JSON, and Parquet files are executable under `data/raw`.
- Bronze preserves native source fields and ingestion lineage metadata.
- Silver parses known formats, resolves exact and cross-batch duplicates, builds
  programme SCD2, and separates accepted and quarantined contributions.
- Gold publishes a contribution fact and programme/fiscal-year summary through WAP.
- SQL validation and a paged Plotly data-trust dashboard are Bundle tasks.
- Project catalog, schema, grants, and raw landing volume are Terraform-managed.

## Verified baseline

- Source contribution rows: 217
- Accepted: 163; quarantined: 43; exact duplicates: 5; corrections collapsed: 6
- Reconciliation: `217 = 163 + 43 + 5 + 6`
- Programme SCD2 versions: 9
- Current cached-runtime Docker gate: 9 passed in 82.08 seconds
- Prior dev job: `723091816060912`; Bronze, Silver, and Gold passed before SQL correction

## Active benchmark

- Correct invalid serverless Bundle environment syntax.
- Keep Bronze unchanged and reuse the immutable snapshot.
- Make data-quality/schema outcomes non-crashing and auditable.
- Use Spark SQL CTEs for Gold and Delta `MERGE` for accepted Silver rows.
- Apply identity-neutral professional job display names.

## Continuation checkpoint

- Branch / head commit: `feature/project-08-timed-benchmark` / candidate not committed
- Files currently changed: bounded Project 8 implementation, tests, and evidence
- Last completed gate: cached-runtime affected-project Docker gate
- Last command and result: `python -m pytest -q`; 9 passed in 82.08 seconds
- Current data counts / reconciliation / WAP: `217 = 163 + 43 + 5 + 6`; prior WAP passed
- Pending approvals: human PR merge; production promotion remains separate
- Current failure: none in project runtime tests
- Exact next action: run static packaging checks and open the documented PR

## Evidence and next action

- Last accepted evidence: `evidence/test-results/project8-mvp-summary.md`
- Pending: static Bundle/Terraform checks, PR, approved merge, and automatic dev
  Terraform/Bundle/job evidence.
- Exact next action: finish static checks and open the implementation PR.
