# Data Sources - Programme Funding & Parallel-Run Reconciliation

## Default source

Eight static files simulating a multi-source migration: a legacy Oracle CSV export, a newer grants-system JSON export, nested grant metadata, and a Finance-maintained FX-rate Parquet table. No live API, no authentication, no optional providers. Complete source:

| File | Format | Role | Rows/records |
|---|---|---|---:|
| `data/raw/DONORS.csv` | CSV | Dimension, key `DONOR_ID` | 7 |
| `data/raw/PROGRAMMES_SNAPSHOT_2025Q1.csv` | CSV | Dimension snapshot @ 2025-01-01, key `PROGRAMME_ID` | 5 |
| `data/raw/PROGRAMMES_SNAPSHOT_2025Q2.csv` | CSV | Dimension snapshot @ 2025-04-01, same key | 5 |
| `data/raw/CONTRIBUTIONS.csv` | CSV | Fact, Q1+Q2 batch, key `CONTRIBUTION_ID` | 152 |
| `data/raw/CONTRIBUTIONS_2025Q3.json` | JSON (array) | Fact, Q3 incremental batch, key `contribution_id` (lowercase, different schema) | 65 |
| `data/raw/GRANTS.json` | JSON (array, nested) | Grant metadata, key `grant_id`, nested `reporting` object, optional `tags` array | 18 |
| `data/raw/EXCHANGE_RATES.parquet` | Parquet | FX lookup, key `(CURRENCY, RATE_MONTH)` | 96 |
| `data/raw/LEGACY_ORACLE_SUMMARY.csv` | CSV | Reconciliation source of truth, key `(PROGRAMME_ID, FISCAL_YEAR)` | 12 |

Originals in `projects/8. Project8/project8_data/` (external assessment material, outside project isolation); copied verbatim into this project's `data/raw/` as the canonical, reproducible snapshot.

## Executability

Complete static file set — `source_status` goes straight to `EXECUTABLE` once Bronze ingestion loads all eight files, same as `projects/07_unicef_supply_chain`. No live-source approval gate.

## Known defects and characteristics (profiled directly against the real files, not transcribed from the brief)

**Schema evolution**: `CONTRIBUTIONS.csv` uses `UPPER_SNAKE_CASE` columns including `EXCHANGE_RATE_TO_USD`/`AMOUNT_USD`; `CONTRIBUTIONS_2025Q3.json` uses `lower_snake_case` keys, drops both of those, and adds `grant_id`/`payment_method`. A naive union or case-sensitive join will silently fail to reconcile these as the same logical table.

**`fiscal_year` — six raw formats across the two contribution batches**: `FY25`, `FY24`, `2024`, `2025`, `2024-2025`, `2023-2024`. `LEGACY_ORACLE_SUMMARY.csv` uses plain 4-digit years only — normalization is mandatory before reconciliation, not optional cleanup (see `REQUIREMENTS.md` Decision 1).

**`CONTRIBUTION_DATE`/`contribution_date` formats found**: `MM/DD/YYYY` (e.g. `01/05/2025`), `DD-MON-YY` Oracle-style (e.g. `02-APR-25`), ISO `YYYY-MM-DD`, and **epoch-millisecond integers** in the JSON batch (e.g. `1756155600000`). No invalid-calendar-date (e.g. Feb 30) or blank dates found in the CSV batch during profiling; the JSON batch has 2 null `contribution_date` values (`CTB9550`, `CTB9541`) — profile your own copy of the data before trusting this list as exhaustive; it is not a guarantee, it is what was found by direct inspection.

**`STATUS`/`status` — eight raw strings, four real states**: `COMMITTED`, `Committed`, `committed`; `PLEDGED`, `Pledged`, `pledged`; `RECEIVED`, `Received`, `received ` (trailing space); i.e. casing plus a trailing-space variant on `received`.

**Orphan foreign keys (confirmed by profiling against the union of Q1+Q2 programme snapshots and the donor dimension)**: `PROGRAMME_ID=PRG999` (13 rows in the CSV batch) and `DONOR_ID=DNR99` (13 rows in the CSV batch, 1 record in the JSON batch) do not exist in any dimension snapshot.

**Nulls, confirmed by profiling** (not the brief's claim — see `REQUIREMENTS.md` Decision 4 for where the brief's prose and the actual data disagree): JSON batch has 3 null `amount_original` (`CTB9513, CTB9516, CTB9538`) and 2 null `contribution_date` (`CTB9550, CTB9541`). Zero null `donor_id`/`programme_id` found in either batch, contrary to the brief's description.

**Duplicates**: 2 exact-duplicate `CONTRIBUTION_ID`s within the CSV batch (`CTB9021`, `CTB9056`), 4 exact-duplicate `contribution_id`s within the JSON batch (`CTB9501, CTB9502, CTB9508, CTB9510`), and 6 `CONTRIBUTION_ID`s present in **both** batches as genuine cross-batch corrections (`CTB9101, CTB9107, CTB9110, CTB9129, CTB9143, CTB9146`) — three distinct duplicate categories requiring three distinct handling rules (drop exact, drop exact, MERGE-upsert cross-batch).

**Programme dimension change between snapshots**: Q1 has `PRG100-104`; Q2 has `PRG100-103, PRG105` — `PRG104` is absent from Q2 and `PRG105` is new. `PRG101`/`PRG102`'s `ANNUAL_BUDGET_USD` also changed between snapshots (e.g. PRG102: 2,750,000 → 3,900,000). See `REQUIREMENTS.md` Decision 7.

**`GRANTS.json` nesting**: 1 of 18 records (`GRT2014`) has `reporting: null`; 3 of 18 (`GRT2008, GRT2017, GRT2018`) have no `tags` key present at all (not `tags: []`, the key is absent).

## Secrets

None required. No environment variables, no API keys, no Databricks secret scope entries for source access.
