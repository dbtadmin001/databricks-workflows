# Implementation Plan - Programme Funding & Parallel-Run Reconciliation

## TIMED_MVP override

The human approved a project-specific 30-minute implementation target. This is a
tighter override of the general 60-minute profile and does not relax catalog
isolation, source fidelity, quarantine, reconciliation, idempotency, secrets controls,
or Silver-to-Gold WAP.

Remote GitHub runner and Databricks queue time are external latency: the reviewed PR
must be submitted within the window, but deployment completion cannot truthfully be
guaranteed within 30 wall-clock minutes. No manual deployment is permitted.

## Phase 1 - Preflight, governance and Bronze (0-7 minutes)

- Confirm all eight local source files are readable with their native readers.
- Resolve the approved catalog, schema and existing SQL warehouse.
- Keep catalog/schema/grants declarative in the project Terraform module.
- Implement notebook-first, idempotent Bronze ingestion with audit metadata.

Gate 1: static source count/profile check; targeted Bronze test; resolved catalog,
schema and warehouse evidence. Terraform drift is nonblocking only under the
read-only existence/access exception in `DATABRICKS_MAPPING.md`.

## Phase 2 - Silver, SCD2 and quarantine (7-20 minutes)

- Align CSV and JSON contribution schemas without losing additive fields.
- Apply explicit casts, all observed date formats, fiscal-year normalization and
  status normalization using ANSI-safe expressions.
- Separate exact duplicates, conflicting duplicates and cross-batch corrections.
- Build donors, grants, FX and programme SCD2 outputs; apply point-in-time-ready keys.
- Publish accepted and quarantined contributions idempotently.

Gate 2: targeted Silver component checks prove `163 + 43 + 5 + 6 = 217`, the reason
breakdown, six later-batch corrections, eight SCD2 rows and an idempotent rerun.

## Phase 3 - Gold, WAP and PR evidence (20-30 minutes)

- Build Gold fact and programme/fiscal-year metrics with explicit Spark SQL columns.
- Stage each Gold target under a run-scoped name.
- Audit schema, non-empty output, keys, nulls, duplicate grain, row counts,
  reconciliation and assignment-specific rules.
- Atomically publish only after every audit passes; preserve current Gold on failure.
- Run one Level 2 reconciliation/WAP pass and Bundle validation without deployment.
- Open the documented PR with actual results and truthful `NOT_RUN` items.

Gate 3: fact count 163, no WAP rejection, reconciliation variance evidence, unchanged
Gold on a failing WAP fixture, Bundle validation result, and PR evidence.

## Task boundaries

Implementation is routed as three bounded tasks, one phase at a time. Terra owns the
Spark/Bundle/Terraform integration tasks; Sol performs one independent MVP review.
The shared branch-workflow correction is `_template` scope and cannot be mixed into a
Project 8 implementation PR.

## Stop conditions

Stop rather than broaden scope when a phase exceeds its budget, the same failure
recurs after one correction, catalog access is absent, source counts differ from the
contract, reconciliation cannot be explained, WAP fails, or deployment would require
a manual action. Record incomplete work and preserve the last passing layer.
