# Data Contracts

## Bronze
All raw columns must be ingested with `STRING` type. Strict source fidelity.
- `bronze_teams`, `bronze_players`, `bronze_roster_season1`, `bronze_roster_season2`, `bronze_games`, `bronze_player_game_stats`.

## Silver
- Parse dates to `DATE`, integers to `INT`, floats to `DOUBLE`.
- Required columns: `team_id`, `player_id`, `game_id`.
- Tracked attributes for SCD2: `team_id`, `jersey_number`, `position`.
- Static attributes: `full_name`, `birthdate`, `height_cm`, `weight_kg`, `draft_year`.

## Gold
1. `dim_player`:
   - `player_sk` (STRING/MD5), `player_id` (STRING), `full_name` (STRING), `birthdate` (DATE), `height_cm` (INT), `weight_kg` (INT), `draft_year` (INT)
   - `team_id` (STRING), `jersey_number` (INT), `position` (STRING)
   - `effective_start_date` (DATE), `effective_end_date` (DATE), `is_current` (BOOLEAN)
2. `fct_player_game_stats`:
   - `player_sk` (STRING), `game_id` (STRING), `team_id` (STRING), `game_date` (DATE), `season` (STRING)
   - Box score stats: `minutes`, `pts`, `reb`, `ast`, etc. (all INT).
3. `kpi_team_win_pct`:
   - `season` (STRING), `team_id` (STRING), `team_name` (STRING)
   - `games_played` (INT), `wins` (INT), `win_pct` (DOUBLE)
4. `kpi_player_points_season`:
   - `season` (STRING), `player_id` (STRING), `team_id` (STRING), `total_points` (INT)
