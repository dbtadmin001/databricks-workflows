# Data Contracts - UNICEF Supply Chain Shipments - Medallion Lakehouse

## Contract principles

- Bronze preserves every source field unmodified, as strings, plus ingestion metadata. No cleaning, no type casting, no row dropped.
- Silver permits only reviewed columns and explicit types; every row is classified accepted or quarantined with an explicit reason, never silently dropped.
- Gold schemas are stable analytical contracts with explicit grain and formulas.
- Every Silver/Gold publish is WAP-gated: stage -> reject-empty (except quarantine) -> atomic replace, per `projects/01_big_bag_data/src/big_bag_data/pipeline.py:56-75`.
- Any change to Silver's reviewed fields, Gold's grain/keys, or a metric formula requires a contract-version bump and independent Sol review — the exact rule that would have caught Project 1's `price_change_frequency` defect if it had been checked line-by-line against this file.

## Required contract metadata

| Field | Purpose |
|---|---|
| dataset_name | Stable logical name |
| contract_version | Semantic contract version |
| business_keys | Uniqueness/deduplication keys |
| event_time | Business event or observation timestamp |
| ingestion_time | Platform ingestion timestamp |
| allowed_evolution | Explicit compatibility policy |
| quality_rules | Required, range, domain and referential rules |
| owner | Accountable data-product owner |

## Bronze (contract_version 1.0.0)

Four tables, one per source file, in the `bronze` schema. Every column is `STRING` (no `inferSchema`), values unmodified. Metadata columns on every table: `_ingest_ts` (timestamp), `_source_file` (string), `_run_id` (string).

- `bronze.warehouses` — business key `WAREHOUSE_ID`. Columns: `WAREHOUSE_ID, WAREHOUSE_NAME, COUNTRY_CODE, REGION, CAPACITY_UNITS`.
- `bronze.programmes` — business key `PROGRAMME_ID`. Columns: `PROGRAMME_ID, PROGRAMME_NAME, SECTOR, START_DATE, END_DATE`.
- `bronze.items` — business key `ITEM_CODE`. Columns: `ITEM_CODE, ITEM_NAME, CATEGORY, UNIT_OF_MEASURE`.
- `bronze.shipments` — business key `SHIPMENT_ID` (not unique at Bronze — duplicates and conflicts are expected and preserved). Columns: `SHIPMENT_ID, WAREHOUSE_ID, PROGRAMME_ID, ITEM_CODE, QUANTITY, SHIP_DATE, STATUS, UNIT_COST`.

## Silver (contract_version 1.0.0)

### `silver.warehouses`, `silver.programmes`, `silver.items`
Pass-through conformed dimensions: trimmed strings, `CAPACITY_UNITS` cast `INT`, `START_DATE`/`END_DATE` cast `DATE` (both already ISO `yyyy-MM-dd` in source — no multi-format parsing needed for dimensions). Grain: one row per business key; source dimensions have no duplicates or nulls, so no quarantine table is needed for these three.

### `silver.shipments_accepted` and `silver.shipments_quarantine`
Grain: one row per `SHIPMENT_ID` (accepted table only — quarantine may retain duplicates since rejected rows are not deduplicated against each other).

**Transform order** (each step matters — later steps depend on earlier ones):
1. Parse `SHIP_DATE` via `coalesce(try_to_timestamp(..., 'yyyy-MM-dd'), try_to_timestamp(..., 'MM/dd/yyyy'), try_to_timestamp(..., 'dd-MMM-yy'))`, cast to `DATE`, so ANSI mode returns null for a nonmatching format instead of aborting before later formats are tried -> `ship_date`.
2. Normalize `STATUS` via `trim(lower(...))` then map to the fixed domain `{pending, in_transit, delivered, cancelled}` (source `IN TRANSIT`/`In Transit` -> `in_transit`, etc.) -> `status`.
3. Clean `UNIT_COST` via `regexp_replace(UNIT_COST, '[$,]', '')` then `cast(decimal(10,2))` -> `unit_cost`.
4. Drop exact full-row duplicates (`dropDuplicates()`).
5. Classify remaining `SHIPMENT_ID` collisions (same key, differing values after step 1-3) as `conflicting_duplicate` — **do not** resolve by an arbitrary tie-break; quarantine every row in the colliding group.
6. Validate referential integrity: `WAREHOUSE_ID` against `silver.warehouses`, `PROGRAMME_ID` against `silver.programmes`, `ITEM_CODE` against `silver.items` (anti-join = orphan).
7. Validate `quantity`: reject null and `<= 0`.

**Quarantine reasons** (a row may carry more than one; concat_ws pattern per `silver.py` in Project 1):
- `conflicting_duplicate` — same `SHIPMENT_ID`, differing values after cleaning, post exact-dup removal.
- `missing_warehouse` — `WAREHOUSE_ID` not in `silver.warehouses` (e.g. `WH099`).
- `missing_programme` — `PROGRAMME_ID` not in `silver.programmes` (e.g. `PRG999`).
- `missing_item` — `ITEM_CODE` not in `silver.items`.
- `missing_quantity` — `QUANTITY` blank.
- `non_positive_quantity` — `QUANTITY` present but `<= 0`.
- `invalid_ship_date` — `SHIP_DATE` non-blank but unparseable by all three known formats.

`silver.shipments_quarantine` columns: `SHIPMENT_ID, WAREHOUSE_ID, PROGRAMME_ID, ITEM_CODE, QUANTITY, SHIP_DATE, STATUS, UNIT_COST, quarantine_reason, _source_file, _ingest_ts`. Preserve every original raw value, not the cleaned ones, so a human can diagnose the source-system defect.

## Gold (contract_version 1.0.0)

### `gold.fact_shipments`
- Grain: one row per `SHIPMENT_ID`, accepted shipments only.
- Key: `SHIPMENT_ID`; refresh: WAP replace after every Silver publish.
- Columns: `SHIPMENT_ID, WAREHOUSE_ID, WAREHOUSE_NAME, PROGRAMME_ID, PROGRAMME_NAME, ITEM_CODE, ITEM_NAME, quantity, unit_cost, total_line_cost, status, ship_date`.
- `total_line_cost = quantity * unit_cost`.

### `gold.programme_monthly_summary`
- Grain: one row per (`programme_name`, `year_month`).
- Key: `programme_name, year_month`; `year_month = date_format(ship_date, 'yyyy-MM')`.
- **Excludes `status = 'cancelled'`** from both metrics — a cancelled shipment was never actually shipped, so it must not count toward "total quantity/cost shipped." This is a distinct decision from the Silver-layer quarantine of negative-quantity/cancelled rows (`REQUIREMENTS.md` Decision 2): a row can be a perfectly valid, accepted shipment record (positive quantity, resolves to real dimensions) and still be excluded from this specific aggregate because it was cancelled.
- `total_qty = sum(quantity)`, `total_cost = sum(total_line_cost)`, both over non-cancelled `gold.fact_shipments` rows only.

## Reconciliation invariant

`count(bronze.shipments) == count(silver.shipments_accepted) + count(silver.shipments_quarantine) + exact_duplicate_rows_removed`, with zero rows unaccounted for. Real numbers for this dataset are in `ACCEPTANCE_CRITERIA.md` — computed by running the actual classification logic against `data/raw/SHIPMENTS.csv`, not estimated.

## Evolution and classification

Bronze accepts additive source fields and stores the raw response as-is; a new column in a future extract is `ADDITIVE`, a missing required column is `BREAKING`. Any change to Silver's cleaning rules, quarantine reasons, Gold's grain/keys, or the `programme_monthly_summary` cancelled-exclusion rule requires a contract-version change and independent Sol review.
