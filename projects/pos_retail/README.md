# POS Retail Project

**Bakehouse franchise POS retail analytics pipeline**

## Overview

This project implements a medallion architecture pipeline for analyzing point-of-sale data from Bakehouse franchise locations.

## Structure

```
config/         Project configuration (data sources, environments)
contracts/      Data contracts and schema definitions
entry_points/   Thin orchestration notebooks/scripts
```

## Business Logic

The core transformation logic lives in `src/core/transformations/` and is shared across all deployment platforms.

## Deployment

Deploy this project to any platform by specifying:

```bash
TARGET_PLATFORM=databricks|fabric|aws
ENVIRONMENT=dev|test|prod
PROJECT_NAME=pos_retail
CONFIG_PATH=projects/pos_retail/config/project.yml
```

See `platforms/<platform>/` for platform-specific deployment instructions.
