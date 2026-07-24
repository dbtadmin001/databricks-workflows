#!/usr/bin/env bash
# Update Docker base image digest in Dockerfile
# Usage: ./scripts/update_base_image.sh [IMAGE:TAG]
# Example: ./scripts/update_base_image.sh python:3.11-slim

set -euo pipefail

IMAGE_TAG="${1:-python:3.11-slim}"
DOCKERFILE="${2:-.devcontainer/Dockerfile}"

# Parse image and tag
IFS=':' read -r IMAGE TAG <<< "$IMAGE_TAG"

echo "Fetching latest digest for ${IMAGE}:${TAG}..."

# Get auth token from Docker Hub
TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/${IMAGE}:pull" | grep -o '"token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "Error: Failed to get Docker Hub auth token"
  exit 1
fi

# Get manifest digest
DIGEST=$(curl -sI -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
  "https://registry-1.docker.io/v2/library/${IMAGE}/manifests/${TAG}" \
  | grep -i docker-content-digest | awk '{print $2}' | tr -d '\r')

if [ -z "$DIGEST" ]; then
  echo "Error: Failed to get digest for ${IMAGE}:${TAG}"
  exit 1
fi

echo "✓ Found digest: ${DIGEST}"
echo ""

# Show the full reference
PINNED_REF="${IMAGE}:${TAG}@${DIGEST}"
echo "Pinned reference: ${PINNED_REF}"
echo ""

# Update Dockerfile
if [ ! -f "$DOCKERFILE" ]; then
  echo "Error: Dockerfile not found at $DOCKERFILE"
  exit 1
fi

# Backup original
cp "$DOCKERFILE" "${DOCKERFILE}.bak"

# Update the FROM line
# Match lines like: FROM python:3.11-slim or FROM python:3.11-slim@sha256:...
sed -i.tmp "s|^FROM ${IMAGE}:[^@[:space:]]*\(@sha256:[^[:space:]]*\)\?|FROM ${PINNED_REF}|" "$DOCKERFILE"
rm -f "${DOCKERFILE}.tmp"

echo "✓ Updated $DOCKERFILE"
echo ""

# Show the diff
echo "Changes:"
diff -u "${DOCKERFILE}.bak" "$DOCKERFILE" || true
echo ""

# Clean up backup
rm -f "${DOCKERFILE}.bak"

echo "✓ Done! Rebuild your Docker image with: docker compose build"
