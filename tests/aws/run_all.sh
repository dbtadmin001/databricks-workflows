#!/usr/bin/env bash
# AWS platform adapter test runner
# Run all tests for AWS infrastructure code

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== AWS Platform Adapter Tests ==="
echo ""

# Track overall success
OVERALL_SUCCESS=true

# Run Terraform validation tests
echo "Running Terraform validation tests..."
if "$SCRIPT_DIR/test_terraform.sh"; then
  echo "✓ Terraform tests passed"
else
  echo "✗ Terraform tests failed"
  OVERALL_SUCCESS=false
fi
echo ""

# Run K8s manifest validation tests
echo "Running Kubernetes manifest validation tests..."
if python3 "$SCRIPT_DIR/test_k8s_manifests.py"; then
  echo "✓ K8s manifest tests passed"
else
  echo "✗ K8s manifest tests failed"
  OVERALL_SUCCESS=false
fi
echo ""

# Summary
if [ "$OVERALL_SUCCESS" = true ]; then
  echo "=== All AWS tests passed! ==="
  exit 0
else
  echo "=== Some AWS tests failed ==="
  exit 1
fi
