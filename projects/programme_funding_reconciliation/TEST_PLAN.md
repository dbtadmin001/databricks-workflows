# Test Plan - Programme Funding & Parallel-Run Reconciliation

## Selection policy

Use `docs/TEST_SELECTION.md`. During implementation, run only the gate associated
with the changed phase. Do not rerun an unaffected upstream stage. Static source
files and saved Bronze/Silver snapshots are the test inputs; no live API exists.

## Gate 1 - Bronze

- Assert the eight source files exist and native reader counts are
  `7, 5, 5, 152, 65, 18, 96, 12`.
- Assert Bronze preserves native JSON nesting and Parquet numeric types.
- Assert every Bronze output has `_ingest_ts`, `_source_file`, `_run_id`.
- Assert an identical rerun does not duplicate Bronze rows.

Validation level: Level 1 while coding, Level 2 only if the reader/Bundle component
contract changes. No Silver or Gold execution.

## Gate 2 - Silver

- Assert exact duplicate removal is 5 and cross-batch correction collapse is 6.
- Assert accepted 163, quarantined 43, and the full reconciliation invariant.
- Assert quarantine counts: missing programme 14, missing donor 13, conflicting
  duplicate 2, missing amount 3, invalid date 12.
- Assert both CTB9021 rows are quarantined and none is accepted.
- Assert all six correction IDs occur once with Q3 values.
- Assert all observed date/fiscal-year formats parse as contracted and invalid/null
  values quarantine without ANSI exceptions.
- Assert SCD2 has nine rows with correct effective boundaries.
- Assert a rerun produces identical keys and counts.

Validation level: targeted Level 1 nodes and one Silver Level 2 component pass from
saved Bronze inputs. Gold is not run unless the Silver published contract changes.

## Gate 3 - Gold and WAP

- Assert staged fact grain is one row per contribution and count is 163.
- Assert staged summary grain is unique `(programme_id, fiscal_year_norm)`.
- Assert WAP rejects empty output, schema drift, null required keys, duplicate grain,
  count/reconciliation failure and assignment-rule failure.
- Assert failed WAP leaves the current Gold table unchanged.
- Assert passing WAP publishes with an explicit column list and records its audit.
- Run reconciliation SQL and record the actual variance count and causes; investigate
  rather than force the brief's claimed count of four.

Validation level: exactly one Level 2 Gold/WAP component pass from saved Silver
input. Bundle validation is separate and does not authorize deployment or execution.

## PR and release evidence

PR evidence lists commands, exit codes, counts, catalog/schema/warehouse resolution,
WAP status, idempotency result and every `NOT_RUN` item. GitHub CI is Level 3 at PR
readiness. Production deployment, smoke and UAT are Level 4 and remain outside this
MVP unless separately approved.
