# Data Sources - UNICEF Supply Chain Shipments - Medallion Lakehouse

## Default source

Four static CSV files simulating a one-time Oracle data-warehouse extract. No live API, no authentication, no optional providers. The complete source is:

| File | Role | Rows (incl. header) | Business key |
|---|---|---:|---|
| `data/raw/WAREHOUSES.csv` | Dimension | 7 (6 data rows) | `WAREHOUSE_ID` |
| `data/raw/PROGRAMMES.csv` | Dimension | 6 (5 data rows) | `PROGRAMME_ID` |
| `data/raw/ITEMS.csv` | Dimension | 8 (7 data rows) | `ITEM_CODE` |
| `data/raw/SHIPMENTS.csv` | Fact | 168 (167 data rows) | `SHIPMENT_ID` |

Original files provided in `projects/7. Project7/practice_data/` (external assessment material, outside project isolation); copied verbatim into this project's `data/raw/` as the canonical, reproducible source snapshot. There is nothing to "reconnect" to — this is the complete dataset, not a sample of a larger live feed.

## Executability

Because the source is a complete static file set rather than a live API, `source_status` in `delivery.json` goes straight to `EXECUTABLE` once Bronze ingestion (M07) loads these four files — there is no `FIXTURE_ONLY`-forever state and no live-source approval gate to clear, unlike Projects 1-6.

## Known defects in the fact file (profiled against the real data, not assumed)

`SHIPMENTS.csv` is a realistic messy raw extract. Profiling `data/raw/SHIPMENTS.csv` directly found:

- **Inconsistent date formats** in `SHIP_DATE`: ISO (`2024-01-15`), US (`06/23/2025`), and Oracle-style (`10-SEP-24`) all present.
- **Inconsistent `STATUS` casing/values**: `CANCELLED`, `Cancelled`, `DELIVERED`, `Delivered`, `delivered`, `IN TRANSIT`, `In Transit`, `Pending`, and `pending ` (trailing space) — nine distinct raw strings for four real states.
- **Currency-formatted `UNIT_COST`**: some values carry a `$` prefix (e.g. `$18.36`); most do not.
- **Exact duplicate rows**: 6 rows are byte-for-byte duplicates of another row in the file.
- **One conflicting duplicate**: `SHIPMENT_ID=SHP5011` appears twice with different `QUANTITY` (99999 vs. 2529) — not a simple duplicate, a genuine data-integrity conflict. See `REQUIREMENTS.md` Decision 3.
- **Orphan foreign keys**: `WAREHOUSE_ID=WH099` (6 rows) does not exist in `WAREHOUSES.csv`; `PROGRAMME_ID=PRG999` (12 rows) does not exist in `PROGRAMMES.csv`. Every `ITEM_CODE` in `SHIPMENTS.csv` does resolve against `ITEMS.csv` — no orphan items.
- **Missing `QUANTITY`**: 4 rows have a blank value.
- **Non-positive `QUANTITY`**: 5 rows are negative; all 5 have `STATUS=CANCELLED` (see `REQUIREMENTS.md` Decision 2).

Full reconciliation of how these resolve into accepted/quarantined counts is in `ACCEPTANCE_CRITERIA.md`, computed by actually running the classification logic against this file, not estimated.

## Secrets

None required. No environment variables, no API keys, no Databricks secret scope entries for source access.
