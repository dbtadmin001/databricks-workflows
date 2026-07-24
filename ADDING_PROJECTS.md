# Adding New Projects to the Multi-Platform Framework

This guide shows how to add a new analytics project to the multi-platform framework.

## Overview

Each project in this repository:
- **Shares** the same transformation code in `src/core/`
- **Has** its own configuration in `projects/<project_name>/`
- **Can deploy** to any platform (Databricks, Fabric, AWS)

## Project Structure Template

```
projects/
└── <project_name>/
    ├── config/
    │   └── project.yml            # Data sources, environments
    ├── contracts/
    │   └── schemas.yml            # Data & quality contracts
    ├── entry_points/
    │   ├── <project_name>.sql     # SQL orchestration (optional)
    │   └── <project_name>.py      # Python orchestration (optional)
    └── README.md                  # Project documentation
```

## Step-by-Step Guide

### 1. Create Project Directory Structure

```bash
cd projects/
mkdir -p my_new_project/{config,contracts,entry_points}
```

### 2. Create Project Configuration

Create `projects/my_new_project/config/project.yml`:

```yaml
project:
  name: my_new_project
  description: "Description of your analytics project"
  owner: "team-name@company.com"
  tags:
    - analytics
    - real-time
    - customer-facing

data_sources:
  raw_events:
    type: s3
    path: "s3://my-bucket/raw/events/"
    format: json
  
  dim_customers:
    type: delta
    path: "catalog.schema.customers"

environments:
  dev:
    catalog: workspace
    schema: my_new_project_dev
    refresh_interval: "1 hour"
  
  test:
    catalog: workspace
    schema: my_new_project_test
    refresh_interval: "30 minutes"
  
  prod:
    catalog: prod
    schema: my_new_project
    refresh_interval: "5 minutes"
```

### 3. Define Data Contracts

Create `projects/my_new_project/contracts/schemas.yml`:

```yaml
bronze_events:
  description: "Raw event data from source system"
  columns:
    - name: event_id
      type: string
      nullable: false
      description: "Unique event identifier"
    
    - name: timestamp
      type: timestamp
      nullable: false
      description: "Event timestamp (UTC)"
    
    - name: user_id
      type: string
      nullable: true
      description: "User who triggered event"
    
    - name: event_type
      type: string
      nullable: false
      description: "Type of event (click, view, purchase)"
  
  quality_rules:
    - name: valid_timestamp
      expression: "timestamp >= current_date() - interval 7 days"
      severity: error
    
    - name: non_empty_event_id
      expression: "length(event_id) > 0"
      severity: error

silver_events_enriched:
  description: "Events enriched with customer dimensions"
  columns:
    - name: event_id
      type: string
      nullable: false
    
    - name: timestamp
      type: timestamp
      nullable: false
    
    - name: customer_name
      type: string
      nullable: true
      description: "Customer name from dim table"
    
    - name: customer_segment
      type: string
      nullable: true
      description: "Customer segment (A, B, C)"
  
  quality_rules:
    - name: valid_segment
      expression: "customer_segment in ('A', 'B', 'C') or customer_segment is null"
      severity: warning

gold_event_summary:
  description: "Aggregated event metrics"
  columns:
    - name: date
      type: date
      nullable: false
    
    - name: event_type
      type: string
      nullable: false
    
    - name: event_count
      type: long
      nullable: false
    
    - name: unique_users
      type: long
      nullable: false
```

### 4. Create Entry Point (Optional)

Create `projects/my_new_project/entry_points/my_new_project.sql` for SQL orchestration or analytics queries.

### 5. Add Transformation Code (if needed)

If your project needs custom transformation logic not in `src/core/`, add it there:

```python
# src/core/transformations/bronze/my_events.py

import dlt
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, current_timestamp

@dlt.table(
    name="bronze_events",
    comment="Raw event data from source system"
)
def bronze_events():
    # Ingest raw events from S3
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", "s3://bucket/schema/events")
        .load("s3://bucket/raw/events/")
        .withColumn("_ingestion_timestamp", current_timestamp())
    )
```

### 6. Create Platform Deployment Definitions

#### Databricks

Create `platforms/databricks/resources/my_new_project_pipeline.yml`:

```yaml
resources:
  pipelines:
    my_new_project_pipeline:
      name: ${var.pipeline_name}
      target: ${var.catalog}.${var.schema}
      channel: CURRENT
      photon: true
      serverless: true
      continuous: true
      
      libraries:
        - path: ../../../src/core/transformations/**
      
      configuration:
        pipelines.enableTraceLogging: true
      
      clusters:
        - label: default
          autoscale:
            min_workers: 1
            max_workers: 5
            mode: ENHANCED
```

#### Fabric (skeleton)

Create `platforms/fabric/my_new_project/` structure

#### AWS (skeleton)

Create `platforms/aws/my_new_project/` structure with Terraform and Glue scripts

### 7. Update Bundle Configuration

Add your project to `platforms/databricks/bundles/databricks.yml`:

```yaml
include:
  - ../resources/*.yml
  - ../resources/my_new_project_pipeline.yml   # Add this line

variables:
  pipeline_name:
    description: Deployed pipeline display name.
    default: My New Project Pipeline
```

### 8. Create Project README

Create `projects/my_new_project/README.md` with project overview, data sources, output tables, deployment instructions, and contact info.

### 9. Add Tests

Create `tests/unit/test_my_new_project.py` with unit tests for your transformation logic.

### 10. Deploy and Verify

```bash
# Validate
cd platforms/databricks/bundles/
databricks bundle validate -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID

# Deploy
databricks bundle deploy -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID

# Verify
databricks bundle summary -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

## Multi-Platform Considerations

### Shared Code
- Keep transformation logic in `src/core/` platform-agnostic
- Use PySpark standard APIs (avoid platform-specific features)
- Document any platform-specific workarounds

### Platform Adapters
- Databricks: Use DLT decorators and streaming
- Fabric: Convert to Fabric notebooks and lakehouses
- AWS: Convert to Glue jobs and EMR steps

### Data Contracts
- Define schemas in `contracts/schemas.yml`
- Use contract validation tests
- Run parity tests across platforms

## Best Practices

1. **Start Small**: Begin with a single Bronze table and validate before adding more
2. **Test Locally**: Use `pytest` to test transformation logic before deploying
3. **Version Control**: Commit each step (structure → config → code → deploy)
4. **Document**: Update project README with all dependencies and contact info
5. **Monitor**: Add data quality rules and alerts from day one

## Example Projects

See existing projects for reference:
- `projects/pos_retail/` — Full example with Bronze/Silver/Gold and dashboard

## Questions?

- Review MIGRATION.md for architecture details
- Check DATABRICKS_DEPLOYMENT.md for deployment specifics
- Contact platform team for help
