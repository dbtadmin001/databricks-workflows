"""Deterministic, label/position-based field parser for digitally generated
ADR/AEFI case documents (CIOMS forms and manufacturer case reports).

This module operates purely on already-extracted text (see `extraction.py`
for the text/OCR extraction boundary) and never touches raw PDF/image bytes,
so it is fully unit-testable without any PDF/OCR dependency. Layout observed
directly from `data/raw/documents/synthetic/*_CIOMS_initial.pdf` and
`*_manufacturer_initial.pdf` (see REQUIREMENTS.md "Verified-source
requirements") — both formats render as a sequence of `Label\nValue\n` pairs
plus fixed-width narrative/table blocks, not free-form prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractedProduct:
    reported_product: str
    active_ingredient: str | None = None


@dataclass(frozen=True)
class ExtractedReaction:
    reaction_term: str
    seriousness: str | None = None
    outcome: str | None = None


@dataclass(frozen=True)
class ParsedFields:
    document_format: str  # "cioms" | "manufacturer" | "unknown"
    case_reference: str | None = None
    report_type: str | None = None
    report_date: str | None = None
    received_date: str | None = None
    patient_age: str | None = None
    patient_sex: str | None = None
    facility: str | None = None
    district: str | None = None
    products: list[ExtractedProduct] = field(default_factory=list)
    reactions: list[ExtractedReaction] = field(default_factory=list)
    seriousness: str | None = None
    seriousness_criterion: str | None = None
    outcome: str | None = None
    reporter_type: str | None = None
    narrative: str | None = None
    missing_fields: list[str] = field(default_factory=list)


CIOMS_TITLE = "CIOMS FORM - SUSPECT ADVERSE REACTION REPORT"
MANUFACTURER_TITLE_INITIAL = "PHARMACOVIGILANCE CASE REPORT - INITIAL"
MANUFACTURER_TITLE_FOLLOWUP = "PHARMACOVIGILANCE CASE REPORT - FOLLOW-UP"

_CIOMS_PRODUCT_HEADER = "No."
_CIOMS_PRODUCT_END_MARKERS = ("III. CONCOMITANT", "IV. MANUFACTURER")
_MANUFACTURER_PRODUCT_HEADER = "Suspect products"
_MANUFACTURER_EVENTS_HEADER = "Reported events"
_MANUFACTURER_NOTES_HEADER = "Assessment and workflow notes"


def detect_document_format(text: str) -> str:
    head = text.strip().splitlines()[0].strip() if text.strip() else ""
    if head == CIOMS_TITLE:
        return "cioms"
    if head in (MANUFACTURER_TITLE_INITIAL, MANUFACTURER_TITLE_FOLLOWUP):
        return "manufacturer"
    return "unknown"


def _label_value_map(lines: list[str], labels: tuple[str, ...]) -> dict[str, str]:
    """Map each known single-line label to the line immediately following it."""
    result: dict[str, str] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped in labels and idx + 1 < len(lines):
            result[stripped] = lines[idx + 1].strip()
    return result


def _slice_between(
    lines: list[str],
    start_marker: str,
    end_markers: tuple[str, ...],
    header_cols: tuple[str, ...] = (),
) -> list[str]:
    """Return the data rows of a labeled table: everything strictly between
    `start_marker` and the first `end_markers` line, with the leading
    `header_cols` stripped **positionally** (not by value-equality) — a data
    cell can legitimately equal a header word (e.g. a seriousness value of
    "Serious" under a "Serious" column header), so filtering by membership
    would silently drop real data."""
    start = None
    for idx, line in enumerate(lines):
        if line.strip().startswith(start_marker):
            start = idx + 1
            break
    if start is None:
        return []
    end = len(lines)
    for idx in range(start, len(lines)):
        if any(lines[idx].strip().startswith(marker) for marker in end_markers):
            end = idx
            break
    block = lines[start:end]
    if header_cols and len(block) >= len(header_cols):
        if tuple(ln.strip() for ln in block[: len(header_cols)]) == header_cols:
            block = block[len(header_cols) :]
    return block


def _parse_cioms(text: str) -> ParsedFields:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    labels = (
        "Case reference",
        "Report type",
        "Country",
        "Date of report",
        "Patient initials",
        "Age",
        "Sex",
        "Reaction onset",
        "Seriousness",
        "Criterion",
        "Reaction(s)",
        "Outcome",
        "District",
        "Facility",
        "Reporter type",
        "Date received",
        "Source",
    )
    values = _label_value_map(lines, labels)

    narrative_lines: list[str] = []
    capture = False
    for line in lines:
        if line.strip().startswith("Narrative:"):
            capture = True
            narrative_lines.append(line.strip().removeprefix("Narrative:").strip())
            continue
        if capture:
            if line.strip().startswith("II. SUSPECT"):
                break
            narrative_lines.append(line.strip())
    narrative = " ".join(narrative_lines).strip() or None

    # Header row is: No. | Reported product | Active ingredient | Dose | Route | Indication
    # then repeating 6-token data rows (row number, product, ingredient, dose, route, indication).
    product_header = ("Reported product", "Active ingredient", "Dose", "Route", "Indication")
    data_lines = _slice_between(
        lines, _CIOMS_PRODUCT_HEADER, _CIOMS_PRODUCT_END_MARKERS, product_header
    )
    products: list[ExtractedProduct] = []
    row_width = 6
    for i in range(0, len(data_lines) - row_width + 1, row_width):
        row = data_lines[i : i + row_width]
        if not row[0].strip().isdigit():
            continue
        products.append(
            ExtractedProduct(reported_product=row[1].strip(), active_ingredient=row[2].strip())
        )

    reaction_terms = [t.strip() for t in values.get("Reaction(s)", "").split(",") if t.strip()]
    reactions = [
        ExtractedReaction(
            reaction_term=term,
            seriousness=values.get("Seriousness"),
            outcome=values.get("Outcome"),
        )
        for term in reaction_terms
    ]

    return ParsedFields(
        document_format="cioms",
        case_reference=values.get("Case reference"),
        report_type=values.get("Report type"),
        report_date=values.get("Date of report"),
        received_date=values.get("Date received"),
        patient_age=values.get("Age"),
        patient_sex=values.get("Sex"),
        facility=values.get("Facility"),
        district=values.get("District"),
        products=products,
        reactions=reactions,
        seriousness=values.get("Seriousness"),
        seriousness_criterion=values.get("Criterion"),
        outcome=values.get("Outcome"),
        reporter_type=values.get("Reporter type"),
        narrative=narrative,
    )


def _parse_manufacturer(text: str) -> ParsedFields:
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    report_type = "FOLLOW-UP" if "FOLLOW-UP" in lines[0] else "INITIAL"
    labels = ("Manufacturer case number", "Country", "Receipt date", "Report date", "Source")
    values = _label_value_map(lines, labels)

    narrative_lines: list[str] = []
    capture = False
    for line in lines:
        if line.strip() == "Case narrative":
            capture = True
            continue
        if capture:
            if line.strip() == _MANUFACTURER_PRODUCT_HEADER:
                break
            narrative_lines.append(line.strip())
    narrative = " ".join(narrative_lines).strip() or None

    product_header = ("Product role", "Reported product", "Standard ingredient", "Dose / route")
    product_rows = _slice_between(
        lines, _MANUFACTURER_PRODUCT_HEADER, (_MANUFACTURER_EVENTS_HEADER,), product_header
    )
    products: list[ExtractedProduct] = []
    for i in range(0, len(product_rows) - 3, 4):
        role, name, ingredient, _dose = product_rows[i : i + 4]
        if role.strip() != "Suspect":
            continue
        products.append(
            ExtractedProduct(reported_product=name.strip(), active_ingredient=ingredient.strip())
        )

    event_header = ("Reported term", "Category", "Serious", "Outcome")
    event_rows = _slice_between(
        lines, _MANUFACTURER_EVENTS_HEADER, (_MANUFACTURER_NOTES_HEADER,), event_header
    )
    reactions: list[ExtractedReaction] = []
    for i in range(0, len(event_rows) - 3, 4):
        term, _category, seriousness, outcome = event_rows[i : i + 4]
        reactions.append(
            ExtractedReaction(
                reaction_term=term.strip(), seriousness=seriousness.strip(), outcome=outcome.strip()
            )
        )

    case_seriousness = reactions[0].seriousness if reactions else None
    case_outcome = reactions[0].outcome if reactions else None

    return ParsedFields(
        document_format="manufacturer",
        case_reference=values.get("Manufacturer case number"),
        report_type=report_type,
        report_date=values.get("Report date"),
        received_date=values.get("Receipt date"),
        products=products,
        reactions=reactions,
        seriousness=case_seriousness,
        outcome=case_outcome,
        reporter_type=values.get("Source"),
        narrative=narrative,
    )


REQUIRED_FIELDS = (
    "case_reference",
    "report_type",
    "report_date",
    "products",
    "reactions",
)


def _apply_missing_fields(parsed: ParsedFields) -> ParsedFields:
    missing = []
    for name in REQUIRED_FIELDS:
        value = getattr(parsed, name)
        if value in (None, "", []):
            missing.append(name)
    return ParsedFields(**{**parsed.__dict__, "missing_fields": missing})


def parse_document_text(text: str) -> ParsedFields:
    """Parse a digitally-generated case document's already-extracted text into
    structured fields. Returns `document_format="unknown"` (all fields empty,
    `missing_fields` populated) for text that doesn't match either known
    layout — the caller routes this to classification/quarantine, this
    function never raises on unrecognized input."""
    fmt = detect_document_format(text)
    if fmt == "cioms":
        parsed = _parse_cioms(text)
    elif fmt == "manufacturer":
        parsed = _parse_manufacturer(text)
    else:
        parsed = ParsedFields(document_format="unknown")
    return _apply_missing_fields(parsed)
