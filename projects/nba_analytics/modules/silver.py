from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def clean_teams(spark: SparkSession, bronze_table: str) -> DataFrame:
    df = spark.read.table(bronze_table)
    return df.select(
        F.col("team_id").cast("string"),
        F.col("team_name").cast("string"),
        F.col("city").cast("string"),
        F.col("conference").cast("string"),
    ).filter(F.col("team_id").isNotNull())


def clean_players(spark: SparkSession, bronze_table: str) -> DataFrame:
    df = spark.read.table(bronze_table)
    return df.select(
        F.col("player_id").cast("string"),
        F.col("full_name").cast("string"),
        F.col("birthdate").cast("date"),
        F.col("height_cm").cast("int"),
        F.col("weight_kg").cast("int"),
        F.col("draft_year").cast("int"),
    ).filter(F.col("player_id").isNotNull())


def clean_roster(spark: SparkSession, bronze_table: str) -> DataFrame:
    df = spark.read.table(bronze_table)
    return df.select(
        F.col("season").cast("string"),
        F.col("player_id").cast("string"),
        F.col("team_id").cast("string"),
        F.col("jersey_number").cast("int"),
        F.col("position").cast("string"),
    ).filter(F.col("player_id").isNotNull() & F.col("season").isNotNull())


def clean_games(spark: SparkSession, bronze_table: str) -> DataFrame:
    df = spark.read.table(bronze_table)
    return df.select(
        F.col("game_id").cast("string"),
        F.col("season").cast("string"),
        F.col("game_date").cast("date"),
        F.col("home_team_id").cast("string"),
        F.col("away_team_id").cast("string"),
        F.col("home_score").cast("int"),
        F.col("away_score").cast("int"),
    ).filter(F.col("game_id").isNotNull())


def clean_player_game_stats(spark: SparkSession, bronze_table: str) -> DataFrame:
    df = spark.read.table(bronze_table)
    return df.select(
        F.col("game_id").cast("string"),
        F.col("player_id").cast("string"),
        F.col("minutes").cast("int"),
        F.col("pts").cast("int"),
        F.col("reb").cast("int"),
        F.col("ast").cast("int"),
        F.col("stl").cast("int"),
        F.col("blk").cast("int"),
        F.col("tov").cast("int"),
        F.col("pf").cast("int"),
        F.col("fgm").cast("int"),
        F.col("fga").cast("int"),
        F.col("fg3m").cast("int"),
        F.col("fg3a").cast("int"),
        F.col("ftm").cast("int"),
        F.col("fta").cast("int"),
    ).filter(F.col("game_id").isNotNull() & F.col("player_id").isNotNull())
