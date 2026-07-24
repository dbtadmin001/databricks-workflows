"""Databricks job entry points (python_wheel_task) for the Bundle job graph."""

from __future__ import annotations

import argparse
import json

from pyspark.sql import SparkSession

from projects.humanitarian_supply_chain.modules.pipeline import (
    run_bronze_phase,
    run_gold_phase,
    run_silver_phase,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    return parser.parse_args()


def run_bronze() -> None:
    args = _parse_args()
    spark = SparkSession.builder.getOrCreate()
    result = run_bronze_phase(spark, args.catalog, args.schema)
    print(json.dumps(result, sort_keys=True, default=str))


def run_silver() -> None:
    args = _parse_args()
    spark = SparkSession.builder.getOrCreate()
    result = run_silver_phase(spark, args.catalog, args.schema)
    print(json.dumps(result, sort_keys=True, default=str))


def run_gold() -> None:
    args = _parse_args()
    spark = SparkSession.builder.getOrCreate()
    result = run_gold_phase(spark, args.catalog, args.schema)
    print(json.dumps(result, sort_keys=True, default=str))
