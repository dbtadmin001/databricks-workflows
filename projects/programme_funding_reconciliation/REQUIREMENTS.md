# Requirements - Programme Funding & Parallel-Run Reconciliation

## Scenario

UNICEF's Programme Funding office tracks donor contributions to country programmes. The Q1+Q2 2025 batch was extracted from the legacy Oracle finance system as CSV. From Q3 onward, contributions come from a newer grants-management system exporting JSON with a **different and evolving schema**. Grant metadata is separate, semi-structured JSON. Monthly FX rates are a Parquet lookup table. Build a lakehouse that lands all of it, reconciles it against the legacy Oracle summary, and proves the pipeline handles the schema drift correctly. Source brief: `projects/8. Project8/Practice_Assessment_2_Instructions_v2.docx` (external reference, outside project isolation); raw files copied verbatim into this project at `data/raw/*` as the canonical source snapshot.

This is a materially harder assessment than `projects/07_unicef_supply_chain`: multi-format ingestion, schema evolution across batches, SCD2 with a point-in-time join, cross-batch upsert corrections, nested/optional JSON, and a currency-conversion join — not just clean/quarantine/aggregate.

## Functional requirements

1. **Multi-format Bronze ingestion**: load `CONTRIBUTIONS.csv` (CSV), `CONTRIBUTIONS_2025Q3.json` (JSON), `GRANTS.json` (nested JSON), and `EXCHANGE_RATES.parquet` (Parquet) into Bronze Delta tables using the format-appropriate Spark reader, preserving raw fidelity plus ingestion metadata (`_ingest_ts`, `_source_file`, `_run_id`).
2. **Schema evolution**: combine the Q1/Q2 CSV batch (columns: `CONTRIBUTION_ID, DONOR_ID, PROGRAMME_ID, FISCAL_YEAR, CONTRIBUTION_DATE, CURRENCY_ORIGINAL, AMOUNT_ORIGINAL, EXCHANGE_RATE_TO_USD, AMOUNT_USD, STATUS`) and the Q3 JSON batch (columns: `contribution_id, donor_id, programme_id, grant_id, fiscal_year, contribution_date, currency_original, amount_original, payment_method, status` — note lowercase naming, `grant_id`/`payment_method` added, `exchange_rate_to_usd`/`amount_usd` absent) into one Silver `contributions` table using Delta schema evolution (`mergeSchema` or `MERGE INTO` with `spark.databricks.delta.schema.autoMerge.enabled`), not manual column intersection.
3. **SCD Type 2 programme dimension**: build `effective_start`/`effective_end`/`is_current` from `PROGRAMMES_SNAPSHOT_2025Q1.csv` (5 programmes: PRG100-104) and `PROGRAMMES_SNAPSHOT_2025Q2.csv` (5 programmes: PRG100-103, **PRG105** — PRG105 is new in Q2, **PRG104 is absent from Q2**, and PRG101/PRG102's `ANNUAL_BUDGET_USD` changed between snapshots). Join contributions to the programme version that was current **on the contribution date** — a point-in-time join, not a latest-version join.
4. **Cleaning: dates, nulls, duplicates** — see `DATA_CONTRACTS.md` for the exact profiled defect inventory (this is not guessed; every number below was counted from the actual files).
5. **Joins**: derive `amount_usd` for Q3 rows via `EXCHANGE_RATES.parquet` on `(currency_original, month(contribution_date))`; join to `GRANTS.json` on `grant_id` where present, surfacing `reporting.frequency` and a due date derived from `reporting.next_due_date_epoch`; handle records with no `reporting` object and no `tags` key without failing.
6. **Gold + reconciliation, in SQL** (`%sql`/`spark.sql()`, not DataFrame API): committed/received totals by programme and normalized fiscal year; reconcile against `LEGACY_ORACLE_SUMMARY.csv`, quantify every variance, and explain the likely cause. Four intentional breaks exist; one is related to Q3 corrections not yet reflected in the legacy system.
7. **Delta Lake mechanics**: a `MERGE INTO` performing the Q3 upsert with schema evolution enabled; `DESCRIBE HISTORY` (or a time-travel query) on the contributions table with an explanation of what each relevant version represents.

## Non-functional requirements

- No secrets in source control or logs. (Static complete source files, no live API, no credentials.)
- Re-runs must be idempotent — the `MERGE INTO` upsert must not duplicate rows on rerun.
- All production-facing tables use explicit three-part names; no `SELECT *`.
- **Dev and prod must use distinct, dedicated Unity Catalog catalogs — never `workspace`, `main`, or `default`.** Same non-negotiable rule as every other project in this repository (see `projects/01_big_bag_data`'s corrected defect and `docs/TIMED_MVP.md`'s catalog governance section).
- **All catalog, schema, and grant objects are Terraform-owned.** No ad hoc `CREATE CATALOG`/`GRANT` from a notebook.
- Every unparseable value (dates, casts) uses ANSI-safe (`try_cast`/`try_to_date`) parsing, not a bare `CAST` that can crash the job under Spark's ANSI mode — see `docs/TIMED_MVP.md`.
- Optional components (dbt, ML, Docker) are out of scope.

## Decisions required at planning approval (Sol + human)

Profiling the real data surfaced defects and ambiguities the brief didn't fully specify. Proposed defaults, for sign-off, not silently assumed:

1. **`fiscal_year` has six distinct raw formats** across the two batches combined: `FY25`, `FY24`, `2024`, `2025`, `2024-2025`, `2023-2024`. `LEGACY_ORACLE_SUMMARY.csv` uses plain 4-digit years (`2024`, `2025`) only. Proposed: normalize every format to a single 4-digit fiscal year matching the legacy convention (`FY25`→`2025`, `2024-2025`→ ambiguous, needs a rule — proposed: a hyphenated range's fiscal year is its **second** (ending) year, matching typical FY-end-year convention, i.e. `2024-2025`→`2025`) before any Gold aggregation or reconciliation join. This directly affects the reconciliation join key — an unresolved format mismatch here would silently produce phantom variances unrelated to the four intentional breaks.
2. **Cross-batch corrections (6 confirmed: `CTB9101, CTB9107, CTB9110, CTB9129, CTB9143, CTB9146`)**: proposed "later batch wins" via `MERGE INTO ... WHEN MATCHED THEN UPDATE`, per the brief. Confirmed via profiling, not assumed from the docx's claim.
3. **Orphan FKs, confirmed by profiling**: `PRG999` (13 CSV rows reference a programme not in Q1 or Q2 snapshot) and `DNR99` (13 CSV rows + 1 JSON row reference a donor not in `DONORS.csv`). Proposed: quarantine, matching Project 7's precedent, not silently joined-and-dropped.
4. **Docx claims vs. profiled reality**: the brief states Q3 has "null `donor_id`/`programme_id`" — **profiling found zero such nulls** in the actual `CONTRIBUTIONS_2025Q3.json`. It does have 3 null `amount_original` (`CTB9513, CTB9516, CTB9538`) and 2 null `contribution_date` (`CTB9550, CTB9541`), confirmed. Contracts and tests below are written to the **profiled reality**, not the brief's prose, per `docs/TIMED_MVP.md`'s "profile before parsing" rule — this is exactly why that rule exists.
5. **Exact JSON duplicates**: `CTB9501, CTB9502, CTB9508, CTB9510` appear more than once within the Q3 batch itself (separate from the 6 cross-batch corrections). Proposed: drop exact duplicates before the cross-batch `MERGE INTO`, same two-step pattern as Project 7's `SHP5011` handling.
6. **`GRANTS.json` nesting**: 1 of 18 grants (`GRT2014`) has `reporting: null`; 3 of 18 (`GRT2008, GRT2017, GRT2018`) have no `tags` key at all. Proposed: both are valid, expected shapes — coalesce to safe defaults (`reporting_frequency`/`next_due_date` null, `tags` empty array), never fail the job or quarantine the grant record for this alone.
7. **PRG104 disappears from Q2, PRG105 is new in Q2**: proposed treatment as two independent SCD2 events — PRG104's Q1 version has no matching Q2 row, so its `effective_end` remains open-ended (still current as far as this dataset shows, no evidence it was retired) unless a contribution after 2025-04-01 references it (worth checking); PRG105 has no Q1 version, so its SCD2 history starts at Q2's snapshot date. Flagged for explicit human confirmation since "disappeared from a snapshot" is genuinely ambiguous between "retired" and "just not resnapshotted."

## Verified-source requirements

- The complete source is eight static files (4 CSV, 2 JSON, 1 Parquet, counted above); no live API, no optional providers.
- Every defect claim in this document and in `DATA_CONTRACTS.md` was counted directly from the real files under `data/raw/`, not transcribed from the assessment brief — see Decision 4 above for a case where the brief was measurably wrong.
