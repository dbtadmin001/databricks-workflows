# Requirements

## Objective
Build a dimensional model (SCD2 dimension and fact table) and KPIs for an internal NBA analytics platform.

## Tasks
1. **dim_player as SCD Type 2**:
   - Merge two season roster extracts (2023-24 and 2024-25).
   - Tracked attributes: `team_id`, `jersey_number`, `position`.
   - Static attributes (not versioned): bio fields (`name`, `birthdate`, `height`, `weight`, `draft_year`).
   - Use surrogate key (`player_sk`), natural key (`player_id`), and effective dates.
   - Use season start dates for boundaries: `2023-10-01` for 2023-24, `2024-10-01` for 2024-25.
   - Implement with `MERGE INTO` and hash-based change detection.

2. **fct_player_game_stats**:
   - Grain: one row per player per game.
   - Join box scores to games (for `game_date`, `season`) and to `dim_player` based on the effective date.
   - Resolve `player_sk` and `team_id`.
   - Include stat measures.

3. **KPIs**:
   1. Points by team, per player, per season.
   2. Team win % by season (wins / games played).
   3. Top 5 scorers by season, by points per game (optional, time permitting).

4. **Visualization**:
   - One chart showing team win % by season across all 8 teams.
