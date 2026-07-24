# UAT Plan - Programme Funding & Parallel-Run Reconciliation

## Entry gate

UAT cannot begin until implementation tasks are independently reviewed, automated acceptance checks pass, reconciliation evidence exists, and the target environment is identified.

## Scenarios

1. Execute the deterministic fixture path from a clean environment.
2. Verify Bronze source fidelity and audit columns.
3. Verify Silver contract enforcement, deduplication and invalid-record handling.
4. Reconcile each Gold outcome listed in `ACCEPTANCE_CRITERIA.md` against expected fixtures.
5. Verify idempotent rerun behavior and actionable source-failure diagnostics.
6. Verify Community/Free limitations and enterprise-only controls are labelled accurately.

## Evidence and approval

Store commands, actual results, screenshots or run identifiers, reconciliation outputs and defects under `evidence/uat/`. Sol performs final UAT review; a human records PASS, FAIL or CONDITIONAL approval. Failed UAT returns the affected bounded task to changes requested.
