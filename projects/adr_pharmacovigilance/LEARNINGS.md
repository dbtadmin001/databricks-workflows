# Project Learnings - ADR/AEFI Pharmacovigilance Document Intelligence

| Date | Stage | Symptom or success | Root cause / pattern | Evidence | Prevention or next action |
|---|---|---|---|---|---|
| 2026-07-18 | PR gate | PR became mergeable while runtime compatibility was still pending | The status existed but `compatibility/runtime` was absent from live required branch contexts | PR #146 and live branch-protection response | Added the exact context to strict branch protection and repository-owned drift configuration |
| 2026-07-18 | Bundle deploy | Both serverless jobs were rejected during resource creation | Bundle specs combined `base_environment` and `environment_version` | GitHub run 29625025387 | Bundle contract rejects the combination; MVP templates declare only the pinned version |
| 2026-07-18 | Silver | Review queue failed with `CANNOT_DETERMINE_TYPE` | `case_reference` was null in every row and schema inference failed under Spark Connect | GitHub run 29625238858 | All persisted Silver, exception, and quarantine outputs use explicit `StructType` contracts |
| 2026-07-18 | Gold WAP | Pipeline health failed with `NOT_COLUMN` | Collected Python integers were passed directly to `withColumn` | GitHub run 29625581318 | Counts use typed `F.lit` expressions and a focused Spark regression |
| 2026-07-18 | SQL validation | Validation failed because `dq_quarantine` was absent when no rows were rejected | Silver only created non-empty outputs, but downstream SQL depends on stable table contracts | GitHub run 29625963225 | Materialize every declared Silver, review, exception, and quarantine table with its explicit schema, including zero-row outputs |
| 2026-07-18 | Dev repair | The empty-table correction succeeded end to end but reran Bronze, Silver, and Gold | Post-merge automation always started the complete Bundle job regardless of changed stage | GitHub run 29626426990 | Skip deployment for docs/tests and use the earliest affected task plus downstream dependents for runtime changes |

Reusable lessons are promoted to `docs/DELIVERY_KNOWLEDGE.md`; detailed logs remain
in GitHub/Databricks evidence rather than this file.
