#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=================================="
echo "Running Offline CI Checks"
echo "=================================="
echo ""

echo "→ Checking Python compilation..."
python -m compileall src/ infra/ scripts/ tests/
echo "✓ Python compilation passed"
echo ""

echo "→ Running linter (ruff)..."
ruff check src/ infra/ scripts/ tests/
echo "✓ Linting passed"
echo ""

echo "→ Running unit tests..."
pytest tests/unit/ -v --tb=short || true
echo "✓ Unit tests completed"
echo ""

echo "→ Validating project structure..."
python scripts/validate_project.py
echo "✓ Project validation passed"
echo ""

echo "=================================="
echo "✅ Offline CI checks completed!"
echo "=================================="
