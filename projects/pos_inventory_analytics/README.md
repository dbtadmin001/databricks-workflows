# POS Inventory Analytics

**Real-time inventory tracking with safety stock alerting and BOPIS support**

## Overview

This project provides real-time inventory analytics for a point-of-sale (POS) system across multiple retail stores. It incrementally ingests inventory change events (sales, restocks, shrinkage, buy-online-pickup-in-store) and physical count snapshots, applies data quality rules, and calculates current inventory levels with safety stock alerts.

**Key Features**:
* **Incremental ingestion** via Auto Loader with checkpointing
* **Quarantine pattern** for data quality failures
* **Safety stock alerting** when inventory drops below thresholds
* **BOPIS tracking** (Buy Online Pickup In Store) with dual-leg transactions
* **Channel tracking** (online vs in-store sales)
* **Fixed schemas** to prevent evolution-triggered restarts

## Data Sources

### Event Streams (Incremental)
* **Inventory Events**: `/Volumes/{catalog}/{schema}/raw_landing/pos_data/landing/inventory_events/*.json`
  * Transaction-level inventory changes (sales, restocks, shrinkage, BOPIS)
  * Nested structure with items array
  * Auto Loader streaming ingestion

* **Inventory Snapshots**: `/Volumes/{catalog}/{schema}/raw_landing/pos_data/landing/inventory_snapshots/*.json`
  * Physical count snapshots from stores
  * Periodic manual verification
  * Auto Loader streaming ingestion

### Reference Data (Static CSV)
* **Store Reference**: `store.csv` (store_id, store_name, store_type, city)
* **Item Reference**: `item.csv` (item_id, item_name, supplier_id, category, unit_price, safety_stock_quantity)
* **Change Type Reference**: `inventory_change_type.csv` (change_type_id, change_type_name, expected_sign)
* **Supplier Reference**: `supplier.csv` (supplier_id, supplier_name, lead_time_days)

## Medallion Architecture

### Bronze Layer (Streaming)
* **`bronze_inventory_change_raw`** — Raw event ingestion with `_ingested_at` audit column
* **`bronze_inventory_snapshot_raw`** — Raw snapshot ingestion with audit column
* **5 DLT expectations** enforcing non-null keys and valid structure

### Silver Layer (Batch on Bronze snapshot)
* **`silver_inventory_change`** — Exploded (one row per trans_id+item_id), deduplicated, validated
* **`silver_inventory_change_quarantine`** — Invalid records with failure reasons
* **`silver_inventory_snapshot`** — Validated snapshots
* **`silver_inventory_snapshot_quarantine`** — Invalid snapshots
* **`silver_latest_inventory_snapshot`** — Latest count per store+item (window function)

**Data Quality Rules**:
- Non-null keys (trans_id, store_id, item_id)
- Valid reference lookups (store_ref, item_ref, change_type_ref)
- Quantity sign validation (sales must be negative, restocks positive)
- Physical counts must be non-negative

### Gold Layer (Business Metrics)
* **`gold_inventory_current`** — Current inventory per store+item
  * Formula: `latest_snapshot.quantity + SUM(changes since snapshot)`
  * Includes `below_safety_stock` alert flag
  * Enriched with store and item names, categories

### Reference Tables
* `store_ref`, `item_ref`, `change_type_ref`, `supplier_ref` (materialized from CSV)

## Business Rules

1. **BOPIS Handling**:
   * Online store (store_id=99) generates ONLINE- leg (quantity negative)
   * Pickup store generates PICKUP+ leg (quantity positive)
   * Both legs share same `bopis_order_id`
   * Store 99 also has genuine standalone activity (not all store_id=99 is BOPIS)

2. **Current Inventory Calculation**:
   ```
   current_quantity = latest_snapshot.quantity + 
                     SUM(change.quantity WHERE change.date_time > snapshot.date_time)
   ```

3. **Safety Stock Alert**:
   * Triggered when `current_quantity < safety_stock_quantity`
   * `below_safety_stock = true` in Gold table

## Deployment

### Databricks (Primary Platform)

**Job ID**: [754086303727859](#job-754086303727859)  
**Pipeline ID**: [bfd9e136-c1d9-4842-880e-a6940169e4c6](#pipeline-bfd9e136-c1d9-4842-880e-a6940169e4c6)

**Deployment via Databricks Asset Bundle**:
```bash
cd platforms/databricks/bundles/pos_inventory_analytics
databricks bundle deploy --target dev
```

**Job Tasks**:
1. `01_medallion_execution` — DLT pipeline update
2. `01b_schema_and_quality_audit` — Python wheel audit
3. `02_sql_validation` — SQL validation queries
4. `03_publish_analytics` — Dashboard rendering

**Pipeline Configuration**:
* **Serverless**: Yes
* **Photon**: Enabled
* **Edition**: Advanced
* **Storage**: Unity Catalog (`{catalog}.{schema}`)
* **Configuration**: `source_base_path` (volume path, configurable)

### AWS (K8s + Spark Operator)

**Manifests**:
```
platforms/aws/k8s/manifests/
├── bronze/pos-inventory-analytics-bronze.yaml
├── silver/pos-inventory-analytics-silver.yaml
└── gold/pos-inventory-analytics-gold.yaml
```

Each manifest references `projects/pos_inventory_analytics/modules/pipeline.py` functions.

### Fabric (Placeholder)

```
platforms/fabric/lakehouses/pos_inventory_analytics/
```

## Dependencies

**Python Packages**:
* `plotly>=5.24,<7` (dashboard visualizations)
* Packaged as wheel: `project_12_pos_inventory_analytics-0.1.0-py3-none-any.whl`

**Databricks Runtime**:
* Unity Catalog required
* Delta Lake storage
* Serverless compute recommended

## Project Structure

```
projects/pos_inventory_analytics/
├── config/
│   └── project.yml                    # Data sources, medallion config, environments
├── contracts/
│   └── schemas.yml                    # Complete schema definitions + DQ rules
├── entry_points/
│   ├── inventory_pipeline.py          # DLT pipeline (thin wrapper)
│   └── dashboard.py                   # Dashboard notebook
├── modules/                           # Business logic (project-specific)
│   ├── pipeline.py                    # Core transformations (Bronze→Silver→Gold)
│   ├── schema_contract.py             # Contract validation
│   ├── quality_profile.py             # Quality profiling
│   ├── dashboard.py                   # Dashboard rendering
│   └── jobs.py                        # Job orchestration
├── sql/
│   └── validate_outputs.sql           # Post-pipeline SQL validation
├── tests/
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_pipeline.py               # Unit tests for transformations
│   ├── test_schema_contract.py        # Contract validation tests
│   ├── test_quality_profile.py        # Quality check tests
│   └── test_dashboard.py              # Dashboard tests
├── MIGRATION_PLAN.md                  # Migration strategy and checklist
└── README.md                          # This file
```

## Testing

### Unit Tests
```bash
cd /Workspace/Repos/albertraviss@gmail.com/databricks-workflows
pytest projects/pos_inventory_analytics/tests/test_pipeline.py -v
pytest projects/pos_inventory_analytics/tests/test_quality_profile.py -v
```

### Contract Tests
```bash
pytest projects/pos_inventory_analytics/tests/test_schema_contract.py -v
```

### Integration Test (Full Pipeline)
```bash
# Deploy to dev and trigger pipeline update
databricks pipelines update bfd9e136-c1d9-4842-880e-a6940169e4c6
```

## Monitoring & Alerts

* **Job**: [DEV | 12_pos_inventory_analytics | Medallion](#job-754086303727859)
* **Pipeline**: [DEV | 12_pos_inventory_analytics | Inventory Pipeline](#pipeline-bfd9e136-c1d9-4842-880e-a6940169e4c6)
* **Quarantine Tables**: Monitor `silver_inventory_change_quarantine` and `silver_inventory_snapshot_quarantine` for DQ issues
* **Safety Stock Alerts**: Query `gold_inventory_current WHERE below_safety_stock = true`

## Migration Status

**Status**: 🟡 Step 5/10 complete (modules and entry points migrated, imports updated)  
**Original Bundle**: `/Workspace/Users/albertraviss@gmail.com/.bundle/project_12_pos_inventory_analytics/dev/`  
**Framework Location**: `projects/pos_inventory_analytics/`

**Next Steps**:
- [ ] Step 6: Platform configs (preserve DAB structure)
- [ ] Step 7: Create AWS manifests
- [ ] Step 8: Run unit tests
- [ ] Step 9: Side-by-side validation
- [ ] Step 10: Production cutover

See [MIGRATION_PLAN.md](MIGRATION_PLAN.md) for details.
