# Pipeline Performance Notes

MVP performance evidence status: COMPLETE

## Bronze profile
Tested directly against the 100k row NBA sample events dataset. Zero nulls in historical columns.

## Transformation decisions
- **Bronze grain**: one row per distinct event checksum.
- **Silver grain**: event parsed and typed correctly.
- **Early filter/projection**: run once per document before any join.
- **Joins**: reference mapping is an in-memory broadcast.
- **No Python UDF** in the core Bronze/Silver/Gold path.

## Query-plan evidence
`NOT_APPLICABLE` for the current bounded local logic.

## Lineage
Source snapshot: `data/raw/` as committed. Code commit: recorded at PR time. Job/run IDs pass through.
