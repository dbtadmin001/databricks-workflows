# Entry Points

This directory contains thin orchestration scripts/notebooks that reference shared transformation logic.

Do NOT place heavy business logic here — that belongs in:
* `src/core/transformations/` (if reusable by 2+ projects)
* `projects/<project_name>/modules/` (if project-specific)

Entry points should be lightweight wrappers that:
1. Import transformation functions
2. Configure environment-specific parameters
3. Orchestrate execution order
