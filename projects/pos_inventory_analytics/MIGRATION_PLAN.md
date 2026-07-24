# pos_inventory_analytics Migration Plan

**Project**: 12_pos_inventory_analytics (Real-Time POS Inventory Analytics)  
**Priority**: Tier 1 — IMMEDIATE  
**Complexity**: MEDIUM  
**Estimated Effort**: 2-3 days  
**Status**: IN PROGRESS

---

## Current State Assessment

### Existing Bundle Structure
**Location**: `/Workspace/Users/albertraviss@gmail.com/.bundle/project_12_pos_inventory_analytics/dev/`

```
├── databricks.yml                      # DAB configuration
├── project.yml                         # Project metadata (JSON format)
├── src/
│   ├── project_12_pos_inventory_analytics/    # Python wheel package
│   │   ├── pipeline.py                 # Core business logic (Bronze/Silver/Gold transforms)
│   │   ├── schema_contract.py          # Data contract validation
│   │   ├── quality_profile.py          # Quality checks
│   │   ├── dashboard.py                # Dashboard logic
│   │   └── jobs.py                     # Job orchestration
│   └── notebooks/
│       ├── dlt_pipeline.py             # DLT pipeline (thin wrapper around pipeline.py)
│       └── 04_dashboard.py             # Dashboard notebook
├── sql/
│   └── validate_outputs.sql            # SQL validation queries
├── resources/
│   ├── 12_pos_inventory_analytics.pipeline.yml    # Pipeline definition
│   ├── 12_pos_inventory_analytics.job.yml         # Medallion job definition
│   └── dashboard.job.yml                          # Dashboard job definition
└── tests/
    ├── conftest.py
    ├── test_pipeline.py                # Unit tests for pipeline.py logic
    ├── test_schema_contract.py
    ├── test_quality_profile.py
    └── test_dashboard.py
```

### Job Configuration
**Job ID**: 754086303727859  
**Name**: "DEV | 12_pos_inventory_analytics | Medallion"  
**Tasks**:
1. `01_medallion_execution` — DLT pipeline execution
2. `01b_schema_and_quality_audit` — Python wheel audit task
3. `02_sql_validation` — SQL validation
4. `03_publish_analytics` — Dashboard notebook

**Recent Runs**: 3 recent successful runs (no failures)

### DLT Pipeline
**Pipeline ID**: bfd9e136-c1d9-4842-880e-a6940169e4c6  
**Name**: "DEV | 12_pos_inventory_analytics | Inventory Pipeline"  
**Type**: Serverless, Advanced Edition, Photon enabled  
**Storage**: Catalog `project_12_pos_inventory_analytics_dev`, Schema `medallion`  
**Source**: `/Volumes/project_12_pos_inventory_analytics_dev/medallion/raw_landing/pos_data`

### Data Architecture
**Medallion Stages**:
- **Bronze**: Raw incremental ingestion via Auto Loader
  - `bronze_inventory_change_raw` (streaming)
  - `bronze_inventory_snapshot_raw` (streaming)
- **Silver**: Cleaned and deduplicated
  - `silver_inventory_change` + `_quarantine`
  - `silver_inventory_snapshot` + `_quarantine`
  - `silver_latest_inventory_snapshot`
- **Gold**: Business metrics
  - `gold_inventory_current` (current inventory + safety stock alerts)
- **Reference**: Static dimension tables
  - `store_ref`
  - `item_ref`
  - `change_type_ref`
  - `supplier_ref`

**Key Features**:
- Auto Loader for incremental file ingestion
- Explicit schemas (no schema evolution issues)
- Quarantine pattern for data quality
- Safety stock alerting
- BOPIS (Buy Online Pickup In Store) support
- Channel tracking (online/in-store)

---

## Migration Strategy

### Decision: Keep Business Logic Project-Local

**Rationale**:
- This is only the 2nd project being migrated (pos_retail was first)
- Business logic in `pipeline.py` is inventory-specific (not generic medallion)
- Current `src/core/transformations/` is still pos_retail-specific
- Extract to `src/core/` only when 2+ projects share logic

**Action**: Place all business logic under `projects/pos_inventory_analytics/modules/`

### Target Framework Structure

```
projects/pos_inventory_analytics/
├── config/
│   └── project.yml                     # Data sources, environments, medallion tables
├── contracts/
│   └── schemas.yml                     # Data contracts (from schema_contract.py)
├── entry_points/
│   └── inventory_pipeline.py           # DLT pipeline (copy from dlt_pipeline.py)
├── modules/                            # ⭐ PROJECT-SPECIFIC LOGIC
│   ├── __init__.py
│   ├── pipeline.py                     # Core transforms (Bronze/Silver/Gold)
│   ├── schema_contract.py              # Contract validation
│   ├── quality_profile.py              # Quality checks
│   └── dashboard.py                    # Dashboard logic
├── sql/
│   └── validate_outputs.sql            # SQL validation
└── README.md                           # Project documentation
```

### Platform Deployment Configs

#### Databricks
Preserve existing DAB structure:
```
platforms/databricks/bundles/pos_inventory_analytics/
├── databricks.yml (copy from bundle)
├── resources/
│   ├── pipeline.yml
│   ├── medallion_job.yml
│   └── dashboard_job.yml
```

**OR** Convert to framework-native jobs (decision needed)

#### AWS
Create K8s manifests:
```
platforms/aws/k8s/manifests/
├── bronze/pos-inventory-analytics-bronze.yaml
├── silver/pos-inventory-analytics-silver.yaml
└── gold/pos-inventory-analytics-gold.yaml
```

Reference: `projects/pos_inventory_analytics/modules/pipeline.py` entry points

#### Fabric
Placeholder:
```
platforms/fabric/lakehouses/pos_inventory_analytics/
```

---

## Migration Steps (Following MIGRATION_PLAYBOOK.md)

### ✅ Step 1: Create Project Structure
- [x] Copy `projects/_template/` to `projects/pos_inventory_analytics/`
- [ ] Create `modules/` directory

### ⏳ Step 2: Extract Configuration

#### 2.1 Create `config/project.yml`
```yaml
project:
  name: pos_inventory_analytics
  description: Real-time POS inventory analytics with safety stock alerting
  version: "1.0.0"

data_sources:
  - name: inventory_events
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/landing/inventory_events
  - name: inventory_snapshots
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/landing/inventory_snapshots
  - name: store_reference
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/reference/store.csv
  - name: item_reference
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/reference/item.csv
  - name: change_type_reference
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/reference/inventory_change_type.csv
  - name: supplier_reference
    type: file
    location: /Volumes/{catalog}/{schema}/raw_landing/pos_data/reference/supplier.csv

medallion:
  bronze_tables:
    - bronze_inventory_change_raw
    - bronze_inventory_snapshot_raw
  silver_tables:
    - silver_inventory_change
    - silver_inventory_change_quarantine
    - silver_inventory_snapshot
    - silver_inventory_snapshot_quarantine
    - silver_latest_inventory_snapshot
  gold_tables:
    - gold_inventory_current
  reference_tables:
    - store_ref
    - item_ref
    - change_type_ref
    - supplier_ref

environments:
  dev:
    catalog: project_12_pos_inventory_analytics_dev
    schema: medallion
    sql_warehouse_id: cc91c315736f92f8
  test:
    catalog: project_12_pos_inventory_analytics_test
    schema: medallion
    sql_warehouse_id: cc91c315736f92f8
  prod:
    catalog: project_12_pos_inventory_analytics_prod
    schema: medallion
    sql_warehouse_id: cc91c315736f92f8
```

#### 2.2 Create `contracts/schemas.yml`
Extract from `schema_contract.py` and DLT pipeline notebook schemas:
- Bronze schemas with `_ingested_at`
- Silver schemas with quality rules
- Gold schema with safety stock calculation
- Quarantine table schemas

### ⏳ Step 3: Copy Business Logic to Modules

```bash
cp src/project_12_pos_inventory_analytics/pipeline.py    projects/pos_inventory_analytics/modules/pipeline.py

cp src/project_12_pos_inventory_analytics/schema_contract.py    projects/pos_inventory_analytics/modules/schema_contract.py

cp src/project_12_pos_inventory_analytics/quality_profile.py    projects/pos_inventory_analytics/modules/quality_profile.py

cp src/project_12_pos_inventory_analytics/dashboard.py    projects/pos_inventory_analytics/modules/dashboard.py
```

### ⏳ Step 4: Copy Entry Points

```bash
cp src/notebooks/dlt_pipeline.py    projects/pos_inventory_analytics/entry_points/inventory_pipeline.py

cp src/notebooks/04_dashboard.py    projects/pos_inventory_analytics/entry_points/dashboard.py
```

Update imports to reference `projects.pos_inventory_analytics.modules.*`

### ⏳ Step 5: Copy SQL and Tests

```bash
cp sql/validate_outputs.sql    projects/pos_inventory_analytics/sql/

cp -r tests/    projects/pos_inventory_analytics/tests/
```

Update test imports.

### ⏳ Step 6: Platform Configs

#### Option A: Preserve DAB (RECOMMENDED)
- Copy bundle structure to `platforms/databricks/bundles/pos_inventory_analytics/`
- Update paths to reference framework structure
- Keep bundle deployment workflow

#### Option B: Convert to Framework-Native
- Create new job/pipeline definitions outside bundle
- Wire into shared CI/CD

### ⏳ Step 7: Create AWS Manifests

Similar to pos-retail manifests, but:
- Reference `projects/pos_inventory_analytics/modules/pipeline.py` functions
- Configure volume paths for incremental ingestion
- Add reference data loading

### ⏳ Step 8: Testing

- [ ] Unit tests pass (test_pipeline.py, test_quality_profile.py)
- [ ] Contract tests pass (test_schema_contract.py)
- [ ] Integration test: Full pipeline run in dev
- [ ] SQL validation passes

### ⏳ Step 9: Side-by-Side Validation

Run both versions on same data:
1. Original bundle job
2. New framework job

Compare:
- Row counts per table
- Gold metrics (inventory current)
- Safety stock alerts
- Quarantine row counts

Acceptance criteria:
- Row counts match exactly
- Key metrics within 0.01% tolerance
- No unexpected quarantine rows

### ⏳ Step 10: Production Cutover

- [ ] Stakeholder approval obtained
- [ ] New framework job deployed to prod
- [ ] Original job disabled (not deleted)
- [ ] Monitor for 48 hours
- [ ] Rollback plan documented

---

## Open Questions

1. **DAB Preservation**: Should we preserve the existing DAB structure or convert to framework-native?
   - Recommendation: Preserve DAB for this project (it's working well)
   - Convert future simpler projects

2. **Shared Logic**: Any transforms reusable across projects?
   - Initial assessment: None yet (inventory-specific)
   - Re-evaluate after next project

3. **Testing Strategy**: Run full DLT pipeline in CI or just unit tests?
   - Recommendation: Unit tests in CI, full pipeline in staging

4. **Incremental Ingestion**: How to handle Auto Loader checkpoints during migration?
   - Keep existing checkpoints, point new pipeline to same location

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto Loader checkpoint conflicts | HIGH | Use separate checkpoint location initially |
| DLT pipeline schema changes | MEDIUM | Use same explicit schemas as original |
| Quarantine logic differences | LOW | Extensive unit test coverage exists |
| SQL warehouse availability | LOW | Use same warehouse ID as original |

---

## Success Criteria

- [ ] All files under `projects/pos_inventory_analytics/`
- [ ] Module imports working
- [ ] All tests passing
- [ ] Side-by-side validation: 100% row count match, < 0.01% metric deviation
- [ ] Original job still running (disabled only after 48hr monitoring)
- [ ] Platform configs created (Databricks/AWS/Fabric to current maturity)
- [ ] Documentation complete

---

## Next Actions

1. Complete config files (project.yml, schemas.yml)
2. Copy business logic to modules/
3. Update imports in entry points
4. Run unit tests
5. Deploy to dev and validate
6. Side-by-side comparison
7. Get stakeholder approval

**Estimated Time**: 2-3 days (8-12 hours of focused work)

---

**Migration Status**: 🟡 IN PROGRESS (Step 1 complete)  
**Blocking Issues**: None  
**Next Session**: Complete Step 2 (configuration files)
