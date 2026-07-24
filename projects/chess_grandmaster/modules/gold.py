from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F


def build_gold(games: DataFrame) -> dict[str, DataFrame]:
    outcomes = (
        games.groupBy("target_username").pivot("target_result", ["win", "draw", "loss"]).count()
    )
    summary = (
        games.groupBy("target_username")
        .agg(
            F.count("game_id").alias("games"),
            F.countDistinct("game_date").alias("active_days"),
            F.round(F.avg("target_rating"), 2).alias("average_rating"),
            F.round(F.avg("opponent_rating"), 2).alias("average_opponent_rating"),
            F.min("game_end_at").alias("first_game_at"),
            F.max("game_end_at").alias("last_game_at"),
        )
        .join(outcomes, "target_username")
        .fillna(0, ["win", "draw", "loss"])
        .withColumn("win_rate", F.round(F.col("win") / F.col("games"), 4))
    )
    segment = summary.select(
        "target_username",
        "games",
        "active_days",
        "average_rating",
        F.when(F.col("games") >= 100, F.lit("POWER"))
        .when(F.col("games") >= 30, F.lit("ACTIVE"))
        .otherwise(F.lit("CASUAL"))
        .alias("player_segment"),
    )
    daily = (
        games.groupBy("target_username", "game_date")
        .agg(
            F.count("game_id").alias("games"),
            F.sum(F.when(F.col("target_result") == "win", 1).otherwise(0)).alias("wins"),
            F.sum(F.when(F.col("target_result") == "draw", 1).otherwise(0)).alias("draws"),
            F.sum(F.when(F.col("target_result") == "loss", 1).otherwise(0)).alias("losses"),
            F.round(F.avg("target_rating"), 2).alias("average_rating"),
        )
        .withColumn("win_rate", F.round(F.col("wins") / F.col("games"), 4))
    )
    opening = (
        games.groupBy("target_username", "opening")
        .agg(
            F.count("game_id").alias("games"),
            F.sum(F.when(F.col("target_result") == "win", 1).otherwise(0)).alias("wins"),
            F.round(F.avg("opponent_rating"), 2).alias("average_opponent_rating"),
        )
        .withColumn("win_rate", F.round(F.col("wins") / F.col("games"), 4))
    )
    daily_rating = games.groupBy("target_username", "game_date").agg(
        F.max_by("target_rating", "game_end_at").alias("ending_rating")
    )
    rating_window = Window.partitionBy("target_username").orderBy("game_date")
    rating = daily_rating.withColumn(
        "rating_change", F.col("ending_rating") - F.lag("ending_rating").over(rating_window)
    )
    return {
        "chess_gold_player_summary": summary,
        "chess_gold_player_segment": segment,
        "chess_gold_daily_activity": daily,
        "chess_gold_opening_performance": opening,
        "chess_gold_rating_progression": rating,
    }


def write_gold(spark: SparkSession, silver_table: str, schema_name: str) -> dict:
    products = build_gold(spark.table(silver_table))
    rows = {}
    for table, dataframe in products.items():
        table_name = f"{schema_name}.{table}"
        dataframe.write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(table_name)
        rows[table] = dataframe.count()
    return {"silver_table": silver_table, "gold_rows": rows}
