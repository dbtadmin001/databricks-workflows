#!/usr/bin/env bash
# Install Spark Operator on EKS cluster
# Prerequisites: kubectl configured, Helm installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Spark Operator Installation ==="
echo ""

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
  echo "Error: kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/"
  exit 1
fi

if ! command -v helm &> /dev/null; then
  echo "Error: Helm not found. Install from https://helm.sh/docs/intro/install/"
  exit 1
fi

# Test kubectl connectivity
echo "Testing kubectl connectivity..."
if ! kubectl cluster-info &> /dev/null; then
  echo "Error: Cannot connect to Kubernetes cluster"
  echo "Run: aws eks update-kubeconfig --name pos-retail-dev --region us-east-1"
  exit 1
fi
echo "✓ Connected to cluster: $(kubectl config current-context)"
echo ""

# Create namespace and RBAC
echo "Creating namespace and RBAC..."
kubectl apply -f "$PLATFORM_DIR/k8s/config/namespace.yaml"
kubectl apply -f "$PLATFORM_DIR/k8s/config/rbac.yaml"
echo "✓ Namespace and RBAC created"
echo ""

# Add Spark Operator Helm repo
echo "Adding Spark Operator Helm repository..."
helm repo add spark-operator https://kubeflow.github.io/spark-operator
helm repo update
echo "✓ Helm repository added"
echo ""

# Install Spark Operator
echo "Installing Spark Operator..."
helm upgrade --install spark-operator spark-operator/spark-operator \
  --namespace spark-operator \
  --create-namespace \
  --values "$PLATFORM_DIR/k8s/spark-operator/values.yaml" \
  --wait
echo "✓ Spark Operator installed"
echo ""

# Wait for operator to be ready
echo "Waiting for Spark Operator to be ready..."
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=spark-operator \
  -n spark-operator \
  --timeout=120s
echo "✓ Spark Operator is ready"
echo ""

# Apply service account with IRSA
echo "Applying service account (IRSA)..."
echo "⚠️  Update k8s/config/service-account.yaml with actual IAM role ARN before this works!"
kubectl apply -f "$PLATFORM_DIR/k8s/config/service-account.yaml" || true
echo ""

# Verify installation
echo "=== Installation Complete ==="
echo ""
echo "Verify installation:"
echo "  kubectl get pods -n spark-operator"
echo "  kubectl get crd | grep sparkoperator"
echo ""
echo "Next steps:"
echo "  1. Get IAM role ARN: terraform output -raw spark_job_role_arn"
echo "  2. Update k8s/config/service-account.yaml with that ARN"
echo "  3. Apply: kubectl apply -f k8s/config/service-account.yaml"
echo "  4. Deploy Spark jobs: kubectl apply -f k8s/manifests/bronze/"
