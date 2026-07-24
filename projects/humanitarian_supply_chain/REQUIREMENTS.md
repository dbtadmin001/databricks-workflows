# Requirements - UNICEF Supply Chain Shipments - Medallion Lakehouse

## Scenario

Simulated UNICEF Oracle data-warehouse extracts describing supply shipments (nutrition, education, WASH, health, child protection) sent from regional warehouses to country programmes. Build a governed medallion lakehouse (Bronze/Silver/Gold) on Unity Catalog that produces trusted, reportable data for a Business Intelligence team. Source brief: `projects/7. Project7/Practice_Assessment_Instructions.docx` (external reference material, outside project isolation); raw CSVs are copied into this project at `data/raw/*.csv` as the canonical, project-scoped source snapshot.

## Functional requirements

1. Load four CSV extracts into Bronze Delta tables with no cleaning: `WAREHOUSES` (dimension, 6 rows), `PROGRAMMES` (dimension, 5 rows), `ITEMS` (dimension, 7 rows), `SHIPMENTS` (fact, 167 rows). Preserve original values as strings; add `_ingest_ts`, `_source_file`, `_run_id`.
2. Silver: standardize types (proper `DATE`, numeric cost, a fixed `STATUS` domain), de-duplicate, validate referential integrity against the dimensions, and route every row that fails validation to a quarantine table (not a flag column — see Decision below) with an explicit reason.
3. Gold: `fact_shipments` (accepted shipments joined to conformed dimensions) and `programme_monthly_summary` (total quantity and total cost shipped per programme per month).
4. Produce a data-quality/reconciliation summary: Bronze row count vs. Silver accepted/rejected counts, with reasons, that reconciles exactly (see `ACCEPTANCE_CRITERIA.md` for the real numbers).
5. **Write-audit-publish (WAP) gate at both Silver and Gold promotion** — stage to a run-scoped table, reject an empty publish (except the quarantine table, which may legitimately be empty), then atomically replace the target with an explicit column list. This extends the practice brief (which only asks for correct output) to match this repository's governance standard — see `projects/01_big_bag_data/src/big_bag_data/pipeline.py:56-75` (`_write_wap`) for the pattern to reuse.
6. Governance stretch goal: grant read access on the `gold` schema to a hypothetical `analysts` group — implemented as a Terraform `databricks_grants` resource, never an ad hoc `GRANT` statement run from a notebook (see Non-functional requirements).
7. Deployable via a Databricks Bundle job with separate Bronze, Silver, Gold, and SQL-validation tasks, mirroring the pattern in `projects/01_big_bag_data/databricks.yml`.

## Non-functional requirements

- No secrets in source control or logs. (This project has no live external API and no credentials — the CSVs are the complete, static source — so this mainly governs future workspace/service-principal references, not application secrets.)
- Re-runs must be idempotent: Bronze overwrite/merge by source file, Silver/Gold WAP replace.
- All production-facing tables use explicit three-part names (`<catalog>.<schema>.<table>`).
- Silver and Gold must avoid `SELECT *`.
- **Dev and prod must use distinct, dedicated Unity Catalog catalogs — never `workspace`, `main`, or `default`, and never the same catalog for both environments.** This is a hard repeat of the exact defect found and corrected in `projects/01_big_bag_data` (see `projects/01_big_bag_data/handoffs/P01-M03-T001-sol-changes-requested.md`) — do not reproduce it here.
- **All catalog, schema, and grant objects are created and owned by Terraform only** (`infra/terraform/`). No `CREATE CATALOG`, `CREATE SCHEMA`, or `GRANT` statement may run ad hoc from a notebook, job, or SQL file — including the governance stretch-goal grant in requirement 6.
- Optional components (dbt, ML, Docker) are out of scope for this project; mark their epics `NOT_APPLICABLE`.

## Decisions required at planning approval (Sol + human)

The assessment brief explicitly asks the builder to decide and justify two things; profiling the real `SHIPMENTS.csv` surfaced a third. All three are recorded here as proposed defaults for Sol/human sign-off during `P07-M00`, not silently assumed:

1. **Flag column vs. quarantine table for invalid rows.** Proposed: quarantine table. Reason: keeps Gold aggregates computed only from unambiguously valid data without a `WHERE dq_valid` filter on every downstream query, and matches the already-approved pattern in `projects/01_big_bag_data`.
2. **Negative `QUANTITY` values (5 rows, all `STATUS=CANCELLED`).** These could be a genuine "reversal" business signal or a data-entry defect — the schema has no signed-adjustment concept to distinguish them. Proposed: quarantine as `non_positive_quantity` regardless of status, since `QUANTITY` cannot structurally represent a reversal in this contract. If a future source models reversals explicitly, revisit.
3. **Conflicting duplicates** (same `SHIPMENT_ID`, different `QUANTITY`) — found exactly one case, `SHP5011` (99999 vs. 2529 — the 99999 is an outlier against every other quantity in the file, which range roughly 1,000-5,000). Proposed: quarantine **both** rows under a distinct `conflicting_duplicate` reason rather than silently picking one value by an arbitrary tie-break (e.g. "keep latest ingested") — there is no `_ingest_ts` difference between them to break the tie honestly, and guessing which value is correct is exactly the kind of data-integrity judgment this repository's governance model requires surfacing, not assuming.

## Verified-source requirements

- The source is fully declared in `DATA_SOURCES.md`: four static CSV files, no live API, no optional providers.
- No live ingestion applies (there is no live source to gate in CI).
- Every column and known defect is documented in `DATA_CONTRACTS.md` and backed by the actual profiling run against `data/raw/SHIPMENTS.csv` (not hypothetical edge cases).
