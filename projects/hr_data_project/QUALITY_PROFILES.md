# Stage Quality Profiles

Each Bronze, Silver, and Gold candidate is profiled once under the pipeline run ID.
The governed Delta report records schema, row count, exact distinct business-key count,
duplicate count, per-column null rates, rejected records, and a bounded deterministic
sample. Bronze and Silver samples contain row fingerprints only; Gold exposes only the
columns explicitly allowlisted in `quality_contracts.json`.

Thresholds are versioned per layer. Row-level Silver defects continue to quarantine,
while a critical profile or schema failure holds Gold publication and preserves the
last good Gold table. Change keys, sample columns, or thresholds through a reviewed
contract update; do not hardcode project-specific rules in notebooks.
