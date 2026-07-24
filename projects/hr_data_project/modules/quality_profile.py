from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Mapping

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


@dataclass(frozen=True)
class CriticalThresholds:
    min_row_count: int
    max_duplicate_count: int
    max_business_key_null_rows: int
    max_rejected_rate: float


@dataclass(frozen=True)
class QualityContract:
    layer: str
    version: int
    sample_size: int
    business_keys: tuple[str, ...]
    safe_sample_columns: tuple[str, ...]
    critical: CriticalThresholds


@dataclass(frozen=True)
class QualityProfile:
    run_id: str
    layer: str
    contract_version: int
    status: str
    schema_json: str
    row_count: int
    business_keys: tuple[str, ...]
    distinct_business_keys: int
    duplicate_count: int
    business_key_null_rows: int
    null_rates: Mapping[str, float]
    rejected_records: int
    rejected_rate: float
    safe_sample: tuple[Mapping[str, Any], ...]
    critical_failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.critical_failures

    def render(self) -> str:
        failures = ", ".join(self.critical_failures) if self.critical_failures else "none"
        return "\n".join(
            (
                f"Quality profile: {self.layer} v{self.contract_version} ({self.status})",
                f"run_id={self.run_id}",
                f"schema={self.schema_json}",
                f"rows={self.row_count}; business_keys={list(self.business_keys)}; "
                f"distinct_keys={self.distinct_business_keys}; duplicates={self.duplicate_count}",
                f"null_rates={json.dumps(self.null_rates, sort_keys=True)}",
                f"rejected_records={self.rejected_records}; rejected_rate={self.rejected_rate:.6f}",
                f"safe_sample={json.dumps(self.safe_sample, sort_keys=True, default=str)}",
                f"critical_failures={failures}",
            )
        )


def _non_negative_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def parse_contract(document: Mapping[str, Any], layer: str) -> QualityContract:
    version = document.get("contract_set_version")
    sample_size = document.get("sample_size")
    layer_data = document.get("layers", {}).get(layer)
    if not isinstance(version, int) or version < 1:
        raise ValueError("quality contract_set_version must be a positive integer")
    if not isinstance(sample_size, int) or not 0 < sample_size <= 20:
        raise ValueError("quality sample_size must be between 1 and 20")
    if not isinstance(layer_data, Mapping):
        raise ValueError(f"Missing quality contract for layer {layer!r}")
    keys = layer_data.get("business_keys")
    safe_columns = layer_data.get("safe_sample_columns")
    critical = layer_data.get("critical")
    if not isinstance(keys, list) or not keys or not all(isinstance(item, str) for item in keys):
        raise ValueError(f"{layer}.business_keys must be a non-empty string list")
    if not isinstance(safe_columns, list) or not all(
        isinstance(item, str) for item in safe_columns
    ):
        raise ValueError(f"{layer}.safe_sample_columns must be a string list")
    if not isinstance(critical, Mapping):
        raise ValueError(f"{layer}.critical must be an object")
    rejected_rate = critical.get("max_rejected_rate")
    if not isinstance(rejected_rate, (int, float)) or not 0 <= rejected_rate <= 1:
        raise ValueError(f"{layer}.critical.max_rejected_rate must be between 0 and 1")
    return QualityContract(
        layer,
        version,
        sample_size,
        tuple(keys),
        tuple(safe_columns),
        CriticalThresholds(
            _non_negative_int(critical.get("min_row_count"), "min_row_count"),
            _non_negative_int(critical.get("max_duplicate_count"), "max_duplicate_count"),
            _non_negative_int(
                critical.get("max_business_key_null_rows"),
                "max_business_key_null_rows",
            ),
            float(rejected_rate),
        ),
    )


def load_contract(layer: str) -> QualityContract:
    path = files("hr_data_project").joinpath("quality_contracts.json")
    return parse_contract(json.loads(path.read_text(encoding="utf-8")), layer)


def contract_set_hash() -> str:
    path = files("hr_data_project").joinpath("quality_contracts.json")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _critical_failures(
    contract: QualityContract,
    row_count: int,
    duplicate_count: int,
    key_null_rows: int,
    rejected_rate: float,
) -> tuple[str, ...]:
    checks = (
        ("ROW_COUNT_BELOW_MINIMUM", row_count < contract.critical.min_row_count),
        ("DUPLICATE_BUSINESS_KEY", duplicate_count > contract.critical.max_duplicate_count),
        (
            "NULL_BUSINESS_KEY",
            key_null_rows > contract.critical.max_business_key_null_rows,
        ),
        ("REJECTED_RATE_EXCEEDED", rejected_rate > contract.critical.max_rejected_rate),
    )
    return tuple(code for code, failed in checks if failed)


def build_profile(
    dataframe: DataFrame,
    layer: str,
    run_id: str,
    *,
    rejected_records: int = 0,
) -> QualityProfile:
    contract = load_contract(layer)
    missing_keys = sorted(set(contract.business_keys) - set(dataframe.columns))
    missing_sample = sorted(set(contract.safe_sample_columns) - set(dataframe.columns))
    key_null = F.lit(bool(missing_keys))
    for key in contract.business_keys:
        if key in dataframe.columns:
            key_null = key_null | F.col(key).isNull()
    distinct_expression = (
        F.lit(0)
        if missing_keys
        else F.countDistinct(*[F.col(key) for key in contract.business_keys])
    )
    aggregate_expressions = [
        F.count(F.lit(1)).alias("row_count"),
        distinct_expression.cast("long").alias("distinct_business_keys"),
        F.sum(F.when(key_null, 1).otherwise(0)).cast("long").alias("key_null_rows"),
    ]
    aggregate_expressions.extend(
        F.sum(F.when(F.col(column).isNull(), 1).otherwise(0)).cast("long").alias(f"null_{index}")
        for index, column in enumerate(dataframe.columns)
    )
    metrics = dataframe.agg(*aggregate_expressions).first()
    row_count = int(metrics["row_count"])
    distinct_keys = int(metrics["distinct_business_keys"])
    key_null_rows = int(metrics["key_null_rows"] or 0)
    duplicate_count = max(row_count - key_null_rows - distinct_keys, 0)
    null_rates = {
        column: (int(metrics[f"null_{index}"] or 0) / row_count if row_count else 0.0)
        for index, column in enumerate(dataframe.columns)
    }
    population = row_count + rejected_records
    rejected_rate = rejected_records / population if population else 0.0

    fingerprint = F.sha2(F.to_json(F.struct(*[F.col(name) for name in dataframe.columns])), 256)
    sample_columns = [fingerprint.alias("row_fingerprint")]
    sample_columns.extend(
        F.col(name) for name in contract.safe_sample_columns if name in dataframe.columns
    )
    sampled_rows = (
        dataframe.select(*sample_columns)
        .orderBy("row_fingerprint")
        .limit(contract.sample_size)
        .select(F.to_json(F.struct("*")).alias("sample_json"))
        .collect()
    )
    safe_sample = tuple(json.loads(row["sample_json"]) for row in sampled_rows)
    failures = tuple(
        dict.fromkeys(
            (
                *(("MISSING_BUSINESS_KEY_COLUMN",) if missing_keys else ()),
                *(("MISSING_SAFE_SAMPLE_COLUMN",) if missing_sample else ()),
                *_critical_failures(
                    contract,
                    row_count,
                    duplicate_count,
                    key_null_rows,
                    rejected_rate,
                ),
            )
        )
    )
    return QualityProfile(
        run_id,
        layer,
        contract.version,
        "PASS" if not failures else "CRITICAL_FAILURE",
        dataframe.schema.json(),
        row_count,
        contract.business_keys,
        distinct_keys,
        duplicate_count,
        key_null_rows,
        null_rates,
        rejected_records,
        rejected_rate,
        safe_sample,
        failures,
    )


def persist_profile(
    spark: SparkSession,
    profile: QualityProfile,
    table_name: str,
) -> None:
    row = (
        profile.run_id,
        profile.layer,
        profile.contract_version,
        profile.status,
        profile.schema_json,
        profile.row_count,
        json.dumps(profile.business_keys),
        profile.distinct_business_keys,
        profile.duplicate_count,
        profile.business_key_null_rows,
        json.dumps(profile.null_rates, sort_keys=True),
        profile.rejected_records,
        profile.rejected_rate,
        json.dumps(profile.safe_sample, sort_keys=True, default=str),
        json.dumps(profile.critical_failures),
    )
    (
        spark.createDataFrame(
            [row],
            [
                "run_id",
                "layer",
                "contract_version",
                "status",
                "schema_json",
                "row_count",
                "business_keys_json",
                "distinct_business_keys",
                "duplicate_count",
                "business_key_null_rows",
                "null_rates_json",
                "rejected_records",
                "rejected_rate",
                "safe_sample_json",
                "critical_failures_json",
            ],
        )
        .withColumn("profiled_at", F.current_timestamp())
        .write.format("delta")
        .mode("append")
        .saveAsTable(table_name)
    )


def profile_and_record(
    spark: SparkSession,
    dataframe: DataFrame,
    catalog: str,
    schema: str,
    layer: str,
    run_id: str,
    *,
    rejected_records: int = 0,
) -> QualityProfile:
    profile = build_profile(dataframe, layer, run_id, rejected_records=rejected_records)
    print(profile.render())
    persist_profile(
        spark,
        profile,
        f"{catalog}.{schema}.hr_data_project_stage_quality_profile",
    )
    return profile
