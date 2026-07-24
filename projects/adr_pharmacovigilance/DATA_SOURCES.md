# Data Sources - ADR/AEFI Pharmacovigilance Document Intelligence

All pipeline sources are static files provided with the assignment and copied into
project isolation under `data/raw/`. No live/external source is called. Full profiling
evidence is in `REQUIREMENTS.md` ("Verified-source requirements"). Real baseline case
documents remain local-only because they may contain patient or reporter PII; they are
excluded from Git and are not pipeline input.

| Source | Path | Rows/files | Format | Role |
|---|---|---|---|---|
| Synthetic case documents | `data/raw/documents/synthetic/` | 140 files (133 distinct after checksum dedup) | PDF/JPG/PNG | Primary document-pipeline input |
| Baseline sample documents | local-only ignored path | 4 files | PDF | Private reference only; excluded from Git and pipeline input after PII preflight |
| Historical ADR events | `data/raw/historical/historical_adr_events_35000.csv` | 35,000 rows, 19,197 distinct cases | CSV | Primary dashboard analytics volume (batch load) |
| Arrival manifest | `data/raw/reference/arrival_manifest.csv` | 140 rows, 1:1 match to synthetic documents | CSV | Authoritative arrival metadata for Bronze |
| Facility master | `data/raw/reference/facility_master.csv` | 60 rows | CSV | Facility standard-name mapping |
| District master | `data/raw/reference/district_master.csv` | 20 rows | CSV | District standard-name mapping |
| Product dictionary | `data/raw/reference/product_dictionary.csv` | 22 rows | CSV | Product/ingredient standard-name mapping |
| Reaction dictionary | `data/raw/reference/reaction_dictionary.csv` | 22 rows | CSV | Reaction standard-term mapping |
| Seriousness rules | `data/raw/reference/seriousness_rules.csv` | 7 rows | CSV | Criterion -> derived seriousness |
| Pipeline status reference | `data/raw/reference/pipeline_status_reference.csv` | 6 rows | CSV | Status code descriptions |
| Assignment brief + wireframe | `data/raw/assignment/` | 2 files | PDF/PNG | Requirements source, not pipeline input |

No executable/live source or deterministic fallback decision is needed —
every input is already a deterministic, versioned file under project
isolation. Re-running the pipeline against the same `data/raw/` contents is
guaranteed idempotent (checksum-keyed Bronze, case-reference-keyed Silver).
