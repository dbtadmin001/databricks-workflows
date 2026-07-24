# Architecture - Chess.com Grandmaster and User Analytics

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

This target is proposed until `P05-M00` receives Sol review and human approval. No implementation decision in this file is approved by initialization alone.
