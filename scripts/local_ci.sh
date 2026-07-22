#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python -m compileall transformations scripts tests
ruff check transformations scripts tests
pytest -q
python scripts/validate_project.py

echo "Offline CI checks completed successfully."
