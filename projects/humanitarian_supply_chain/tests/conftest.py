import os
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


@pytest.fixture(scope="session")
def spark():
    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)
    session = (
        SparkSession.builder.master("local[2]")
        .appName("project-07-unicef-supply-chain-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    yield session
    session.stop()


def _read_raw_csv(spark: SparkSession, filename: str):
    return (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .csv(str(RAW_DATA_DIR / filename))
    )


@pytest.fixture(scope="session")
def warehouses_df(spark):
    return _read_raw_csv(spark, "WAREHOUSES.csv")


@pytest.fixture(scope="session")
def programmes_df(spark):
    return _read_raw_csv(spark, "PROGRAMMES.csv")


@pytest.fixture(scope="session")
def items_df(spark):
    return _read_raw_csv(spark, "ITEMS.csv")


@pytest.fixture(scope="session")
def shipments_df(spark):
    return _read_raw_csv(spark, "SHIPMENTS.csv")
