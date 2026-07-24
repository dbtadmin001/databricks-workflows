# Acceptance Criteria — Chess.com Grandmaster and User Analytics

## Minimum working stack

- [ ] Package installs from a clean environment.
- [ ] Unit tests and Chispa tests pass.
- [ ] One source adapter works against deterministic fixtures.
- [ ] Bronze write preserves source rows and audit metadata.
- [ ] Silver transformation enforces explicit types and deterministic deduplication.
- [ ] Invalid records are quarantined or fail according to policy.
- [ ] Gold models produce the required KPIs.
- [ ] Re-running the same data does not duplicate results.
- [ ] Bundle validates and the dev smoke job completes.
- [ ] Test and run evidence is saved.

## Project-specific acceptance

- [ ] Daily active players is calculated and verified against expected fixtures.
- [ ] Games per user is calculated and verified against expected fixtures.
- [ ] Win/draw/loss rate is calculated and verified against expected fixtures.
- [ ] Rating change is calculated and verified against expected fixtures.
- [ ] Opening success is calculated and verified against expected fixtures.
- [ ] Power-user segmentation is calculated and verified against expected fixtures.

## UAT acceptance

- [ ] Show that unchanged API resources are skipped, changed archives are loaded once, and bad data cannot be published.
- [ ] A reviewer can reproduce the result using documented commands.
- [ ] Known limitations and unsupported enterprise features are clearly labelled.
