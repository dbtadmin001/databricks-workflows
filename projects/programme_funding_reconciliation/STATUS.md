# Project 8 Status

- Current milestone: M3 - PR and automated delivery
- Branch: `feature/project-08-timed-benchmark`
- Local implementation: complete
- Source status: executable immutable snapshot in `data/raw/`
- Dev catalog: `project_08_programme_funding_reconciliation_dev`
- Production catalog: `project_08_programme_funding_reconciliation_prod`
- Schema: `medallion`
- Landing volume: `raw_landing`
- SQL warehouse mode: approved existing serverless warehouse from `delivery.json`

## Completed

The existing Bronze, Silver/quarantine, Gold WAP, SQL validation, dashboard, Terraform,
and Bundle vertical slice is implemented. This benchmark is a bounded hardening pass.

## Implemented

- Terraform-managed dedicated catalog, schema, grants, and managed raw landing volume.
- Bronze notebook stages eight source files into the UC volume and writes eight native-format Delta tables.
- Silver notebook parses and casts all known formats, normalizes schema drift, removes exact duplicates, handles cross-batch corrections, builds SCD2, and writes accepted plus quarantine tables.
- Gold notebook builds the fact and programme summary, validates required types, allows additive columns, rejects dropped/type-changed columns, and uses run-scoped WAP staging.
- Read-only SQL warehouse validation task runs only after successful Gold publication.
- Plotly funding-intelligence notebook with executive KPIs, monthly funding flow,
  donor concentration, sector allocation, programme received-versus-committed,
  currency exposure, quarantine reasons, and latest WAP status.
- Dashboard refresh is the final end-to-end task and is also exposed as a separate
  on-demand Bundle job. Future deployment and execution ownership is declared for
  `data-automation-services`; the ownership change is not claimed as deployed yet.

## Verified Results

### Tests passed

- Bronze counts: donors 7; programme snapshots 5 + 5; contributions 152 + 65; grants 18; exchange rates 96; legacy summary 12.
- Reconciliation: `217 = 163 accepted + 43 quarantined + 5 exact duplicates + 6 corrected pairs`.
- Quarantine reasons: missing programme 14; missing donor 13; conflicting duplicate 2; missing amount 3; invalid date 12.
- Programme SCD2: 9 versions, including PRG103's sector change.
- Gold fact: 163 rows at one row per accepted contribution.
- Gold WAP: local audit passed; failed-audit path preserves current Gold by publishing only after every audit succeeds.
- Cached-runtime Docker gate: 9 passed in 82.08 seconds.
- The gate covers Bronze ingestion and idempotency, Silver reconciliation,
  quarantine comments, SCD2, explicit Delta merge publication, Spark SQL Gold,
  WAP hold/publish decisions, and additive-only schema drift.
- Ruff lint/format, TIMED_MVP validation, serverless Bundle/runtime contract,
  Terraform formatting, and offline Terraform validation passed.

## NOT_RUN

### Known limitations / NOT_RUN

- Databricks Terraform apply, Bundle deployment, job execution, and SQL warehouse query
  for this candidate commit.
- Production catalog bootstrap/import and production deployment.

## Remote Delivery Evidence

- Merge commit `ab9626b` triggered GitHub Actions run `29539272481`.
- Project Terraform apply and dev Bundle deployment completed successfully.
- The workflow did not execute the declared Bundle job, so no Bronze-Silver-Gold run
  was created. The delivery workflow correction enables approved job execution after
  deploy and records its log as deployment evidence.
- Merge commit `fb705be` deployed and ran job `723091816060912`; Bronze, Silver, and
  Gold WAP succeeded. SQL validation failed because stale scaffold SQL preceded the
  governed parameterized query. The bounded correction removes that SQL and adds the
  primary user to Terraform-managed catalog, schema, and volume grants.

Production actions remain behind the `main` to `production` promotion and environment
approval boundary.

## Blockers

- Human merge approval is required before automatic dev deployment.
- Shared anonymity/deployment hardening in PR #156 should be merged before this
  project PR so the post-merge workflow uses the latest generic-principal controls.

## Next action

Complete static PR checks, open the documented PR, then wait for human merge approval.
