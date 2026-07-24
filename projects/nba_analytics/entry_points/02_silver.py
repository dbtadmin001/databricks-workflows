# Databricks notebook source
# MAGIC %md
# MAGIC # Purpose
# MAGIC Process raw Bronze data into Silver datasets: parsing data types, filtering invalid rows (quarantine).
# MAGIC
# MAGIC # Inputs
# MAGIC `bronze_teams`, `bronze_players`, `bronze_roster_season1`, `bronze_roster_season2`, `bronze_games`, `bronze_player_game_stats`.
# MAGIC
# MAGIC # Processing
# MAGIC Uses PySpark DataFrame API to select and explicitly cast columns into standard data types (INT, DATE, STRING). It implements basic validation to drop missing essential identifiers, ensuring that Silver tables only contain clean rows.
# MAGIC
# MAGIC # Key optimizations
# MAGIC Reuses modular python transformations defined in `silver.py`.
# MAGIC
# MAGIC # Expected outputs
# MAGIC Cleaned Silver Delta tables: `silver_teams`, `silver_players`, `silver_roster_season1`, `silver_roster_season2`, `silver_games`, `silver_player_game_stats`.
# MAGIC

# COMMAND ----------
import os
import sys

try:
    notebook_path = (
        dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    )
    sys.path.append(os.path.normpath(f"/Workspace{os.path.dirname(notebook_path)}/.."))
except Exception:
    sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "src")))

from pyspark.sql import SparkSession

from projects.nba_analytics.modules.silver import (
    clean_games,
    clean_player_game_stats,
    clean_players,
    clean_roster,
    clean_teams,
)

spark = SparkSession.builder.getOrCreate()
dbutils.widgets.text("catalog", "project_13_nba_analytics_dev")
catalog = dbutils.widgets.get("catalog")

spark.sql(f"USE CATALOG {catalog}")
spark.sql("USE SCHEMA medallion")

# COMMAND ----------
# Process Teams
clean_teams(spark, "bronze_teams").write.format("delta").mode("overwrite").saveAsTable(
    "silver_teams"
)

# Process Players
clean_players(spark, "bronze_players").write.format("delta").mode("overwrite").saveAsTable(
    "silver_players"
)

# Process Rosters
clean_roster(spark, "bronze_roster_season1").write.format("delta").mode("overwrite").saveAsTable(
    "silver_roster_season1"
)
clean_roster(spark, "bronze_roster_season2").write.format("delta").mode("overwrite").saveAsTable(
    "silver_roster_season2"
)

# Process Games
clean_games(spark, "bronze_games").write.format("delta").mode("overwrite").saveAsTable(
    "silver_games"
)

# Process Stats
clean_player_game_stats(spark, "bronze_player_game_stats").write.format("delta").mode(
    "overwrite"
).saveAsTable("silver_player_game_stats")

print("Silver transformations complete.")
