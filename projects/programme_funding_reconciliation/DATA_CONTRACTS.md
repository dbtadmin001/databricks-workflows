# Data Contracts - Programme Funding & Parallel-Run Reconciliation

## Contract principles

- Bronze preserves every source field unmodified, in its native reader shape (CSV/JSON/Parquet), plus ingestion metadata. No cleaning, no cross-batch merging, no row dropped.
- Silver permits only reviewed, typed columns; every row is classified accepted or quarantined with an explicit reason.
- Gold schemas are stable analytical contracts with explicit grain and formulas, built in SQL per `REQUIREMENTS.md`.
- Every Silver/Gold publish is WAP-gated: stage → reject-empty (except quarantine) → atomic replace, per `docs/TIMED_MVP.md`.
- Any change to Silver's reviewed fields, the SCD2 grain/keys, or a Gold formula requires a contract-version bump and independent Sol review.

## Bronze (contract_version 1.0.0)

One table per source file, native reader per format, unmodified values plus `_ingest_ts`, `_source_file`, `_run_id`:

- `bronze.donors` (CSV) — business key `DONOR_ID`.
- `bronze.programmes_q1`, `bronze.programmes_q2` (CSV, kept separate — do not merge at Bronze, SCD2 construction is a Silver concern) — business key `PROGRAMME_ID`.
- `bronze.contributions_csv` (CSV, `UPPER_SNAKE_CASE` columns as-is) — business key `CONTRIBUTION_ID`, not unique at Bronze (2 exact duplicates expected and preserved).
- `bronze.contributions_json` (JSON, `lower_snake_case` keys as-is, `contribution_date` as the raw epoch-millis/string value) — business key `contribution_id`, not unique at Bronze (4 exact duplicates expected and preserved).
- `bronze.grants` (JSON, nested `reporting` struct and `tags` array preserved as-is, including records with `reporting=null` or no `tags` key) — business key `grant_id`.
- `bronze.exchange_rates` (Parquet, unmodified) — business key `(CURRENCY, RATE_MONTH)`.
- `bronze.legacy_oracle_summary` (CSV, unmodified) — business key `(PROGRAMME_ID, FISCAL_YEAR)`, reconciliation source of truth, never treated as a contribution source.

## Silver (contract_version 1.0.0)

### `silver.donors`
Pass-through conformed dimension, trimmed strings. Grain: one row per `DONOR_ID`.

### `silver.dim_programme` (SCD2)
Built from `bronze.programmes_q1` UNION `bronze.programmes_q2`, keyed `PROGRAMME_ID`:
- `effective_start` = the snapshot date the row first appears at its current `ANNUAL_BUDGET_USD` value (2025-01-01 for every Q1 row; 2025-04-01 for a Q2 row whose budget changed from Q1, or for PRG105 which is new in Q2).
- `effective_end` = the next snapshot date if the value changed there, else `NULL` (still current). A programme present in Q1 but absent from Q2 (`PRG104`) keeps `effective_end = NULL` unless a later signal contradicts it — see `REQUIREMENTS.md` Decision 7; this is an explicit, flagged assumption, not a silent default.
- `is_current` = `effective_end IS NULL`.
- `version_rank` orders known versions. Gold contributions dated before the first available snapshot use `version_rank = 1`; this is an explicit earliest-known-version fallback, not a claim that the snapshot was effective before its recorded date.
- Grain: one row per `(PROGRAMME_ID, effective_start)`.

### `silver.contributions_accepted` / `silver.contributions_quarantine`
Grain: one row per `CONTRIBUTION_ID` (accepted only). Transform order:

1. **Normalize schema**: lowercase all CSV column names to match the JSON batch's naming; add `payment_method`/`grant_id` as `NULL` to CSV-origin rows; add `exchange_rate_to_usd`/`amount_usd` as `NULL` to JSON-origin rows pending the FX join. This is the schema-evolution step — implemented via Delta `mergeSchema`/explicit union, not by silently dropping either batch's unique columns.
2. **Normalize `fiscal_year`** to a 4-digit year matching `bronze.legacy_oracle_summary`'s convention, per `REQUIREMENTS.md` Decision 1 (`FY25`→`2025`, `2024-2025`→`2025` i.e. the range's ending year).
3. **Parse `contribution_date`** via ANSI-safe `try_to_date`/`try_to_timestamp` across all known formats (`MM/dd/yyyy`, `dd-MMM-yy`, `yyyy-MM-dd`) plus an epoch-millisecond branch (`try_cast(value/1000 AS timestamp)` when the raw value is numeric). A value that fails every branch is quarantined as `invalid_date`, never silently null-and-passed.
4. **Normalize `status`** via `trim(lower(...))` to the fixed domain `{committed, pledged, received, cancelled}`... contract note: `cancelled` was not observed in profiling but the assessment brief implies a fourth eventual state; if never observed in this dataset, that's a `NOT_APPLICABLE`-with-reason in acceptance criteria, not an invented row.
5. **Drop exact full-row duplicates** within each batch independently (`dropDuplicates()` on CSV rows, then on JSON rows) — resolves 1 CSV and 4 JSON exact duplicates found in profiling.
6. **Quarantine intra-batch conflicting duplicates**: after exact-dup removal, a `CONTRIBUTION_ID`/`contribution_id` that still appears more than once within the *same* batch is a conflicting duplicate — **distinct from the cross-batch corrections in step 7**. Profiling found exactly one: `CTB9021` within the CSV batch, appearing twice with different `AMOUNT_USD` (5260.04 vs 4605.96) and no tie-break signal. Quarantine **both** rows under `conflicting_duplicate`, same rule as `SHP5011` in `projects/07_unicef_supply_chain` — do not silently pick one via a `groupBy`/dict-style last-value-wins collapse (a real bug caught during this project's own profiling script, not a hypothetical).
7. **Cross-batch upsert**: `MERGE INTO` the (exact-dup-removed, intra-batch-conflict-removed) CSV-origin rows as the base, matched on `CONTRIBUTION_ID`, with the equivalent JSON-origin rows as the source — `WHEN MATCHED THEN UPDATE` (later batch wins, resolves the 6 confirmed cross-batch corrections: `CTB9101, CTB9107, CTB9110, CTB9129, CTB9143, CTB9146`), `WHEN NOT MATCHED THEN INSERT`, schema evolution enabled on the merge.
7. **Validate referential integrity**: `DONOR_ID`/`donor_id` against `silver.donors`, `PROGRAMME_ID`/`programme_id` against the union of `silver.dim_programme` (any version, not just current). Anti-join = orphan.
8. **Validate `amount_original`**: reject null or `<= 0`.
9. **Derive `amount_usd`**: for CSV-origin rows, pass through the source `AMOUNT_USD`. For JSON-origin rows, join to `silver.exchange_rates` on `(currency_original, date_format(contribution_date, 'yyyy-MM'))` and compute `amount_original * RATE_TO_USD`; a row whose FX join misses is quarantined as `missing_exchange_rate`, not silently null.

**Quarantine reasons** (a row may carry more than one): `conflicting_duplicate`, `missing_donor`, `missing_programme`, `missing_amount`, `non_positive_amount`, `invalid_date`, `missing_exchange_rate`.

### `silver.grants`
Pass-through with nested flattening: `reporting_frequency = reporting.frequency` (null when `reporting` is null), `next_due_date = try_to_date(reporting.next_due_date_epoch / 1000)` (null when `reporting` is null), `tags_str = concat_ws(',', coalesce(tags, array()))` (empty string when `tags` key is absent). No row is quarantined for missing `reporting`/`tags` — both are documented-valid shapes per `REQUIREMENTS.md` Decision 6. Grain: one row per `grant_id`.

## Gold (contract_version 1.0.0), built in SQL

### `gold.fact_contributions`
- Grain: one row per accepted `CONTRIBUTION_ID`.
- Joins: `silver.contributions_accepted` to `silver.donors`, to `silver.dim_programme` on the **point-in-time** condition (`contribution_date >= effective_start AND (contribution_date < effective_end OR effective_end IS NULL)`), and to `silver.grants` on `grant_id` (left join — not every contribution has a grant).
- Columns include `programme_name` (the point-in-time version, not necessarily current), `reporting_frequency`, `next_due_date`.

### `gold.programme_fy_summary`
- Grain: one row per `(programme_id, fiscal_year_norm)`.
- `total_committed_usd = SUM(amount_usd) WHERE LOWER(status) = 'committed'`; `total_received_usd = SUM(amount_usd) WHERE LOWER(status) = 'received'`.
- Built with `%sql`/`spark.sql()`, not the DataFrame API, per `REQUIREMENTS.md` #6.

### Reconciliation query (SQL, not a table — a diagnostic deliverable)
`FULL OUTER JOIN gold.programme_fy_summary` against `bronze.legacy_oracle_summary` on `(programme_id, fiscal_year_norm)`, flagging any pair where `ABS(committed_diff) > 0.01 OR ABS(received_diff) > 0.01`. Every flagged variance gets a recorded, explained cause — the assignment states 4 intentional breaks exist, at least one tied to Q3 corrections not yet reflected in the legacy system; this project's own reconciliation must independently discover and count them, not assume the brief's number without running the query.

## Reconciliation invariant

`count(bronze.contributions_csv) + count(bronze.contributions_json) == count(exact_duplicates_removed) + count(silver.contributions_accepted) + count(silver.contributions_quarantine) + count(cross_batch_corrections_collapsed)`. The verified result is `217 = 5 + 163 + 43 + 6`; quarantine includes all 12 null, blank, or impossible dates.

## Evolution and classification

Bronze accepts additive fields per format; a genuinely new column in a future extract is `ADDITIVE`, a missing required column is `BREAKING`. Any change to the Silver schema-evolution mapping, the SCD2 point-in-time join condition, the `fiscal_year` normalization rule, or a Gold formula requires a contract-version change and independent Sol review — this is precisely the kind of change class that produced Project 1's `price_change_frequency` defect when it wasn't checked line-by-line against this file.
