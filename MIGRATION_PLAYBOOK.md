# PROJECT MIGRATION PLAYBOOK

**Version**: 1.0  
**Based on**: pos_retail reference pattern  
**Target Framework**: Multi-platform medallion (Databricks, AWS, Fabric)

---

## Overview

This playbook guides the migration of a project from standalone Databricks notebooks/jobs into the unified multi-platform framework under `projects/<name>/`.

## Pre-Migration Checklist

- [ ] Project identified in Phase 3A inventory
- [ ] Migration priority/tier assigned
- [ ] Run history analyzed (at least 3 recent runs)
- [ ] Source notebooks/jobs located
- [ ] Data sources identified
- [ ] Existing tests cataloged
- [ ] Dependencies documented (libraries, external APIs)
- [ ] Medallion stages confirmed (Bronze/Silver/Gold/other)

---

## Migration Steps

### Step 1: Create Project Structure

```bash
cd /Workspace/Repos/<user>/databricks-workflows
mkdir -p projects/<project_name>/{config,contracts,entry_points}
```

**Files to create:**
1. `projects/<project_name>/config/project.yml`
2. `projects/<project_name>/contracts/schemas.yml`
3. `projects/<project_name>/README.md`
4. `projects/<project_name>/entry_points/` (SQL/notebook entry points)

**Template locations:**
- See `projects/pos_retail/` for reference structure

### Step 2: Extract and Document Configuration

#### 2.1 Analyze Original Project

Inspect original job details, source notebooks. Note:
- Data sources
- Table names
- Transformation logic
- Dependencies

#### 2.2 Create `project.yml`

Document:
- **Project metadata**: name, description, version
- **Data sources**: all input tables/files with locations
- **Medallion tables**: Bronze/Silver/Gold table names
- **Environments**: dev/test/prod catalog/schema mappings

Example:
```yaml
project:
  name: <project_name>
  description: <business purpose>
  version: "1.0.0"

data_sources:
  - name: source_table_1
    type: table
    location: catalog.schema.table

medallion:
  bronze_tables:
    - bronze_<entity>
  silver_tables:
    - silver_<entity>_enriched
  gold_tables:
    - gold_<metric>

environments:
  dev:
    catalog: workspace
    schema: <project_name>_dev
  test:
    catalog: workspace
    schema: <project_name>_test
  prod:
    catalog: workspace
    schema: <project_name>_prod
```

### Step 3: Define Data Contracts

Create `contracts/schemas.yml`:

```yaml
bronze_<entity>:
  description: Raw data with audit columns
  columns:
    - name: <column>
      type: string|int|timestamp
      nullable: true|false
      constraints:
        - type: positive|unique|pattern
          message: "Constraint description"

silver_<entity>:
  description: Enriched/cleaned data
  quality_rules:
    - name: rule_name
      rule: "SQL expression"
      action: drop|warn|fail

gold_<metric>:
  description: Business-level aggregation
  grain:
    - dimension_1
    - dimension_2
  aggregations:
    - metric_1
    - metric_2
```

### Step 4: Migrate Transformation Logic

#### Decision Tree: Where Does Code Go?

```
Is this transformation used by multiple projects?
├─ YES → Extract to src/core/transformations/<stage>/
└─ NO  → Keep in projects/<project_name>/modules/

Is this a standard medallion stage (Bronze/Silver/Gold)?
├─ YES → Use src/core/transformations/<stage>/
└─ NO  → Document as custom stage, keep project-local
```

#### 4.1 For Code Going to `src/core/`

**Only if reusable by 2+ projects:**

```python
# src/core/transformations/bronze/<entity>.py
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(
    name="bronze_<entity>",
    comment="<description>",
    table_properties={"quality": "bronze"}
)
def bronze_<entity>():
    return (
        spark.read.table("<source_table>")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit("<source_table>"))
    )
```

#### 4.2 For Project-Specific Code

Keep under `projects/<project_name>/modules/`:

```python
# projects/<project_name>/modules/custom_logic.py
def project_specific_transform(df):
    # Custom business logic
    return df.transform(...)
```

### Step 5: Create Entry Points

Thin orchestration scripts that reference shared logic:

```sql
-- projects/<project_name>/entry_points/<project_name>_pipeline.sql
-- Bronze
CREATE OR REFRESH STREAMING LIVE TABLE bronze_<entity>
AS SELECT * FROM LIVE.bronze_<entity>();

-- Silver
CREATE OR REFRESH STREAMING LIVE TABLE silver_<entity>_enriched
AS SELECT * FROM LIVE.silver_<entity>_enriched();

-- Gold
CREATE OR REFRESH LIVE TABLE gold_<metric>
AS SELECT * FROM LIVE.gold_<metric>();
```

### Step 6: Platform Deployment Configs

#### 6.1 Databricks

Wire into existing deployment framework:
- Use `TARGET_PLATFORM=databricks` deployment
- Create job/pipeline definitions

#### 6.2 AWS (K8s + Spark Operator)

Create manifests for each medallion stage:

```bash
platforms/aws/k8s/manifests/
├─ bronze/<project_name>-bronze.yaml
├─ silver/<project_name>-silver.yaml
└─ gold/<project_name>-gold.yaml
```

Template:
```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: <project_name>-<stage>
  namespace: spark-jobs
spec:
  type: Python
  mainApplicationFile: local:///opt/spark/work-dir/src/core/transformations/<stage>/<entity>.py
  image: "<ECR_REGISTRY>/<project_name>-spark:<GIT_SHA>"
  # ... (see pos-retail-bronze.yaml for full spec)
```

#### 6.3 Fabric

**Currently stub-only** — create placeholder directory:
```bash
mkdir -p platforms/fabric/lakehouses/<project_name>
```

### Step 7: Tests

#### 7.1 Unit Tests

```python
# tests/unit/test_<project_name>_transformations.py
import pytest
from src.core.transformations.bronze.<entity> import bronze_<entity>

def test_bronze_<entity>_adds_audit_columns():
    # Test logic
    pass
```

#### 7.2 Contract Tests

Validate schemas match `contracts/schemas.yml`:

```python
# tests/contracts/test_<project_name>_contracts.py
def test_bronze_<entity>_schema():
    # Load expected schema from contracts/schemas.yml
    # Compare to actual table schema
    pass
```

#### 7.3 SCD2 Invariant Tests (if applicable)

Only if project uses SCD2 (slowly changing dimensions):

```python
# tests/scd2/test_<project_name>_scd2.py
def test_no_overlapping_validity_periods():
    # Validate effective_date/end_date ranges don't overlap per key
    pass
```

### Step 8: CI/CD Integration

Add project to `.github/workflows/deploy-databricks.yml`:

```yaml
jobs:
  deploy-<project_name>:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy <project_name>
        run: |
          TARGET_PLATFORM=databricks \
          ENVIRONMENT=${{ github.ref == 'refs/heads/main' && 'prod' || 'dev' }} \
          PROJECT_NAME=<project_name> \
          CONFIG_PATH=projects/<project_name>/config/project.yml \
          ./scripts/deploy.sh
```

### Step 9: Side-by-Side Validation

**CRITICAL: Do NOT disable original job until parity confirmed**

1. Deploy new framework-based version to dev/test
2. Run both versions on same input data
3. Compare outputs:
   ```sql
   -- Row count comparison
   SELECT COUNT(*) FROM <original_table>;
   SELECT COUNT(*) FROM <new_table>;
   
   -- Key aggregate comparison
   SELECT SUM(<metric>), AVG(<metric>) FROM <original_table>;
   SELECT SUM(<metric>), AVG(<metric>) FROM <new_table>;
   
   -- Full outer join to find differences
   SELECT * FROM <original_table> o
   FULL OUTER JOIN <new_table> n
   ON o.key = n.key
   WHERE o.key IS NULL OR n.key IS NULL;
   ```

4. Document any differences
5. Get stakeholder approval for cutover

### Step 10: Production Cutover

1. **Scheduled jobs**: Update schedule to point to new job, disable old schedule
2. **On-demand jobs**: Switch references, archive old job
3. **Pipelines**: Update upstream/downstream dependencies
4. **Monitor**: Watch for 24-48 hours, have rollback plan ready

---

## Post-Migration Checklist

- [ ] New project deployed successfully to dev/test/prod
- [ ] Side-by-side validation passed (row counts, key metrics match)
- [ ] All tests passing in CI
- [ ] Original job disabled/archived (NOT deleted yet)
- [ ] Documentation updated (README, runbooks)
- [ ] Platform configs created for Databricks/AWS/Fabric (to current adapter maturity)
- [ ] Stakeholder sign-off obtained
- [ ] Monitoring/alerts configured

---

## Common Issues & Solutions

### Issue: Transformation logic is tightly coupled to original notebook

**Solution**: Refactor into functions first, then migrate incrementally

### Issue: Hard-coded paths/table names

**Solution**: Parameterize using `project.yml` config, pass as environment variables

### Issue: External API dependencies

**Solution**: Document in `project.yml`, ensure credentials/network access in target platform

### Issue: Complex reconciliation logic (not Bronze/Silver/Gold)

**Solution**: Add custom stages under `projects/<project_name>/stages/`, document architecture decision

### Issue: Existing DAB conflicts with framework structure

**Solution**: Convert DAB to framework structure OR preserve DAB and wire into framework via thin wrapper

---

## Success Criteria

A migration is complete when:

1. ✅ Project exists under `projects/<project_name>/` with all required files
2. ✅ Transformation logic extracted (shared to `src/core/`, project-specific local)
3. ✅ Platform configs created (Databricks, AWS to current maturity, Fabric placeholder)
4. ✅ All tests passing (unit, contract, SCD2 if applicable)
5. ✅ CI/CD integrated
6. ✅ Side-by-side validation passed
7. ✅ Original job left running until cutover approved
8. ✅ Production cutover completed successfully

---

## Rollback Plan

If issues arise post-migration:

1. **Immediate**: Re-enable original job/pipeline
2. **Investigate**: Identify root cause (data diff, performance, errors)
3. **Fix Forward**: If quick fix possible (< 1 hour), fix and redeploy
4. **Full Rollback**: If complex issue, rollback to original, document lessons learned

---

## Reference: pos_retail Pattern

**Structure:**
```
projects/pos_retail/
├─ config/project.yml          # Data sources, environments, medallion tables
├─ contracts/schemas.yml       # Data contracts, quality rules
├─ entry_points/               # Thin SQL/notebook orchestration
└─ README.md                   # Project overview
```

**Shared logic:**
```
src/core/transformations/
├─ bronze/bronze_tables.py     # Raw ingestion + audit columns
├─ silver/silver_tables.py     # Enrichment + cleaning
└─ gold/gold_tables.py         # Business aggregations
```

**Platform configs:**
```
platforms/
├─ databricks/                 # Jobs/pipelines (via DAB or direct)
├─ aws/k8s/manifests/          # SparkApplication CRDs per stage
└─ fabric/                     # Placeholder (stub)
```

**Tests:**
```
tests/
├─ unit/test_transformations.py      # Logic correctness
├─ contracts/test_schemas.py         # Contract validation
└─ scd2/test_invariants.py           # SCD2 rules (if applicable)
```

---

**End of Playbook**
