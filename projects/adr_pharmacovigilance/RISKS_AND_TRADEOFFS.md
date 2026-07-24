# Risks and Trade-offs - ADR/AEFI Pharmacovigilance Document Intelligence

## OCR/document-AI is mocked, not real

**Risk**: ~55 of 140 real documents (scanned forms, mobile photos,
low-quality/rescanned variants) have no extractable text layer (confirmed
directly — `pypdf` returns empty text for these, not an error). No OCR
engine or Databricks workspace is available in this development
environment, so `MockOcrTextExtractor` honestly returns no text and an
explicit `no_ocr_service_configured_locally` error rather than fabricating
extracted fields.

**Mitigation**: these documents correctly route to `silver_review_queue`
with `reason_code=unreadable_no_text_or_low_confidence`, visible in the
"Pipeline health" dashboard page, not silently dropped. Production swaps in
`DatabricksAIParseService` (same `TextExtractor` interface) calling
`ai_parse_document()` against a real SQL warehouse — the interface boundary
was designed specifically so this swap requires no change to
`bronze.py`/`silver.py`. **Not yet done.**

## Reference mapping is exact-match only

**Risk**: 18 of 91 extracted products in the real document set don't match
`product_dictionary.csv` by exact case-insensitive name/brand — e.g.
`"GlargiBase"`, `"D1clofenac"`, `"Vasc1mab"` are deliberately
fictional/misspelled product names in the synthetic data, not present in
the 22-row dictionary. These correctly land in
`reference_mapping_exceptions` rather than being silently accepted as
free text or silently dropped.

**Mitigation**: documented as a known gap, not assumed accurate. A
production iteration would add fuzzy/synonym matching (edit-distance,
embeddings, or an `ai_query()`-based entity-resolution call) rather than
exact string match. **Not yet done** — out of scope for this delivery.

## Containerized `local-platform` gate not run for this project

**Risk**: 3 of 22 tests (`test_bronze.py`'s idempotency test, both tests in
`test_gold.py`) call `.format("delta")` writes or `CREATE DATABASE`, which
require Delta package configuration and (on Windows) `HADOOP_HOME`/
`winutils.exe` — neither is present on this bare host. Attempting them
directly surfaces `java.io.FileNotFoundException: HADOOP_HOME and
hadoop.home.dir are unset`, a pre-existing Windows-Spark limitation, not a
defect in the pipeline code. `docs/TIMED_MVP.md` documents exactly this
split: "Test Bronze and Silver with Spark/Chispa inside `local-platform/`
... Host PySpark results are diagnostic only and do not satisfy the local
runtime gate."

**Mitigation**: the 19 tests that don't require Delta/catalog operations
pass cleanly on host and were additionally cross-checked by hand against
all 140 real documents (see `STATUS.md` for the exact counts). The 3
Delta-dependent tests are written, logically reviewed, and ready to run;
they need `py -3.11 local-platform/manage.py test --project
projects/10_adr_pharmacovigilance` inside the Linux-based Docker image
(which has Delta/winutils configured) to produce real pass/fail evidence.
**This is the single most important open item before any Databricks
deployment claim can be made** — matches the exact gap called out for
project 09 in this repo, and the same lesson applies: a Docker/host
mismatch here is about *portability* evidence, separate from *logic
correctness* (already hand-verified against real data).

## Two "duplicate detection" mechanisms exist but only one is exercised by this dataset

**Risk/observation**: all 7 `duplicate_*` files in the assignment's
synthetic set turned out to be byte-identical (sha256 match) to their
originals, caught entirely at the Bronze checksum layer
(`bronze.dedupe_by_checksum`). Silver's separate near-duplicate detection
(same case reference, two different-byte INITIAL documents) has unit-test
coverage with synthetic input but no positive example in the real fixture
set — a real-world resubmission with even one byte different (a re-saved
PDF, a re-typed form) would exercise this path and has not been observed
here.

**Mitigation**: not a gap in coverage (both code paths exist and are
tested independently), just a note that the real dataset happened to only
exercise the simpler case.

## PAT / secrets handling

No credentials, tokens, or connection strings were introduced by this
delivery — every source in `data/raw/` is a static file, no live API/OAuth
flow was needed. The real OCR/AI service credential and Databricks
service-principal secrets, when wired up, must come from a Databricks
secret scope per `docs/TIMED_MVP.md`, never a notebook literal or committed
file — no exception has been taken from this rule.
