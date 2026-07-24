#!/usr/bin/env python3
"""
Kubernetes manifest validation tests
Validates SparkApplication CRDs and K8s configs for syntax and required fields.

Run: python tests/aws/test_k8s_manifests.py
"""

import os
import sys
import yaml
from pathlib import Path

# Colors for output
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color

def load_yaml(file_path):
    """Load YAML file and return parsed content."""
    try:
        with open(file_path, 'r') as f:
            return list(yaml.safe_load_all(f))
    except Exception as e:
        print(f"{RED}ERROR{NC}: Failed to parse {file_path}: {e}")
        return None

def validate_spark_application(manifest, file_path):
    """Validate SparkApplication manifest structure."""
    errors = []
    
    # Required fields
    if manifest.get('kind') != 'SparkApplication':
        errors.append("kind must be 'SparkApplication'")
    
    if manifest.get('apiVersion') != 'sparkoperator.k8s.io/v1beta2':
        errors.append("apiVersion must be 'sparkoperator.k8s.io/v1beta2'")
    
    metadata = manifest.get('metadata', {})
    if not metadata.get('name'):
        errors.append("metadata.name is required")
    
    if not metadata.get('namespace'):
        errors.append("metadata.namespace is required")
    
    spec = manifest.get('spec', {})
    if not spec.get('type'):
        errors.append("spec.type is required")
    
    if not spec.get('image'):
        errors.append("spec.image is required")
    
    if not spec.get('mainApplicationFile'):
        errors.append("spec.mainApplicationFile is required")
    
    if not spec.get('driver'):
        errors.append("spec.driver is required")
    
    if not spec.get('executor'):
        errors.append("spec.executor is required")
    
    # Check for placeholder values
    image = spec.get('image', '')
    if '<ECR_REGISTRY>' in image or '<GIT_SHA>' in image:
        errors.append("image contains placeholders (expected in template, not deployed)")
    
    return errors

def validate_namespace(manifest, file_path):
    """Validate Namespace manifest."""
    errors = []
    
    if manifest.get('kind') != 'Namespace':
        errors.append("kind must be 'Namespace'")
    
    if manifest.get('apiVersion') != 'v1':
        errors.append("apiVersion must be 'v1'")
    
    metadata = manifest.get('metadata', {})
    if not metadata.get('name'):
        errors.append("metadata.name is required")
    
    return errors

def validate_service_account(manifest, file_path):
    """Validate ServiceAccount manifest."""
    errors = []
    
    if manifest.get('kind') != 'ServiceAccount':
        errors.append("kind must be 'ServiceAccount'")
    
    metadata = manifest.get('metadata', {})
    if not metadata.get('name'):
        errors.append("metadata.name is required")
    
    if not metadata.get('namespace'):
        errors.append("metadata.namespace is required")
    
    # Check for IRSA annotation
    annotations = metadata.get('annotations', {})
    if 'eks.amazonaws.com/role-arn' not in annotations:
        errors.append("IRSA annotation 'eks.amazonaws.com/role-arn' is required")
    
    return errors

def validate_rbac(manifest, file_path):
    """Validate Role or RoleBinding manifest."""
    errors = []
    
    kind = manifest.get('kind')
    if kind not in ['Role', 'RoleBinding']:
        errors.append(f"Unexpected kind: {kind}")
        return errors
    
    metadata = manifest.get('metadata', {})
    if not metadata.get('name'):
        errors.append("metadata.name is required")
    
    if kind == 'Role':
        rules = manifest.get('rules', [])
        if not rules:
            errors.append("Role must have rules")
    
    if kind == 'RoleBinding':
        if not manifest.get('roleRef'):
            errors.append("RoleBinding must have roleRef")
        if not manifest.get('subjects'):
            errors.append("RoleBinding must have subjects")
    
    return errors

def test_manifest_file(file_path):
    """Test a single manifest file."""
    print(f"Testing {file_path.relative_to(repo_root)}... ", end='')
    
    manifests = load_yaml(file_path)
    if manifests is None:
        print(f"{RED}FAIL{NC} (YAML parse error)")
        return False
    
    all_errors = []
    for idx, manifest in enumerate(manifests):
        if manifest is None:
            continue
        
        kind = manifest.get('kind')
        if kind == 'SparkApplication':
            errors = validate_spark_application(manifest, file_path)
        elif kind == 'Namespace':
            errors = validate_namespace(manifest, file_path)
        elif kind == 'ServiceAccount':
            errors = validate_service_account(manifest, file_path)
        elif kind in ['Role', 'RoleBinding']:
            errors = validate_rbac(manifest, file_path)
        else:
            errors = [f"Unknown kind: {kind}"]
        
        if errors:
            all_errors.extend([f"  Document {idx}: {err}" for err in errors])
    
    if all_errors:
        print(f"{RED}FAIL{NC}")
        for error in all_errors:
            print(f"    {error}")
        return False
    
    print(f"{GREEN}PASS{NC}")
    return True

if __name__ == '__main__':
    print("=== Kubernetes Manifest Validation Tests ===")
    print("")
    
    # Find repository root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    k8s_dir = repo_root / 'platforms' / 'aws' / 'k8s'
    
    if not k8s_dir.exists():
        print(f"{RED}ERROR{NC}: k8s directory not found: {k8s_dir}")
        sys.exit(1)
    
    # Find all YAML files
    yaml_files = list(k8s_dir.rglob('*.yaml'))
    
    if not yaml_files:
        print(f"{YELLOW}WARNING{NC}: No YAML files found in {k8s_dir}")
        sys.exit(0)
    
    pass_count = 0
    fail_count = 0
    
    for yaml_file in yaml_files:
        if test_manifest_file(yaml_file):
            pass_count += 1
        else:
            fail_count += 1
    
    print("")
    print("=== Summary ===")
    print(f"Passed: {pass_count}")
    print(f"Failed: {fail_count}")
    
    if fail_count > 0:
        print(f"{RED}Some tests failed!{NC}")
        sys.exit(1)
    
    print(f"{GREEN}All K8s manifest tests passed!{NC}")
