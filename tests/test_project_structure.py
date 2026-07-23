import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_multi_platform_directories_exist():
    """Test that multi-platform directory structure exists"""
    required_dirs = [
        "src/core/transformations",
        "projects/pos_retail",
        "platforms/databricks",
        "platforms/fabric",
        "platforms/aws",
        "config/environments",
        "infra/scripts",
        "tests/unit",
        "tests/integration",
        "tests/contracts",
        "tests/parity",
    ]
    
    for dir_path in required_dirs:
        assert (ROOT / dir_path).exists(), f"Missing directory: {dir_path}"


def test_databricks_bundle_declares_targets():
    """Test Databricks bundle has dev and prod targets"""
    bundle_path = ROOT / "platforms" / "databricks" / "bundles" / "databricks.yml"
    bundle = yaml.safe_load(bundle_path.read_text())
    assert set(bundle["targets"].keys()) == {"dev", "prod"}


def test_transformation_sources_exist():
    """Test that core transformation modules exist"""
    for relative_path in [
        "src/core/transformations/bronze/bronze_tables.py",
        "src/core/transformations/silver/silver_tables.py",
        "src/core/transformations/gold/gold_tables_v2.py",
    ]:
        assert (ROOT / relative_path).exists(), f"Missing: {relative_path}"


def test_project_config_exists():
    """Test that project configuration files exist"""
    assert (ROOT / "projects" / "pos_retail" / "config" / "project.yml").exists()
    assert (ROOT / "projects" / "pos_retail" / "contracts" / "schemas.yml").exists()


def test_environment_configs_exist():
    """Test that environment configs exist for dev, test, prod"""
    for env in ["dev", "test", "prod"]:
        env_config = ROOT / "config" / "environments" / f"{env}.yml"
        assert env_config.exists(), f"Missing environment config: {env}"
        
        config = yaml.safe_load(env_config.read_text())
        assert config["environment"] == env
        assert "databricks" in config
        assert "fabric" in config
        assert "aws" in config


def test_databricks_dashboard_resource_valid():
    """Test Databricks dashboard resource is valid"""
    dashboard_path = ROOT / "platforms" / "databricks" / "resources" / "dashboard.yml"
    dashboard_resource = yaml.safe_load(dashboard_path.read_text())
    
    assert "resources" in dashboard_resource
    assert "dashboards" in dashboard_resource["resources"]
    assert "pos_retail_bakehouse_analytics" in dashboard_resource["resources"]["dashboards"]


def test_config_loader_script_exists():
    """Test that config loader utility exists"""
    loader_path = ROOT / "infra" / "scripts" / "load_config.py"
    assert loader_path.exists()


def test_platform_readme_files_exist():
    """Test that platform README files exist"""
    assert (ROOT / "platforms" / "databricks" / "README.md").exists()
