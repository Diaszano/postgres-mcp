# PostgreSQL MCP Release Checklist & Rollback Procedure

Release Version: `0.3.0`
Primary Image Registry: `ghcr.io/diaszano/postgres-mcp`
Release Automation: Python Semantic Release (PSR 10.7.0) via GitHub Actions

## Pre-Release Verification Checklist

Execute the following verification gates before tagging and publishing any release:

- [ ] **Dependency Lock**: Run `uv lock --check` to ensure `uv.lock` is consistent with `pyproject.toml`.
- [ ] **Lint and Formatting**: Run `just lint` (`uv run ruff check .` and `uv run ruff format --check .`).
- [ ] **Static Type Analysis**: Run `just typecheck` (`uv run pyright`).
- [ ] **Unit Test Suite**: Run `just test-unit` (`uv run pytest -q tests/unit`).
- [ ] **Integration Test Suite**: Run `just test-integration` across PostgreSQL 16 and 17 with HypoPG extension containers.
- [ ] **Release Suite**: Run `uv run pytest -q tests/release` covering SemVer rules, conventions, security scans, and workflow gates.
- [ ] **Performance Benchmarks**: Run `uv run --group dev pytest -q tests/performance --run-performance`.
- [ ] **Smoke Tests**: Run `uv run pytest -q tests/release/test_smoke.py`.
- [ ] **Package Build**: Run `uv build` and inspect wheel contents under `dist/`.
- [ ] **Container Build**: Verify multi-architecture container build for `linux/amd64` and `linux/arm64`.

## Automated CI/CD & Delivery Gates

1. **Pull Requests**:
   - All PRs execute read-only checks across linting, typechecking, tests, package build, and HypoPG integration.
   - PR metadata is validated against Conventional Commits.
   - Privileged secrets and publish permissions are blocked on PR events.

2. **Main Branch & Semantic Release**:
   - Pushes to `main` evaluate commit history using Conventional Commits.
   - Python Semantic Release calculates next SemVer (pre-1.0 zero-version policy: breaking changes increment minor).
   - Python wheels and sdist packages are built and attached to GitHub Releases.

3. **GHCR Multiarch Delivery**:
   - Multiarch images (`linux/amd64,linux/arm64`) are built with Docker Buildx and staged using immutable commit SHAs.
   - Container vulnerability scans run with Trivy (fail-closed on HIGH/CRITICAL CVEs).
   - Provenance (SLSA) and SBOM attestations are attached to each image build.
   - Verified staging digests are promoted to `vX.Y.Z`, `X.Y`, `X`, and `latest` tags on `ghcr.io/diaszano/postgres-mcp`.

## Production Rollback & Emergency Backout Procedure

If regressions, unexpected query rejections, or client incompatibilities emerge in production:

1. **Disable Query Guardrails**:
   Set `DATABASE_QUERY_GUARDRAILS_ENABLED=false` in the server environment. This immediately restores legacy statement behavior without breaking connection pools or dropping security warnings.
2. **Disable Cursor Pagination**:
   Set `DATABASE_PAGINATION_ENABLED=false` if clients have issues consuming continuation tokens.
3. **In-Memory Store Isolation**:
   The cursor cache is strictly in-process and memory-bounded with zero external storage dependencies (no external cache services or broker daemons required). Restarting the container or process cleanly flushes active cursor state without persistent corruption.
4. **Binary / Container Rollback**:
   Re-deploy the previous container tag (e.g. `ghcr.io/diaszano/postgres-mcp:v0.2.0`) or wheel release.
5. **Publish-Only Recovery**:
   If release publication fails midway (e.g., GitHub Release exists but container promotion timed out), trigger `.github/workflows/retry-publish.yml` with the validated release tag to safely republish without bumping versions.
