# Databricks notebook source
# MAGIC %md
# MAGIC # Purpose
# MAGIC Ingest raw NBA analytics CSV datasets into the Bronze Delta layer with 100% source fidelity.
# MAGIC
# MAGIC # Inputs
# MAGIC `dbfs:/Volumes/{catalog}/medallion/raw_landing/dataset/` (teams, players, roster_season1, roster_season2, games, player_game_stats)
# MAGIC
# MAGIC # Processing
# MAGIC Uses PySpark DataFrame CSV reader to load the raw data, converting all columns to strings to preserve fidelity, and appends `_ingested_at` and `_source_file` metadata columns.
# MAGIC
# MAGIC # Key optimizations
# MAGIC Reuses a modular python implementation function.
# MAGIC
# MAGIC # Expected outputs
# MAGIC Overwritten Bronze Delta tables: `bronze_teams`, `bronze_players`, `bronze_roster_season1`, `bronze_roster_season2`, `bronze_games`, `bronze_player_game_stats`.
# MAGIC

# COMMAND ----------
import os
import shutil
import sys
from pathlib import Path

try:
    notebook_path = (
        dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    )
    sys.path.append(os.path.normpath(f"/Workspace{os.path.dirname(notebook_path)}/.."))
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src")))

from pyspark.sql import SparkSession

from projects.nba_analytics.modules.bronze import ingest_csv_to_bronze

RAW_FILES = (
    "teams.csv",
    "players.csv",
    "roster_season1.csv",
    "roster_season2.csv",
    "games.csv",
    "player_game_stats.csv",
)


def _bundle_files_root() -> Path:
    try:
        notebook_path = (
            dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        )
        return Path(f"/Workspace{os.path.dirname(notebook_path)}").parents[1]
    except Exception:
        return Path.cwd()


def seed_raw_dataset(raw_path: str) -> None:
    source_dir = _bundle_files_root() / "dataset"
    if not source_dir.exists():
        raise FileNotFoundError(f"Bundled source dataset not found: {source_dir}")

    target_dir = Path(raw_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    for file_name in RAW_FILES:
        source = source_dir / file_name
        if not source.exists():
            raise FileNotFoundError(f"Required bundled source file is missing: {source}")
        shutil.copyfile(source, target_dir / file_name)


spark = SparkSession.builder.getOrCreate()
dbutils.widgets.text("catalog", "project_13_nba_analytics_dev")
catalog = dbutils.widgets.get("catalog")
dbutils.widgets.text("landing_volume", "raw_landing", "Terraform-managed raw landing volume")
landing_volume = dbutils.widgets.get("landing_volume")
if not landing_volume:
    raise ValueError("A Terraform-managed raw landing volume is required")

spark.sql(f"USE CATALOG {catalog}")
spark.sql("USE SCHEMA medallion")

# COMMAND ----------
# Ingest all CSVs
raw_path = f"/Volumes/{catalog}/medallion/{landing_volume}/dataset"
seed_raw_dataset(raw_path)

ingest_csv_to_bronze(spark, f"{raw_path}/teams.csv", "bronze_teams")
ingest_csv_to_bronze(spark, f"{raw_path}/players.csv", "bronze_players")
ingest_csv_to_bronze(spark, f"{raw_path}/roster_season1.csv", "bronze_roster_season1")
ingest_csv_to_bronze(spark, f"{raw_path}/roster_season2.csv", "bronze_roster_season2")
ingest_csv_to_bronze(spark, f"{raw_path}/games.csv", "bronze_games")
ingest_csv_to_bronze(spark, f"{raw_path}/player_game_stats.csv", "bronze_player_game_stats")

print("Bronze ingestion complete.")
