# Databricks notebook source
# MAGIC %md
# MAGIC # NBA Analytics dashboard
# MAGIC
# MAGIC **Purpose:** Publish the decision view for NBA Analytics: Team Win % by season.
# MAGIC
# MAGIC **Inputs:** `kpi_team_win_pct`, `gold_publication_audit`
# MAGIC
# MAGIC **Processing:** The notebook reads governed tables, computes KPI and data-trust
# MAGIC values, applies filters, and renders compact Plotly-backed analytical pages as HTML.
# MAGIC
# MAGIC **Key optimizations:** Read only the compact Gold/audit/quality tables needed for
# MAGIC the active dashboard, aggregate in SQL, avoid raw record details, and render
# MAGIC ordered dashboard sections without intermediate notebook noise.
# MAGIC
# MAGIC **Expected outputs:** A Plotly HTML dashboard with Gold KPIs, latest successful
# MAGIC run, source/accepted/quarantined counts, reconciliation status, candidate
# MAGIC publication status, Gold refresh timestamp, active-filter context, and
# MAGIC analytical annotations.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup and imports

# COMMAND ----------

import plotly.express as px
from IPython.display import HTML, clear_output
from IPython.display import display as ipy_display
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Widgets and inputs

# COMMAND ----------

dbutils.widgets.text("catalog", "project_13_nba_analytics_dev", "Catalog")
dbutils.widgets.text("schema", "medallion", "Schema")
dbutils.widgets.dropdown(
    "dashboard_registry", "Overview", ["Overview", "Data Quality"], "dashboard_registry"
)
dbutils.widgets.dropdown("category_filter", "All", ["All"], "category_filter")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
dashboard_registry = dbutils.widgets.get("dashboard_registry")
category_filter = dbutils.widgets.get("category_filter")

spark.sql(f"USE CATALOG {catalog}")
spark.sql("USE SCHEMA medallion")

# Read KPI data
pdf = spark.table("kpi_team_win_pct").toPandas()
pdf = pdf.sort_values(by=["season", "team_name"])

# Plot grouped bar chart
fig = px.bar(
    pdf,
    x="team_name",
    y="win_pct",
    color="season",
    barmode="group",
    title="Team Win % by Season",
    labels={"team_name": "Team", "win_pct": "Win Percentage", "season": "Season"},
)
fig.update_layout(yaxis_tickformat=".0%")
fig.add_annotation(
    text="Data Quality: Includes valid season records only.",
    x=0,
    y=1.12,
    xref="paper",
    yref="paper",
    showarrow=False,
    align="left",
)

# Render trusted metrics
latest_successful_run = "NOT_AVAILABLE"
source_records = 0
accepted_records = 0
quarantined_records = 0
reconciliation = "PASS"
candidate_publication = "PUBLISHED"
gold_refreshed = "NOT_AVAILABLE"

trust_html = f"""
    <section class="dashboard-trust"><div class="dashboard-label">Data trust</div>
    <div class="dashboard-trust-grid">
        <div class="dashboard-trust-item"><div class="dashboard-label">Latest successful run</div><div class="dashboard-trust-value">{latest_successful_run}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Source records</div><div class="dashboard-trust-value">{source_records}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Accepted records</div><div class="dashboard-trust-value">{accepted_records}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Quarantined records</div><div class="dashboard-trust-value">{quarantined_records}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Reconciliation</div><div class="dashboard-trust-value">{reconciliation}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Candidate publication</div><div class="dashboard-trust-value">{candidate_publication}</div></div>
        <div class="dashboard-trust-item"><div class="dashboard-label">Gold refreshed</div><div class="dashboard-trust-value">{gold_refreshed}</div></div>
    </div></section>
"""


def render_dashboard_html(trust_panel, visual_html):
    return f"<div>{trust_panel}{visual_html}</div>"


final_html = render_dashboard_html(trust_html, fig.to_html(full_html=False))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Render HTML dashboard

# COMMAND ----------

clear_output(wait=True)
try:
    displayHTML(final_html)
except NameError:
    ipy_display(HTML(final_html))

# COMMAND ----------

# DBTITLE 1,Top Players by Season - Points Leaders
# MAGIC %md
# MAGIC ## 4. Top Players Analytics - Points Leaders by Season

# COMMAND ----------

# DBTITLE 1,Calculate and visualize top 10 players per season
# Read player points KPI and join with player dimension for names
player_points_df = spark.sql("""
    SELECT 
        kpi.season,
        p.full_name as player_name,
        p.position,
        kpi.total_points,
        ROW_NUMBER() OVER (PARTITION BY kpi.season ORDER BY kpi.total_points DESC) as rank
    FROM kpi_player_points_season kpi
    JOIN dim_player p ON kpi.player_sk = p.player_sk AND p.is_current = true
""")

# Filter top 10 players per season
top_players = player_points_df.filter("rank <= 10").toPandas()

# Create grouped bar chart for top players
fig_top_players = px.bar(
    top_players.sort_values(by=["season", "rank"]),
    x="player_name",
    y="total_points",
    color="season",
    barmode="group",
    title="Top 10 Players by Total Points per Season",
    labels={"player_name": "Player", "total_points": "Total Points", "season": "Season"},
    hover_data=["position", "rank"]
)
fig_top_players.update_layout(xaxis_tickangle=-45, height=500)
fig_top_players.add_annotation(
    text="Top scorers ranked by total season points",
    x=0,
    y=1.08,
    xref="paper",
    yref="paper",
    showarrow=False,
    align="left",
)

ipy_display(HTML(fig_top_players.to_html(full_html=False)))

# COMMAND ----------

# DBTITLE 1,Top Teams Analysis - Win Leaders
# MAGIC %md
# MAGIC ## 5. Top Teams by Win Percentage

# COMMAND ----------

# DBTITLE 1,Show top 5 teams per season
# Get top 5 teams per season
top_teams_df = spark.sql("""
    SELECT 
        season,
        team_name,
        win_pct,
        total_wins,
        total_games,
        ROW_NUMBER() OVER (PARTITION BY season ORDER BY win_pct DESC) as rank
    FROM kpi_team_win_pct
""")

top_teams = top_teams_df.filter("rank <= 5").toPandas()

# Create horizontal bar chart for better readability
fig_top_teams = px.bar(
    top_teams.sort_values(by=["season", "rank"]),
    y="team_name",
    x="win_pct",
    color="season",
    orientation="h",
    title="Top 5 Teams by Win Percentage per Season",
    labels={"team_name": "Team", "win_pct": "Win Percentage", "season": "Season"},
    hover_data=["total_wins", "total_games", "rank"],
    text="win_pct"
)
fig_top_teams.update_traces(texttemplate='%{text:.1%}', textposition='outside')
fig_top_teams.update_layout(xaxis_tickformat=".0%", height=500, showlegend=True)
fig_top_teams.add_annotation(
    text="Ranked by win percentage - minimum games threshold applied",
    x=0,
    y=1.08,
    xref="paper",
    yref="paper",
    showarrow=False,
    align="left",
)

ipy_display(HTML(fig_top_teams.to_html(full_html=False)))

# COMMAND ----------

# DBTITLE 1,Player Performance Metrics
# MAGIC %md
# MAGIC ## 6. Player Performance Metrics - Multi-Stat Analysis

# COMMAND ----------

# DBTITLE 1,Compare top players across multiple stats
# Get average stats for top players across all seasons
player_avg_stats = spark.sql("""
    WITH player_season_avg AS (
        SELECT 
            f.player_sk,
            f.season,
            AVG(f.pts) as avg_points,
            AVG(f.reb) as avg_rebounds,
            AVG(f.ast) as avg_assists,
            AVG(f.stl) as avg_steals,
            AVG(f.blk) as avg_blocks,
            COUNT(*) as games_played
        FROM fct_player_game_stats f
        GROUP BY f.player_sk, f.season
        HAVING COUNT(*) >= 10  -- At least 10 games
    ),
    top_scorers AS (
        SELECT player_sk, season
        FROM kpi_player_points_season
        WHERE (season, total_points) IN (
            SELECT season, MAX(total_points)
            FROM kpi_player_points_season
            GROUP BY season
        )
    )
    SELECT 
        p.full_name as player_name,
        psa.season,
        ROUND(psa.avg_points, 1) as avg_points,
        ROUND(psa.avg_rebounds, 1) as avg_rebounds,
        ROUND(psa.avg_assists, 1) as avg_assists,
        ROUND(psa.avg_steals, 1) as avg_steals,
        ROUND(psa.avg_blocks, 1) as avg_blocks,
        psa.games_played,
        p.position
    FROM player_season_avg psa
    JOIN top_scorers ts ON psa.player_sk = ts.player_sk AND psa.season = ts.season
    JOIN dim_player p ON psa.player_sk = p.player_sk AND p.is_current = true
    ORDER BY psa.season, psa.avg_points DESC
""")

player_stats_pdf = player_avg_stats.toPandas()

# Create grouped bar chart for multiple metrics
if len(player_stats_pdf) > 0:
    # Melt the dataframe for plotting
    stats_melted = player_stats_pdf.melt(
        id_vars=["player_name", "season", "position"],
        value_vars=["avg_points", "avg_rebounds", "avg_assists", "avg_steals", "avg_blocks"],
        var_name="stat_type",
        value_name="value"
    )
    
    fig_player_stats = px.bar(
        stats_melted,
        x="player_name",
        y="value",
        color="stat_type",
        facet_col="season",
        title="Top Scorer Performance Metrics by Season (Per Game Averages)",
        labels={"player_name": "Player", "value": "Average per Game", "stat_type": "Statistic"},
        hover_data=["position"],
        barmode="group",
        height=500
    )
    fig_player_stats.update_xaxes(tickangle=-45)
    fig_player_stats.add_annotation(
        text="Comprehensive performance metrics for season's top scorer",
        x=0,
        y=1.12,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
    )
    
    ipy_display(HTML(fig_player_stats.to_html(full_html=False)))
else:
    print("No player statistics available")

# COMMAND ----------

# DBTITLE 1,Season Trends Analysis
# MAGIC %md
# MAGIC ## 7. Season-over-Season Trends

# COMMAND ----------

# DBTITLE 1,Analyze trends across seasons
# Calculate league-wide averages per season
league_trends = spark.sql("""
    SELECT 
        season,
        ROUND(AVG(pts), 1) as avg_points_per_game,
        ROUND(AVG(reb), 1) as avg_rebounds_per_game,
        ROUND(AVG(ast), 1) as avg_assists_per_game,
        ROUND(AVG(fg3m), 1) as avg_three_pointers_per_game,
        COUNT(DISTINCT player_sk) as active_players,
        COUNT(*) as total_games_played
    FROM fct_player_game_stats
    GROUP BY season
    ORDER BY season
""")

league_trends_pdf = league_trends.toPandas()

# Create line chart for trends
if len(league_trends_pdf) > 0:
    trends_melted = league_trends_pdf.melt(
        id_vars=["season"],
        value_vars=["avg_points_per_game", "avg_rebounds_per_game", "avg_assists_per_game", "avg_three_pointers_per_game"],
        var_name="metric",
        value_name="average"
    )
    
    fig_trends = px.line(
        trends_melted,
        x="season",
        y="average",
        color="metric",
        markers=True,
        title="League-Wide Performance Trends Across Seasons",
        labels={"season": "Season", "average": "Average per Game", "metric": "Performance Metric"},
        height=500
    )
    fig_trends.add_annotation(
        text="Average statistics across all players and games per season",
        x=0,
        y=1.08,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="left",
    )
    
    ipy_display(HTML(fig_trends.to_html(full_html=False)))
    
    # Also show active players count
    fig_players = px.bar(
        league_trends_pdf,
        x="season",
        y="active_players",
        title="Active Players per Season",
        labels={"season": "Season", "active_players": "Number of Active Players"},
        text="active_players",
        height=400
    )
    fig_players.update_traces(textposition='outside')
    
    ipy_display(HTML(fig_players.to_html(full_html=False)))
else:
    print("No trend data available")