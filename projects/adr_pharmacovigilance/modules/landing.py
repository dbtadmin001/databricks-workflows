"""Stages the Bundle-synced raw document set into the Terraform-managed
Unity Catalog landing volume, so the immutable source-document copy the
assignment requires ("keep source documents immutable and retain lineage
from dashboard output to source document") lives in governed UC storage,
not only in the ephemeral workspace files sync. Mirrors
projects/09_github_sentiment_analytics's `stage_raw_files` pattern.
"""

from __future__ import annotations

import re
from typing import Protocol

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class FileSystem(Protocol):
    def mkdirs(self, path: str) -> object: ...

    def cp(self, source: str, destination: str, recurse: bool = False) -> object: ...


def validate_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe {label}: {value!r}")
    return value


def volume_raw_path(catalog: str, schema: str, volume: str) -> str:
    for value, label in ((catalog, "catalog"), (schema, "schema"), (volume, "volume")):
        validate_identifier(value, label)
    return f"/Volumes/{catalog}/{schema}/{volume}/raw"


def stage_raw_files(fs: FileSystem, raw_dir: str, catalog: str, schema: str, volume: str) -> str:
    """Copy the immutable document/historical/reference snapshot into the
    governed UC landing volume. Idempotent: re-running with unchanged source
    files overwrites the same destination paths, it does not duplicate."""
    destination_root = volume_raw_path(catalog, schema, volume)
    fs.mkdirs(destination_root)
    source = raw_dir.replace("\\", "/")
    source_uri = source if ":" in source[:8] else f"file:{source}"
    fs.cp(source_uri, f"dbfs:{destination_root}", True)
    return destination_root
