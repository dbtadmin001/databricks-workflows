# Project Learnings - HR Data Workforce Planning

Record only observed results. Do not paste secrets or full logs.

| Date | Stage | Symptom or success | Root cause / pattern | Evidence | Prevention or next action |
|---|---|---|---|---|---|
| 2026-07-19 | V0 Terraform | Dev deploy reached Terraform but failed before Bundle deployment on UC grants to `admins`; group id also failed. | `admins` is visible as a workspace-local SCIM group to the user profile, but is not resolvable as a Unity Catalog/account principal by the automation deployment identity. | GitHub runs 29686107368 and 29686242852, `Apply project dev Terraform`. | V0 smoke can proceed with `data-automation-services` as the only Terraform grant principal; full admin visibility requires account-level/synced UC `admins` or an account-identity Terraform module before project grants. |
| 2026-07-19 | V0 Databricks smoke | Multiple failed dev runs exposed notebook syntax, missing raw source availability, missing materialized Silver tables, and incorrect task parameter/sequence behavior after the project should have been caught locally. | The implementation skipped the repository's local Spark compatibility image and source/package/task contract checks before remote smoke, then burned the MVP time budget on serial Databricks retries. | GitHub dev deployment runs 29686330264, 29686479763, 29686660620, 29686839783, 29687001206, 29687321139, 29687462797, and 29687621314. | Before any V0 Databricks smoke, run the local Spark image/compatibility path for notebook syntax, raw-source packaging, Bronze/Silver/Gold table materialization, WAP, SQL validation inputs, and rendered Bundle task parameters. Stop after the first repeated remote symptom and fix the local gate. |
| 2026-07-19 | Delivery ownership | User stopped Codex after the failed V0 loop and switched to Claude Code to repair the implementation. | Codex did not follow the agreed MVP sequencing and did not use the existing local Spark image to catch preventable issues before remote deployment. | User instruction in chat on 2026-07-19 after run 29687621314. | Record the handoff truthfully; future agents must treat the current branch as failed/incomplete until Claude Code or another owner records passing local compatibility and successful dev smoke evidence. |

## SHARED_SYSTEM_BLOCKER

The shared Terraform grant template should distinguish workspace-local groups from
account-level Unity Catalog principals and fail in preflight before partial
infrastructure apply. The recurring symptom is `Could not find principal with name
admins` even when `databricks groups list` from a user profile shows a workspace group.

Promote reusable lessons to `docs/DELIVERY_KNOWLEDGE.md` and pair them with the
smallest practical test, validator, template, workflow, or global rule.
