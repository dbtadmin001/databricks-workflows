"""Silver layer: assembles Bronze document rows into versioned cases,
case-level product/reaction child rows, document links, a human review
queue, and reference-mapping/data-quality quarantine. Pure Python over the
Bronze row dicts (see bronze.py) so case-assembly logic is testable without
a SparkSession; `to_spark_tables` is the thin PySpark boundary for writing
Delta tables.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

CASE_REPORT = "case_report"
FOLLOW_UP = "follow_up"
SUPPORTING_DOCUMENT = "supporting_document"
UNREADABLE = "unreadable_quarantined"


def _schema(fields: list[tuple[str, object]]) -> StructType:
    return StructType([StructField(name, data_type, True) for name, data_type in fields])


SILVER_TABLE_SCHEMAS = {
    "silver_cases": _schema(
        [
            ("case_reference", StringType()),
            ("first_report_date", StringType()),
            ("latest_report_date", StringType()),
            ("latest_case_version_id", StringType()),
            ("version_count", IntegerType()),
            ("duplicate_document_count", IntegerType()),
            ("current_seriousness", StringType()),
            ("current_outcome", StringType()),
        ]
    ),
    "silver_case_versions": _schema(
        [
            ("case_version_id", StringType()),
            ("case_reference", StringType()),
            ("version_number", IntegerType()),
            ("document_id", StringType()),
            ("report_type", StringType()),
            ("report_date", StringType()),
            ("received_date", StringType()),
            ("patient_age", StringType()),
            ("patient_sex", StringType()),
            ("facility", StringType()),
            ("district", StringType()),
            ("seriousness", StringType()),
            ("seriousness_criterion", StringType()),
            ("outcome", StringType()),
            ("reporter_type", StringType()),
            ("narrative", StringType()),
            ("extraction_confidence", DoubleType()),
            ("missing_fields", StringType()),
            ("facility_id", StringType()),
            ("district_id", StringType()),
        ]
    ),
    "silver_case_products": _schema(
        [
            ("case_version_id", StringType()),
            ("case_reference", StringType()),
            ("reported_product", StringType()),
            ("active_ingredient", StringType()),
            ("standard_product_id", StringType()),
        ]
    ),
    "silver_case_reactions": _schema(
        [
            ("case_version_id", StringType()),
            ("case_reference", StringType()),
            ("reaction_term", StringType()),
            ("seriousness", StringType()),
            ("outcome", StringType()),
            ("standard_reaction_id", StringType()),
        ]
    ),
    "silver_document_links": _schema(
        [
            ("link_id", StringType()),
            ("document_id", StringType()),
            ("case_reference", StringType()),
            ("link_type", StringType()),
            ("target_document_id", StringType()),
        ]
    ),
    "silver_review_queue": _schema(
        [
            ("review_id", StringType()),
            ("document_id", StringType()),
            ("case_reference", StringType()),
            ("reason_code", StringType()),
            ("comment", StringType()),
            ("status", StringType()),
        ]
    ),
    "reference_mapping_exceptions": _schema(
        [
            ("exception_id", StringType()),
            ("case_reference", StringType()),
            ("exception_type", StringType()),
            ("raw_value", StringType()),
        ]
    ),
    "dq_quarantine": _schema(
        [
            ("case_version_id", StringType()),
            ("case_reference", StringType()),
            ("reason_code", StringType()),
            ("comment", StringType()),
        ]
    ),
}


@dataclass(frozen=True)
class SilverBuild:
    cases: list[dict]
    case_versions: list[dict]
    case_products: list[dict]
    case_reactions: list[dict]
    document_links: list[dict]
    review_queue: list[dict]


def _fields(row: dict) -> dict:
    return json.loads(row["parsed_fields_json"])


def build_silver(bronze_rows: list[dict]) -> SilverBuild:
    case_versions: list[dict] = []
    case_products: list[dict] = []
    case_reactions: list[dict] = []
    document_links: list[dict] = []
    review_queue: list[dict] = []

    by_case_ref: dict[str, list[dict]] = {}
    for row in bronze_rows:
        if row["classification"] not in (CASE_REPORT, FOLLOW_UP):
            reason = (
                "unreadable_no_text_or_low_confidence"
                if row["classification"] == UNREADABLE
                else "non_case_supporting_document"
            )
            review_queue.append(
                {
                    "review_id": str(uuid.uuid4()),
                    "document_id": row["document_id"],
                    "case_reference": None,
                    "reason_code": reason,
                    "comment": f"classification={row['classification']}, confidence={row['extraction_confidence']}",
                    "status": "PENDING",
                }
            )
            continue
        fields = _fields(row)
        case_ref = fields.get("case_reference")
        if not case_ref:
            review_queue.append(
                {
                    "review_id": str(uuid.uuid4()),
                    "document_id": row["document_id"],
                    "case_reference": None,
                    "reason_code": "missing_case_reference",
                    "comment": "Recognized layout but no case reference parsed",
                    "status": "PENDING",
                }
            )
            continue
        by_case_ref.setdefault(case_ref, []).append({**row, "_fields": fields})

    cases: list[dict] = []
    for case_ref, docs in by_case_ref.items():
        initials = sorted(
            (d for d in docs if (d["_fields"].get("report_type") or "").upper() == "INITIAL"),
            key=lambda d: d["document_id"],
        )
        follow_ups = sorted(
            (d for d in docs if (d["_fields"].get("report_type") or "").upper() == "FOLLOW-UP"),
            key=lambda d: d["_fields"].get("report_date") or "",
        )

        if not initials:
            for doc in follow_ups:
                review_queue.append(
                    {
                        "review_id": str(uuid.uuid4()),
                        "document_id": doc["document_id"],
                        "case_reference": case_ref,
                        "reason_code": "follow_up_without_initial",
                        "comment": "Follow-up document has no matching initial case report",
                        "status": "PENDING",
                    }
                )
            continue

        canonical_initial, *duplicate_initials = initials
        for dup in duplicate_initials:
            document_links.append(
                {
                    "link_id": str(uuid.uuid4()),
                    "document_id": dup["document_id"],
                    "case_reference": case_ref,
                    "link_type": "duplicate_of",
                    "target_document_id": canonical_initial["document_id"],
                }
            )

        version_docs = [canonical_initial, *follow_ups]
        case_version_ids: list[str] = []
        this_case_versions: list[dict] = []
        for version_number, doc in enumerate(version_docs, start=1):
            fields = doc["_fields"]
            version_id = str(uuid.uuid4())
            case_version_ids.append(version_id)
            version_row = {
                "case_version_id": version_id,
                "case_reference": case_ref,
                "version_number": version_number,
                "document_id": doc["document_id"],
                "report_type": fields.get("report_type"),
                "report_date": fields.get("report_date"),
                "received_date": fields.get("received_date"),
                "patient_age": fields.get("patient_age"),
                "patient_sex": fields.get("patient_sex"),
                "facility": fields.get("facility"),
                "district": fields.get("district"),
                "seriousness": fields.get("seriousness"),
                "seriousness_criterion": fields.get("seriousness_criterion"),
                "outcome": fields.get("outcome"),
                "reporter_type": fields.get("reporter_type"),
                "narrative": fields.get("narrative"),
                "extraction_confidence": doc["extraction_confidence"],
                "missing_fields": fields.get("missing_fields") or [],
            }
            case_versions.append(version_row)
            this_case_versions.append(version_row)
            document_links.append(
                {
                    "link_id": str(uuid.uuid4()),
                    "document_id": doc["document_id"],
                    "case_reference": case_ref,
                    "link_type": "source_of_version",
                    "target_document_id": None,
                }
            )
            for product in fields.get("products", []):
                case_products.append(
                    {
                        "case_version_id": version_id,
                        "case_reference": case_ref,
                        "reported_product": product.get("reported_product"),
                        "active_ingredient": product.get("active_ingredient"),
                    }
                )
            for reaction in fields.get("reactions", []):
                case_reactions.append(
                    {
                        "case_version_id": version_id,
                        "case_reference": case_ref,
                        "reaction_term": reaction.get("reaction_term"),
                        "seriousness": reaction.get("seriousness"),
                        "outcome": reaction.get("outcome"),
                    }
                )

        latest_row = this_case_versions[-1]
        latest_version_id = case_version_ids[-1]
        cases.append(
            {
                "case_reference": case_ref,
                "first_report_date": this_case_versions[0]["report_date"],
                "latest_report_date": latest_row["report_date"],
                "latest_case_version_id": latest_version_id,
                "version_count": len(version_docs),
                "duplicate_document_count": len(duplicate_initials),
                "current_seriousness": latest_row["seriousness"],
                "current_outcome": latest_row["outcome"],
            }
        )

    return SilverBuild(
        cases=cases,
        case_versions=case_versions,
        case_products=case_products,
        case_reactions=case_reactions,
        document_links=document_links,
        review_queue=review_queue,
    )


def apply_reference_mapping(
    build: SilverBuild,
    product_dictionary: list[dict],
    reaction_dictionary: list[dict],
    facility_master: list[dict],
    district_master: list[dict],
) -> tuple[SilverBuild, list[dict]]:
    """Case-insensitive exact-name match against the reference dictionaries.
    Unmatched values are recorded as exceptions, not silently dropped or
    silently passed through as unverified free text (REQUIREMENTS.md
    Functional requirement 9). Fuzzy/synonym matching (e.g. "GlargiBase" vs
    "Insulin glargine") is a documented follow-up, not attempted here — see
    RISKS_AND_TRADEOFFS.md."""
    product_names = {
        row["standard_product_name"].strip().lower(): row["product_id"]
        for row in product_dictionary
    }
    product_brands = {
        row["example_brand"].strip().lower(): row["product_id"]
        for row in product_dictionary
        if row.get("example_brand")
    }
    reaction_terms = {
        row["preferred_term"].strip().lower(): row["reaction_id"] for row in reaction_dictionary
    }
    facility_names = {
        row["facility_name"].strip().lower(): row["facility_id"] for row in facility_master
    }
    district_names = {
        row["district_name"].strip().lower(): row["district_id"] for row in district_master
    }

    exceptions: list[dict] = []
    mapped_products = []
    for row in build.case_products:
        key = (row.get("reported_product") or "").strip().lower()
        product_id = product_names.get(key) or product_brands.get(key)
        if product_id is None:
            exceptions.append(
                {
                    "exception_id": str(uuid.uuid4()),
                    "case_reference": row["case_reference"],
                    "exception_type": "unmapped_product",
                    "raw_value": row.get("reported_product"),
                }
            )
        mapped_products.append({**row, "standard_product_id": product_id})

    mapped_reactions = []
    for row in build.case_reactions:
        key = (row.get("reaction_term") or "").strip().lower()
        reaction_id = reaction_terms.get(key)
        if reaction_id is None:
            exceptions.append(
                {
                    "exception_id": str(uuid.uuid4()),
                    "case_reference": row["case_reference"],
                    "exception_type": "unmapped_reaction",
                    "raw_value": row.get("reaction_term"),
                }
            )
        mapped_reactions.append({**row, "standard_reaction_id": reaction_id})

    mapped_versions = []
    for row in build.case_versions:
        facility_key = (row.get("facility") or "").strip().lower()
        district_key = (row.get("district") or "").strip().lower()
        facility_id = facility_names.get(facility_key)
        district_id = district_names.get(district_key)
        if row.get("facility") and facility_id is None:
            exceptions.append(
                {
                    "exception_id": str(uuid.uuid4()),
                    "case_reference": row["case_reference"],
                    "exception_type": "unmapped_facility",
                    "raw_value": row.get("facility"),
                }
            )
        if row.get("district") and district_id is None:
            exceptions.append(
                {
                    "exception_id": str(uuid.uuid4()),
                    "case_reference": row["case_reference"],
                    "exception_type": "unmapped_district",
                    "raw_value": row.get("district"),
                }
            )
        mapped_versions.append({**row, "facility_id": facility_id, "district_id": district_id})

    mapped_build = SilverBuild(
        cases=build.cases,
        case_versions=mapped_versions,
        case_products=mapped_products,
        case_reactions=mapped_reactions,
        document_links=build.document_links,
        review_queue=build.review_queue,
    )
    return mapped_build, exceptions


REQUIRED_VERSION_FIELDS = ("case_reference", "report_type", "report_date")


def classify_dq_quarantine(build: SilverBuild) -> tuple[list[dict], list[dict]]:
    """Reason-coded quarantine for case *versions* that made it through
    extraction but fail mandatory-field checks — separate from
    `review_queue` (document-triage) per REQUIREMENTS.md Functional
    requirement 11. Returns (accepted_versions, quarantined_versions)."""
    accepted: list[dict] = []
    quarantined: list[dict] = []
    products_by_version: dict[str, int] = {}
    reactions_by_version: dict[str, int] = {}
    for p in build.case_products:
        products_by_version[p["case_version_id"]] = (
            products_by_version.get(p["case_version_id"], 0) + 1
        )
    for r in build.case_reactions:
        reactions_by_version[r["case_version_id"]] = (
            reactions_by_version.get(r["case_version_id"], 0) + 1
        )

    for version in build.case_versions:
        reasons = []
        for field_name in REQUIRED_VERSION_FIELDS:
            if not version.get(field_name):
                reasons.append(f"missing_{field_name}")
        if products_by_version.get(version["case_version_id"], 0) == 0:
            reasons.append("no_suspect_product")
        if reactions_by_version.get(version["case_version_id"], 0) == 0:
            reasons.append("no_reaction_term")
        if reasons:
            quarantined.append(
                {
                    "case_version_id": version["case_version_id"],
                    "case_reference": version["case_reference"],
                    "reason_code": ",".join(reasons),
                    "comment": f"Case version failed mandatory-field checks: {reasons}",
                }
            )
        else:
            accepted.append(version)
    return accepted, quarantined


def to_spark_tables(
    spark: SparkSession, build: SilverBuild, exceptions: list[dict], quarantine: list[dict]
) -> dict[str, DataFrame]:
    rows_by_table = {
        "silver_cases": build.cases,
        "silver_case_versions": [
            {**v, "missing_fields": ",".join(v.get("missing_fields") or [])}
            for v in build.case_versions
        ],
        "silver_case_products": build.case_products,
        "silver_case_reactions": build.case_reactions,
        "silver_document_links": build.document_links,
        "silver_review_queue": build.review_queue,
        "reference_mapping_exceptions": exceptions,
        "dq_quarantine": quarantine,
    }
    return {
        name: spark.createDataFrame(rows, schema=SILVER_TABLE_SCHEMAS[name])
        for name, rows in rows_by_table.items()
    }


def write_silver_tables(
    spark: SparkSession, tables: dict[str, DataFrame], catalog: str, schema: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, df in tables.items():
        table_name = f"{catalog}.{schema}.{name}"
        df.write.format("delta").mode("overwrite").saveAsTable(table_name)
        counts[name] = df.count()
    return counts
