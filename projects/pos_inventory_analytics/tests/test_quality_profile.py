from __future__ import annotations

import pytest

from projects.pos_inventory_analytics.modules.quality_profile import _critical_failures, parse_contract

pytestmark = [pytest.mark.unit, pytest.mark.local_fast]


def document() -> dict:
    return {
        "contract_set_version": 2,
        "sample_size": 3,
        "layers": {
            "gold": {
                "business_keys": ["business_id"],
                "safe_sample_columns": ["metric"],
                "critical": {
                    "min_row_count": 1,
                    "max_duplicate_count": 0,
                    "max_business_key_null_rows": 0,
                    "max_rejected_rate": 0.1,
                },
            }
        },
    }


def test_contract_parses_versioned_keys_sample_allowlist_and_thresholds():
    contract = parse_contract(document(), "gold")

    assert contract.version == 2
    assert contract.business_keys == ("business_id",)
    assert contract.safe_sample_columns == ("metric",)
    assert contract.sample_size == 3


def test_critical_checks_return_stable_reason_codes():
    contract = parse_contract(document(), "gold")

    failures = _critical_failures(contract, 0, 2, 1, 0.2)

    assert failures == (
        "ROW_COUNT_BELOW_MINIMUM",
        "DUPLICATE_BUSINESS_KEY",
        "NULL_BUSINESS_KEY",
        "REJECTED_RATE_EXCEEDED",
    )


def test_invalid_sample_size_is_rejected():
    invalid = document()
    invalid["sample_size"] = 21

    with pytest.raises(ValueError, match="sample_size"):
        parse_contract(invalid, "gold")
