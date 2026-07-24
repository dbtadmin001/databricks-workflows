# Project 8 Workflow

Use `docs/SINGLE_MODEL_WORKFLOW.md`. Any capable model may continue this project end to
end; do not route between Sol, Terra, Gemini, or other personas.

## M0 - Preflight and contract

Source profiling and contracts are complete. The dedicated dev catalog is
`PENDING_AUTOMATED_PROVISION`; CI must create/import it before Bundle deployment.

## M1 - Core MVP

- Gate A: finish and validate Bronze.
- Gate B: implement Silver schema alignment, parsing/casting, exact/conflicting
  duplicates, six cross-batch corrections, quarantine, FX/grants and SCD2.
- Gate C: implement SQL Gold fact/summary, reconciliation and mandatory WAP.

Do not stop or switch models between gates. Use saved upstream data for downstream
tests.

## M2 - Review and improvements

Run one review against `ACCEPTANCE_CRITERIA.md`, fix correctness first, then add the
highest-value hardening within the remaining time.

## M3 - PR and delivery

Open one documented PR. Human merge to `main` triggers dev Terraform, catalog/schema
verification, Bundle deployment and approved smoke. Promotion to `production` remains
human controlled.
