# Data Contracts - HR Data Workforce Planning

Versioned executable contracts live in
`src/hr_data_project/schema_contracts.json`.

## Bronze

`bronze_source_register` preserves file-level source fidelity and ingestion metadata:
source id, source file, format, document type, office/country/region, reporting period,
processing status, extraction method, evidence excerpt, file size, source URI, run id,
ingestion timestamp, and deterministic record hash.

`bronze_structured_rows` is an internal Bronze staging table for workbook rows:
source id, file, sheet name/key, row number, row JSON, and ingestion metadata.

## Silver

`silver_workforce_signals` converts document and survey evidence to typed analytical
signals: source id/file, document type, office/country/region, reporting period,
skill id/name, demand direction, urgency, evidence text, confidence, and negation flag.

`silver_skill_supply` aggregates supply by office and skill. It uses assessed
proficiency, active employment status, mobility readiness, retention risk, and
funding-weighted planned positions. Employee identifiers are not published downstream.

Reason-coded rejects are materialized in `hr_data_project_quarantine`.

## Gold

`gold_workforce_gap` uses Spark SQL over accepted Silver tables. Its business grain is
one row per office and skill. WAP publishes only explicit columns and records
publication status in `hr_data_project_gold_publication_audit`.

Required Gold fields: office, country, region, skill id/name, demand score, supply FTE
score, gap value/severity, urgency, strategic alignment, source count, recommended
action, evidence summary, and assumption/model note.
