from __future__ import annotations

import argparse
import json
import os
import uuid

from pyspark.sql import SparkSession

from .bronze import (
    checkpoint_conditionals,
    latest_archive_urls,
    latest_conditionals,
    merge_bronze,
    to_bronze_dataframe,
    upsert_checkpoint,
)
from .sources import ChessComClient


DEFAULT_USER_AGENT = "databricks-blueprints-chess-mvp/0.1 (github: alutadbt)"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--catalog", required=True)
    result.add_argument("--schema", required=True)
    result.add_argument("--usernames", default="hikaru")
    result.add_argument("--archive-months", type=int, default=1)
    result.add_argument("--run-id", default=None)
    result.add_argument("--request-timeout-seconds", type=float, default=20)
    result.add_argument("--source-max-retries", type=int, default=2)
    return result


def source_probe() -> None:
    client = ChessComClient(
        os.getenv("CHESS_USER_AGENT", DEFAULT_USER_AGENT),
        timeout_seconds=float(os.getenv("CHESS_REQUEST_TIMEOUT_SECONDS", "15")),
        max_retries=0,
    )
    resource = client.get("profile", "https://api.chess.com/pub/player/hikaru")
    print(
        json.dumps(
            {
                "status": resource.status,
                "endpoint": resource.endpoint,
                "etag_present": bool(resource.etag),
                "username": (resource.payload or {}).get("username"),
                "title": (resource.payload or {}).get("title"),
            },
            sort_keys=True,
        )
    )


def main() -> None:
    args = parser().parse_args()
    spark = SparkSession.builder.getOrCreate()
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {args.catalog}.{args.schema}")
    table_name = f"{args.catalog}.{args.schema}.chess_bronze_pubapi"
    checkpoint_table = f"{args.catalog}.{args.schema}.chess_ingestion_checkpoints"
    client = ChessComClient(
        os.getenv("CHESS_USER_AGENT", DEFAULT_USER_AGENT),
        timeout_seconds=args.request_timeout_seconds,
        max_retries=args.source_max_retries,
    )
    usernames = [value.strip().lower() for value in args.usernames.split(",") if value.strip()]
    resources = client.iter_user_games(
        usernames=usernames,
        archive_months=args.archive_months,
        conditionals=checkpoint_conditionals(spark, checkpoint_table)
        or latest_conditionals(spark, table_name),
        known_archives=latest_archive_urls(spark, table_name),
    )
    run_id = args.run_id or str(uuid.uuid4())
    rows_before = spark.table(table_name).count() if spark.catalog.tableExists(table_name) else 0
    inserted = 0
    api_resources = 0
    not_modified = 0
    record_types: dict[str, int] = {}
    for resource in resources:
        api_resources += 1
        not_modified += int(resource.status == 304)
        incoming = to_bronze_dataframe(spark, [resource], run_id, str(uuid.uuid4()))
        merge_result = merge_bronze(spark, incoming, table_name)
        inserted += merge_result["rows_inserted"]
        upsert_checkpoint(spark, resource, checkpoint_table, run_id, merge_result["rows_inserted"])
        for row in incoming.groupBy("record_type").count().collect():
            record_types[row.record_type] = record_types.get(row.record_type, 0) + row["count"]
    rows_after = spark.table(table_name).count()
    result = {
        "table": table_name,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_inserted": inserted,
        "run_id": run_id,
        "api_resources": api_resources,
        "not_modified_resources": not_modified,
        "record_types": record_types,
        "checkpoint_strategy": "bronze_page_commit_then_next_archive",
        "checkpoint_table": checkpoint_table,
    }
    print(json.dumps(result, sort_keys=True))
