# Docker Image Digest Pinning

## Overview

This repository pins Docker base images by **digest** (SHA256 hash) rather than tag to ensure:
* **Reproducibility** — Identical builds across time and environments
* **Security** — Explicit control over image updates
* **Auditability** — Clear record of which image version is used

## Why Digest Pinning?

### Problem with Tag-Based References

```dockerfile
FROM python:3.11-slim
```

**Issues**:
* Tags are **mutable** — `python:3.11-slim` can point to different images over time
* CI builds today may differ from CI builds tomorrow
* Kubernetes pods may pull different images across nodes
* No guarantee of what you're running

### Solution: Digest Pinning

```dockerfile
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93
```

**Benefits**:
* Digest is **immutable** — uniquely identifies image content
* Builds are **reproducible** — same Dockerfile always builds same image
* Kubernetes pulls are **consistent** — all nodes get identical image
* Updates are **explicit** — requires intentional digest update

## Current Pinned Images

| Image | Tag | Digest | Updated |
|-------|-----|--------|---------|
| python | 3.11-slim | `sha256:db3ff2e...053a93` | 2024-01 |

## How to Update Base Image

### Automatic Update (Recommended)

```bash
# Update to latest python:3.11-slim digest
./scripts/update_base_image.sh python:3.11-slim

# Update and specify Dockerfile location
./scripts/update_base_image.sh python:3.11-slim .devcontainer/Dockerfile
```

The script:
1. Fetches the latest digest from Docker Hub
2. Updates the `FROM` line in the Dockerfile
3. Shows a diff of changes
4. Preserves the tag for readability

### Manual Update

1. **Get the current digest**:
   ```bash
   docker pull python:3.11-slim
   docker inspect python:3.11-slim | grep -A 5 RepoDigests
   ```

2. **Update Dockerfile**:
   ```dockerfile
   FROM python:3.11-slim@sha256:<NEW_DIGEST>
   ```

3. **Rebuild**:
   ```bash
   docker compose build
   ```

### Verification

```bash
# Check what image your container is using
docker compose run --rm ci sh -c "cat /etc/os-release && python --version"
```

## When to Update

### Security Updates
* Monitor [Python Docker Hub](https://hub.docker.com/_/python) for security advisories
* Update digest when critical CVEs are patched
* Test thoroughly before merging

### Feature Updates
* Update when a new Python patch version is released (3.11.x → 3.11.y)
* Do NOT auto-update without testing
* Document breaking changes in commit message

### Regular Maintenance
* Review quarterly (or monthly for security-critical apps)
* Check for base image EOL announcements
* Consider CI alerts for outdated digests

## CI Integration

### Current Behavior
* CI uses the pinned digest from `.devcontainer/Dockerfile`
* All CI runs use identical base image
* Docker layer caching still works (digest is consistent)

### Future: Automated Digest Updates (Phase 2C)
When implementing Kubernetes in AWS:
* Add Dependabot/Renovate to create PRs for digest updates
* Run CI tests on each digest update PR
* Auto-merge if tests pass (with approval)

Example Renovate config:
```json
{
  "dockerfile": {
    "enabled": true,
    "pinDigests": true
  },
  "kubernetes": {
    "enabled": true,
    "pinDigests": true
  }
}
```

## Kubernetes Considerations

### Why Pinning Matters More for K8s

In CI, a mutable tag may cause:
* **Inconsistent builds** — annoying but detectable

In Kubernetes, a mutable tag may cause:
* **Silent runtime drift** — pods on different nodes run different code
* **Failed rollbacks** — "rollback" pulls a different image than originally deployed
* **Debug nightmares** — behavior varies by pod

### K8s Best Practices
1. **Always pin by digest** in Kubernetes manifests
2. **Use image pull policy**: `IfNotPresent` (not `Always`)
3. **Immutable tags**: If using tags, append digest
4. **Image scanning**: Scan digests before deployment

Example K8s manifest:
```yaml
spec:
  containers:
  - name: spark-driver
    image: python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93
    imagePullPolicy: IfNotPresent
```

## Troubleshooting

### Problem: "No matching manifest for linux/arm64"
**Cause**: The digest is for a different architecture.

**Solution**: Pull for your architecture first:
```bash
docker pull --platform linux/amd64 python:3.11-slim
docker inspect python:3.11-slim | grep RepoDigests
```

### Problem: "Digest verification failed"
**Cause**: The digest was tampered with or the image was removed.

**Solution**:
1. Verify digest on Docker Hub
2. Update to a known-good digest
3. Rebuild

### Problem: "Image is outdated"
**Cause**: Pinned digest is old; new security patches available.

**Solution**:
```bash
./scripts/update_base_image.sh python:3.11-slim
git commit -am "chore: update Python base image digest"
```

## References

* [Docker Content Trust](https://docs.docker.com/engine/security/trust/)
* [Kubernetes Best Practices — Image Tagging](https://kubernetes.io/docs/concepts/containers/images/#image-names)
* [CNCF Supply Chain Security](https://www.cncf.io/blog/2021/12/13/sigstore-beyond-signing-verify-container-images-using-cosign-and-kyverno/)

## Related Files

* `.devcontainer/Dockerfile` — Development container (digest-pinned)
* `docker-compose.yml` — Local CI runner
* `scripts/update_base_image.sh` — Automated digest updater
* `.github/workflows/ci-shared.yml` — CI that uses pinned image
