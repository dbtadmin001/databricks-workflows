# Data Sources

## Location
Local CSV snapshots loaded into a raw landing volume: `dbfs:/Volumes/13_nba_analytics_dev/medallion/raw_landing/dataset/`.

## Files
1. `teams.csv`: 8 NBA teams (team_id, team_name, city, conference)
2. `players.csv`: 32 players (player_id, full_name, birthdate, height_cm, weight_kg, draft_year)
3. `roster_season1.csv`: 2023-24 season roster snapshot (player_id, team_id, jersey_number, position)
4. `roster_season2.csv`: 2024-25 season roster snapshot
5. `games.csv`: 77 games (game_id, season, game_date, home_team_id, away_team_id, home_score, away_score)
6. `player_game_stats.csv`: 616 box-score lines (game_id, player_id, minutes, pts, reb, ast, stl, blk, tov, pf, fgm, fga, fg3m, fg3a, ftm, fta)

Note: `player_game_stats` has no `team_id` column.
