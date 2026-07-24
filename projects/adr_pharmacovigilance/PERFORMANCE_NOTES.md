# Pipeline Performance Notes

MVP performance evidence status: COMPLETE

## Bronze profile

Measured directly against the real 140-document set and the 35,000-row
historical CSV (see `REQUIREMENTS.md` "Verified-source requirements" for
full profiling): 133 distinct documents after checksum dedup (7 exact
byte-identical duplicates), 19,197 distinct cases across 35,000 historical
event rows, zero orphan foreign keys against the 4 reference dictionaries,
zero nulls in any checked historical column. `report_source` distribution:
Digital PDF 12,310, Scanned PDF 12,111, Mobile image 6,966, Manufacturer
XML/PDF 3,613 — no single channel dominates, all four are materially
represented. This is a fixed, bounded dataset (140 documents + one 35K-row
CSV), not a large/many-file source — no deterministic-manifest sampling was
needed; every provided row/file is processed.

## Transformation decisions

- **Bronze grain**: one row per distinct document checksum
  (`bronze_documents`), plus a full un-deduped arrival ledger
  (`bronze_document_arrivals`) for lineage. Historical CSV loaded at its
  native event grain (case x product x reaction) — no grain change at
  Bronze.
- **Silver grain**: case (`silver_cases`) x version
  (`silver_case_versions`) x product/reaction (`silver_case_products`/
  `silver_case_reactions`), matching the historical table's own observed
  grain. Deduplication order is deterministic: exact-checksum duplicates
  resolved by `file_name` sort at Bronze; same-case-reference INITIAL
  duplicates resolved by `document_id` sort at Silver (see
  `silver.build_silver`).
- **Early filter/projection**: `dedupe_by_checksum` and
  `classify_and_extract` run once per document before any join; Gold SQL
  filters `processing_status = 'READY_FOR_DASHBOARD'` before aggregation,
  not after.
- **Joins**: reference-dictionary mapping (`apply_reference_mapping`) is an
  in-memory dict lookup against 4 small dictionaries (22/22/60/20 rows) —
  no shuffle-relevant join; the Spark-side equivalent in production would
  broadcast these dimension tables.
- **No Python UDF** in the core Bronze/Silver/Gold path — extraction runs
  driver-side over a bounded 140-file set (a legitimate simplification at
  this scale, documented in `README.md`; production Auto Loader +
  `ai_parse_document()` replaces this, still no per-row Python UDF).

## Query-plan evidence

`NOT_APPLICABLE` for the current bounded local logic (140 documents, 35K
historical rows — well under any threshold where join/window/repartition
strategy matters) — no `explain("formatted")` review was needed for
correctness at this scale. This becomes required once Gold SQL runs against
a live warehouse with the full historical volume; tracked as a Docker-gate
/ Databricks-dev follow-up, not skipped silently.

**Measured elapsed time** (host Python 3.11, driver-side, excludes Spark
session startup and Delta writes — those require the Docker/Databricks
gate, see `RISKS_AND_TRADEOFFS.md`):

- Bronze (140 documents: checksum, extraction, classification, parsing):
  **1.48s**
- Silver (case assembly, reference mapping, DQ quarantine): **0.01s**
- Total: **1.48s**, well under the 8-minute `target_job_minutes` budget.
  Spark/Delta write overhead (table creation, MERGE, WAP staging) is not
  included in this figure and must be measured in the Docker gate or a real
  Databricks dev run before this note can claim the *deployed* job also
  meets the 8-minute target — flagged here rather than assumed.

AQE (`adaptive_query_execution: true`) and one-pass WAP audit
(`gold.write_gold_wap` builds each Gold table once into `_staging`, reads
reconciliation once, then either promotes or leaves the previous Gold table
unchanged — no second full recompute) are both satisfied by design; no
Cartesian product, repeated full scan on the same table, or avoidable
exchange is present in the SQL in `gold.py`.

## Lineage

Source snapshot: `data/raw/` as committed in this delivery (no watermark —
static fixture set). Code commit: recorded at PR time. Job/run IDs: every
Bronze/Silver/Gold row carries `run_id`; `gold_pipeline_health` is keyed by
`run_id`. Named table edges: `bronze_document_arrivals` ->
`bronze_documents` -> `silver_case_versions` -> `silver_cases` ->
`gold_adr_overview_cases` -> `gold_adr_overview`, with `document_id` and
`case_reference` carried through every stage for traceability. Publication
decision and reconciliation counts: `gold.reconcile` /
`sql/validate_outputs.sql`. Real job/run-ID evidence from a deployed
Databricks run is recorded in `STATUS.md` once the dev job has actually run.
