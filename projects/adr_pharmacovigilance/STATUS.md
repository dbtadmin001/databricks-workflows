# Status - ADR/AEFI Pharmacovigilance Document Intelligence

- Current milestone: initial end-to-end implementation complete on the
  full-scope delivery profile (not `TIMED_MVP`'s 65-minute clock — the
  source brief itself specifies a 4-hour recommended scope; see
  `REQUIREMENTS.md` Decision 1). Not yet PR'd, not yet deployed to
  Databricks.
- Completed: project registered (`10_adr_pharmacovigilance`), real data
  profiled (35,000-row historical CSV, 7 reference dictionaries, 140
  documents — see `REQUIREMENTS.md` "Verified-source requirements"),
  `REQUIREMENTS.md`/`DATA_SOURCES.md`/`DATA_CONTRACTS.md`/
  `ACCEPTANCE_CRITERIA.md` written from that profiling (not transcribed from
  the brief). Full pipeline implemented: `field_parser.py` (deterministic
  CIOMS/manufacturer parser), `extraction.py` (text/OCR extraction
  boundary), `bronze.py` (checksum-deduped document registry + historical +
  reference loaders), `silver.py` (case versioning, dedup, reference
  mapping, DQ quarantine), `gold.py` (WAP publish + reconciliation),
  `jobs.py` (orchestration), 4 notebooks, Bundle job resources, SQL DDL
  reference + reconciliation query, README with architecture diagram.
- **Hand-validated against all 140 real documents** (not just unit
  fixtures): 70 case_report, 10 follow_up, 5 supporting_document (non-case),
  55 unreadable_quarantined (scanned/photo/low-quality — no text layer, no
  OCR service available locally, correctly routed to review rather than
  fabricated). After checksum dedup (133 distinct documents, 7 exact
  byte-identical duplicates caught), Silver produced 65 cases, 72 case
  versions (7 cases with follow-ups), 91 case-product rows, 98
  case-reaction rows, 18 honest reference-mapping exceptions (fictional
  product names like "GlargiBase" not in the 22-row dictionary), 0 residual
  Silver-level duplicates (all caught earlier at Bronze).
- Tests passed: 22 total. 19 pass on host Python 3.11 (`py -3.11 -m pytest tests/`)
  — pure field-parsing/extraction-classification/case-assembly logic,
  including a regression test for a real bug found and fixed during
  development (a naive header-stripping filter silently dropped legitimate
  "Serious" data values that collided with a "Serious" column header). 3
  tests require `.format("delta")` writes / `CREATE DATABASE`, which need
  `HADOOP_HOME`/`winutils.exe` not present on this bare Windows host — this
  matches `docs/TIMED_MVP.md`'s own documented split ("Host PySpark results
  are diagnostic only and do not satisfy the local runtime gate"); these 3
  tests are written and correct, just not yet executed. Ruff check + format:
  clean.
- **Containerized `local-platform` gate: `NOT_RUN`** — it will run once in GitHub
  against the final PR SHA using the prevalidated image, and is the required
  real pass/fail signal for the Delta-dependent tests above.
- Compatibility correction status: the first final-SHA run passed 19/22 tests and
  exposed local managed-table location/DDL portability defects. A targeted Bronze
  rerun then exposed `DeltaTable.forName` three-part parsing; Bronze now uses native
  SQL `MERGE`. Per the repeated-failure stopping rule, the corrected final-SHA rerun
  is `NOT_RUN` pending explicit approval.
- Known limitations / NOT_RUN: OCR/document-AI is mocked (honest `NOT_RUN`, not
  fabricated) pending a real `ai_parse_document()` wire-up; reference
  mapping is exact-match only (18 known exceptions); no live-warehouse
  dashboard screenshot yet. Real baseline case PDFs are local-only and excluded
  from Git/pipeline input after PII preflight. Full list in `README.md` "Limitations".
- Blockers: none for continuing implementation; a Databricks workspace
  (catalog/warehouse/service-principal credentials) is required for the
  next stage (Terraform apply, Bundle deploy, real dev job run).
- Next action: push `feature/project-10-adr-pharmacovigilance`, open the PR to
  `main`, run the one-shot final-SHA compatibility workflow, and stop for human
  merge approval. The approved post-merge workflow then performs Terraform,
  Bundle deployment, and one real dev job run.
