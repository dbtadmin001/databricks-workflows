## Summary

## Local evidence
* [ ] Ran `docker compose run --rm ci`
* [ ] Verified `python scripts/validate_project.py`
* [ ] Verified `pytest -q`

## Databricks impact
* [ ] Pipeline definitions updated
* [ ] Dashboard definition updated
* [ ] Bundle configuration updated

## Review notes
* Branch protection should require pull requests to `main`
* Branch protection should require the `offline-local-ci` and `bundle-validate` checks
* Branch protection should require at least one code-owner review
