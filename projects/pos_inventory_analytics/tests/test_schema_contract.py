from __future__ import annotations

import pytest

from projects.pos_inventory_analytics.modules.schema_contract import (
    FieldContract,
    LayerContract,
    ObservedField,
    compare_schema,
)

pytestmark = [pytest.mark.unit, pytest.mark.local_fast]


def contract(
    *,
    additive: dict[str, FieldContract] | None = None,
    renames: dict[str, str] | None = None,
) -> LayerContract:
    return LayerContract(
        "gold",
        2,
        {
            "category": FieldContract("string", False),
            "record_count": FieldContract("bigint", False),
        },
        additive or {},
        renames or {},
    )


def codes(report) -> set[str]:
    return {difference.code for difference in report.differences}


def test_exact_schema_and_explicit_additive_column_are_compatible():
    report = compare_schema(
        contract(additive={"metric_p95": FieldContract("double", True)}),
        [
            ObservedField("category", "string", False),
            ObservedField("record_count", "bigint", False),
            ObservedField("metric_p95", "double", True),
        ],
    )
    assert report.compatible
    assert codes(report) == {"ALLOWED_ADDITIVE_COLUMN"}
    assert "Result: COMPATIBLE" in report.render()
    assert "metric_p95" in report.render()


@pytest.mark.parametrize(
    ("candidate", "expected_code"),
    [
        ([ObservedField("category", "string", False)], "MISSING_REQUIRED_FIELD"),
        (
            [
                ObservedField("category", "string", False),
                ObservedField("record_count", "double", False),
            ],
            "INCOMPATIBLE_DATA_TYPE",
        ),
        (
            [
                ObservedField("category", "string", True),
                ObservedField("record_count", "bigint", False),
            ],
            "INVALID_NULLABILITY_CHANGE",
        ),
        (
            [
                ObservedField("category", "string", False),
                ObservedField("record_count", "bigint", False),
                ObservedField("surprise", "string", True),
            ],
            "UNDECLARED_ADDITIVE_COLUMN",
        ),
    ],
)
def test_incompatible_contract_changes_are_rejected(candidate, expected_code):
    report = compare_schema(contract(), candidate)
    assert not report.compatible
    assert expected_code in codes(report)
    assert "Result: REJECTED" in report.render()


def test_rename_requires_declaration_and_preserves_shape():
    previous = [
        ObservedField("category_old", "string", False),
        ObservedField("record_count", "bigint", False),
    ]
    candidate = [
        ObservedField("category", "string", False),
        ObservedField("record_count", "bigint", False),
    ]
    rejected = compare_schema(contract(), candidate, previous)
    assert not rejected.compatible
    assert "UNDECLARED_RENAME" in codes(rejected)

    accepted = compare_schema(
        contract(renames={"category_old": "category"}),
        candidate,
        previous,
    )
    assert accepted.compatible
    assert "DECLARED_RENAME" in codes(accepted)
