# <Project Name>

**<One-line business purpose>**

## Overview

<Detailed description of what this project does>

## Data Sources

* **Source 1**: `catalog.schema.table` — <description>
* **Source 2**: `catalog.schema.table` — <description>

## Medallion Architecture

### Bronze Layer
* `bronze_<entity>` — Raw ingestion with audit columns

### Silver Layer
* `silver_<entity>_enriched` — Cleaned and enriched data

### Gold Layer
* `gold_<metric>` — Business aggregations

## Deployment

```bash
TARGET_PLATFORM=databricks|fabric|aws
ENVIRONMENT=dev|test|prod
PROJECT_NAME=<project_name>
CONFIG_PATH=projects/<project_name>/config/project.yml
./scripts/deploy.sh
```

See `platforms/<platform>/` for platform-specific instructions.

## Dependencies

* Python packages: <list>
* External APIs: <list>
* Compute requirements: <specify>

## Testing

```bash
pytest tests/unit/test_<project_name>_*.py
pytest tests/contracts/test_<project_name>_*.py
```

## Monitoring & Alerts

* Job URL: <link>
* Dashboard: <link>
* Alerts: <email/slack>
