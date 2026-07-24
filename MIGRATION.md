# Multi-Platform Migration Documentation

## Overview

This document describes the migration from a Databricks-only mono-repo structure to a multi-platform architecture that supports Databricks, Microsoft Fabric, and AWS deployments with shared business logic.

## Migration Goals

1. **Platform Agnosticism**: Separate business logic from platform-specific deployment code
2. **Multi-Project Support**: Enable multiple analytics projects in one repository
3. **Security**: Remove hardcoded credentials and workspace-specific paths
4. **Reusability**: Share transformation code across platforms
5. **Maintainability**: Clear separation of concerns and standardized structure

## Architecture Changes

### Before (Mono-Platform)

```
databricks-workflows/
├── databricks.yml                    # Bundle definition (root)
├── transformations/                  # Databricks-specific code
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── resources/                        # Databricks resources
├── dashboards/                       # Databricks dashboards
└── .github/workflows/deploy.yml      # Single deployment workflow
```

**Problems**:
- Databricks-specific code mixed with business logic
- Can't reuse transformation code on other platforms
- Hardcoded workspace paths and secrets
- Single project structure (doesn't scale)

### After (Multi-Platform)

```
databricks-workflows/
├── src/
│   └── core/
│       └── transformations/           # Platform-agnostic PySpark
│           ├── bronze/                # Raw data ingestion logic
│           ├── silver/                # Enrichment & DQ logic
│           └── gold/                  # Aggregation logic
│
├── projects/
│   └── pos_retail/                    # Project-specific config
│       ├── config/project.yml         # Data sources, environments
│       ├── contracts/schemas.yml      # Data contracts
│       └── entry_points/              # Thin orchestration code
│
├── platforms/
│   ├── databricks/                    # Databricks-specific plumbing
│   │   ├── bundles/databricks.yml
│   │   ├── resources/
│   │   └── dashboards/
│   ├── fabric/                        # Fabric-specific plumbing
│   └── aws/                           # AWS-specific plumbing
│
├── config/
│   ├── environments/                  # Environment configs
│   │   ├── dev.yml
│   │   ├── test.yml
│   │   └── prod.yml
│   └── .env.example                   # Template for secrets
│
├── infra/
│   ├── scripts/load_config.py         # Config loader utility
│   └── terraform_modules/             # IaC modules
│
├── tests/
│   ├── unit/                          # Local Spark unit tests
│   ├── integration/                   # Integration tests
│   ├── contracts/                     # Data contract validation
│   └── parity/                        # Cross-platform parity tests
│
└── .github/workflows/
    ├── ci-shared.yml                  # Platform-agnostic CI
    ├── deploy-databricks.yml          # Databricks deployment
    ├── deploy-fabric.yml              # Fabric deployment
    └── deploy-aws.yml                 # AWS deployment
```

**Benefits**:
- ✅ Business logic reusable across platforms
- ✅ Clear separation of concerns
- ✅ No hardcoded secrets
- ✅ Multi-project support
- ✅ Platform-specific CI/CD

## Migration Steps Taken

### Phase 0: Audit (Completed)

- Mapped entire repository structure
- Identified business logic vs. platform plumbing
- Flagged hardcoded paths and secrets
- Created migration plan

### Phase 1: Incremental Migration (Completed)

1. ✅ **Created multi-platform directory structure**
   - Added `src/core/`, `projects/`, `platforms/`, `config/`, `infra/`, `tests/`
   - Preserved `.gitkeep` files for empty directories

2. ✅ **Migrated business logic to `src/core/`**
   - Moved `transformations/` → `src/core/transformations/`
   - Added `__init__.py` to all Python packages
   - No code changes, just relocation

3. ✅ **Created project-specific structure**
   - Created `projects/pos_retail/` with config, contracts, entry points
   - Moved SQL notebook to `entry_points/`

4. ✅ **Migrated Databricks platform plumbing**
   - Moved `databricks.yml` → `platforms/databricks/bundles/`
   - Moved `resources/` → `platforms/databricks/resources/`
   - Moved `dashboards/` → `platforms/databricks/dashboards/`
   - Updated all paths to reference new structure

5. ✅ **Externalized hardcoded configs**
   - Created `config/environments/{dev,test,prod}.yml`
   - Created `.env.example` template
   - Built config loader utility with `${VAR}` substitution
   - Removed hardcoded workspace URLs from README

6. ✅ **Refactored CI/CD**
   - Created `ci-shared.yml` for platform-agnostic checks
   - Split `deploy.yml` into platform-specific workflows
   - Updated `pr-checks.yml` to use shared CI

7. ✅ **Validation**
   - Validated structure with `scripts/validate_project.py`
   - Documented deployment process
   - Created deployment guide

## Key Design Decisions

### 1. Relative Paths in Bundle Config

**Decision**: Use `../../../src/core/transformations/**` instead of absolute paths

**Rationale**:
- Works across different clones/forks
- No workspace-specific hardcoding
- Easier to test locally

### 2. Config Loader Utility

**Decision**: Build a Python script for config loading with `${VAR}` substitution

**Rationale**:
- Simple, no external dependencies (just PyYAML)
- Works in CI and locally
- Supports nested variable references

### 3. Platform Adapters

**Decision**: Each platform gets its own directory with deployment definitions

**Rationale**:
- Clear ownership and maintenance boundaries
- Platform-specific features isolated
- Easy to add new platforms without affecting existing ones

### 4. Shared CI + Platform-Specific Deploy

**Decision**: One shared CI workflow, multiple deploy workflows

**Rationale**:
- Avoid duplicate linting/testing across platforms
- Each platform can have custom deploy logic
- Fast feedback (shared CI runs first)

## Breaking Changes

### For Databricks Users

**Old bundle path**:
```bash
cd /Workspace/Repos/user/databricks-workflows/
databricks bundle deploy -t dev
```

**New bundle path**:
```bash
cd /Workspace/Repos/user/databricks-workflows/platforms/databricks/bundles/
databricks bundle deploy -t dev --var warehouse_id=$DATABRICKS_WAREHOUSE_ID
```

**Migration**:
- Update CI/CD scripts to use new path
- Add `warehouse_id` variable

### For Local Development

**Old imports**:
```python
from transformations.bronze import bronze_tables
```

**New imports**:
```python
from src.core.transformations.bronze import bronze_tables
```

**Migration**:
- Update notebook imports if running locally
- Databricks bundle handles this automatically in workspace

## Testing Strategy

### 1. Local CI (Docker)

```bash
docker compose run --rm ci
```

Runs:
- Python compilation
- Linting (ruff)
- Unit tests (pytest)
- Structure validation

### 2. GitHub Actions CI

Triggered on every PR:
- Runs shared CI checks
- Validates Databricks bundle
- Blocks merge if fails

### 3. Platform-Specific Deployment

Triggered on push to `main`:
- Runs shared CI first
- Deploys to target platform (dev or prod)
- Shows summary of deployed resources

## Configuration Management

### Environment Variables (`.env`)

```bash
# Databricks
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE_ID=abc123

# AWS
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Fabric
FABRIC_WORKSPACE_ID=...
FABRIC_TENANT_ID=...
```

### Environment Config Files

```yaml
# config/environments/dev.yml
environment: dev

databricks:
  host: ${DATABRICKS_HOST}
  catalog: workspace
  schema: default_dev
  
aws:
  region: ${AWS_REGION}
  s3_bucket: ${AWS_S3_BUCKET_DEV}
```

### Loading Config in Code

```python
from infra.scripts.load_config import load_environment_config

config = load_environment_config(environment='dev', platform='databricks')
print(config['databricks']['catalog'])  # "workspace"
```

## Rollout Plan

### Phase 1: Databricks (Current)

- ✅ Migrate structure
- ✅ Deploy to dev
- ⏳ Verify end-to-end pipeline
- ⏳ Deploy to prod
- ⏳ Monitor for 1 week

### Phase 2: Microsoft Fabric

- Create Fabric notebooks from shared code
- Deploy to Fabric dev workspace
- Run parity tests (compare outputs)
- Deploy to Fabric prod

### Phase 3: AWS

- Create Glue jobs from shared code
- Deploy infrastructure via Terraform
- Run parity tests
- Deploy to AWS prod

## Success Metrics

- ✅ **No hardcoded secrets in repo**
- ✅ **Platform-agnostic business logic**
- ✅ **Multi-project support**
- ⏳ **Databricks end-to-end validated**
- ⏳ **CI/CD fully automated**
- ⏳ **Documentation complete**

## Next Steps

1. Deploy to Databricks dev and verify
2. Monitor for issues
3. Complete documentation (ADDING_PROJECTS.md)
4. Add comprehensive unit tests
5. Implement Fabric adapter
6. Implement AWS adapter

## Questions & Support

For questions or issues with the migration, contact the platform team or create an issue in the repository.
