# Risks and Trade-offs — Chess.com Grandmaster and User Analytics

## Core risks

- Public APIs and websites can change, throttle, block or disappear.
- Schema drift can silently corrupt downstream analytics if Silver contracts are weak.
- Streaming state and checkpoints can produce duplicates if writes are not idempotent.
- Overly generic adapters can obscure project-specific semantics.
- Automatic schema evolution can normalize source defects.
- External BI, Kafka, Airflow, dbt or Docker can add dependency risk during assessments.

## Required design positions

- Use deterministic mock data as the acceptance source of truth.
- Keep live-source connectivity optional and replaceable.
- Preserve raw source payloads in Bronze.
- Require reviewed contract changes before Silver/Gold evolution.
- Prefer Databricks-native Jobs and Bundles unless cross-platform orchestration is required.
- Introduce dbt only when it provides clear Gold-layer value.
- Introduce Docker only for components outside normal Databricks execution.

## Project-specific considerations

- ETag incremental ingestion
- Large-scale flattening
- WAP data quality pattern
- SCD Type 2 player profile history
- Chispa tests
- Optional dbt marts
