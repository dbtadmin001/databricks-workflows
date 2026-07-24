from __future__ import annotations

import argparse
import json

from pyspark.sql import SparkSession

from .gold import write_gold
from .silver import write_silver


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--catalog", required=True)
    result.add_argument("--schema", required=True)
    return result


def run_silver() -> None:
    args = parser().parse_args()
    spark = SparkSession.builder.getOrCreate()
    schema_name = f"{args.catalog}.{args.schema}"
    result = write_silver(spark, f"{schema_name}.chess_bronze_pubapi", schema_name)
    print(json.dumps(result, sort_keys=True))


def run_gold() -> None:
    args = parser().parse_args()
    spark = SparkSession.builder.getOrCreate()
    schema_name = f"{args.catalog}.{args.schema}"
    result = write_gold(spark, f"{schema_name}.chess_silver_games", schema_name)
    print(json.dumps(result, sort_keys=True))
