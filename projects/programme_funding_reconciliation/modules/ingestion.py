from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


Record = TypeVar("Record")


@dataclass(frozen=True)
class SourcePage(Generic[Record]):
    records: list[Record]
    next_cursor: str | None
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False


@dataclass(frozen=True)
class Checkpoint:
    cursor: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    complete: bool = False


@dataclass(frozen=True)
class IngestionOptions:
    max_pages: int = 100
    request_timeout_seconds: float = 20
    max_retries: int = 2
    cache_ttl_seconds: float = 300


FetchPage = Callable[[str | None, float, Checkpoint], SourcePage[Record]]
WritePage = Callable[[list[Record]], int]
SaveCheckpoint = Callable[[Checkpoint], None]


class PageCache(Generic[Record]):
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._items: dict[str, tuple[float, SourcePage[Record]]] = {}

    def get(self, key: str, ttl_seconds: float) -> SourcePage[Record] | None:
        cached = self._items.get(key)
        if cached is None or self._now() - cached[0] > ttl_seconds:
            return None
        return cached[1]

    def put(self, key: str, page: SourcePage[Record]) -> None:
        self._items[key] = (self._now(), page)


def ingest_pages(
    fetch_page: FetchPage[Record],
    write_page: WritePage[Record],
    save_checkpoint: SaveCheckpoint,
    checkpoint: Checkpoint | None = None,
    options: IngestionOptions = IngestionOptions(),
    cache: PageCache[Record] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int | bool]:
    """Fetch, commit, then checkpoint each bounded page so failed runs can resume."""
    state = checkpoint or Checkpoint()
    cursor = state.cursor
    seen: set[str | None] = set()
    pages = 0
    rows = 0
    while pages < options.max_pages:
        if cursor in seen:
            raise RuntimeError(f"Source pagination repeated cursor: {cursor}")
        seen.add(cursor)
        cache_key = cursor or "__first__"
        page = cache.get(cache_key, options.cache_ttl_seconds) if cache else None
        if page is None:
            for attempt in range(options.max_retries + 1):
                try:
                    page = fetch_page(cursor, options.request_timeout_seconds, state)
                    break
                except (TimeoutError, ConnectionError):
                    if attempt == options.max_retries:
                        raise
                    sleep(min(2**attempt, 8))
            if cache and page is not None:
                cache.put(cache_key, page)
        assert page is not None
        written = 0 if page.not_modified else write_page(page.records)
        rows += written
        pages += 1
        state = Checkpoint(
            cursor=page.next_cursor,
            etag=page.etag,
            last_modified=page.last_modified,
            complete=page.next_cursor is None,
        )
        save_checkpoint(state)
        if state.complete:
            return {"pages": pages, "rows_written": rows, "complete": True}
        cursor = state.cursor
    return {"pages": pages, "rows_written": rows, "complete": False}
