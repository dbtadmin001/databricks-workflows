# Humanitarian Supply Chain (UNICEF Shipment Tracking)

**UNICEF humanitarian supply chain shipment tracking and analytics**

## Overview

Tracks UNICEF supply chain shipments from warehouses to humanitarian programmes. Ingests static CSV extracts from Oracle data warehouse, cleanses messy data (inconsistent dates, status values, duplicates), validates foreign keys, and produces analytics on shipment patterns and programme summaries.

**Key Features**:
* **Static CSV source** (4 files: warehouses, programmes, items, shipments)
* **Data quality handling** (9 status variants → 4 canonical, mixed date formats, currency parsing)
* **Duplicate detection** (exact + conflicting duplicates)
* **Orphan FK handling** (quarantine records with invalid warehouse/programme refs)
* **Cancelled shipment logic** (negative quantities allowed for CANCELLED status)
* **Monthly programme summaries** (total shipments, quantity, cost per programme)

## Data Sources

### Static CSV Files (Oracle Extract)
* **WAREHOUSES.csv** (6 rows) — Warehouse dimension (ID, name, location, capacity)
* **PROGRAMMES.csv** (5 rows) — Programme dimension (ID, name, manager, budget)
* **ITEMS.csv** (7 rows) — Item dimension (code, description, UOM, cost)
* **SHIPMENTS.csv** (167 rows) — Shipment fact table with known defects:
  * Inconsistent date formats (ISO/US/Oracle)
  * 9 status value variants (case, spacing)
  * Currency-formatted costs ($18.36)
  * 6 exact duplicates
  * 1 conflicting duplicate (SHP5011 with different quantities)
  * Orphan FKs (WH099, PRG999 — 18 rows)
  * Missing quantities (4 rows)
  * Negative quantities (5 rows, all CANCELLED)

## Medallion Architecture

### Bronze Layer
* **bronze_warehouses** — Raw warehouse CSV
* **bronze_programmes** — Raw programme CSV
* **bronze_items** — Raw item CSV
* **bronze_shipments** — Raw shipment CSV (with defects)

### Silver Layer
* **silver_warehouses** — Conformed warehouse dimension
* **silver_programmes** — Conformed programme dimension
* **silver_items** — Conformed item dimension
* **silver_shipments** — Normalized and validated shipments
  * Date formats normalized to timestamp
  * Status values standardized (DELIVERED, IN_TRANSIT, PENDING, CANCELLED)
  * Currency symbols removed from UNIT_COST
  * Exact duplicates removed
  * Conflicting duplicates quarantined
  * Orphan FKs quarantined
* **silver_shipments_quarantine** — Invalid shipments with failure reasons

### Gold Layer
* **fact_shipments** — Enriched shipment fact with dimension attributes
  * Warehouse name, location, capacity
  * Programme name, manager, budget
  * Item description, UOM
  * Calculated total_cost (QUANTITY × UNIT_COST)
* **programme_monthly_summary** — Monthly aggregation by programme
  * Total shipments, quantity, cost
  * Avg unit cost
  * Distinct items, warehouses

## Business Rules

1. **Status Normalization**: 9 variants → 4 canonical values
2. **Date Parsing**: ISO/US/Oracle formats → timestamp
3. **Currency Parsing**: $18.36 → 18.36
4. **Deduplication**:
   * Exact duplicates: remove all but first
   * Conflicting duplicates (same ID, different data): quarantine
5. **FK Validation**: Orphan warehouse/programme refs → quarantine
6. **Quantity Validation**: Must be positive UNLESS status=CANCELLED

## Deployment

### Databricks
**Job ID**: [1019295447746053](#job-1019295447746053)  
**Pipeline ID**: [ae4f06ca-11ee-458e-a081-6382026093d4](#pipeline-ae4f06ca-11ee-458e-a081-6382026093d4)

```bash
cd platforms/databricks/bundles/humanitarian_supply_chain
# Bundle deployment commands would go here
```

**Schedule**: Daily at 2 AM UTC  
**Email Alerts**: On failure → albertraviss@gmail.com

## Project Structure

```
projects/humanitarian_supply_chain/
├── config/
│   └── project.yml                   # Data sources, medallion config
├── contracts/
│   └── schemas.yml                   # Schema definitions + quality rules
├── entry_points/
│   └── supply_chain_pipeline.py      # Pipeline orchestration
├── modules/
│   ├── bronze.py                     # Bronze ingestion
│   ├── silver.py                     # Silver normalization
│   ├── gold.py                       # Gold aggregations
│   ├── pipeline.py                   # End-to-end orchestration
│   └── jobs.py                       # Job definitions
├── sql/
│   └── validate_outputs.sql          # Post-pipeline validation
├── tests/
│   ├── test_pipeline.py              # Pipeline unit tests
│   └── test_raw_csv_fixtures.py      # CSV fixture tests
├── REQUIREMENTS.md                    # Business requirements
├── DATA_CONTRACTS.md                  # Detailed contracts
├── ARCHITECTURE.md                    # Technical architecture
├── DATA_SOURCES.md                    # Source data documentation
└── README.md                          # This file
```

## Dependencies

**Python Packages**: None (standard PySpark only)

## Testing

```bash
cd /Workspace/Repos/albertraviss@gmail.com/databricks-workflows
pytest projects/humanitarian_supply_chain/tests/test_pipeline.py -v
pytest projects/humanitarian_supply_chain/tests/test_raw_csv_fixtures.py -v
```

## Monitoring & Alerts

* **Job**: [Humanitarian Supply Chain ETL Orchestration](#job-1019295447746053)
* **Schedule**: Daily 2 AM UTC
* **Alerts**: Email on failure
* **Quarantine Table**: Monitor `silver_shipments_quarantine` for DQ issues

## Migration Status

**Status**: 🟡 Steps 1-7/10 complete (70%)  
**Original Bundle**: `/Workspace/Users/.../. bundle/project_07_unicef_supply_chain/`  
**Framework Location**: `projects/humanitarian_supply_chain/`

**Completed**:
- ✅ Project structure
- ✅ Configuration files (project.yml, schemas.yml)
- ✅ Modules (bronze, silver, gold, pipeline)
- ✅ Tests
- ✅ Platform configs (Databricks bundle)

**Remaining**:
- ⏳ Test execution
- ⏳ Side-by-side validation
- ⏳ Production cutover
