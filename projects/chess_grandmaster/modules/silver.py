from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql import types as T


PLAYER_SCHEMA = T.StructType(
    [
        T.StructField("username", T.StringType()),
        T.StructField("rating", T.LongType()),
        T.StructField("result", T.StringType()),
    ]
)

GAME_SCHEMA = T.StructType(
    [
        T.StructField("url", T.StringType()),
        T.StructField("pgn", T.StringType()),
        T.StructField("time_control", T.StringType()),
        T.StructField("end_time", T.LongType()),
        T.StructField("rated", T.BooleanType()),
        T.StructField("rules", T.StringType()),
        T.StructField("time_class", T.StringType()),
        T.StructField("eco", T.StringType()),
        T.StructField("white", PLAYER_SCHEMA),
        T.StructField("black", PLAYER_SCHEMA),
    ]
)

DRAW_RESULTS = [
    "agreed",
    "repetition",
    "stalemate",
    "insufficient",
    "timevsinsufficient",
    "50move",
]


def transform_games(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    parsed = bronze.filter(F.col("record_type") == "games").withColumn(
        "game", F.from_json("payload_json", GAME_SCHEMA)
    )
    games = parsed.select(
        F.col("source_record_id").alias("game_id"),
        F.col("record_hash").alias("source_record_hash"),
        F.lower("username").alias("target_username"),
        F.col("game.url").alias("game_url"),
        F.col("game.pgn").alias("pgn"),
        F.col("game.time_control").alias("time_control"),
        F.col("game.time_class").alias("time_class"),
        F.col("game.rated").alias("is_rated"),
        F.col("game.rules").alias("rules"),
        F.to_timestamp(F.from_unixtime(F.col("game.end_time"))).alias("game_end_at"),
        F.to_date(F.from_unixtime(F.col("game.end_time"))).alias("game_date"),
        F.lower(F.col("game.white.username")).alias("white_username"),
        F.col("game.white.rating").alias("white_rating"),
        F.col("game.white.result").alias("white_result"),
        F.lower(F.col("game.black.username")).alias("black_username"),
        F.col("game.black.rating").alias("black_rating"),
        F.col("game.black.result").alias("black_result"),
        F.regexp_replace(
            F.regexp_replace(F.col("game.eco"), r"^https://www\.chess\.com/openings/", ""),
            "-",
            " ",
        ).alias("opening"),
        "run_id",
        "ingested_at",
    )
    games = (
        games.withColumn(
            "target_color",
            F.when(F.col("target_username") == F.col("white_username"), F.lit("white"))
            .when(F.col("target_username") == F.col("black_username"), F.lit("black"))
            .otherwise(F.lit(None).cast("string")),
        )
        .withColumn(
            "target_rating",
            F.when(F.col("target_color") == "white", F.col("white_rating")).otherwise(
                F.col("black_rating")
            ),
        )
        .withColumn(
            "opponent_username",
            F.when(F.col("target_color") == "white", F.col("black_username")).otherwise(
                F.col("white_username")
            ),
        )
        .withColumn(
            "opponent_rating",
            F.when(F.col("target_color") == "white", F.col("black_rating")).otherwise(
                F.col("white_rating")
            ),
        )
        .withColumn(
            "target_raw_result",
            F.when(F.col("target_color") == "white", F.col("white_result")).otherwise(
                F.col("black_result")
            ),
        )
        .withColumn(
            "target_result",
            F.when(F.col("target_raw_result") == "win", F.lit("win"))
            .when(F.col("target_raw_result").isin(DRAW_RESULTS), F.lit("draw"))
            .otherwise(F.lit("loss")),
        )
    )
    required = (
        F.col("game_id").isNotNull()
        & F.col("game_end_at").isNotNull()
        & F.col("target_color").isNotNull()
        & F.col("target_rating").isNotNull()
        & F.col("opponent_username").isNotNull()
    )
    quarantine = games.filter(~required).withColumn(
        "validation_error", F.lit("missing required game identity, timestamp, or player fields")
    )
    valid = games.filter(required)
    rank = Window.partitionBy("game_id").orderBy(
        F.col("ingested_at").desc(), F.col("source_record_hash").desc()
    )
    silver = (
        valid.withColumn("_rank", F.row_number().over(rank))
        .filter(F.col("_rank") == 1)
        .drop("_rank", "target_raw_result")
        .withColumn("processed_at", F.current_timestamp())
    )
    return silver, quarantine


def write_silver(spark: SparkSession, bronze_table: str, schema_name: str) -> dict:
    silver, quarantine = transform_games(spark.table(bronze_table))
    silver_table = f"{schema_name}.chess_silver_games"
    quarantine_table = f"{schema_name}.chess_quarantine_games"
    silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
        silver_table
    )
    quarantine.write.format("delta").mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(quarantine_table)
    return {
        "bronze_table": bronze_table,
        "silver_table": silver_table,
        "silver_rows": silver.count(),
        "quarantine_table": quarantine_table,
        "quarantine_rows": quarantine.count(),
    }
