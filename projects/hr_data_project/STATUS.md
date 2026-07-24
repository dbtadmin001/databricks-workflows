# Status - HR Data Workforce Planning

- Current milestone: `P12-M02` - implementation validation
- Branch / head commit: `fix/explicit-pipeline-requirement-audit`
- Files currently changed: project implementation, source copy, docs, one shared project-init bug fix
- Completed: project registration, source snapshot copy, source contract extraction, Bronze/Silver/Gold implementation, SQL validation, dashboard update
- Tests passed:
  - `py -3.11 -m compileall projects/hr_data_project/src`
  - `py -3.11 -m ruff check projects/hr_data_project/src projects/hr_data_project/tests`
  - `py -3.11 orchestration/scripts/validate_timed_mvp.py --project-root projects/hr_data_project`
  - `$env:PYTHONPATH='projects/hr_data_project/src'; py -3.11 -m pytest projects/hr_data_project/tests/test_pipeline.py -q`
  - `databricks bundle validate -t dev --var code_sha=local-validation`
- Remote evidence: `CLI_V0_BLOCKED` by Databricks smoke run pending successful Bundle
  deploy/run; Terraform catalog/schema/volume exist from workflow run 29686107368
- Known limitations / NOT_RUN: Databricks AI extraction, Terraform apply, Bundle deploy, Databricks job run, dashboard execution
- Blockers: `admins` is a workspace-local SCIM group visible to the user profile, but
  is not resolvable as a Unity Catalog/account principal by the automation deployment
  identity. V0 Terraform grants are limited to `data-automation-services`; admins
  catalog visibility remains a governance blocker until the account-level group is
  provisioned/synced.
- Next action: approve CLI V0 dev deployment, then run Terraform apply/import where
  needed, Bundle deploy, raw volume upload, deployed Databricks job smoke run, task
  inspection, bounded fixes, and evidence capture

## Source Contract

The project implements the supplied UNDP-style HR workforce assessment pack. Required
business outputs are skill priorities by country office and region, evidence-supported
recommended action, aggregate supply estimation, and a governed dashboard with no
employee-level details.

## Pre-PR Requirement Audit

- Source-specific implementation: `VERIFIED` in `src/hr_data_project/source_documents.py`,
  `src/hr_data_project/pipeline.py`, and `REQUIREMENTS.md`.
- Terraform dedicated dev/prod catalog, schema, raw landing volume, ownership, grants,
  and warehouse references: `VERIFIED` in `infra/terraform/main.tf` and `delivery.json`.
- Separate Bundle tasks for Bronze, Silver, Gold WAP, SQL validation, dashboard:
  `VERIFIED` in `resources/hr_data_project.job.yml`.
- Bronze source fidelity/register/structured staging/profile: `VERIFIED` in
  `src/hr_data_project/jobs.py`; local source-pack test registered at least 18 files.
- Silver parsing, nullable policy, quarantine, reconciliation: `VERIFIED` in
  `src/hr_data_project/pipeline.py` and `jobs.py`; local Spark test passed.
- Gold Spark SQL, explicit grain, WAP audit, last-good preservation on hold:
  `VERIFIED` in `src/hr_data_project/pipeline.py` and `jobs.py`; runtime publication
  `NOT_RUN`.
- SQL validation DBSQL task: `VERIFIED` in `sql/validate_outputs.sql`.
- Dashboard Gold KPIs, data trust, filters/pages, no employee detail: `VERIFIED` in
  `src/notebooks/04_dashboard.py`.
- Notebook documentation sections: `VERIFIED` in `src/notebooks/00_orchestrate.py` and
  `src/notebooks/04_dashboard.py`; stage-specific notebooks still scaffold wrappers.
- Architecture artifacts tailored/current: `VERIFIED` in `architecture.json`,
  `ARCHITECTURE.jpg`, and `ARCHITECTURE.manifest.json`.
- Runtime target/serverless version/warehouse/SP/source fixtures/privacy/AI behavior:
  `VERIFIED` in `delivery.json`; remote capability evidence `NOT_RUN`.
- Required Databricks skills read: `VERIFIED` for DABs, jobs, DBSQL, Unity Catalog/core
  in this delivery thread.

## Version 0 Status

`CLI_V0_DEPLOYED` is not claimed. Workflow runs 29686107368 and 29686242852 reached
Terraform but did not reach Bundle deployment or Databricks smoke. The first failure
created/imported the dev catalog, schema, and raw landing volume, then failed because
Unity Catalog grants could not resolve principal `admins`; using the workspace group id
also failed. Version 0 still requires a successful inspected Databricks dev smoke run
through Bronze, Silver, Gold/WAP, SQL validation, and dashboard tasks, with sanitized
run evidence under `evidence/deployments/`.
