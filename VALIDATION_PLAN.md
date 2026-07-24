# Side-by-Side Validation Plan - All 7 Projects

**Purpose**: Validate that framework-migrated pipelines produce identical results to original bundle implementations before production cutover.

**Validation Strategy**: Row-level comparison + metric validation + quarantine comparison

---

## Validation Approach

### Phase 1: Deployment
1. Deploy framework version to **dev** environment
2. Keep original bundle job running (do not disable)
3. Run both versions side-by-side for 3-5 runs

### Phase 2: Comparison
1. **Row Count Validation**: Exact match required
2. **Key Metrics Validation**: <0.01% tolerance
3. **Schema Validation**: Column names, types, nullability
4. **Quarantine Validation**: Same records quarantined
5. **Execution Time**: Within 20% of original

### Phase 3: Sign-Off
1. Document comparison results
2. Stakeholder review
3. Production cutover approval

---

## Project-Specific Validation

### 1. pos_inventory_analytics

**Original Job**: 754086303727859  
**Framework Location**: `projects/pos_inventory_analytics/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | bronze_inventory_change_raw | Row count | Exact |
| Bronze | bronze_inventory_snapshot_raw | Row count | Exact |
| Silver | silver_inventory_change | Row count + dedup check | Exact |
| Silver | silver_inventory_change_quarantine | Row count + reasons | Exact |
| Silver | silver_inventory_snapshot | Row count | Exact |
| Silver | silver_latest_inventory_snapshot | Row count + window logic | Exact |
| Gold | gold_inventory_current | Row count + metrics | <0.01% |

**Key Metrics**:
- Total items below safety stock (count)
- Total stores with alerts (count)
- Average inventory coverage (%)
- BOPIS transaction count

**Validation SQL**:
```sql
-- Row count comparison
SELECT 'original' as source, COUNT(*) as row_count 
FROM project_12_pos_inventory_analytics_dev.medallion.gold_inventory_current
UNION ALL
SELECT 'framework' as source, COUNT(*) as row_count 
FROM project_12_pos_inventory_analytics_dev.medallion.gold_inventory_current_framework;

-- Metric comparison
SELECT 
  SUM(CASE WHEN below_safety_stock THEN 1 ELSE 0 END) as items_below_threshold,
  COUNT(DISTINCT store_id) as total_stores,
  AVG(current_quantity) as avg_inventory
FROM gold_inventory_current;
```

**Expected Runtime**: ~5-10 minutes (original vs framework within 20%)

---

### 2. humanitarian_supply_chain

**Original Job**: 1019295447746053  
**Framework Location**: `projects/humanitarian_supply_chain/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | bronze_warehouses | Row count | Exact (6 rows) |
| Bronze | bronze_programmes | Row count | Exact (5 rows) |
| Bronze | bronze_items | Row count | Exact (7 rows) |
| Bronze | bronze_shipments | Row count | Exact (167 rows) |
| Silver | silver_shipments | Row count + dedup | Exact |
| Silver | silver_shipments_quarantine | Row count + reasons | Exact (18 rows) |
| Gold | fact_shipments | Row count + enrichment | Exact |
| Gold | programme_monthly_summary | Row count + aggregations | <0.01% |

**Key Metrics**:
- Total shipments (count): 167 - 18 (quarantined) = 149 valid
- Quarantined shipments: 18 (6 orphan WH099, 12 orphan PRG999)
- Total cost (sum): Aggregate of QUANTITY × UNIT_COST
- Distinct programmes: 5

**Validation SQL**:
```sql
-- Shipment counts
SELECT 
  COUNT(*) as total_bronze,
  SUM(CASE WHEN shipment_id IN (SELECT shipment_id FROM silver_shipments) THEN 1 ELSE 0 END) as valid_silver,
  SUM(CASE WHEN shipment_id IN (SELECT shipment_id FROM silver_shipments_quarantine) THEN 1 ELSE 0 END) as quarantined
FROM bronze_shipments;

-- Known defects check
SELECT 
  SUM(CASE WHEN warehouse_id = 'WH099' THEN 1 ELSE 0 END) as orphan_wh099,
  SUM(CASE WHEN programme_id = 'PRG999' THEN 1 ELSE 0 END) as orphan_prg999
FROM silver_shipments_quarantine;
```

**Expected Runtime**: ~2-5 minutes (static CSV, fast)

---

### 3. nba_analytics

**Original Job**: 364963341440842  
**Framework Location**: `projects/nba_analytics/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | bronze_games | Row count | Exact |
| Bronze | bronze_players | Row count | Exact |
| Silver | silver_games_enriched | Row count | Exact |
| Silver | silver_player_stats | Row count | Exact |
| Gold | gold_player_performance | Row count + metrics | <0.01% |
| Gold | gold_team_analytics | Row count + aggregations | <0.01% |

**Key Metrics**:
- Player count (distinct)
- Game count (distinct)
- Average points per game
- Top 10 scorers

**Expected Runtime**: ~10-15 minutes (API calls)

---

### 4. programme_funding_reconciliation

**Original Jobs**: 518546374749400 (Medallion), 224769968918180 (Analytics)  
**Framework Location**: `projects/programme_funding_reconciliation/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | All bronze tables | Row count | Exact |
| Silver | All silver tables | Row count + reconciliation | Exact |
| Gold | All gold tables | Row count + financial metrics | <0.001% |

**Key Metrics**:
- Total funding amount (sum) — financial precision critical
- Reconciliation variances (must be 0 or within tolerance)
- Programme counts
- Funding by source

**Expected Runtime**: ~10-15 minutes

---

### 5. hr_data_project

**Original Jobs**: 389295305684183 (Medallion), 774839317009851 (Analytics)  
**Framework Location**: `projects/hr_data_project/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | All bronze tables | Row count + PDF parsing | Exact |
| Silver | All silver tables | Row count | Exact |
| Gold | All gold tables | Row count + HR metrics | <0.01% |

**Key Metrics**:
- Employee count (distinct)
- PDF documents processed
- HR metrics (turnover, headcount, etc.)

**Dependencies**: pypdf (verify parsing consistency)

**Expected Runtime**: ~15-20 minutes (PDF processing)

---

### 6. chess_grandmaster

**Original Job**: 187002625635144  
**Framework Location**: `projects/chess_grandmaster/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | chess_bronze_pubapi | Row count + API data | Exact |
| Silver | chess_silver_games | Row count + dedup | Exact |
| Silver | chess_quarantine_games | Row count + reasons | Exact |
| Gold | chess_gold_rating_progression | Row count + rating calc | <0.01% |
| Gold | chess_gold_player_summary | Row count + aggregations | <0.01% |
| Gold | chess_gold_daily_activity | Row count + daily agg | <0.01% |
| Gold | chess_gold_player_segment | Row count + segmentation | Exact |
| Gold | chess_gold_opening_performance | Row count + opening stats | <0.01% |

**Key Metrics**:
- Game count per player
- Rating progression accuracy
- Opening performance stats

**API Dependency**: Chess.com API (validate source_connectivity first)

**Expected Runtime**: ~20-30 minutes (API + complex transformations)

---

### 7. adr_pharmacovigilance

**Original Jobs**: 949124535840052 (end-to-end), 585576372845387 (dashboard)  
**Framework Location**: `projects/adr_pharmacovigilance/`

**Tables to Validate**:
| Layer | Table | Validation Type | Tolerance |
|-------|-------|-----------------|-----------|
| Bronze | All bronze tables | Row count | Exact |
| Silver | All silver tables | Row count + medical data quality | Exact |
| Gold | All gold_wap tables | Row count + ADR metrics | <0.01% |

**Key Metrics**:
- ADR report count
- Severity distribution
- Drug-reaction correlations

**Expected Runtime**: ~10-15 minutes

---

## Validation Execution Order

### Recommended Order (by complexity)
1. **humanitarian_supply_chain** (simplest, static CSV)
2. **programme_funding_reconciliation** (financial, precise)
3. **pos_inventory_analytics** (moderate complexity)
4. **nba_analytics** (API-based)
5. **hr_data_project** (PDF processing)
6. **adr_pharmacovigilance** (medical domain)
7. **chess_grandmaster** (most complex, API + many Gold tables)

---

## Validation Checklist (Per Project)

### Pre-Validation
- [ ] Framework code deployed to dev
- [ ] Original bundle job still running
- [ ] Test data available in landing zones
- [ ] Catalogs/schemas created with correct permissions

### During Validation
- [ ] Run framework version (3-5 times)
- [ ] Run original version (same data)
- [ ] Capture row counts for all tables
- [ ] Capture key metrics
- [ ] Compare execution times
- [ ] Document any discrepancies

### Post-Validation
- [ ] All row counts match (exact or within tolerance)
- [ ] All metrics match (<0.01% tolerance for aggregations)
- [ ] No new errors in framework version
- [ ] Execution time within 20% of original
- [ ] Stakeholder sign-off
- [ ] Production cutover approved

---

## Discrepancy Resolution

**If row counts don't match**:
1. Check for missing/extra files in landing zone
2. Verify deduplication logic
3. Compare Bronze timestamps (_ingested_at)
4. Check for schema evolution issues

**If metrics don't match**:
1. Verify aggregation logic (SUM, AVG, COUNT)
2. Check for NULL handling differences
3. Validate join keys and conditions
4. Compare sample records row-by-row

**If execution time differs >20%**:
1. Check cluster configuration (framework vs original)
2. Verify Photon/serverless settings
3. Review query plans (EXPLAIN)
4. Optimize if framework is slower

---

## Success Criteria

**Required for Production Cutover**:
1. ✅ Row counts match (all tables)
2. ✅ Key metrics within tolerance
3. ✅ No new errors
4. ✅ Execution time acceptable
5. ✅ Stakeholder approval

**Red Flags** (block cutover):
- ❌ Row count mismatch >0 rows
- ❌ Financial metrics off by >0.001%
- ❌ New quarantine reasons not in original
- ❌ Framework consistently slower (>30%)
- ❌ Stakeholder concerns unresolved

---

## Timeline

**Per Project**:
- Validation runs: 1-2 hours
- Result comparison: 30 minutes
- Documentation: 30 minutes
- Stakeholder review: 1-2 days

**Total (7 projects, sequential)**:
- Technical validation: ~2 weeks
- Stakeholder reviews: 1-2 weeks
- Production cutover: 1 week

**Total Phase 9 Duration**: 4-5 weeks

---

**Prepared by**: Databricks Assistant  
**Date**: July 24, 2026  
**Status**: READY FOR EXECUTION
