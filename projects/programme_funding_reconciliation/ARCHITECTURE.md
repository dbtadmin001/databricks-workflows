# Architecture - Programme Funding & Parallel-Run Reconciliation

## Target flow

Approved source profile -> source-aligned Bronze Delta -> contract-enforced Silver -> stable Gold products -> governed serving and UAT evidence.

## Databricks mapping

`DATABRICKS_MAPPING.md` is the project-specific component map. PySpark owns ingestion and operational transformations; Spark SQL owns relational Gold models; Databricks Asset Bundles own application deployment; Terraform owns account, workspace and Unity Catalog infrastructure when supported.

## Platform profiles

- Community/Free: deterministic fixtures, available compute, Delta and local/remote tests; unsupported governance features are documented or simulated.
- Enterprise AWS: Unity Catalog, service principals, cloud storage credentials, private networking and production controls require approved values.
- Enterprise Azure: Unity Catalog, managed identities/service principals, ADLS access, private networking and production controls require approved values.

## Contracts and boundaries

Bronze preserves source payload and ingestion metadata. Silver permits reviewed schemas only. Gold has explicit grain, keys, metric semantics and reconciliation tolerances. Secret values never enter repository files.

## Approval

The target architecture and the Project 8 planning defaults received human approval
in `handoffs/P08-M00-human-approved.md` and passed Sol planning review on 2026-07-16.
Implementation remains blocked until the orchestrator processes the structured Sol
result and records the approval in project state.
