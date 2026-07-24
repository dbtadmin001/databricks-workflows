# POS Retail — Multi-Platform Analytics Pipeline

**Bakehouse franchise POS retail analytics — deployable to Databricks, Microsoft Fabric, or AWS**

## Overview

This repository implements a medallion architecture pipeline for analyzing point-of-sale data. The codebase is organized as a **multi-platform framework**: business logic is shared across platforms, while platform-specific deployment adapters live in separate directories.

## Repository Structure

```
src/core/                      Platform-agnostic business logic (PySpark/SQL transforms)
projects/pos_retail/           Project-specific configuration
platforms/                     Platform-specific deployment adapters
  ├── databricks/              Databricks Asset Bundles, pipelines, dashboards, dbt
  ├── fabric/                  Microsoft Fabric workspace items, lakehouses
  └── aws/                     AWS EKS, Spark-on-K8s, Terraform
config/environments/           Environment-specific configuration (dev/test/prod)
infra/                         Shared infrastructure modules and scripts
tests/                         Unit, integration, contract, and parity tests
```

## Deployment Interface

Deploy any project to any platform with:

- `TARGET_PLATFORM`: databricks | fabric | aws
- `ENVIRONMENT`: dev | test | prod
- `PROJECT_NAME`: pos_retail
- `CONFIG_PATH`: config/environments/${ENVIRONMENT}.yml

## Quick Start

### 1. Configure Environment

Copy the template and fill in your values:

```bash
cp config/.env.example config/.env
# Edit config/.env with your credentials
```

### 2. Deploy to Databricks

See `platforms/databricks/README.md` for detailed deployment instructions.

### 3. Deploy to Fabric

See `platforms/fabric/README.md` (coming soon)

### 4. Deploy to AWS

See `platforms/aws/README.md` (coming soon)

## CI/CD Flow

```
feature-branch → PR → pr-checks.yml (shared CI) → merge → platform-specific deploy
```

All merges to `main` require PR review and passing CI checks.

## Development

### Local CI (Docker)

Run offline CI checks without Databricks compute:

```bash
docker compose run --rm ci
```

This uses a **digest-pinned** base image for reproducibility. See [DOCKER_DIGEST_PINNING.md](DOCKER_DIGEST_PINNING.md) for details.

### Environment Configuration

Environment-specific settings live in `config/environments/{env}.yml`. Load programmatically:

```bash
python infra/scripts/load_config.py --environment dev --platform databricks
```

## Required Secrets

Configure as GitHub secrets (CI/CD) or environment variables (local):

| Secret | Description |
|--------|-------------|
| `DATABRICKS_HOST` | Workspace URL |
| `DATABRICKS_TOKEN` | Service principal or user PAT |
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse ID |
| `DATABRICKS_HTTP_PATH` | SQL warehouse HTTP path (for dbt) |

For Fabric and AWS, see `config/.env.example`.

## Documentation

### Platform-Specific Deployment
* **Databricks**: [platforms/databricks/README.md](platforms/databricks/README.md)
* **Fabric**: `platforms/fabric/README.md` (coming soon)
* **AWS**: `platforms/aws/README.md` (coming soon)

### Architecture & Concepts
* **Migration Guide**: [MIGRATION.md](MIGRATION.md) — Refactoring history and architecture decisions
* **dbt Usage**: [DBT_USAGE.md](DBT_USAGE.md) — What dbt does vs doesn't do; PySpark vs dbt boundary
* **Docker Digest Pinning**: [DOCKER_DIGEST_PINNING.md](DOCKER_DIGEST_PINNING.md) — Why and how we pin base images

### Testing
* **dbt Tests**: [platforms/databricks/dbt/README.md](platforms/databricks/dbt/README.md) — Gold layer data quality tests
* **Unit Tests**: `tests/unit/` — Platform-agnostic transform tests
* **Contract Tests**: `tests/contracts/` — Schema validation tests
* **Parity Tests**: `tests/parity/` (coming soon) — Cross-platform consistency tests

### Adding New Projects
* [ADDING_PROJECTS.md](ADDING_PROJECTS.md) — Template for adding new analytics projects to this framework
