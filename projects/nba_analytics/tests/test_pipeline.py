import os
import sys

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import types as T

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from projects.nba_analytics.modules.gold import initialize_dim_player, process_roster_snapshot
from projects.nba_analytics.modules.silver import clean_players


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder.appName("test_13_nba_analytics")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
        .getOrCreate()
    )


@pytest.mark.docker_compat
def test_clean_players(spark, tmp_path):
    schema = T.StructType(
        [
            T.StructField("player_id", T.StringType(), True),
            T.StructField("full_name", T.StringType(), True),
            T.StructField("birthdate", T.StringType(), True),
            T.StructField("height_cm", T.StringType(), True),
            T.StructField("weight_kg", T.StringType(), True),
            T.StructField("draft_year", T.StringType(), True),
        ]
    )

    data = [
        ("1", "John Doe", "1990-01-01", "200", "100", "2010"),
        (None, "Invalid", "1990-01-01", "200", "100", "2010"),
    ]
    df = spark.createDataFrame(data, schema)

    bronze_path = str(tmp_path / "bronze_players")
    df.write.format("delta").save(bronze_path)
    spark.sql(f"CREATE TABLE bronze_players_test USING DELTA LOCATION '{bronze_path}'")

    clean_df = clean_players(spark, "bronze_players_test")

    # Assert
    assert clean_df.count() == 1
    assert clean_df.schema["birthdate"].dataType == T.DateType()
    assert clean_df.schema["height_cm"].dataType == T.IntegerType()


@pytest.mark.docker_compat
def test_process_roster_snapshot(spark, tmp_path):
    # Setup players
    players_schema = T.StructType(
        [
            T.StructField("player_id", T.StringType(), True),
            T.StructField("full_name", T.StringType(), True),
            T.StructField("birthdate", T.DateType(), True),
            T.StructField("height_cm", T.IntegerType(), True),
            T.StructField("weight_kg", T.IntegerType(), True),
            T.StructField("draft_year", T.IntegerType(), True),
        ]
    )
    players_df = spark.createDataFrame(
        [("1", "John Doe", None, 200, 100, 2010), ("2", "Jane Doe", None, 190, 90, 2015)],
        players_schema,
    )

    # Setup roster 1
    roster_schema = T.StructType(
        [
            T.StructField("season", T.StringType(), True),
            T.StructField("player_id", T.StringType(), True),
            T.StructField("team_id", T.StringType(), True),
            T.StructField("jersey_number", T.IntegerType(), True),
            T.StructField("position", T.StringType(), True),
        ]
    )
    roster_s1 = spark.createDataFrame([("2023-24", "1", "LAL", 23, "SF")], roster_schema)

    # Init target dim
    dim_path = str(tmp_path / "dim_player")
    spark.sql("DROP TABLE IF EXISTS dim_player_test")
    initialize_dim_player(spark, "dim_player_test", location=dim_path)

    # Process Season 1
    process_roster_snapshot(spark, players_df, roster_s1, "2023-10-01", "dim_player_test")

    dim_df = spark.table("dim_player_test")
    assert dim_df.count() == 1
    assert dim_df.filter("is_current = true").count() == 1

    # Process Season 2 (Player 1 changes team, Player 2 joins)
    roster_s2 = spark.createDataFrame(
        [("2024-25", "1", "BOS", 23, "SF"), ("2024-25", "2", "BOS", 0, "PG")], roster_schema
    )

    process_roster_snapshot(spark, players_df, roster_s2, "2024-10-01", "dim_player_test")

    dim_df2 = spark.table("dim_player_test")
    assert (
        dim_df2.count() == 3
    )  # 1 old row for Player 1, 1 new row for Player 1, 1 new row for Player 2

    p1_rows = dim_df2.filter("player_id = '1'").orderBy("effective_start_date").collect()
    assert len(p1_rows) == 2
    assert not p1_rows[0].is_current
    assert p1_rows[0].effective_end_date.strftime("%Y-%m-%d") == "2024-10-01"
    assert p1_rows[1].is_current
    assert p1_rows[1].team_id == "BOS"

    # Cleanup
    spark.sql("DROP TABLE IF EXISTS bronze_players_test")
    spark.sql("DROP TABLE IF EXISTS dim_player_test")
