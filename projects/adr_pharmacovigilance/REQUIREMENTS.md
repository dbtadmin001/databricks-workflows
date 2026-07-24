# Requirements (URS) - ADR/AEFI Pharmacovigilance Document Intelligence

## Scenario

Build a Databricks lakehouse pipeline that ingests mixed-format adverse drug
reaction (ADR) and adverse event following immunisation (AEFI) case documents
(digitally generated CIOMS forms, manufacturer narratives, scanned forms,
mobile photographs, follow-ups, duplicates, and non-case supporting
documents), classifies and extracts structured case data, curates a
versioned lakehouse model, applies data quality/reconciliation, and publishes
a dashboard covering both pharmacovigilance operations and data-product
monitoring. Source brief: `data/raw/assignment/ADR_Databricks_Candidate_Assignment.pdf`
(copied verbatim into project isolation). This is a full-scope delivery
(brief states "recommended implementation time 4 hours" plus a 10-minute
oral defense) — **not** run under the repo's 65-minute `TIMED_MVP` clock;
`docs/SINGLE_MODEL_WORKFLOW.md`'s full milestone sequence applies instead.

## Verified-source requirements

Profiled directly from the files in `data/raw/` on 2026-07-18 (not
transcribed from the brief):

- **`historical/historical_adr_events_35000.csv`**: 35,000 rows, 31 columns,
  zero nulls in any column checked (`case_id`, dates, `facility_id`,
  `product_id`, `reaction_id`, `seriousness`, `outcome`, flags,
  `processing_status`, scores). **19,197 distinct `case_id` values across
  35,000 rows** — this is an **event grain** table (one row per
  case×product×reaction combination), not a case grain table. Confirms the
  brief's explicit warning literally: "a case with two products and two
  reactions must not accidentally become four cases." All Gold case-volume
  metrics must `COUNT(DISTINCT case_id)`, never `COUNT(*)`, over this table.
- **Referential integrity is clean**: zero orphan `facility_id` (60 distinct,
  all in `facility_master.csv`), zero orphan `product_id` (22 distinct, all
  in `product_dictionary.csv`), zero orphan `reaction_id` (22 distinct, all
  in `reaction_dictionary.csv`), zero orphan `district` (20 distinct, all in
  `district_master.csv`). Silver/Gold referential-integrity checks should
  therefore report `0` on the historical fixture; a non-zero orphan count
  during development indicates a join-key bug, not expected real-world noise
  (the assignment's synthetic 140-document set is a separate, deliberately
  messier source — see below).
- **`processing_status` distribution** (historical): `READY_FOR_DASHBOARD`
  30,072; `QUARANTINED` 2,874; `NORMALISED` 1,355; `FAILED` 699. Only
  `READY_FOR_DASHBOARD` rows are safe to publish to Gold as-is; the other
  three states are exactly the pipeline-health signal `gold_pipeline_health`
  must expose, not rows to silently drop or silently include.
- **`duplicate_flag`**: `True` for 1,643 of 35,000 rows (4.7%).
  **`follow_up_flag`**: `True` for 3,609 of 35,000 rows (10.3%). Both must
  drive dashboard "initial vs. follow-up" and duplicate-rate metrics.
- **`seriousness`**: near-even split, 17,836 `Serious` / 17,164 `Not
  serious` — no dominant class to sanity-check against.
- **`report_source`**: `Digital PDF` 12,310; `Scanned PDF` 12,111; `Mobile
  image` 6,966; `Manufacturer XML/PDF` 3,613. Confirms all four document
  channels named in the brief are materially represented, not edge cases.
- **`report_date` range**: 2023-01-01 through 2026-06-29 (~3.5 years).
- **`reference/arrival_manifest.csv`**: 140 rows, one per synthetic document,
  columns `file_name, relative_path, source_system, arrival_timestamp,
  arrival_batch`. **Exact 1:1 match against the 140 files physically present
  in `data/raw/documents/synthetic/`** (0 in manifest not on disk, 0 on disk
  not in manifest) — this is the authoritative arrival-metadata source for
  Bronze ingestion of the document set; do not re-derive arrival time from
  filesystem mtime alone.
- **Document content, sampled directly** (not assumed from filenames):
  - `*_CIOMS_initial.pdf` and `non_case_*.pdf` files carry a **real text
    layer** (digitally generated) with a consistent labeled-table layout —
    `Case reference`, `Report type`, `Reaction(s)`, `Seriousness`/
    `Criterion`, `Outcome`, `District`, a suspect-drug table, and a
    narrative paragraph. A **deterministic, position/label-based parser is
    fully viable** for this subset without OCR.
  - `*_scanned_form.pdf` files are **rasterized images embedded in a PDF
    container** (confirmed by direct read — no extractable text layer,
    despite the `.pdf` extension). They render as a scanned paper form
    ("NATIONAL PHARMACOVIGILANCE CENTRE — SUSPECTED ADR/AEFI REPORTING
    FORM") with checkboxes and cursive-style filled-in field values.
    **Requires OCR/vision extraction**, not a text parser.
  - `*_mobile_photo.{jpg,png}` files are genuine raster images of the same
    paper form style, photographed at an angle — **requires OCR/vision
    extraction**.
  - This confirms the brief's own guidance is the right split: a
    deterministic parser is production-appropriate for the digitally
    generated subset (CIOMS/manufacturer/non-case), and an
    OCR/document-AI abstraction (mockable locally, `ai_parse_document()` in
    real Databricks) is required for the scanned/photographed subset.
- **Filename taxonomy in `raw_documents/synthetic/`** (140 files, exact 1:1
  match against `arrival_manifest.csv` — re-verified after an initial
  miscounted `ls` pass) encodes ground-truth
  classification signal the brief expects the pipeline to *derive*, not
  read from the filename: `*_CIOMS_initial`, `*_manufacturer_initial`,
  `*_followup`/`*_followup_scan`, `*_scanned_form`, `*_mobile_photo`,
  `duplicate_<n>_<original filename>`, `low_quality_<n>_<...>`,
  `rescan_<n>_<...>`, `non_case_<n>_<...>`. The pipeline's classifier output
  must be validated against this naming as an informal ground truth during
  development, but must **not** parse the filename as a production
  extraction mechanism — real intake filenames will not follow this
  convention.

## Functional requirements

1. **Idempotent incremental document ingestion (Bronze)**: register every
   file under `data/raw/documents/**` (PDF/JPG/PNG) capturing file path,
   name, extension, size, arrival metadata (from `arrival_manifest.csv` for
   the assignment set; from actual landing metadata in production),
   modification time, SHA-256 checksum, ingestion timestamp, and processing
   status. Re-ingesting the same file (same checksum) must not create a
   second Bronze document row or a second case — checksum is the natural
   dedup key at the file level, independent of the Silver-level content/
   near-duplicate detection in Functional requirement 4.
2. **Content capture**: persist extracted raw text/OCR payload
   (`bronze_document_content`) and the raw extraction service response
   (`bronze_extraction_payloads`) separately from the structured Bronze
   document registry, preserving source fidelity per `docs/TIMED_MVP.md`'s
   Bronze contract.
3. **Classification**: classify each document into `case_report`,
   `follow_up`, `supporting_document`, `duplicate`, or
   `unreadable_quarantined`, using extracted content (form title/section
   headers present, case-reference pattern match, narrative presence) —
   not filename. Route `unreadable_quarantined` outcomes (failed
   extraction, extraction confidence below threshold, non-case content) to
   `silver_review_queue`/`dq_quarantine` rather than silently dropping them
   (brief's explicit non-negotiable).
4. **Extraction**: extract case reference, report type
   (initial/follow-up), report/received dates, patient age band/sex,
   facility/district, suspect product(s), reaction(s), seriousness +
   criterion, outcome, reporter type, narrative text, and an extraction
   confidence score for every field group. A document with N suspect
   products or M reactions produces N/M linked child rows, never a
   flattened single row (`silver_case_products`, `silver_case_reactions`)
   — matches the historical CSV's own event grain (Verified-source finding
   above) and the brief's Section 6 model.
5. **Deterministic parser for digitally-generated text**: implement a
   label/position-based parser for the CIOMS/manufacturer/non-case text-PDF
   subset (Verified-source finding above) as the primary extraction path —
   this is the "deterministic parser" the brief explicitly permits.
6. **OCR/document-AI abstraction for scanned/photo subset**: implement an
   extraction-service interface (`extract_document(bytes, mime_type) ->
   ExtractionResult`) with two implementations: a `MockExtractionService`
   (deterministic, offline, used for local/CI testing) and a
   `DatabricksAIParseService` (calls `ai_parse_document()` against a real
   Databricks SQL warehouse, used in deployed dev/prod). Failure handling
   (timeout, unsupported format, empty response, low-confidence result)
   must route to quarantine with a `reason_code`, never raise an unhandled
   exception into the batch.
7. **Duplicate detection**: exact-checksum duplicates never create a second
   case (Functional requirement 1). Near-duplicate detection (same case
   reference re-submitted under a different filename/checksum, e.g. the
   `duplicate_<n>_*` and `rescan_<n>_*` naming pattern observed in the
   synthetic set) is a Silver-level match on extracted case reference +
   patient/product/reaction similarity, recorded in `silver_case_versions`
   and linked via `silver_document_links`, not blocked at Bronze.
8. **Follow-up linkage**: a follow-up document (`report type = FOLLOW-UP`
   or `*_followup*` content pattern) must link to its parent case by case
   reference and create a new `silver_case_versions` row, not a new case —
   case volume metrics must separate initial vs. follow-up counts per the
   brief's dashboard requirement.
9. **Reference mapping**: join extracted product/reaction/facility/district
   free text against `product_dictionary.csv`, `reaction_dictionary.csv`,
   `facility_master.csv`, `district_master.csv` to their standard IDs;
   unmatched values go to `reference_mapping_exceptions`, not silently
   dropped or silently passed through as free text into Gold.
10. **Seriousness derivation**: apply `seriousness_rules.csv`
    (criterion → derived seriousness) to reconcile extracted/asserted
    seriousness against the rule table; disagreement is a data-quality
    signal (recorded, not auto-corrected silently).
11. **Data quality and reconciliation**: mandatory-field completeness, valid
    date parsing (`try_to_date`, ANSI-safe), product/reaction standard
    mapping, duplicate detection, follow-up linkage, referential integrity
    against reference tables, pipeline reconciliation (documents ingested
    vs. cases produced vs. quarantined vs. published), and dashboard-total
    reconciliation (Gold distinct case counts must equal Silver accepted
    distinct case counts). Invalid records are quarantined with a
    machine-readable `reason_code` and a human-readable `comment`, matching
    this repo's standard WAP audit contract (`docs/TIMED_MVP.md`).
12. **Gold publication (WAP)**: `gold_adr_overview`, `gold_product_reaction`,
    `gold_facility_reporting`, `gold_pipeline_health`, built from accepted
    Silver only, published via write-audit-publish so a failed reconciliation
    never exposes a partial/inconsistent Gold state.
13. **Dashboard**: cover every bullet in the brief's Section 4 (case volume
    initial vs. follow-up over time; serious/non-serious with criteria and
    outcomes; top products/ingredients/reactions/classes/categories;
    district/region/facility/source-channel/reporter-type reporting;
    timeliness/completeness/extraction-confidence/missing-field rates;
    document processing status, failed/quarantined counts, duplicate rate,
    review backlog; drill-down filters from aggregate to case/document
    level without exposing uncontrolled free text). Historical 35K-row
    dataset is the primary analytics volume; the 140-document pipeline
    output demonstrates the same schema end-to-end at small scale.
14. **Orchestration**: a Databricks Workflow/Bundle job chaining Bronze →
    classify/extract → Silver → Gold/WAP → SQL validation → dashboard
    refresh, parameterized by environment (dev/prod), matching this repo's
    existing project job pattern (see `projects/09_github_sentiment_analytics/resources/`).

## Non-functional requirements

- No secrets, tokens, or connection strings committed (brief's explicit
  constraint) — any real OCR/AI service credential is a Databricks secret
  scope reference, never a literal.
- Idempotent/repeatable: rerunning the same input must not inflate case or
  dashboard counts (brief's explicit constraint) — enforced by checksum
  dedup at Bronze and case-reference+version dedup at Silver.
- Source documents are immutable; lineage from dashboard output back to
  source document and case version must be traceable end to end (brief's
  explicit constraint) — every Silver/Gold row carries the originating
  `document_id`/`case_version_id`.
- Dedicated dev/prod Unity Catalog catalogs, never `workspace`/`main`/
  `default` — same non-negotiable rule as every other project in this repo.
- All catalog/schema/grant objects are Terraform-owned.
- PII (patient initials, reporter name/contact) is classified and
  masked/excluded before Gold/dashboard exposure, consistent with this
  repo's minimal, non-blocking privacy default (`docs/TIMED_MVP.md`).

## Decisions required at planning approval

1. **Execution profile — resolved**: full delivery profile (this document,
   milestone-based), not `TIMED_MVP`'s 65-minute clock, because the source
   brief itself specifies a 4-hour recommended scope and a full versioned
   entity model with an oral defense. Chosen from the assignment document
   directly, not assumed from repo default.
2. **OCR/document-AI service — mock-first, ai_parse_document in dev**: no
   external OCR credential is available in this environment. Local/CI tests
   run against `MockExtractionService` (deterministic, seeded from the real
   CIOMS-form field layout observed above). The real dev job path calls
   Databricks `ai_parse_document()` per `docs/TIMED_MVP.md`'s AI-function
   guidance; an unavailable endpoint degrades to `NOT_RUN` plus quarantine,
   not a failed pipeline.
3. **Ingestion pattern — Auto Loader for the document stream, batch for the
   historical CSV**: Auto Loader (`cloudFiles`) is the natural fit for
   incremental PDF/JPG/PNG landing with built-in file-notification/checksum
   support; the 35K-row historical CSV is a one-time/periodic batch load,
   not a streaming source. Justification recorded here per the brief's
   explicit "the choice must be justified" constraint.
4. **Case grain — event-level child tables, case-level parent**: modeled as
   `silver_cases` (one row per case) + `silver_case_products` /
   `silver_case_reactions` (one row per case×product or case×reaction) to
   match both the brief's Section 6 suggested model and the historical
   CSV's actual observed grain (19,197 distinct cases across 35,000 event
   rows) — not flattened, per the brief's explicit warning.
5. **Reference facility/district data covers a subset of the historical
   region**: 60 facilities / 20 districts in the reference files fully
   cover the historical CSV's facility/district values (Verified-source
   finding: zero orphans). No open question here — reference data is
   sufficient as supplied.
6. **Synthetic document count — confirmed, no open question**:
   `arrival_manifest.csv` (140 rows) and `data/raw/documents/synthetic/`
   (140 files on disk) match exactly, 1:1, by filename. Bronze ingestion
   can treat the manifest as complete, authoritative arrival metadata for
   the assignment document set.
