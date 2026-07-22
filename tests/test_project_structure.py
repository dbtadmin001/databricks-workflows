import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_declares_targets():
    bundle = yaml.safe_load((ROOT / "databricks.yml").read_text())
    assert set(bundle["targets"].keys()) == {"dev", "prod"}


def test_pipeline_sources_exist():
    for relative_path in [
        "transformations/bronze/bronze_tables.py",
        "transformations/silver/silver_tables.py",
        "transformations/gold/gold_tables_v2.py",
    ]:
        assert (ROOT / relative_path).exists()


def test_dashboard_export_contains_pages_and_widgets():
    dashboard_resource = yaml.safe_load((ROOT / "resources" / "dashboard.yml").read_text())
    dashboard = json.loads(dashboard_resource["resources"]["dashboards"]["pos_retail_bakehouse_analytics"]["serialized_dashboard"])
    assert len(dashboard["pages"]) == 2
    assert sum(len(page.get("layout", [])) for page in dashboard["pages"]) >= 14
