#!/usr/bin/env bash
# Terraform validation tests
# Run: ./tests/aws/test_terraform.sh

set -euo pipefail

echo "=== Terraform Validation Tests ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TF_DIR="$REPO_ROOT/platforms/aws/terraform"

# Colors
GREEN="\033[0;32m"
RED="\033[0;31m"
NC="\033[0m"  # No Color

PASS_COUNT=0
FAIL_COUNT=0

test_terraform_module() {
  local module_path="$1"
  local module_name=$(basename "$module_path")
  
  echo -n "Testing $module_name... "
  
  cd "$module_path"
  
  # Init
  if ! terraform init -backend=false > /dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} (init failed)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
  
  # Validate
  if ! terraform validate > /dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} (validation failed)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
  
  # Format check
  if ! terraform fmt -check -recursive > /dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} (formatting issues)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
  
  echo -e "${GREEN}PASS${NC}"
  PASS_COUNT=$((PASS_COUNT + 1))
}

# Test modules
echo "Testing Terraform modules..."
for module in "$TF_DIR"/modules/*; do
  if [ -d "$module" ]; then
    test_terraform_module "$module"
  fi
done

echo ""
echo "Testing environment configurations..."
for env in "$TF_DIR"/environments/*; do
  if [ -d "$env" ]; then
    test_terraform_module "$env"
  fi
done

echo ""
echo "=== Summary ==="
echo "Passed: $PASS_COUNT"
echo "Failed: $FAIL_COUNT"

if [ $FAIL_COUNT -gt 0 ]; then
  exit 1
fi

echo -e "${GREEN}All Terraform tests passed!${NC}"
