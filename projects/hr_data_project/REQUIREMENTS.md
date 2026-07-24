# Requirements - HR Data Workforce Planning

## Source-Specific Contract

This project implements the supplied UNDP-style HR technology assessment pack in
`data/raw`. The MVP must answer:

- Which skills should be prioritized by country office and region.
- What evidence supports the priority.
- Whether the office should recruit, mobilize existing talent, use temporary surge
  support, invest in capability development, or monitor.

## Required MVP Outputs

- `bronze_source_register`: one row per registered file with source id, filename,
  format, document type, country, region, period, processing status, extraction method,
  and evidence excerpt.
- `bronze_structured_rows`: parsed workbook rows with sheet metadata and row JSON.
- `silver_workforce_signals`: qualitative and survey evidence converted to skill demand
  signals with demand direction, urgency, confidence, and negation flag.
- `silver_skill_supply`: aggregate office/skill supply using assessed proficiency,
  employment status, mobility readiness, retention risk, and planned positions.
- `gold_workforce_gap`: office/skill Gold gap grain with demand score, supply FTE score,
  gap value/severity, urgency, strategic alignment, source count, recommended action,
  evidence summary, and model note.

## Dashboard Questions

- Largest workforce gaps by country office and skill.
- Regional demand and supply pattern.
- Recommended workforce action supported by source evidence.

## Constraints

- Register every supplied file; extract usable evidence from at least eight documents
  spanning structured and unstructured sources.
- Do not fabricate missing values. Image OCR unavailable locally is reported as an OCR
  fallback, not as parsed text.
- No employee-level details are shown in Gold or dashboard outputs.
- Local and PR validation do not call remote AI; Databricks AI document/NLP extraction
  remains `NOT_RUN` for Version 0 unless approved during dev deployment.
