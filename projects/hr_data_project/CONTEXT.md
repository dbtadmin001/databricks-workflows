# Current Project Context

## Identity

- Project: `hr_data_project` - HR Data Workforce Planning
- Execution profile: `TIMED_MVP`, classified `AI_NLP` because sources mix PDF, DOCX,
  image, Excel, and qualitative workforce-signal extraction
- Current milestone: implementation validation
- Next action: run focused local checks, refresh architecture, then Docker compatibility

## Continuation Checkpoint

- Branch / head commit: `fix/explicit-pipeline-requirement-audit`
- Files currently changed: project implementation/docs/data copy plus
  `orchestration/scripts/init_project.py` null-milestone bug fix
- Last completed gate: focused local validation and Bundle validation
- Last command and result: `databricks bundle validate -t dev --var code_sha=local-validation`
  returned `Validation OK`
- Current data counts / reconciliation / WAP: local Spark component tests passed; remote
  Delta table counts, reconciliation audit and WAP publication remain `NOT_RUN`
- Pending approvals: Terraform apply, CLI V0 deployment, PR merge, production
- Current failure: none known before validation
- Exact next action: run selected Docker compatibility gate or approve CLI V0 dev deployment

## Active Scope

Deliver one deployable HR workforce-planning vertical slice:
Bronze source register, structured staging, Silver workforce signals, Silver skill
supply, quarantine, reconciliation, Gold WAP workforce gap, SQL validation, and a
dashboard with gap priorities, regional demand/supply, recommended actions, and data
trust.

## Source And Outputs

- Source snapshot: `data/raw`, copied from root `hr data project`
- Source register: `bronze_source_register`, one row per file
- Structured staging: `bronze_structured_rows`, workbook row JSON
- Silver signals: `silver_workforce_signals`
- Silver supply: `silver_skill_supply`
- Quarantine: `hr_data_project_quarantine`
- Gold: `gold_workforce_gap`; compatibility alias `hr_data_project_gold_metrics`
- WAP audit: `hr_data_project_gold_publication_audit`
- Reconciliation audit: `hr_data_project_reconciliation_audit`
- Fixture: `src/hr_data_project/fixtures/source_shape.json`
- Adversarial fixture: `src/hr_data_project/fixtures/adversarial_shape.json`
- Privacy: employee identifiers excluded from Gold/dashboard
- AI processing: Databricks `ai_parse_document`/`ai_query` path `NOT_RUN`; local fallback
  extracts PDF/DOCX/XLSX and flags image OCR as not run

## Decisions And Evidence

- Use configurable `source_base_path`; Bundle default is
  `/Volumes/${catalog}/${schema}/${landing_volume}/workforce_assessment`.
- Source extraction registers all files; XLSX/DOCX/PDF parsed locally; images are
  explicit fallback records.
- Supply is proficiency-adjusted aggregate FTE score, not one mention equals one FTE.
- Gold is Spark SQL and publishes through WAP with explicit column list and readable
  publication audit.
- Dashboard reads governed aggregate/trust tables only.

## Blockers

- Databricks CLI V0 proof requires human approval for Terraform/apply/deploy/run.
