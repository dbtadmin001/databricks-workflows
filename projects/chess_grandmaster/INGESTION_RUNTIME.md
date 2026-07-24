# Project 5 Ingestion Runtime

| Control | Project 5 implementation |
|---|---|
| Incremental load | Canonical per-game hashes and endpoint ETag/Last-Modified conditionals insert only changed source records. |
| Checkpoint | `chess_ingestion_checkpoints` advances only after the corresponding Bronze Delta merge commits. |
| Resume | A `304` archive index reuses its last Bronze archive URL list and still checks the latest monthly page for new games. |
| Pagination | Monthly archive URLs are bounded by `archive_months`; each URL is a separately committed page. |
| Caching | Durable ETag and Last-Modified values avoid downloading unchanged archive pages. |
| Timeout | API requests use 20 seconds; Bronze, Silver, and Gold tasks use 600-second bounds. |
| Retry | Transient 429, 5xx, timeout, and URL errors use two bounded exponential retries. |

The operational order is fetch page -> merge Bronze -> update endpoint checkpoint -> request next page. A failed fetch never advances the checkpoint. Bronze record hashes and Silver `game_id` deduplication make replay idempotent.
