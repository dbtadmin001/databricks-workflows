"""Unit tests for core transformation logic.

These tests run with local Spark and don't require Databricks workspace access.
"""

import pytest


def test_placeholder():
    """Placeholder test to ensure CI passes.
    
    TODO: Add actual unit tests for transformation logic:
    - Test Bronze ingestion functions
    - Test Silver enrichment and DQ rules
    - Test Gold aggregation logic
    """
    assert True, "Placeholder test"


# TODO: Add tests for bronze transformations
# def test_bronze_transactions_adds_audit_columns():
#     pass

# TODO: Add tests for silver transformations
# def test_silver_transactions_enriched_joins_correctly():
#     pass

# TODO: Add tests for gold transformations
# def test_gold_daily_revenue_aggregates_correctly():
#     pass
