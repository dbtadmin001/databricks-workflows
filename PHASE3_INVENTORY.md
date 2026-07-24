
================================================================================
PHASE 3A: DATABRICKS PORTFOLIO INVENTORY & CLASSIFICATION
Generated: 2026-07-24
================================================================================

SUMMARY
-------
- Total Projects Identified: 8
- Already Migrated: 1 (pos_retail)
- Pending Migration: 7
- Jobs: 13
- Pipelines (DLT): 3

================================================================================
PROJECT CLASSIFICATION
================================================================================

┌────────────────────────────────────────────────────────────────────────────┐
│ PRODUCTION PROJECTS (Active, business-critical, scheduled or frequent runs)│
└────────────────────────────────────────────────────────────────────────────┘

1. HUMANITARIAN_SUPPLY_CHAIN ⭐ HIGH PRIORITY
   ├─ Status: PRODUCTION
   ├─ Schedule: Daily at 2AM UTC (0 0 2 * * ?)
   ├─ Assets:
   │  ├─ Job: "Humanitarian Supply Chain ETL Orchestration" [1019295447746053]
   │  │     - Scheduled, email alerts on failure
   │  │     - Last run: SUCCESS (2026-07-21)
   │  └─ Pipeline: "Humanitarian Supply Chain Medallion" [ae4f06ca-11ee-458e-a081-6382026093d4]
   ├─ Medallion Stages: Likely Bronze → Silver → Gold (needs verification)
   ├─ Complexity: MEDIUM (has pipeline + orchestration job)
   ├─ Existing Tests: Unknown (needs inspection)
   └─ Business Value: HIGH (scheduled prod job, email monitoring)

2. CHESS_GRANDMASTER ⚠️  NEEDS INVESTIGATION
   ├─ Status: PRODUCTION (tagged as "prod")
   ├─ Schedule: None (manual trigger)
   ├─ Assets:
   │  └─ Job: "[prod] chess_grandmaster_end_to_end" [187002625635144]
   │        - Recent runs: 2 FAILED, 1 SUCCESS
   │        - Failure: "Task source_connectivity failed"
   ├─ Medallion Stages: Unknown (multi-task job, needs inspection)
   ├─ Complexity: MEDIUM (multi-task, connectivity issues)
   ├─ Existing Tests: Unknown
   └─ Business Value: MEDIUM (prod-tagged but unstable)

3. POS_INVENTORY_ANALYTICS ✅ PATTERN EXISTS
   ├─ Status: ACTIVE DEVELOPMENT → PRODUCTION CANDIDATE
   ├─ Schedule: None (manual trigger)
   ├─ Assets:
   │  ├─ Job (Medallion): "DEV | 12_pos_inventory_analytics | Medallion" [754086303727859]
   │  │     - Multiple recent successful runs
   │  │     - Bundle-managed (DAB)
   │  ├─ Job (Analytics): "DEV | 12_pos_inventory_analytics | Analytics" [654124852702488]
   │  │     - Dashboard/visualization workload
   │  └─ Pipeline: "DEV | 12_pos_inventory_analytics | Inventory Pipeline" [bfd9e136-c1d9-4842-880e-a6940169e4c6]
   ├─ Medallion Stages: Bronze → Silver → Gold + Analytics Dashboard
   ├─ Complexity: MEDIUM (bundle-managed, has pipeline + analytics)
   ├─ Existing Tests: Unknown (bundle structure suggests some)
   ├─ Bundle Location: /Workspace/Users/albertraviss@gmail.com/.bundle/project_12_pos_inventory_analytics/
   └─ Business Value: HIGH (mirrors pos_retail pattern, most mature)
   └─ NOTE: This appears to be a separate POS inventory project from pos_retail

4. NBA_ANALYTICS
   ├─ Status: ACTIVE DEVELOPMENT
   ├─ Schedule: None
   ├─ Assets:
   │  ├─ Job: "DEV | 13_nba_analytics | Analytics" [364963341440842]
   │  │     - Recent run: SUCCESS (2026-07-20)
   │  └─ Pipeline: "NBA Medallion Pipeline" [d77a9048-11dd-43c4-a976-3f013bff8bd0]
   ├─ Medallion Stages: Likely Bronze → Silver → Gold (pipeline + analytics)
   ├─ Complexity: MEDIUM (bundle-managed, sports analytics)
   ├─ Existing Tests: Unknown
   ├─ Bundle Location: /Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/project_13_nba_analytics/
   └─ Business Value: MEDIUM (active, clean runs)

5. HR_DATA_PROJECT
   ├─ Status: ACTIVE DEVELOPMENT (unstable)
   ├─ Schedule: None
   ├─ Assets:
   │  ├─ Job (Medallion): "DEV | hr_data_project | Medallion" [389295305684183]
   │  │     - Recent runs: 2 SUCCESS, 1 FAILED
   │  │     - Failure: "Task 01_bronze_ingestion failed"
   │  │     - Dependencies: pypdf>=5,<7 (PDF processing)
   │  └─ Job (Analytics): "DEV | hr_data_project | Analytics" [774839317009851]
   ├─ Medallion Stages: Bronze → Silver → Gold + Analytics
   ├─ Complexity: MEDIUM-HIGH (PDF ingestion, data extraction)
   ├─ Existing Tests: Unknown
   ├─ Bundle Location: /Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/hr_data_project/
   └─ Business Value: MEDIUM (active but needs stabilization)

6. PROGRAMME_FUNDING_RECONCILIATION
   ├─ Status: ACTIVE DEVELOPMENT
   ├─ Schedule: None
   ├─ Assets:
   │  ├─ Job (Medallion): "DEV | 08_programme_funding_reconciliation | Medallion" [518546374749400]
   │  └─ Job (Analytics): "DEV | 08_programme_funding_reconciliation | Analytics" [224769968918180]
   ├─ Medallion Stages: Bronze → Silver → Gold + Reconciliation + Analytics
   ├─ Complexity: MEDIUM-HIGH (reconciliation logic, funding insights)
   ├─ Existing Tests: Unknown
   ├─ Bundle Location: /Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/project_08_programme_funding_reconciliation/
   └─ Business Value: MEDIUM (financial reconciliation, important but dev)

┌────────────────────────────────────────────────────────────────────────────┐
│ EXPERIMENTAL / TEST PROJECTS (generic names, minimal business logic)       │
└────────────────────────────────────────────────────────────────────────────┘

7. NEWPROJECT ⛔ EXPERIMENTAL
   ├─ Status: TEST/DEMO PROJECT
   ├─ Classification Rationale:
   │  - Generic name "newproject" (not a real business domain)
   │  - Recent runs but likely template/scaffold testing
   │  - Dependencies: pypdf, plotly (common test stack)
   ├─ Assets:
   │  ├─ Job (Medallion): "DEV | newproject | Medallion" [150098697225848]
   │  └─ Job (Analytics): "DEV | newproject | Analytics" [817891176449745]
   ├─ Bundle Location: /Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/newproject/
   └─ RECOMMENDATION: DO NOT MIGRATE (scaffold/template, not production data)

┌────────────────────────────────────────────────────────────────────────────┐
│ LEGACY / UNCERTAIN (needs stakeholder confirmation)                        │
└────────────────────────────────────────────────────────────────────────────┘

8. ADR_PHARMACOVIGILANCE ⚠️  UNCLEAR STATUS
   ├─ Status: UNKNOWN (inconsistent naming, fewer runs)
   ├─ Assets:
   │  ├─ Job: "[dev data_automation_services] [dev] project_10_adr_pharmacovigilance_end_to_end" [949124535840052]
   │  └─ Job: "[dev data_automation_services] [dev] project_10_adr_pharmacovigilance_insights_dashboard" [585576372845387]
   ├─ Classification Rationale:
   │  - Inconsistent naming pattern (different from other DEV jobs)
   │  - No recent run history visible in sample
   │  - Medical/pharma domain (could be important)
   ├─ Bundle Location: /Workspace/Users/e553c7e6-ec16-4dba-b19d-39f24d43486b/.bundle/project_10_adr_pharmacovigilance/
   └─ RECOMMENDATION: CONFIRM with stakeholders before migrating

================================================================================
MIGRATION PRIORITY & ORDER
================================================================================

Tier 1 — IMMEDIATE (Production-critical or pattern-validated)
──────────────────────────────────────────────────────────────
1. pos_inventory_analytics (12)         [✅ READY - bundle pattern exists]
   - Rationale: Bundle-managed, recent successful runs, clear medallion structure
   - Estimated Effort: 2-3 days
   - Risk: LOW (similar to pos_retail)

2. humanitarian_supply_chain            [⚠️  SCHEDULED PRODUCTION]
   - Rationale: Only scheduled job, email monitoring, business-critical
   - Estimated Effort: 3-4 days
   - Risk: MEDIUM (prod cutover requires careful validation)

Tier 2 — HIGH VALUE (Active projects with business logic)
──────────────────────────────────────────────────────────
3. nba_analytics (13)                   [✅ CLEAN RUNS]
   - Rationale: Clean recent runs, bundle-managed, sports analytics
   - Estimated Effort: 2-3 days
   - Risk: LOW

4. programme_funding_reconciliation (08) [📊 FINANCIAL DATA]
   - Rationale: Financial reconciliation, important domain
   - Estimated Effort: 3-4 days (reconciliation logic complexity)
   - Risk: MEDIUM

5. hr_data_project                      [📄 PDF PROCESSING]
   - Rationale: Active development, PDF ingestion (unique capability)
   - Estimated Effort: 3-4 days (PDF extraction complexity)
   - Risk: MEDIUM (recent failures, needs stabilization)

Tier 3 — INVESTIGATE FIRST
───────────────────────────
6. chess_grandmaster                    [⚠️  UNSTABLE]
   - Rationale: Prod-tagged but failing, needs investigation first
   - Estimated Effort: TBD (depends on connectivity issue resolution)
   - Risk: HIGH (source_connectivity failures)
   - Action: Debug connectivity issues before migration

7. adr_pharmacovigilance (10)           [❓ CONFIRM STATUS]
   - Rationale: Unclear activity level, important domain
   - Estimated Effort: TBD
   - Risk: UNKNOWN
   - Action: Confirm with stakeholders if this is active/needed

Tier 4 — DO NOT MIGRATE
────────────────────────
8. newproject                           [⛔ EXPERIMENTAL]
   - Rationale: Generic name, test/scaffold project
   - Action: Leave in place, do not migrate to production framework

================================================================================
PROPOSED MIGRATION SCHEDULE
================================================================================

Week 1:
  Days 1-3: pos_inventory_analytics (12)
  Days 4-5: Begin humanitarian_supply_chain investigation

Week 2:
  Days 1-3: Complete humanitarian_supply_chain migration
  Days 4-5: nba_analytics (13)

Week 3:
  Days 1-3: programme_funding_reconciliation (08)
  Days 4-5: hr_data_project

Week 4:
  Days 1-2: chess_grandmaster (if connectivity resolved)
  Days 3-5: adr_pharmacovigilance (10) if confirmed needed

================================================================================
GAPS & QUESTIONS FOR CONFIRMATION
================================================================================

1. chess_grandmaster: What is the "source_connectivity" task doing? 
   - Is there an API/external system dependency?
   - Should we fix connectivity before migration?

2. adr_pharmacovigilance: Is this project still active?
   - Last run date unclear from sample
   - Stakeholder confirmation needed

3. newproject: Confirm this is test/scaffold
   - If it's a real project with a temporary name, rename before migration
   - Otherwise exclude from production framework

4. pos_retail vs pos_inventory_analytics:
   - Are these the same project or different?
   - pos_retail is already migrated — is 12_pos_inventory_analytics a new/separate project?

5. Existing bundle structures:
   - Several projects already use DABs (Databricks Asset Bundles)
   - Should we preserve their bundle structure or convert to our framework?
   - Recommendation: Convert to unified framework for consistency

================================================================================
NEXT STEPS
================================================================================

AWAITING CONFIRMATION:
1. Approve classification (Production vs Experimental vs Legacy)
2. Confirm migration order (or suggest changes)
3. Answer gaps/questions above
4. Approve non-migration of "newproject"

ONCE APPROVED:
1. Begin Phase 3B: Extract reference pattern from pos_retail
2. Create migration playbook/template
3. Start Tier 1 migrations one at a time

================================================================================
