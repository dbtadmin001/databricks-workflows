from __future__ import annotations

import json
import pathlib
import py_compile
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_yaml(path: pathlib.Path):
    return yaml.safe_load(path.read_text())


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_python_sources() -> None:
    for path in (ROOT / "transformations").rglob("*.py"):
        py_compile.compile(str(path), doraise=True)


def validate_bundle_files() -> None:
    bundle = _load_yaml(ROOT / "databricks.yml")
    pipeline = _load_yaml(ROOT / "resources" / "pipeline.yml")
    dashboard = _load_yaml(ROOT / "resources" / "dashboard.yml")

    _assert(bundle["bundle"]["name"] == "pos_retail_analytics", "Unexpected bundle name")
    _assert("resources/*.yml" in bundle["include"], "Bundle must include resource YAML files")
    _assert("transformations/**" in bundle["sync"]["include"], "Transformations must sync with the bundle")

    pipeline_def = pipeline["resources"]["pipelines"]["pos_retail_medallion"]
    _assert(pipeline_def["channel"] == "CURRENT", "Pipeline must pin the CURRENT channel")
    _assert(pipeline_def["serverless"] is True, "Pipeline must stay serverless")
    _assert(pipeline_def["photon"] is True, "Pipeline must keep Photon enabled")

    dashboard_def = dashboard["resources"]["dashboards"]["pos_retail_bakehouse_analytics"]
    _assert(dashboard_def["embed_credentials"] is True, "Dashboard must embed credentials for published viewers")


def validate_dashboard_export() -> None:
    dashboard_resource = _load_yaml(ROOT / "resources" / "dashboard.yml")
    dashboard_payload = dashboard_resource["resources"]["dashboards"]["pos_retail_bakehouse_analytics"]["serialized_dashboard"]
    dashboard = json.loads(dashboard_payload)
    _assert(len(dashboard["datasets"]) >= 10, "Dashboard export must include the persisted datasets")
    _assert(len(dashboard["pages"]) == 2, "Dashboard export must keep the two-page layout")
    widget_count = sum(len(page.get("layout", [])) for page in dashboard["pages"])
    _assert(widget_count >= 14, "Dashboard export must keep all verified widgets")


def validate_sql_notebook_export() -> None:
    notebook_text = (ROOT / "notebooks" / "pos_retail_analytics.sql").read_text()
    _assert(notebook_text.count("-- COMMAND ----------") >= 9, "Notebook export is missing commands")
    required_refs = [
        "workspace.default.silver_transactions_enriched",
        "workspace.default.gold_daily_revenue",
        "workspace.default.gold_product_performance",
        "workspace.default.gold_franchise_ranking",
        "workspace.default.gold_customer_segments",
    ]
    for ref in required_refs:
        _assert(ref in notebook_text, f"Notebook export is missing required table reference: {ref}")


def main() -> int:
    validate_python_sources()
    validate_bundle_files()
    validate_dashboard_export()
    validate_sql_notebook_export()
    print("Project validation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
