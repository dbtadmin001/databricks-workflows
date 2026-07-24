# Ingestion Runtime Contract

Every real source adapter records these controls. The MVP implements only the bounded
timeout/retry behavior needed for its immutable snapshot. The remaining controls move
to Reliability unless source correctness requires them immediately:

| Control | Required behavior |
|---|---|
| Incremental load | Use a source watermark, cursor, version, ETag, or deterministic record hash; document backfill behavior. |
| Checkpoint | Persist progress only after the corresponding Bronze page or batch commits successfully. |
| Resume | Restart from the last committed cursor/watermark without rewriting or skipping accepted records. |
| Pagination | Bound page count and page size, detect repeated cursors, and retain page-level lineage. |
| Caching | Prefer source conditionals such as ETag/Last-Modified; set an explicit TTL for local response caches. |
| Timeout | Set request and task timeouts; never rely on library defaults. |
| Retry | Retry only transient failures with bounded exponential backoff and preserve the failed endpoint. |

`ingestion.py` supplies a tested page orchestration primitive for Reliability. When it
is activated, preserve its fetch -> Bronze commit -> checkpoint ordering.
