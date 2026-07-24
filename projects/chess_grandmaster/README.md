# Chess.com Grandmaster and User Analytics

## Objective

Incrementally ingest large Chess.com game datasets, preserve history, enforce data quality through WAP, and produce user and gameplay analytics.

## Source profile

- Chess.com public API or archived API responses
- Player profile endpoints
- Game archives in PGN/JSON

## Processing mode

Scheduled incremental API ingestion using ETag/If-None-Match semantics where available.

## MVP tables

- Bronze: `chess_bronze_pubapi`
- Silver: `chess_silver_games`
- Quarantine: `chess_quarantine_games`
- Gold: `chess_gold_daily_activity`
- Gold: `chess_gold_player_segment`
- Gold: `chess_gold_opening_performance`
- Gold: `chess_gold_rating_progression`
- Gold: `chess_gold_player_summary`

The dev target writes only to `project_05_chess_grandmaster_dev.medallion`; production is reserved for `project_05_chess_grandmaster_prod.medallion`. The former `workspace.chess_grandmaster_dev` tables are legacy MVP evidence and receive no new writes. P05-M03 will insert the WAP audit/publish task between `silver_transform` and `gold_publish`; production release remains disabled until that gate is reviewed.

## Core outcomes

- Daily active players
- Games per user
- Win/draw/loss rate
- Rating change
- Opening success
- Power-user segmentation

## Distinguishing engineering features

- ETag incremental ingestion
- Page-level Bronze commits and durable endpoint checkpoints
- Resume from stored archive URLs when the archive index is unchanged
- Bounded archive pagination, source caching, retries, and explicit timeouts
- Large-scale flattening
- WAP data quality pattern
- SCD Type 2 player profile history
- Chispa tests
- Optional dbt marts

## UAT goal

Show that unchanged API resources are skipped, changed archives are loaded once, and bad data cannot be published.

Start with `REQUIREMENTS.md`, then follow `IMPLEMENTATION_PLAN.md`.


## Verified sources

See [`DATA_SOURCES.md`](DATA_SOURCES.md) for executable providers, credentials, limitations, fixtures, and source-probe acceptance criteria.
