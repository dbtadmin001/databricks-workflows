# Acceptance Criteria - Programme Funding & Parallel-Run Reconciliation

Every number below is checked against the real `data/raw/CONTRIBUTIONS.csv` (152
rows) and `data/raw/CONTRIBUTIONS_2025Q3.json` (65 records). The implementation
review corrected an earlier profiling defect: the JSON contains two null dates, four
blank dates, and six impossible `2025-02-30` dates. All 12 are irreconcilable and
must be quarantined rather than coerced or silently accepted.

## Bronze

- `bronze.contributions_csv` row count == 152.
- `bronze.contributions_json` row count == 65.
- `bronze.donors` == 7, `bronze.programmes_q1` == 5, `bronze.programmes_q2` == 5, `bronze.grants` == 18, `bronze.exchange_rates` == 96, `bronze.legacy_oracle_summary` == 12.
- Every Bronze column is unmodified from its native reader (CSV strings, JSON native types incl. epoch-millis integers and nested structs, Parquet native types).

## Silver contributions reconciliation (exact)

| Stage | Count |
|---|---:|
| Bronze `contributions_csv` + `contributions_json` combined | 217 |
| Exact full-row duplicates removed (1 CSV + 4 JSON) | 5 |
| Rows entering cross-batch merge | 212 |
| Cross-batch corrections collapsed (6 pairs → 6 rows) | 6 |
| **Accepted** (`silver.contributions_accepted`) | **163** |
| **Quarantined** (`silver.contributions_quarantine`) | **43** |

Invariant: `163 + 43 + 5 + 6 == 217`. Must hold exactly.

### Quarantine reason breakdown (a row may carry more than one reason)

| Reason | Row count |
|---|---:|
| `missing_programme` | 14 |
| `missing_donor` | 13 |
| `conflicting_duplicate` | 2 (both rows of `CTB9021`) |
| `missing_amount` | 3 |
| `invalid_date` | 12 |

- `CTB9021` (both copies, `AMOUNT_USD` 5260.04 vs 4605.96) must appear in `silver.contributions_quarantine` tagged `conflicting_duplicate`, and must **not** appear in `silver.contributions_accepted` under either value — picking one silently is a defect, not an implementation detail.
- The 6 confirmed cross-batch corrections (`CTB9101, CTB9107, CTB9110, CTB9129, CTB9143, CTB9146`) must each appear **once** in the merged set, with the Q3 (JSON) values winning per `WHEN MATCHED THEN UPDATE`.
- `missing_exchange_rate` is not expected to fire for the currency/month combinations actually present in Q3 against `EXCHANGE_RATES.parquet`'s 96 rows (4 currencies × 24 months) — if implementation finds it firing, treat that as a discrepancy against this baseline to investigate, not silently accept.

## SCD2 programme dimension

Verified directly by diffing `PROGRAMMES_SNAPSHOT_2025Q1.csv` against
`PROGRAMMES_SNAPSHOT_2025Q2.csv` — `silver.dim_programme` row count == **9**.
The implementation review corrected an earlier budget-only comparison that missed
PRG103's sector change from `Health` to `Health & Immunization`.

| Programme | Q1 budget | Q2 budget | Versions |
|---|---:|---:|---:|
| PRG100 | 4,200,000 | 4,200,000 (unchanged) | 1 |
| PRG101 | 3,100,000 | 3,450,000 (changed) | 2 |
| PRG102 | 2,750,000 | 3,900,000 (changed) | 2 |
| PRG103 | 5,600,000 / Health | 5,600,000 / Health & Immunization | 2 |
| PRG104 | 1,800,000 | absent from Q2 | 1 (`effective_end IS NULL` per `REQUIREMENTS.md` Decision 7) |
| PRG105 | absent from Q1 | 2,200,000 | 1 (`effective_start = 2025-04-01`) |

Total: 1+2+2+2+1+1 = **9**.

## Gold

- `gold.fact_contributions` row count == 163 (equals `silver.contributions_accepted`; the point-in-time SCD2 join and the `grants` left join must not drop or duplicate rows). Contributions before the first available programme snapshot use that programme's earliest known version, explicitly marked by `version_rank = 1`; this avoids inventing a pre-snapshot change while preserving valid historical facts.
- `gold.programme_fy_summary` row count == distinct `(programme_id, fiscal_year_norm)` pairs among accepted contributions — count this from the actual accepted data at implementation time.
- Reconciliation query against `bronze.legacy_oracle_summary` (12 rows) must surface **exactly 4** flagged variances per the assignment brief — but this number comes from the brief's prose, not independently profiled (unlike every other number on this page, which was computed directly). Treat 4 as the brief's claim to verify, not a pre-verified fact: if implementation finds a different count, investigate and record which is true rather than forcing the number to match.

## Multi-format ingestion

- `bronze.exchange_rates` preserves Parquet's native decimal/double type for `RATE_TO_USD` — no string round-trip.
- `bronze.grants` preserves the nested `reporting` struct and `tags` array as-is; `GRT2014` (`reporting=null`) and `GRT2008/GRT2017/GRT2018` (no `tags` key) must load without error and without being dropped.

## Delta Lake mechanics

- A `MERGE INTO` statement performs the Q3 upsert with `mergeSchema`/`autoMerge` enabled — verify via `DESCRIBE HISTORY` that the operation is recorded as a `MERGE`, not a manual delete+insert.
- `DESCRIBE HISTORY silver.contributions_accepted` records the reviewed publication. The accepted result contains 163 rows after exact duplicates, conflicting duplicates, corrections, and quality quarantine are applied.

## Data-quality summary deliverable

A written or generated summary stating: Bronze counts per format, exact-duplicate count, intra-batch conflicting-duplicate count, cross-batch correction count, accepted/quarantined counts with reason breakdown, SCD2 dimension version count, and the actual reconciliation-variance count found — matching the numbers in this file, or explicitly noting and explaining any discrepancy against them.
