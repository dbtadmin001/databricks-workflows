# Production Cutover Playbook - All 7 Projects

**Purpose**: Safe, auditable production cutover from original bundle jobs to framework-migrated pipelines.

**Strategy**: One project at a time, with 48-hour monitoring and rollback capability.

---

## Cutover Principles

1. **Non-Destructive**: Original jobs disabled, not deleted (for 30 days)
2. **Rollback Ready**: Can re-enable original job within minutes
3. **Monitored**: 48-hour observation period post-cutover
4. **Auditable**: Complete paper trail of approvals and results

---

## Pre-Cutover Requirements (Per Project)

### Technical Requirements
- ✅ Validation complete (Steps 8-9)
- ✅ Row counts match (all tables)
- ✅ Metrics within tolerance
- ✅ No new errors
- ✅ Framework deployed to prod
- ✅ Permissions verified (UC catalogs, volumes, clusters)
- ✅ Alerts configured (email, Slack)
- ✅ Monitoring dashboards created

### Business Requirements
- ✅ Stakeholder sign-off (email or ticket)
- ✅ Downtime window approved (if needed)
- ✅ Communication plan (notify downstream consumers)
- ✅ Rollback decision criteria agreed

### Documentation Requirements
- ✅ Validation results documented
- ✅ Comparison report reviewed
- ✅ Run logs archived
- ✅ Known issues documented (if any)

---

## Cutover Procedure (Standard)

### Phase 1: Pre-Cutover (1-2 hours before)

**Actions**:
1. **Final Validation Run**: Run framework version one more time in prod, verify SUCCESS, compare row counts
2. **Backup Configuration**: Export original job config via UI or API
3. **Stakeholder Notification**: Email notification including validation results, expected duration, rollback plan
4. **Monitoring Setup**: Open job run pages for both framework and original jobs, prepare monitoring dashboards

---

### Phase 2: Cutover Execution (15-30 minutes)

**Actions**:
1. **Pause Original Job**: For scheduled jobs, pause the schedule via UI. Do NOT delete. Tag with cutover_date and status=disabled_by_framework_cutover
2. **Enable Framework Job**: Ensure framework job schedule is active
3. **Manual Trigger**: Manually trigger framework job (first run post-cutover), monitor closely
4. **Immediate Validation**: Check table row counts, verify no errors, compare with last original run

---

### Phase 3: Post-Cutover Monitoring (48 hours)

**Hour 0-4** (Critical Window):
- Monitor every scheduled run
- Check email alerts
- Verify row counts match expected
- No quarantine anomalies

**Hour 4-24**:
- Monitor 2-3 scheduled runs
- Review execution times
- Check for downstream consumer issues
- Stakeholder check-in

**Hour 24-48**:
- Daily summary review
- Confirm no degradation
- Stakeholder final sign-off

---

### Phase 4: Cutover Completion (After 48 hours)

**If Successful**:
1. Document success with cutover summary
2. Update framework job tags (cutover_status=complete, cutover_date, original_job_id)
3. Archive original job after 30 days (delete via UI)

**If Rollback Needed**:
1. Re-enable original job (unpause schedule)
2. Pause framework job
3. Document rollback with detailed reason, issues observed, action items
4. Root cause analysis: investigate, fix framework issues, re-run validation, reschedule cutover

---

## Project-Specific Cutover Plans

### 1. pos_inventory_analytics

**Original Job**: 754086303727859  
**Framework Job**: TBD (deploy to prod first)  
**Dependencies**: DLT pipeline bfd9e136-c1d9-4842-880e-a6940169e4c6

**Cutover Window**: Low-traffic period (recommend 2-4 AM)  
**Downstream Consumers**: Safety stock alerts, inventory dashboard  
**Rollback Criteria**: Row count mismatch >0, safety stock alert failures, dashboard rendering errors

---

### 2. humanitarian_supply_chain

**Original Job**: 1019295447746053  
**Framework Job**: TBD  
**Schedule**: Daily 2 AM UTC  
**Dependencies**: Static CSV files in volume

**Cutover Window**: 2 AM UTC (scheduled time)  
**Downstream Consumers**: UNICEF reporting systems  
**Rollback Criteria**: Shipment count ≠ 149 valid (167 - 18 quarantined), quarantine logic changed, monthly summaries incorrect

---

### 3. nba_analytics

**Original Job**: 364963341440842  
**Framework Job**: TBD  
**Dependencies**: NBA Stats API

**Cutover Window**: Off-season or low-activity period  
**Downstream Consumers**: Player performance dashboards  
**Rollback Criteria**: API call failures, player stats incorrect, performance degradation

---

### 4. programme_funding_reconciliation

**Original Jobs**: 518546374749400 (Medallion), 224769968918180 (Analytics)  
**Framework Jobs**: TBD  
**Dependencies**: Financial data feeds

**Cutover Window**: End-of-day (after financial close)  
**Downstream Consumers**: Finance team reports  
**Rollback Criteria**: Funding amounts off by >0.001%, reconciliation variances unexpected, financial metrics incorrect

**⚠️ CRITICAL**: Financial data requires extra validation and stakeholder sign-off

---

### 5. hr_data_project

**Original Jobs**: 389295305684183 (Medallion), 774839317009851 (Analytics)  
**Framework Jobs**: TBD  
**Dependencies**: PDF documents, pypdf library

**Cutover Window**: After monthly HR close  
**Downstream Consumers**: HR analytics dashboards  
**Rollback Criteria**: PDF parsing failures, employee count mismatch, HR metrics incorrect

---

### 6. chess_grandmaster

**Original Job**: 187002625635144  
**Framework Job**: TBD  
**Dependencies**: Chess.com API

**Cutover Window**: Any (low business criticality)  
**Downstream Consumers**: Chess analytics dashboards  
**Rollback Criteria**: API connectivity failures, game count mismatches, rating calculations incorrect

---

### 7. adr_pharmacovigilance

**Original Jobs**: 949124535840052 (end-to-end), 585576372845387 (dashboard)  
**Framework Jobs**: TBD  
**Dependencies**: ADR data feeds

**Cutover Window**: After daily ADR reporting window  
**Downstream Consumers**: Pharmacovigilance reports  
**Rollback Criteria**: ADR count mismatch, severity distribution changed, dashboard errors

**⚠️ CRITICAL**: Medical data requires regulatory compliance validation

---

## Cutover Order (Recommended)

**Phase 1** (Low-Risk Projects):
1. **humanitarian_supply_chain** (static CSV, simple)
2. **nba_analytics** (low business criticality)

**Phase 2** (Moderate-Risk Projects):
3. **pos_inventory_analytics** (real-time, moderate complexity)
4. **hr_data_project** (PDF processing, HR data)

**Phase 3** (High-Risk Projects):
5. **programme_funding_reconciliation** (financial data, precision critical)
6. **adr_pharmacovigilance** (medical data, regulatory)

**Phase 4** (Optional/Deferred):
7. **chess_grandmaster** (if stable, low priority)

---

## Rollback Decision Matrix

| Severity | Criteria | Action | Timeline |
|----------|----------|--------|----------|
| **P0** | Data loss, incorrect financial data, regulatory violation | Immediate rollback | <15 min |
| **P1** | Row count mismatch, job failures, downstream errors | Rollback within 1 hour | <1 hour |
| **P2** | Performance degradation >30%, minor metric differences | Monitor, rollback if worsens | 4-24 hours |
| **P3** | Non-critical warnings, cosmetic issues | Document, fix in next release | No rollback |

---

## Communication Templates

### Pre-Cutover Email
```
Subject: [CUTOVER] <project_name> - Scheduled for <date> at <time>

Team,

We are proceeding with the production cutover for <project_name> from the original bundle implementation to the framework-migrated pipeline.

Cutover Details:
- Date: <YYYY-MM-DD>
- Time: <HH:MM TZ>
- Expected Duration: 15-30 minutes
- Validation Status: Complete (row counts match, metrics within tolerance)

During Cutover:
- Original job will be paused (not deleted)
- Framework job will take over
- First framework run will be manually triggered and monitored

Post-Cutover:
- 48-hour monitoring period
- Rollback capability maintained for 30 days
- Daily status updates

Stakeholder Approval:
- [X] <stakeholder_name> - approved on <date>

Questions? Reply to this email.

Regards,
<your_name>
```

### Post-Cutover Success Email
```
Subject: [CUTOVER COMPLETE] <project_name> - Success

Team,

The production cutover for <project_name> is complete and successful.

Results:
- Cutover Date: <YYYY-MM-DD HH:MM>
- Framework Job: <framework_job_id>
- Runs Since Cutover: <count>
- All runs: SUCCESS
- Row counts: Match expected
- Metrics: Within tolerance
- Downstream consumers: No issues reported

Original job <original_job_id> is paused and will be deleted after 30 days.

Monitoring will continue for the next 48 hours. Please report any issues immediately.

Regards,
<your_name>
```

### Rollback Email
```
Subject: [ROLLBACK] <project_name> - Rollback Executed

Team,

A rollback has been executed for <project_name> due to issues observed during the cutover monitoring period.

Rollback Details:
- Rollback Date: <YYYY-MM-DD HH:MM>
- Reason: <detailed reason>
- Original job re-enabled: <original_job_id>
- Framework job paused: <framework_job_id>

Issues Observed:
- <issue 1>
- <issue 2>

Next Steps:
1. Root cause analysis
2. Fix framework implementation
3. Re-run validation
4. Reschedule cutover

The original pipeline is now active and functioning normally.

Regards,
<your_name>
```

---

## Post-Cutover Review (30 days)

**Review Checklist**:
- [ ] All 7 projects cutover complete
- [ ] No active rollbacks
- [ ] Downstream consumers satisfied
- [ ] Performance metrics stable
- [ ] Original jobs deleted (after 30-day grace period)
- [ ] Documentation updated
- [ ] Lessons learned documented

**Metrics to Review**:
- Total cutover duration (per project)
- Rollback count (target: 0)
- Post-cutover issues (count)
- Downstream consumer feedback
- Cost comparison (original vs framework)

---

## Success Criteria (Overall)

**Phase 3 Complete**:
- ✅ All 7 projects migrated (Steps 1-10)
- ✅ All projects running on framework in prod
- ✅ Zero active issues
- ✅ Stakeholder satisfaction confirmed
- ✅ Original jobs archived
- ✅ Documentation complete

---

**Prepared by**: Databricks Assistant  
**Date**: July 24, 2026  
**Status**: READY FOR EXECUTION  
**Estimated Duration**: 4-6 weeks (phased cutover)