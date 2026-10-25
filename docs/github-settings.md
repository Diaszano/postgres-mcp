# GitHub Repository Governance and Settings Guide

This document defines the required GitHub repository configuration, branch rulesets, token permissions, and rollback procedures for maintainers and repository owners.

## 1. Branch Protection & Ruleset for `main`

Configure a GitHub Ruleset or Branch Protection rule targeting the default branch `main`:

- **Require a pull request before merging**:
  - Require at least 1 approval from repository maintainers / CODEOWNERS.
  - Dismiss stale pull request approvals when new commits are pushed.
  - Require conversation resolution before merging.
- **Require status checks to pass before merging**:
  - Require branches to be up to date before merging.
  - Mandatory status checks:
    - `conventions`: PR metadata and repository convention checks
    - `lint`: Ruff linter and code formatting
    - `typecheck`: Pyright strict static typing
    - `unit`: pytest unit test suite
    - `package`: uv build artifact validation
    - `integration`: Fail-fast PostgreSQL 16 & 17 HypoPG integration gate
- **Block Unsafe Git Operations**:
  - Restrict force push (force pushes strictly disabled).
  - Restrict deletions of the default branch.

## 2. Tag Protection for Stable Releases (`v*`)

Configure tag protection rules targeting `refs/tags/v*`:
- Prevent deletions of release tags.
- Prevent force push / tag rewriting.
- Allow creation only via GitHub Actions release workflow (`contents: write`).

## 3. GitHub Actions Token Permissions & Narrow Bypass

- Under **Repository Settings -> Actions -> General -> Workflow permissions**:
  - Default permissions: Read repository contents.
  - Elevated permissions (`contents: write`, `packages: write`, `id-token: write`) are granted only explicitly within the reusable `.github/workflows/release.yml` and `.github/workflows/retry-publish.yml` workflows.
  - Allow GitHub Actions to create and approve pull requests: Disabled.
- Narrow Bypass List:
  - If ruleset enforcement blocks bot pushes to `main`, configure a bypass rule allowing GitHub Actions / `GITHUB_TOKEN` to push commits with messages matching `chore(release): * [skip ci]` and create tags matching `v*`.

## 4. GitHub Container Registry (GHCR) Configuration

- Package visibility: Public.
- Manage Actions access: Ensure `diaszano/postgres-mcp` has Admin / Write access to the `ghcr.io/diaszano/postgres-mcp` package.

## 5. Rollback and Disaster Recovery Procedure

If a published release exhibits critical defects or security regressions:

1. **Rollback Production to Last Known Good Digest**:
   ```bash
   docker pull ghcr.io/diaszano/postgres-mcp@sha256:<known-good-digest>
   ```
2. **Never Force-Push or Delete Published Release Tags**:
   Published tags (`vX.Y.Z`) and GitHub Releases must remain immutable to preserve reproducibility and supply chain trust.
3. **Roll-Forward Fix**:
   Merge a fix commit with `fix:` conventional commit prefix. The release pipeline will automatically produce a new patch version (e.g. `v0.3.1`) and update the stable aliases.
