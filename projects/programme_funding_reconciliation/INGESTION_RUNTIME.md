# Ingestion Runtime Contract

Every real source adapter must decide and test these controls before Silver work begins:

| Control | Required behavior |
|---|---|
| Incremental load | Use a source watermark, cursor, version, ETag, or deterministic record hash; document backfill behavior. |
| Checkpoint | Persist progress only after the corresponding Bronze page or batch commits successfully. |
| Resume | Restart from the last committed cursor/watermark without rewriting or skipping accepted records. |
| Pagination | Bound page count and page size, detect repeated cursors, and retain page-level lineage. |
| Caching | Prefer source conditionals such as ETag/Last-Modified; set an explicit TTL for local response caches. |
| Timeout | Set request and task timeouts; never rely on library defaults. |
| Retry | Retry only transient failures with bounded exponential backoff and preserve the failed endpoint. |

`ingestion.py` supplies a tested page orchestration primitive. Replace the fixture adapter during PXX-M01, but preserve its fetch -> Bronze commit -> checkpoint ordering.
