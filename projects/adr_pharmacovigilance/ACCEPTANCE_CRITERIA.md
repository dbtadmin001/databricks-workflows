# Acceptance Criteria - ADR/AEFI Pharmacovigilance Document Intelligence

Maps directly to the assignment brief's Section 3 (required implementation),
Section 4 (dashboard expectations), and Section 7 (constraints). Status
reflects host-pytest-verified behavior against the real 140-document /
35,000-row fixtures as of this delivery (see `STATUS.md` for what still
needs the Docker/Databricks gate).

| # | Criterion | Verified by | Status |
|---|---|---|---|
| 1 | Idempotent incremental document ingestion; exact duplicates never create duplicate cases | `test_bronze.py::test_exact_duplicate_file_does_not_create_a_second_document`, hand-run against all 140 real files (133 distinct) | PASS (host) |
| 2 | Capture file path, name, extension, size, arrival metadata, mtime, checksum, ingestion timestamp, processing status | `bronze.register_and_extract_documents` schema; `bronze_document_arrivals` ledger | PASS (host, schema-level) |
| 3 | Classify into case report / follow-up / supporting document / duplicate / unreadable-quarantined | `test_extraction.py` parametrized against real fixtures of each type | PASS (host) |
| 4 | Extract case reference, dates, patient age/sex, facility/district, product(s), reaction(s), seriousness, outcome, reporter type, narrative, confidence | `test_field_parser.py`, hand-run against all 140 real files | PASS (host) |
| 5 | Service stub / deterministic parser acceptable where OCR unavailable, with production-credible interface and failure handling | `extraction.py` (`TextExtractor` protocol, `MockOcrTextExtractor` returns explicit `NOT_RUN`-equivalent, never fabricates) | PASS (host) |
| 6 | Bronze/Silver/Gold Delta tables; preserve raw metadata and extracted text; model cases/versions/products/reactions/links/reviews without flattening | `sql/ddl_reference.sql`, `DATA_CONTRACTS.md`, `test_silver.py::test_case_with_two_products_and_two_reactions_is_one_case_not_four` | PASS (host, schema+logic); Delta writes need Docker gate |
| 7 | Mandatory fields, valid dates, product/reaction mapping, duplicate detection, follow-up linkage, referential integrity, pipeline reconciliation, dashboard totals; quarantine without silent drop | `test_silver.py` (6 tests), `gold.reconcile` | PASS (host, logic); full reconciliation run needs Docker/Databricks |
| 8 | Gold tables + dashboard covering all Section 4 bullets | `src/notebooks/04_dashboard.py` (4 pages) | Implemented, not yet screenshotted against a live warehouse |
| 9 | Orchestration, parameterisation, environment separation, secure config, logging, testing, CI/CD or Bundle | `resources/10_adr_pharmacovigilance.job.yml`, `infra/terraform/` | Implemented from repo scaffold; not yet deployed |
| 10 | Repeatable: rerun does not inflate counts | Checksum dedup (Bronze) + case-reference dedup (Silver); `test_bronze.py::test_write_bronze_documents_is_idempotent_across_reruns` | Written, needs Docker gate (Delta not configured on host) |
| 11 | Source documents immutable; lineage dashboard -> document -> case version | `silver_document_links`, `document_id` carried through every Silver/Gold row | PASS (host, schema-level) |
| 12 | Dashboard counts distinct business entities correctly (2 products + 2 reactions != 4 cases) | `test_gold.py::test_historical_event_grain_case_volume_counts_distinct_cases_not_rows`, `test_silver.py` case-grain test | Written, needs Docker gate to execute |
| 13 | No credentials/tokens/connection strings committed | No secrets in any file added this session (verified by inspection) | PASS |

## Minimum deliverables checklist (assignment Section 5)

| Item | Status |
|---|---|
| 1. Notebooks / Python package | Done — `src/project_10_adr_pharmacovigilance/`, `src/notebooks/` |
| 2. DDL for Bronze/Silver/Gold/quarantine | Done — `sql/ddl_reference.sql` |
| 3. Orchestrated workflow / job definition | Done — `resources/10_adr_pharmacovigilance.job.yml` |
| 4. Automated tests for transformations and reconciliations | Done — 22 tests, 19 pass on host; 3 Delta-writing tests need the Docker gate |
| 5. Dashboard / dashboard-ready queries | Done — `src/notebooks/04_dashboard.py`; no live-warehouse screenshot yet |
| 6. Architecture diagram + README | Done — `README.md` (mermaid diagram, setup, assumptions, limitations, next steps) |
| 7. 10-minute presentation | Not applicable to this delivery session — candidate-prepared |
