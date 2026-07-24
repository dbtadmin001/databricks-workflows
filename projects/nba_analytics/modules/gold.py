from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

DIM_PLAYER_COLUMNS = [
    "player_sk",
    "player_id",
    "full_name",
    "birthdate",
    "height_cm",
    "weight_kg",
    "draft_year",
    "team_id",
    "jersey_number",
    "position",
    "tracked_hash",
    "effective_start_date",
    "effective_end_date",
    "is_current",
]


def initialize_dim_player(spark: SparkSession, table_name: str, location: str | None = None):
    """Creates the empty dim_player table if it doesn't exist."""
    location_clause = f" LOCATION '{location}'" if location else ""
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            player_sk STRING,
            player_id STRING,
            full_name STRING,
            birthdate DATE,
            height_cm INT,
            weight_kg INT,
            draft_year INT,
            team_id STRING,
            jersey_number INT,
            position STRING,
            tracked_hash STRING,
            effective_start_date DATE,
            effective_end_date DATE,
            is_current BOOLEAN
        ) USING DELTA{location_clause}
    """)


def process_roster_snapshot(
    spark: SparkSession,
    players_df: DataFrame,
    roster_df: DataFrame,
    season_start_date: str,
    dim_table_name: str,
):
    from delta.tables import DeltaTable

    """
    Applies a full roster snapshot to the SCD2 dim_player table.
    season_start_date is formatted as 'YYYY-MM-DD'.
    """
    # 1. Prepare the incoming snapshot
    incoming_df = roster_df.join(players_df, on="player_id", how="inner")

    # Calculate hash of tracked attributes
    incoming_df = incoming_df.withColumn(
        "tracked_hash",
        F.md5(F.concat_ws("|", F.col("team_id"), F.col("jersey_number"), F.col("position"))),
    )

    # Add SCD2 metadata for incoming records
    incoming_df = incoming_df.withColumn(
        "effective_start_date", F.lit(season_start_date).cast("date")
    )
    incoming_df = incoming_df.withColumn("effective_end_date", F.lit("9999-12-31").cast("date"))
    incoming_df = incoming_df.withColumn("is_current", F.lit(True))
    incoming_df = incoming_df.withColumn(
        "player_sk", F.md5(F.concat_ws("|", F.col("player_id"), F.col("effective_start_date")))
    )

    # 2. Get the current target state to find what changed or was deleted
    target_table = DeltaTable.forName(spark, dim_table_name)

    # In a real CDC, we'd use MERGE directly. With full snapshots, we need to handle deletes
    # (players who disappeared in the new snapshot).
    # Insert a new version only when a tracked attribute actually changed.
    # and "Implement with MERGE INTO and hash-based change detection"

    # We will build a staging DataFrame that contains:
    # a) New records and Changed records (action = 'upsert')
    # b) Existing records to expire because they changed or were deleted.

    # Current active records in dimension
    current_dim = spark.table(dim_table_name).filter(F.col("is_current"))

    # Join incoming with current
    joined = incoming_df.alias("inc").join(
        current_dim.alias("cur"), on="player_id", how="full_outer"
    )

    # Identify what needs to be inserted: incoming exists, and either no current or hash differs
    inserts = (
        joined.filter(
            F.col("inc.player_id").isNotNull()
            & (
                F.col("cur.player_id").isNull()
                | (F.col("cur.tracked_hash") != F.col("inc.tracked_hash"))
            )
        )
        .select("inc.*")
        .select(*DIM_PLAYER_COLUMNS)
        .withColumn("mergeKey", F.lit(None).cast("string"))
    )

    # Identify what needs to be expired: current exists, and either no incoming or hash differs
    expires = (
        joined.filter(
            F.col("cur.player_id").isNotNull()
            & (
                F.col("inc.player_id").isNull()
                | (F.col("cur.tracked_hash") != F.col("inc.tracked_hash"))
            )
        )
        .select("cur.*")
        .select(*DIM_PLAYER_COLUMNS)
        .withColumn("mergeKey", F.col("player_id"))
    )

    staged_updates = inserts.unionByName(expires)

    # 3. Perform the MERGE
    target_table.alias("target").merge(
        staged_updates.alias("staged"),
        "target.player_id = staged.mergeKey AND target.is_current = true",
    ).whenMatchedUpdate(
        set={
            "is_current": F.lit(False),
            "effective_end_date": F.lit(season_start_date).cast("date"),
        }
    ).whenNotMatchedInsert(
        values={
            "player_sk": "staged.player_sk",
            "player_id": "staged.player_id",
            "full_name": "staged.full_name",
            "birthdate": "staged.birthdate",
            "height_cm": "staged.height_cm",
            "weight_kg": "staged.weight_kg",
            "draft_year": "staged.draft_year",
            "team_id": "staged.team_id",
            "jersey_number": "staged.jersey_number",
            "position": "staged.position",
            "tracked_hash": "staged.tracked_hash",
            "effective_start_date": "staged.effective_start_date",
            "effective_end_date": "staged.effective_end_date",
            "is_current": "staged.is_current",
        }
    ).execute()


def build_fct_player_game_stats(
    spark: SparkSession, silver_games_table: str, silver_stats_table: str, dim_player_table: str
) -> DataFrame:
    games = spark.table(silver_games_table)
    stats = spark.table(silver_stats_table)
    dim = spark.table(dim_player_table)

    # Join games to stats
    gs = stats.join(games, on="game_id", how="inner")

    # Join to dim_player using game_date between effective_start_date and effective_end_date
    cond = [
        gs.player_id == dim.player_id,
        gs.game_date >= dim.effective_start_date,
        gs.game_date < dim.effective_end_date,
    ]
    fact = gs.join(dim, on=cond, how="inner")

    # Select columns
    return fact.select(
        dim.player_sk,
        gs.game_id,
        dim.team_id,
        gs.game_date,
        gs.season,
        gs.minutes,
        gs.pts,
        gs.reb,
        gs.ast,
        gs.stl,
        gs.blk,
        gs.tov,
        gs.pf,
        gs.fgm,
        gs.fga,
        gs.fg3m,
        gs.fg3a,
        gs.ftm,
        gs.fta,
    )


def kpi_team_win_pct(
    spark: SparkSession, silver_games_table: str, silver_teams_table: str
) -> DataFrame:
    games = spark.table(silver_games_table)
    teams = spark.table(silver_teams_table)

    # Determine the winner of each game
    games = games.withColumn(
        "winner_team_id",
        F.when(F.col("home_score") > F.col("away_score"), F.col("home_team_id")).otherwise(
            F.col("away_team_id")
        ),
    )

    # Calculate wins and games played per team per season
    # Explode games into team perspectives
    home_games = games.select(
        F.col("season"), F.col("home_team_id").alias("team_id"), F.col("winner_team_id")
    )
    away_games = games.select(
        F.col("season"), F.col("away_team_id").alias("team_id"), F.col("winner_team_id")
    )
    all_team_games = home_games.unionByName(away_games)

    all_team_games = all_team_games.withColumn(
        "is_win", F.when(F.col("team_id") == F.col("winner_team_id"), 1).otherwise(0)
    )

    kpi = (
        all_team_games.groupBy("season", "team_id")
        .agg(F.count("*").alias("games_played"), F.sum("is_win").alias("wins"))
        .withColumn("win_pct", F.col("wins") / F.col("games_played"))
    )

    return kpi.join(teams, on="team_id", how="inner").select(
        "season", "team_id", "team_name", "games_played", "wins", "win_pct"
    )


def kpi_player_points_season(spark: SparkSession, fct_table: str) -> DataFrame:
    fct = spark.table(fct_table)
    return fct.groupBy("season", "player_sk", "team_id").agg(F.sum("pts").alias("total_points"))
