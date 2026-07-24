import os

import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)
    builder = SparkSession.builder.master("local[2]")
    session = builder.appName("project_12_pos_inventory_analytics-tests").getOrCreate()
    yield session
    session.stop()
