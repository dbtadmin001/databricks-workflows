# Current Project Context

## Identity

- Project: `10_adr_pharmacovigilance` - ADR/AEFI Pharmacovigilance Document Intelligence
- Execution profile: `TIMED_MVP`
- Current milestone: Implementation complete, PR readiness
- Next action: push feature branch, open PR, and run one final-SHA compatibility gate

## Continuation checkpoint

- Branch / head commit: `feature/project-10-adr-pharmacovigilance`; current Git HEAD
- Files currently changed: full pipeline implementation under
  `projects/10_adr_pharmacovigilance/`
- Last completed gate: `validate_timed_mvp.py` PASS; 14 selected unit tests PASS;
  Ruff check + format clean; wheel build PASS; static Bundle/runtime contract PASS
  for two serverless version-2 environments; `terraform validate` PASS.
- Last command and result: `terraform -chdir=infra/terraform validate` -> configuration valid.
- Current data counts / reconciliation / WAP: hand-validated against real
  data (133 distinct documents, 65 cases, 72 case versions, 0 residual
  Silver duplicates, 18 reference-mapping exceptions) — see `STATUS.md`.
  Real Delta/warehouse reconciliation evidence: `NOT_RUN` until dev job runs.
- Pending approvals: human PR merge. The one-shot container compatibility gate is
  `NOT_RUN` until the final PR SHA exists; it will pull the prevalidated image.
- Current failure: final-SHA compatibility failed on local managed-table paths and
  `DeltaTable.forName` parsing. Bounded corrections are implemented; rerun is `NOT_RUN`.
- Exact next action: push the correction commit, then obtain explicit approval for
  one final compatibility rerun before human merge approval.

## Active scope

Deliver one deployable Bronze, Silver/quarantine, Gold WAP, SQL validation,
and dashboard vertical slice for ADR/AEFI document intelligence. Detailed
requirements remain authoritative in the adjacent project documents.

## Resolved environment

- Python: 3.11
- Dev catalog: `project_10_adr_pharmacovigilance_dev`
- Dev schema: `medallion`
- SQL warehouse: `cc91c315736f92f8` (existing, shared across this repo's projects)
- Runtime target: serverless `environment_version: "2"`, matches `local-platform/runtime-lock.json`

## Source and outputs

- Source snapshot: `data/raw/` (140 documents, 35,000-row historical CSV, 7 reference CSVs) — static, immutable, committed
- Source-derived shape fixture / provenance: `tests/fixtures/documents/` (source-derived), see `delivery.json.source_shape_fixture`
- Adversarial fixture: `tests/fixtures/documents/ADR-2026-0066_scanned_form.pdf` (no text layer)
- Observed NULL / missing-field variants preserved: yes (verified zero nulls in historical CSV; missing-field tracking in Silver)
- Bronze: implemented, hand-validated against real data
- Silver: implemented, hand-validated against real data
- Quarantine: implemented (`dq_quarantine`, `silver_review_queue`), hand-validated
- Gold: implemented (WAP), reconciliation logic tested
- WAP audit: `gold.write_gold_wap` — staging + reconciliation-gated promotion
- Reconciliation (`source = accepted + quarantined + explicitly excluded`): logic implemented and tested; real Databricks run evidence NOT_RUN
- Privacy: automatic classification; restricted PII 90-day maximum; temporary copies 30-day maximum; no direct PII (patient initials, reporter contact) in Gold schema
- Source privacy preflight: real baseline case PDFs are local-only, ignored by Git,
  and excluded from pipeline input; publishable fixtures are assignment-provided synthetic data.
- AI processing: OCR/document-AI mocked locally (honest NOT_RUN, no fabrication); real `ai_parse_document()` wiring is a follow-up

## Decisions and evidence

- Use only this project as working context; do not inspect sibling projects.
- Record concise decisions and link detailed evidence instead of copying logs here.
- Refresh the continuation checkpoint after each MVP gate and before any model pause.
- Full-scope delivery profile chosen over `TIMED_MVP`'s 65-minute pacing
  (see `REQUIREMENTS.md` Decision 1) — `execution_profile` field stays
  `TIMED_MVP` because that's the only value the delivery-contract tooling
  supports; the pacing decision is separate from that mechanical field.

## Blockers

- None. Docker `local-platform` gate skipped on explicit human direction
  for this delivery (see `RISKS_AND_TRADEOFFS.md`); Databricks credentials
  confirmed available for dev deployment.
