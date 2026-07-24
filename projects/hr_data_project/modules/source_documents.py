from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


SPREADSHEET_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

COUNTRY_TO_OFFICE = {
    "Uganda": "CO001",
    "Indonesia": "CO002",
    "Ghana": "CO003",
    "Peru": "CO004",
}
COUNTRY_TO_REGION = {
    "Uganda": "Africa",
    "Ghana": "Africa",
    "Indonesia": "Asia and the Pacific",
    "Peru": "Latin America and the Caribbean",
}


@dataclass(frozen=True)
class AssessmentPack:
    source_register: list[dict[str, object]]
    structured_rows: list[dict[str, object]]


def normalize_key(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z]+", "_", value.strip()).strip("_").lower()
    return value or "unnamed"


def stable_source_id(relative_path: str) -> str:
    return "SRC_" + hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:10].upper()


def document_type(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.stem.lower()
    if "05_structured_data" in parts:
        return "structured_workbook"
    if "01_strategic_and_regional" in parts:
        return "strategy_regional_pack"
    if "02_country_programme_documents" in parts:
        return "country_programme_document"
    if "03_office_workplans" in parts:
        return "office_workplan"
    if "04_periodic_office_reports" in parts:
        return "periodic_office_report"
    if "survey" in name:
        return "workforce_planning_survey"
    return "supporting_document"


def infer_country(path: Path) -> tuple[str, str, str]:
    text = path.as_posix().lower()
    for country, office_id in COUNTRY_TO_OFFICE.items():
        if country.lower() in text:
            return office_id, country, COUNTRY_TO_REGION[country]
    return "MULTI", "Multiple", "Multiple"


def infer_period(path: Path) -> str:
    text = path.as_posix()
    quarter = re.search(r"20\d{2}Q[1-4]", text)
    if quarter:
        return quarter.group(0)
    years = re.findall(r"20\d{2}", text)
    return "_".join(dict.fromkeys(years)) if years else "UNSPECIFIED"


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
    return " ".join(text.text or "" for text in xml.findall(".//w:t", WORD_NS)).strip()


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return " ".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return ""


def extract_text(path: Path) -> tuple[str, str, str]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path), "parsed_docx_xml", "PARSED"
    if suffix == ".pdf":
        text = extract_pdf_text(path)
        status = "PARSED" if text else "REGISTERED_TEXT_UNAVAILABLE"
        return text, "pypdf_text_extract" if text else "pdf_registered_only", status
    if suffix in {".png", ".jpg", ".jpeg"}:
        country = infer_country(path)[1]
        fallback = (
            f"Image source for {country} registered. OCR was not available in local MVP; "
            "filename and folder metadata identify the office report or workplan for review."
        )
        return fallback, "deterministic_image_metadata_fallback", "REGISTERED_OCR_NOT_RUN"
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore"), "plain_text", "PARSED"
    return "", "registered_only", "REGISTERED"


def spreadsheet_col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter.upper()) - 64
    return index - 1


def load_xlsx_rows(path: Path) -> list[tuple[str, int, dict[str, str | None]]]:
    rows: list[tuple[str, int, dict[str, str | None]]] = []
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_xml.findall("a:si", SPREADSHEET_NS):
                shared.append("".join(t.text or "" for t in item.findall(".//a:t", SPREADSHEET_NS)))
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        for sheet in workbook.findall("a:sheets/a:sheet", SPREADSHEET_NS):
            sheet_name = sheet.attrib["name"]
            rel_id = sheet.attrib[
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            ]
            target = rel_targets[rel_id]
            if not target.startswith("worksheets/"):
                target = "worksheets/" + target.split("/")[-1]
            sheet_xml = ET.fromstring(archive.read("xl/" + target))
            raw_rows: list[list[str | None]] = []
            for row in sheet_xml.findall("a:sheetData/a:row", SPREADSHEET_NS):
                values: list[tuple[int, str | None]] = []
                for cell in row.findall("a:c", SPREADSHEET_NS):
                    value_node = cell.find("a:v", SPREADSHEET_NS)
                    value = None if value_node is None else value_node.text
                    if cell.attrib.get("t") == "s" and value is not None:
                        value = shared[int(value)]
                    values.append((spreadsheet_col_index(cell.attrib.get("r", "A1")), value))
                width = max((position for position, _ in values), default=-1) + 1
                dense: list[str | None] = [None] * width
                for position, value in values:
                    dense[position] = value
                raw_rows.append(dense)
            if not raw_rows:
                continue
            headers = [normalize_key(str(value or "")) for value in raw_rows[0]]
            for row_number, row in enumerate(raw_rows[1:], start=2):
                payload = {
                    header: row[index] if index < len(row) else None
                    for index, header in enumerate(headers)
                    if header
                }
                if any(value not in (None, "") for value in payload.values()):
                    rows.append((sheet_name, row_number, payload))
    return rows


def discover_pack(base_path: str | Path) -> AssessmentPack:
    root = Path(base_path)
    files = sorted(path for path in root.rglob("*") if path.is_file())
    register: list[dict[str, object]] = []
    structured_rows: list[dict[str, object]] = []
    for file_path in files:
        relative = file_path.relative_to(root).as_posix()
        source_id = stable_source_id(relative)
        office_id, country, region = infer_country(file_path)
        doc_type = document_type(file_path)
        text, method, status = extract_text(file_path)
        text_excerpt = " ".join(text.split())[:4000]
        register.append(
            {
                "source_id": source_id,
                "source_file": relative,
                "format": file_path.suffix.lower().lstrip(".") or "unknown",
                "document_type": doc_type,
                "office_id": office_id,
                "country": country,
                "region": region,
                "reporting_period": infer_period(file_path),
                "processing_status": status,
                "extraction_method": method,
                "evidence_text": text_excerpt,
                "source_size_bytes": file_path.stat().st_size,
            }
        )
        if file_path.suffix.lower() == ".xlsx":
            for sheet_name, row_number, payload in load_xlsx_rows(file_path):
                structured_rows.append(
                    {
                        "source_id": source_id,
                        "source_file": relative,
                        "sheet_name": sheet_name,
                        "sheet_key": normalize_key(sheet_name),
                        "row_number": row_number,
                        "row_json": json.dumps(payload, sort_keys=True),
                    }
                )
    return AssessmentPack(register, structured_rows)
