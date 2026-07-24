from __future__ import annotations

import uuid
from collections.abc import Mapping

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

from .execution import ExecutionIdentity

LEDGER_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("source_fingerprint", StringType(), False),
        StructField("configuration_hash", StringType(), False),
        StructField("code_sha", StringType(), False),
        StructField("pipeline_run_id", StringType(), False),
        StructField("attempt_id", StringType(), False),
        StructField("stage", StringType(), False),
        StructField("status", StringType(), False),
        StructField("event_sequence", IntegerType(), False),
        StructField("reason_code", StringType(), False),
        StructField("comment", StringType(), False),
    ]
)


class SparkStageLedger:
    """Append-only Delta execution ledger keyed by source, configuration, and code."""

    def __init__(self, spark: SparkSession, table_name: str):
        self.spark = spark
        self.table_name = table_name

    def latest_statuses(self, identity: ExecutionIdentity) -> Mapping[str, str]:
        if not self.spark.catalog.tableExists(self.table_name):
            return {}
        matching = self.spark.table(self.table_name).where(
            (F.col("source_fingerprint") == identity.source_fingerprint)
            & (F.col("configuration_hash") == identity.configuration_hash)
            & (F.col("code_sha") == identity.code_sha)
        )
        latest = (
            matching.withColumn(
                "_rank",
                F.row_number().over(
                    Window.partitionBy("stage").orderBy(
                        F.col("event_at").desc(), F.col("event_sequence").desc()
                    )
                ),
            )
            .where(F.col("_rank") == 1)
            .select("stage", "status")
        )
        return {row.stage: row.status for row in latest.collect()}

    def record(
        self,
        identity: ExecutionIdentity,
        pipeline_run_id: str,
        attempt_id: str,
        stage: str,
        status: str,
        sequence: int,
        reason_code: str,
        comment: str,
    ) -> None:
        row = (
            uuid.uuid4().hex,
            identity.source_fingerprint,
            identity.configuration_hash,
            identity.code_sha,
            pipeline_run_id,
            attempt_id,
            stage,
            status,
            sequence,
            reason_code,
            comment,
        )
        (
            self.spark.createDataFrame([row], LEDGER_SCHEMA)
            .withColumn("event_at", F.current_timestamp())
            .write.format("delta")
            .mode("append")
            .saveAsTable(self.table_name)
        )
