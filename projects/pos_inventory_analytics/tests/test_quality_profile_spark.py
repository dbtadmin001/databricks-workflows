from __future__ import annotations

import pytest

from projects.pos_inventory_analytics.modules.quality_profile import build_profile

pytestmark = [pytest.mark.component, pytest.mark.docker_compat]


def test_bronze_profile_reports_metrics_and_masks_the_safe_sample(spark):
    # business_keys for bronze/silver is ["trans_id", "item_id"] (composite),
    # matching the real grain in quality_contracts.json / DATA_CONTRACTS.md.
    candidate = spark.createDataFrame(
        [
            ("TXN-1", 1001, "alpha"),
            ("TXN-1", 1001, None),
            (None, 1002, "beta"),
        ],
        "trans_id string, item_id int, category string",
    )

    profile = build_profile(candidate, "bronze", "run-123", rejected_records=1)

    assert profile.run_id == "run-123"
    assert profile.row_count == 3
    assert profile.distinct_business_keys == 1
    assert profile.duplicate_count == 1
    assert profile.business_key_null_rows == 1
    assert profile.null_rates == {"trans_id": 1 / 3, "item_id": 0.0, "category": 1 / 3}
    assert profile.rejected_records == 1
    assert profile.rejected_rate == 0.25
    assert profile.critical_failures == ()
    silver_profile = build_profile(candidate, "silver", "run-123", rejected_records=1)
    assert set(silver_profile.critical_failures) == {
        "DUPLICATE_BUSINESS_KEY",
        "NULL_BUSINESS_KEY",
    }
    assert len(profile.safe_sample) == 3
    assert all(set(row) == {"row_fingerprint"} for row in profile.safe_sample)
    assert all(len(row["row_fingerprint"]) == 64 for row in profile.safe_sample)
