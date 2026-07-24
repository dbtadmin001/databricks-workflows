from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def ingest_csv_to_bronze(spark: SparkSession, source_path: str, target_table: str) -> DataFrame:
    """
    Ingests a CSV file into a Bronze Delta table with raw fidelity (all string columns).
    Adds ingestion metadata.
    """
    df = (
        spark.read.format("csv")
        .option("header", "true")
        .option("inferSchema", "false")  # Keep everything as string in Bronze
        .load(source_path)
    )

    # Add ingestion metadata
    df = df.withColumn("_ingested_at", F.current_timestamp())
    df = df.withColumn("_source_file", F.col("_metadata.file_path"))

    # Write to target
    df.write.format("delta").mode("overwrite").saveAsTable(target_table)
    return spark.read.table(target_table)
