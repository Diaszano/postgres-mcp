# CI/CD and Automated Release Architecture Guide

This document describes the automated continuous integration and delivery architecture for the **Postgres MCP Server**.

## 1. Pipeline Overview

The project uses GitHub Actions workflows for continuous validation and zero-manual-intervention releases:

```
[Developer Branch]
       │
       ▼ (Pull Request)
[.github/workflows/ci.yml]
       ├── Lint & Formatting (Ruff)
       ├── Type Checking (Pyright)
       ├── Unit Tests (pytest tests/unit)
       ├── Package Build (uv build)
       ├── HypoPG Integration Gate (PG16 & PG17)
       └── PR Metadata & Conventional Commits Validation
       │
       ▼ (Merge to main)
[Release Handoff]
       │
       ▼ (Trigger reusable .github/workflows/release.yml)
[Semantic Release Job]
       ├── Verify git baseline & clean history
       ├── Python Semantic Release (PSR 10.7.0 via uvx)
       ├── Calculate next SemVer (vX.Y.Z) & update pyproject.toml
       ├── Create tag & GitHub Release with wheel/sdist assets
       │
       ▼ (On New Release)
[Multiarch GHCR Staging & Delivery]
       ├── Docker Buildx & QEMU (linux/amd64, linux/arm64)
       ├── Generate SLSA Provenance & SBOM (SPDX)
       ├── Stage immutable image: ghcr.io/diaszano/postgres-mcp:sha-<commit-sha>
       ├── Fail-closed vulnerability scan (Trivy HIGH/CRITICAL exit 1)
       └── Promote immutable digest to stable SemVer aliases:
           - ghcr.io/diaszano/postgres-mcp:vX.Y.Z
           - ghcr.io/diaszano/postgres-mcp:X.Y.Z
           - ghcr.io/diaszano/postgres-mcp:X.Y
           - ghcr.io/diaszano/postgres-mcp:X
           - ghcr.io/diaszano/postgres-mcp:latest
```

## 2. Dependency Management & Versioning Invariants

- **Dependency Lock Verification**: `uv lock --check` ensures that dependencies in `uv.lock` strictly match `pyproject.toml`.
- **Release Tag Specification**: Stable releases strictly follow the format `vX.Y.Z` where X, Y, and Z are non-negative integers. Prerelease tags (`-rc`, `-alpha`, `-beta`) are prohibited from stable delivery.
- **Zero-Version Policy**: While on `0.x.y`, breaking changes increment minor (`0.3.0` -> `0.4.0`) rather than bumping to `1.0.0`.

## 3. Pulling and Verifying Images

Users and orchestrators should deploy images using immutable content digests:

```bash
# Pull image by verified immutable SHA256 digest:
docker pull ghcr.io/diaszano/postgres-mcp@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

# Run container
docker run -it --rm \
  ghcr.io/diaszano/postgres-mcp@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 \
  postgres://mcp_agent:password@localhost:5432/mydb
```

## 4. Partial Release Recovery Procedure

In rare scenarios where Python Semantic Release successfully tags a release and publishes to GitHub Releases, but network or container registry timeouts interrupt image build or promotion:

1. **Do not create a duplicate version or re-tag manually.**
2. Navigate to Actions -> **Retry Publish** workflow (`.github/workflows/retry-publish.yml`).
3. Click **Run workflow**, enter the existing verified tag (e.g. `v0.3.0`), and submit.
4. The workflow verifies the commit ancestry and `pyproject.toml` version using `scripts/ci/validate_release_ref.py`, builds the staging image from the exact release commit, scans both architectures with Trivy, and promotes the missing aliases to GHCR without bumping version numbers.
