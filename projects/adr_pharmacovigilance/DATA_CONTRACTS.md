# Data Contracts - ADR/AEFI Pharmacovigilance Document Intelligence

Full column-level DDL: `sql/ddl_reference.sql`. This document states the
grain and non-negotiable invariant per layer; see `REQUIREMENTS.md` for the
functional requirements each table serves.

## Bronze

- `bronze_document_arrivals`: grain = one row per physical file arrival
  event. No dedup. Append-only ledger.
- `bronze_documents`: grain = one row per **distinct document checksum**
  (`document_id = sha256(bytes)`). Exact-duplicate files never produce a
  second row (enforced in `bronze.dedupe_by_checksum`, re-verified across
  runs by `write_bronze_documents`'s MERGE).
- `bronze_document_content`, `bronze_extraction_payloads`: 1:1 with
  `bronze_documents` on `document_id`.
- `bronze_historical_events`: grain = one row per historical event
  (case_id x product x reaction). **Not** case grain — verified 19,197
  distinct `case_id` across 35,000 rows.
- `ref_*`: 1:1 mirror of the source reference CSVs, overwritten each run.

## Silver

- `silver_cases`: grain = one row per **case_reference**. Current-state
  view (latest accepted version's seriousness/outcome).
- `silver_case_versions`: grain = one row per case_reference x
  document-driven version (initial + each follow-up). Never conflates
  versions of the same case into one row.
- `silver_case_products`, `silver_case_reactions`: grain = one row per
  case_version_id x product (or reaction). A case with N products and M
  reactions produces N + M child rows, never inflating the case count
  (assignment's explicit non-negotiable — verified by
  `test_silver.py::test_case_with_two_products_and_two_reactions_is_one_case_not_four`).
- `silver_document_links`: grain = one row per document-to-case
  relationship (`source_of_version` or `duplicate_of`).
- `silver_review_queue`: grain = one row per document requiring human
  review (unreadable, non-case, orphan follow-up, missing case reference).
- `dq_quarantine`: grain = one row per case_version_id failing mandatory
  field checks. Quarantined versions are **excluded** from `silver_cases`
  aggregation feeding Gold — never silently included.
- `reference_mapping_exceptions`: grain = one row per unmapped
  product/reaction/facility/district value.

## Gold (write-audit-publish)

- `gold_adr_overview`: grain = one row per (source_pipeline, report_type,
  seriousness, outcome). `distinct_case_count` is always
  `COUNT(DISTINCT case_reference)`.
- `gold_product_reaction`, `gold_facility_reporting`: aggregated from
  `bronze_historical_events` (the analytics-volume source), grain per the
  dimensional combination in the SELECT's GROUP BY.
- `gold_pipeline_health`: grain = one row per (run_id, classification) from
  the document pipeline, joined with scalar reconciliation counts.
- `gold_adr_overview_cases`: case-grain detail table feeding reconciliation
  (`sql/validate_outputs.sql`) — must always have `COUNT(DISTINCT
  case_reference) == silver_cases`'s count, or publication is held (WAP:
  built into `_staging` tables first, promoted only on reconciliation pass).

## Non-negotiable invariants (tested)

1. Exact-duplicate file bytes never create a second document or case.
2. A case with N products/M reactions is 1 case, never N or M or N*M cases.
3. A follow-up document creates a new case *version*, never a new case.
4. A quarantined case version is excluded from Gold, never silently
   published or silently dropped without a `reason_code`.
5. Gold published case count must equal Silver accepted case count, or the
   previous Gold table is left unchanged (WAP).
