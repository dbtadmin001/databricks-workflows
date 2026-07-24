# Workflow - ADR/AEFI Pharmacovigilance Document Intelligence

Use `docs/SINGLE_MODEL_WORKFLOW.md`. Any capable coding model may continue this
project end to end. Keep one model actively editing at a time; another model may resume
from `CONTEXT.md`, `STATUS.md`, and the worktree without a routing transition.

## Milestones

- `P10-M00`: preflight, source profile, environment and contracts.
- `P10-M01`: complete Bronze, Silver, quarantine, Gold and WAP MVP.
- `P10-M02`: one review pass and prioritized hardening.
- `P10-M03`: documented PR and automated dev/production delivery evidence.

## Mandatory MVP controls

Python 3.11; dedicated dev/prod catalogs; declarative Terraform; declared SQL
warehouse; notebook-first jobs backed by importable modules; source-faithful Bronze;
typed/deduplicated/quarantined Silver; explicit-grain Gold; mandatory WAP;
reconciliation; idempotency; secrets excluded.
