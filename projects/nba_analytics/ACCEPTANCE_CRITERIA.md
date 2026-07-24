# Acceptance Criteria

1. **Preflight**:
   - `dim_player` is an SCD2 table with `effective_start_date`, `effective_end_date`, and `is_current`.
   - Players unchanged across seasons have exactly one row spanning both seasons.
   - Effective boundaries are 2023-10-01 and 2024-10-01.

2. **Transformations**:
   - `fct_player_game_stats` joins box scores to `dim_player` using `game_date` vs `effective_start_date` / `effective_end_date`.
   - Traded players attribute games correctly to their respective teams.

3. **Outputs**:
   - KPIs generate accurate numbers.
   - Win % is calculated correctly.

4. **Pipeline**:
   - End-to-end pipeline executes gracefully as a Databricks Workflow.
   - WAP pattern applies to Gold tables.
