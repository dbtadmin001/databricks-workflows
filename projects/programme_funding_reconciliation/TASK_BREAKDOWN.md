# Task Breakdown - Programme Funding & Parallel-Run Reconciliation

Only the next task is activated after P08-M00 approval. These are approved candidates,
not simultaneously active assignments.

| Candidate | Scope | Implementer | Reviewer | Gate |
|---|---|---|---|---|
| P08-M01-T001 | Environment preflight, declarative dev catalog/schema inputs, native-format Bronze notebooks/modules | Terra | Sol | Gate 1 |
| P08-M02-T001 | Silver schema evolution, parsing/casting, dedup/corrections, quarantine, FX/grants and programme SCD2 | Terra | Sol | Gate 2 |
| P08-M03-T001 | SQL Gold models, mandatory WAP, reconciliation, Bundle validation and PR evidence | Terra | Sol + human PR review | Gate 3 |

The CI branch-model correction is not a Project 8 task. It requires a separate
`_template` task with `.github/**` explicitly allowed and human review.

P08-M01-T001 is selected first only after the orchestrator processes this Sol result
and formally records the existing human approval. Later tasks require the preceding
gate evidence and must not rerun unaffected upstream stages.
