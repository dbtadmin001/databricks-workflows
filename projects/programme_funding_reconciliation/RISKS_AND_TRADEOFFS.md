# Risks and Trade-offs - Programme Funding & Parallel-Run Reconciliation

| Risk | Decision / mitigation | Residual risk |
|---|---|---|
| Thirty-minute target is shorter than normal TIMED_MVP | Three bounded phases, fixtures/snapshots, targeted gates, one review cycle | GitHub/Databricks queue time may finish after the submission window |
| Shared CI currently does not implement the approved branch model | Separate `_template` governance change must make `main` dev and `production` prod before Project 8 merge | Automatic deployment is blocked until that change lands |
| Free Edition catalog creation may reject Terraform storage settings | Default-storage SQL bootstrap followed immediately by Terraform import; allow drift-only fallback after read-only access proof | Missing catalog or privileges remains blocking |
| One schema is approved while contracts use logical layer names | Physical table prefixes in `medallion` are authoritative and mapped in `DATABRICKS_MAPPING.md` | Naming must remain explicit in every SQL statement |
| CSV/JSON schema evolution can silently lose fields | Reviewed explicit alignment plus Delta MERGE schema evolution and contract tests | New breaking fields require quarantine and contract review |
| CTB9021 can be silently collapsed by naive deduplication | Quarantine both conflicting rows before cross-batch MERGE | Any unstated tie-break is a release defect |
| Date/fiscal-year formats can crash or mis-reconcile | Profiled format list, `try_*` parsing, ending-year rule and targeted tests | Future unprofiled formats quarantine until reviewed |
| Q1/Q2 snapshot absence is ambiguous for PRG104 | Human approved open-ended current version absent retirement evidence | Later retirement evidence requires SCD2 correction |
| Brief claims four variances but this is not independently verified | Execute reconciliation and report actual causes; never force four | Assignment expectation may differ from source truth |
| WAP or publish failure could corrupt Gold | Run-scoped staging, complete audits, explicit columns, atomic replace, preserve current table on failure | Stale staging requires safe expiry/cleanup |
| Production values are intentionally unresolved | Production disabled for MVP; distinct production catalog remains declared | Production release requires separate Level 4 approval and inputs |

No secrets are required by the static source. Authentication is referenced only
through the approved Databricks profile locally and GitHub environment secrets in CI.
