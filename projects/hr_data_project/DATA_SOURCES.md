# Data Sources - HR Data Workforce Planning

## Snapshot

Source snapshot: `data/raw`, copied from the root `hr data project` intake.

The pack contains 18 candidate data files plus `Candidate_Instructions.pdf` and
`START_HERE.txt`. The pipeline registers all 20 project-local files and parses the four
structured-data workbooks plus the Ghana periodic-report workbook.

## Files

- `01_Strategic_and_Regional`: strategic plan extract and regional programme/workplan
  PDFs.
- `02_Country_Programme_Documents`: Ghana, Indonesia, Peru PDFs and Uganda DOCX.
- `03_Office_Workplans`: Ghana PNG, Indonesia/Peru PDFs, Uganda DOCX.
- `04_Periodic_Office_Reports`: Ghana XLSX, Indonesia PDF, Peru JPG, Uganda DOCX.
- `05_Structured_Data`: job architecture/skills, office-region reference, workforce and
  talent data, and workforce planning survey XLSX files.

## Extraction

- XLSX: standard-library Open XML reader, staged as `bronze_structured_rows`.
- DOCX: standard-library Word XML text extraction.
- PDF: `pypdf` text extraction.
- PNG/JPG: registered with deterministic metadata fallback; OCR is explicitly marked
  `REGISTERED_OCR_NOT_RUN`.

## Source Grain

- Bronze source register grain: one row per file.
- Bronze structured row grain: one row per workbook sheet row.
- Silver signal grain: one source/office/skill evidence signal.
- Silver supply grain: one office/skill aggregate.
- Gold grain: one office/skill workforce gap.
