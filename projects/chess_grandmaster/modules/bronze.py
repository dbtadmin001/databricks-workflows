from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import types as T

from .sources import ApiResource


BRONZE_SCHEMA = T.StructType(
    [
        T.StructField("record_hash", T.StringType(), False),
        T.StructField("source_record_id", T.StringType(), False),
        T.StructField("record_type", T.StringType(), False),
        T.StructField("username", T.StringType(), True),
        T.StructField("endpoint", T.StringType(), False),
        T.StructField("payload_json", T.StringType(), False),
        T.StructField("source_etag", T.StringType(), True),
        T.StructField("source_last_modified", T.StringType(), True),
        T.StructField("source_status", T.IntegerType(), False),
        T.StructField("request_id", T.StringType(), False),
        T.StructField("run_id", T.StringType(), False),
        T.StructField("ingested_at", T.TimestampType(), False),
    ]
)

CHECKPOINT_SCHEMA = T.StructType(
    [
        T.StructField("endpoint", T.StringType(), False),
        T.StructField("record_type", T.StringType(), False),
        T.StructField("source_etag", T.StringType(), True),
        T.StructField("source_last_modified", T.StringType(), True),
        T.StructField("source_status", T.IntegerType(), False),
        T.StructField("records_inserted", T.LongType(), False),
        T.StructField("last_run_id", T.StringType(), False),
        T.StructField("checkpointed_at", T.TimestampType(), False),
    ]
)


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def resource_records(resources: list[ApiResource], run_id: str, request_id: str) -> list[tuple]:
    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    records = []
    for resource in resources:
        if resource.status == 304 or resource.payload is None:
            continue
        payloads: list[dict]
        if resource.kind == "games":
            payloads = resource.payload.get("games", [])
        elif resource.kind == "leaderboard":
            payloads = resource.payload.get("live_blitz", [])
        else:
            payloads = [resource.payload]
        for payload in payloads:
            body = canonical_json(payload)
            username = _username(resource.kind, payload, resource.endpoint)
            source_id = _source_id(resource.kind, payload, resource.endpoint)
            digest = hashlib.sha256(
                f"{resource.kind}|{source_id}|{body}".encode("utf-8")
            ).hexdigest()
            records.append(
                (
                    digest,
                    source_id,
                    resource.kind,
                    username,
                    resource.endpoint,
                    body,
                    resource.etag,
                    resource.last_modified,
                    resource.status,
                    request_id,
                    run_id,
                    ingested_at,
                )
            )
    return records


def _username(kind: str, payload: dict, endpoint: str) -> str | None:
    if kind in {"profile", "leaderboard"}:
        value = payload.get("username")
        return value.lower() if isinstance(value, str) else None
    if kind == "games":
        return endpoint.split("/player/")[-1].split("/")[0].lower()
    return None


def _source_id(kind: str, payload: dict, endpoint: str) -> str:
    if kind == "games":
        return str(payload.get("uuid") or payload.get("url") or endpoint)
    if kind in {"profile", "leaderboard"}:
        return str(payload.get("player_id") or payload.get("username") or endpoint)
    return endpoint


def to_bronze_dataframe(
    spark: SparkSession, resources: list[ApiResource], run_id: str, request_id: str
) -> DataFrame:
    return spark.createDataFrame(resource_records(resources, run_id, request_id), BRONZE_SCHEMA)


def merge_bronze(spark: SparkSession, incoming: DataFrame, table_name: str) -> dict:
    before = spark.table(table_name).count() if spark.catalog.tableExists(table_name) else 0
    if not spark.catalog.tableExists(table_name):
        incoming.limit(0).write.format("delta").mode("overwrite").saveAsTable(table_name)
    incoming.createOrReplaceTempView("chess_bronze_incoming")
    spark.sql(
        f"""
        MERGE INTO {table_name} AS target
        USING chess_bronze_incoming AS source
        ON target.record_hash = source.record_hash
        WHEN NOT MATCHED THEN INSERT *
        """
    )
    after = spark.table(table_name).count()
    return {
        "table": table_name,
        "rows_before": before,
        "rows_after": after,
        "rows_inserted": after - before,
    }


def latest_conditionals(spark: SparkSession, table_name: str) -> dict[str, dict[str, str]]:
    if not spark.catalog.tableExists(table_name):
        return {}
    rows = spark.sql(
        f"""
        SELECT endpoint, max_by(source_etag, ingested_at) AS etag,
               max_by(source_last_modified, ingested_at) AS last_modified
        FROM {table_name}
        GROUP BY endpoint
        """
    ).collect()
    return {
        row.endpoint: {"etag": row.etag, "last_modified": row.last_modified}
        for row in rows
        if row.etag or row.last_modified
    }


def latest_archive_urls(spark: SparkSession, table_name: str) -> dict[str, list[str]]:
    """Recover pagination checkpoints from the latest persisted archive-index payload."""
    if not spark.catalog.tableExists(table_name):
        return {}
    rows = spark.sql(
        f"""
        SELECT endpoint, max_by(payload_json, ingested_at) AS payload_json
        FROM {table_name}
        WHERE record_type = 'archive_index'
        GROUP BY endpoint
        """
    ).collect()
    checkpoints = {}
    for row in rows:
        username = row.endpoint.split("/player/")[-1].split("/")[0].lower()
        checkpoints[username] = json.loads(row.payload_json).get("archives", [])
    return checkpoints


def upsert_checkpoint(
    spark: SparkSession,
    resource: ApiResource,
    table_name: str,
    run_id: str,
    records_inserted: int,
) -> None:
    """Advance the endpoint checkpoint only after its Bronze merge commits."""
    row = [
        (
            resource.endpoint,
            resource.kind,
            resource.etag,
            resource.last_modified,
            resource.status,
            records_inserted,
            run_id,
            datetime.now(timezone.utc).replace(tzinfo=None),
        )
    ]
    incoming = spark.createDataFrame(row, CHECKPOINT_SCHEMA)
    if not spark.catalog.tableExists(table_name):
        incoming.limit(0).write.format("delta").mode("overwrite").saveAsTable(table_name)
    incoming.createOrReplaceTempView("chess_checkpoint_incoming")
    spark.sql(
        f"""
        MERGE INTO {table_name} AS target
        USING chess_checkpoint_incoming AS source
        ON target.endpoint = source.endpoint
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """
    )


def checkpoint_conditionals(spark: SparkSession, table_name: str) -> dict[str, dict[str, str]]:
    if not spark.catalog.tableExists(table_name):
        return {}
    return {
        row.endpoint: {"etag": row.source_etag, "last_modified": row.source_last_modified}
        for row in spark.table(table_name).collect()
        if row.source_etag or row.source_last_modified
    }
