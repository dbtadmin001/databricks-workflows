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
    """Validate Python sources in src/core/transformations/"""
    transformation_dir = ROOT / "src" / "core" / "transformations"
    if not transformation_dir.exists():
        raise AssertionError(f"Transformations directory not found: {transformation_dir}")
    
    python_files = list(transformation_dir.rglob("*.py"))
    _assert(len(python_files) > 0, "No Python transformation files found")
    
    for path in python_files:
        py_compile.compile(str(path), doraise=True)
    
    print(f"✓ Validated {len(python_files)} Python transformation files")


def validate_multi_platform_structure() -> None:
    """Validate multi-platform directory structure"""
    required_dirs = [
        "src/core/transformations",
        "projects/pos_retail",
        "platforms/databricks",
        "config/environments",
        "tests/unit",
        "tests/integration",
        "tests/contracts",
        "tests/parity",
    ]
    
    for dir_path in required_dirs:
        full_path = ROOT / dir_path
        _assert(full_path.exists(), f"Required directory missing: {dir_path}")
    
    print("✓ Multi-platform structure validated")


def validate_databricks_bundle() -> None:
    """Validate Databricks bundle configuration"""
    bundle_path = ROOT / "platforms" / "databricks" / "bundles" / "databricks.yml"
    pipeline_path = ROOT / "platforms" / "databricks" / "resources" / "pipeline.yml"
    dashboard_path = ROOT / "platforms" / "databricks" / "resources" / "dashboard.yml"
    
    _assert(bundle_path.exists(), "Databricks bundle config not found")
    _assert(pipeline_path.exists(), "Pipeline resource config not found")
    _assert(dashboard_path.exists(), "Dashboard resource config not found")
    
    bundle = _load_yaml(bundle_path)
    pipeline = _load_yaml(pipeline_path)
    dashboard = _load_yaml(dashboard_path)
    
    _assert(bundle["bundle"]["name"] == "pos_retail_analytics", "Unexpected bundle name")
    
    pipeline_def = pipeline["resources"]["pipelines"]["pos_retail_medallion"]
    _assert(pipeline_def["channel"] == "CURRENT", "Pipeline must pin CURRENT channel")
    _assert(pipeline_def["serverless"] is True, "Pipeline must be serverless")
    _assert(pipeline_def["photon"] is True, "Pipeline must enable Photon")
    
    dashboard_def = dashboard["resources"]["dashboards"]["pos_retail_bakehouse_analytics"]
    _assert(dashboard_def["embed_credentials"] is True, "Dashboard must embed credentials")
    
    print("✓ Databricks bundle validated")


def validate_project_config() -> None:
    """Validate project configuration files"""
    project_config = ROOT / "projects" / "pos_retail" / "config" / "project.yml"
    contracts = ROOT / "projects" / "pos_retail" / "contracts" / "schemas.yml"
    
    _assert(project_config.exists(), "Project config not found")
    _assert(contracts.exists(), "Contracts/schemas not found")
    
    config = _load_yaml(project_config)
    schemas = _load_yaml(contracts)
    
    _assert(config["project"]["name"] == "pos_retail", "Unexpected project name")
    _assert("bronze_transactions" in schemas, "Bronze table contract missing")
    
    print("✓ Project configuration validated")


def validate_environment_configs() -> None:
    """Validate environment configuration files"""
    for env in ["dev", "test", "prod"]:
        env_config = ROOT / "config" / "environments" / f"{env}.yml"
        _assert(env_config.exists(), f"Environment config missing: {env}")
        
        config = _load_yaml(env_config)
        _assert(config["environment"] == env, f"Environment mismatch in {env}.yml")
        _assert("databricks" in config, f"Databricks config missing in {env}.yml")
    
    print("✓ Environment configs validated")


def validate_sql_notebook() -> None:
    """Validate SQL notebook exists in entry points"""
    notebook_path = ROOT / "projects" / "pos_retail" / "entry_points" / "pos_retail_analytics.sql"
    
    if not notebook_path.exists():
        print("⚠ SQL notebook not found in entry_points (optional)")
        return
    
    notebook_text = notebook_path.read_text()
    _assert(len(notebook_text) > 0, "SQL notebook is empty")
    
    print("✓ SQL notebook validated")


def main() -> int:
    try:
        validate_multi_platform_structure()
        validate_python_sources()
        validate_databricks_bundle()
        validate_project_config()
        validate_environment_configs()
        validate_sql_notebook()
        
        print("\n" + "="*50)
        print("✅ All project validation checks passed!")
        print("="*50)
        return 0
    
    except AssertionError as e:
        print(f"\n❌ Validation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
