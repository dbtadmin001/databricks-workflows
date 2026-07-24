# Architecture - UNICEF Supply Chain Shipments - Medallion Lakehouse

## Target flow

`data/raw/*.csv` (static, project-scoped) -> Bronze Delta (unmodified, one table per source file) -> Silver (typed, deduplicated, referentially validated, WAP-published as `shipments_accepted`/`shipments_quarantine`) -> Gold (`fact_shipments`, `programme_monthly_summary`, WAP-published) -> governed serving via the `gold` schema and reconciliation/UAT evidence.

## Unity Catalog and Terraform ownership

One dedicated Unity Catalog **catalog per environment**, both created only by `infra/terraform/main.tf`'s `databricks_catalog` resource — this project's scaffold already provisions this correctly (`create_catalog = true` in `delivery.json`), unlike `projects/01_big_bag_data`, which had to be corrected after Sol review found it collapsing dev and prod onto `workspace.default`. Do not regress that fix here:

- Dev catalog: `project_07_unicef_supply_chain_dev`
- Prod catalog: `project_07_unicef_supply_chain_prod`
- Both carry schema `medallion`, containing the `bronze`, `silver`, `gold` **sub-schemas** described in `DATA_CONTRACTS.md` (Free/Community Edition's auto-provisioned metastore supports one catalog with multiple schemas cleanly; see Platform profiles below for how the practice brief's single-catalog three-schema demo maps onto this project's dev/prod-separated structure).
- Grants (`databricks_grants` in `main.tf`) are principal-scoped via `admin_user_principals`/`owner_principal`, never a direct user grant.
- The governance stretch goal (read-only `analysts` group on `gold`) is a new `databricks_grants` resource scoped to the `gold` schema only, with `SELECT`+`USE_SCHEMA` privileges — added at M06, not run ad hoc from a notebook.
- `databricks.yml`'s `catalog`/`schema` Bundle variables and Terraform's `catalog_name`/`schema_name` variables must resolve to the same names per environment — wire both from `delivery.json`'s `environments.<env>.catalog`/`.schema` as the single source of truth, so there is exactly one place per environment that names the catalog, not two that could drift apart (this is precisely how Project 1's collapse happened: `databricks.yml` and `delivery.json` each hardcoded their own value instead of one driving the other).

## Databricks mapping

See `DATABRICKS_MAPPING.md` for the full component map. Summary: PySpark owns Bronze ingestion and Silver cleaning/validation; Spark SQL owns Gold aggregation and the `sql/` validation task; Databricks Asset Bundles own job deployment; Terraform owns catalog/schema/grant infrastructure exclusively.

## Write-audit-publish

Both Silver (`shipments_accepted`, `shipments_quarantine`) and Gold (`fact_shipments`, `programme_monthly_summary`) publish through the WAP pattern in `projects/01_big_bag_data/src/big_bag_data/pipeline.py:56-75`: write to a run-scoped staging table, reject an empty publish (except quarantine, which may be legitimately empty), then atomically replace the target via `CREATE OR REPLACE TABLE ... AS SELECT <explicit columns>`. Bronze itself is a plain overwrite/append per source file — there is no WAP quality gate at Bronze because Bronze intentionally accepts everything, including bad rows; the gate belongs at the boundary where quality is actually enforced.

## Platform profiles

- **Community/Free**: this project's actual target. Auto-provisioned Unity Catalog metastore (per `Databricks_Cheat_Sheet.docx`), single-node/serverless compute, CSVs uploaded to a Unity Catalog Volume and read with Spark (`inferSchema=False`). No multi-node clusters. If `CREATE CATALOG` is denied by the workspace's permission model, fall back to creating `bronze`/`silver`/`gold` as schemas inside the workspace's existing default catalog and record that deviation explicitly in a handoff — do not silently rename the dedicated catalogs to `workspace`.
- **Enterprise AWS/Azure**: not a target for this project; the practice assessment is explicitly a Free/Community Edition exercise. Leave both `NOT_APPLICABLE` unless the human later directs otherwise.

## Contracts and boundaries

Bronze preserves source payload and ingestion metadata with zero cleaning. Silver permits only the reviewed, typed columns in `DATA_CONTRACTS.md`, with every row classified accepted or quarantined — never silently dropped. Gold has explicit grain, keys, and metric formulas, including the `cancelled`-exclusion rule for `programme_monthly_summary`. No secret values enter repository files (this project has none to begin with — no live API, no credentials).

## Approval

This target is proposed until `P07-M00` receives Sol review and human approval. No implementation decision in this file is approved by initialization or drafting alone.
