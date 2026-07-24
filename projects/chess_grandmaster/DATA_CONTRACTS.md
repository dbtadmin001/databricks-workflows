# Data Contracts — Chess.com Grandmaster and User Analytics

## Contract principles

- Bronze may preserve unknown or additive fields.
- Silver permits only reviewed columns and explicit types.
- Gold schemas are stable analytical contracts.
- New columns, missing columns, type changes, nullability changes and grain changes must be classified.
- Every table must define business keys, event/observation time, ingestion time and source lineage.

## Required contract metadata

| Field | Purpose |
|---|---|
| dataset_name | Stable logical name |
| contract_version | Semantic contract version |
| business_keys | Uniqueness/deduplication keys |
| event_time | Business event or observation timestamp |
| ingestion_time | Platform ingestion timestamp |
| allowed_evolution | Explicit compatibility policy |
| quality_rules | Required, range, domain and referential rules |
| pii_classification | Sensitive-field classification |
| owner | Accountable data-product owner |

## MVP contracts

| Table | Grain / key | Core semantics | MVP update strategy |
|---|---|---|---|
| `chess_bronze_pubapi` | One source payload per `record_hash` | Canonical raw JSON plus source, request, run and ingestion metadata | Delta merge, insert only when the hash is new |
| `chess_ingestion_checkpoints` | One row per source endpoint | Latest conditional cache, status, committed row count, run and checkpoint time | Delta merge after successful Bronze commit |
| `chess_silver_games` | One valid row per `game_id` | Typed game, target-player perspective, opponent, result and opening | Deterministic full rebuild from Bronze |
| `chess_quarantine_games` | One invalid candidate per source hash | Invalid Silver candidates with rejection reason | Deterministic full rebuild from Bronze |
| `chess_gold_daily_activity` | `target_username`, `game_date` | Games, outcomes, average rating and win rate | Full publish from accepted Silver |
| `chess_gold_player_segment` | `target_username` | POWER >= 100 games, ACTIVE >= 30, otherwise CASUAL | Full publish from accepted Silver |
| `chess_gold_opening_performance` | `target_username`, `opening` | Games, wins, average opponent rating and win rate | Full publish from accepted Silver |
| `chess_gold_rating_progression` | `target_username`, `game_date` | End-of-day rating and change from prior active day | Full publish from accepted Silver |
| `chess_gold_player_summary` | `target_username` | Games, active days, outcomes, ratings, date bounds and win rate | Full publish from accepted Silver |

All MVP tables are non-PII public chess data owned by this project. P05-M03 replaces direct Silver-to-Gold execution with stage, audit, and conditional publish; Gold tables must not be enabled for production before that gate passes.
