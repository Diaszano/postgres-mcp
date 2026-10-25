# Continuous Integration Quality Gates Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Replace the inherited CI with required, deterministic PR/main verification and a guarded handoff to delivery.
**Architecture:** One `ci.yml` owns all required checks and invokes the release reusable workflow after success. Integration images are explicitly prepared; extensions needed by required tests must be present or the job fails.
**Tech Stack:** GitHub Actions, uv, Ruff, Pyright, pytest, Docker PostgreSQL 16/17/18
**Spec:** `docs/superpowers/specs/2026-10-25-ci-cd-semantic-release-ghcr-design.md`
## Global Constraints
- Baseline branch: `feature/security-query-pagination`; default release branch: `main`.
- Runtime Python >=3.12; uv is the package manager and `uv.lock` is committed.
- No changes to SQL/MCP runtime or existing pinned `pglast==7.11` except separately reviewed work.
- Package metadata version is unprefixed; public releases use `vX.Y.Z`; image is `ghcr.io/diaszano/postgres-mcp`.
- Use Conventional Commits and Conventional Branch names in English; apply TDD and frequent scoped commits.
- Do not publish to PyPI or Docker Hub; preserve upstream license and attribution.
- On PRs use read-only credentials; no privileged `pull_request_target` builds.
- Release only when gated push to `main` succeeds. PSR version is pinned to 10.7.0 initially.
- Protect history and tags: never force-rewrite a published tag or bypass tests silently.
## Review Focus
Five expected edge conditions; their owning tasks below must include the named regression.
- **README-only PR** (Task 1): Convention validation still executes even if expensive tests are skipped.
- **Required HypoPG missing** (Task 3): Required 16/17 job fails before pytest, no `|| true`.
- **PG18 experimental behavior** (Task 3): Experimental status clearly separated, not greenwashed.
- **Fork PR execution** (Task 4): No publishing token or secret is available.
- **Main CI failure** (Task 4): No reusable release workflow invocation.

---

### Task 1: Install workflow lint and metadata checks
**Files:**
- Create `tests/release/test_ci_workflow.py`
- Create `.github/workflows/ci.yml`
- Modify `pyproject.toml` dev group to include PyYAML test-only if needed

**Interfaces:**
- Consumes: Validator `validate_pr` from Plan 01; top-level default `permissions: contents: read`.
- Produces: `ci.yml` PR and push-main event structure with `conventions` and config validation jobs; deterministic required status name.

- [x] **Step 1: Write failing tests.** `test_ci_triggers_pr_and_main` parses workflow with `yaml.BaseLoader` to avoid YAML 1.1 `on` coercion, asserts `pull_request` and `push.branches == [main]`; `test_pr_jobs_have_read_only_permissions` asserts no `contents: write` or packages write.

```python
from pathlib import Path
import yaml
ci = yaml.load(Path('.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
assert 'pull_request' in ci['on']
assert ci['on']['push']['branches'] == ['main']
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_ci_workflow.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Create CI workflow; use checked-out SHA-pinned actions and `validate_pr` through safe environment variables; validate GitHub workflow YAML with actionlint and unit fixture. Do not delete old workflow yet.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_ci_workflow.py && actionlint .github/workflows/ci.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: add read-only PR validation workflow"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Define deterministic code and artifact gates
**Files:**
- Modify `.github/workflows/ci.yml`
- Create `scripts/ci/check_version.py`
- Create `tests/release/test_release_metadata.py`

**Interfaces:**
- Consumes: Existing justfile `lint`, `typecheck`, unit/performance/release-smoke and Python project 0.3.0.
- Produces: CI jobs `lint`, `typecheck`, `unit`, `package`, `smoke`; `check_package_version(tag: str | None, project_dir: Path) -> None` raises on mismatch.

- [x] **Step 1: Write failing tests.** `test_ci_has_required_gates` validates job names and expected commands; `test_package_metadata_matches_pyproject` builds temporary wheel metadata and compares project version; `test_lock_check_required` asserts locked uv sync and `uv lock --check` present.

```python
from pathlib import Path
ci = Path('.github/workflows/ci.yml').read_text()
assert 'uv lock --check' in ci and 'uv build' in ci
assert 'ruff check .' in ci and 'pyright' in ci
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_release_metadata.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Wire `uv sync --locked --group dev`, Ruff, Pyright, pytest unit/release/performance, uv build and artifact metadata inspection. Supply check_version CLI with `--tag` optional; use GitHub Actions cache keyed by uv.lock.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_release_metadata.py tests/release/test_ci_workflow.py && uv lock --check && uv build`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: gate Python quality and package metadata"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Make database integration reliable
**Files:**
- Modify `.github/workflows/ci.yml`
- Create `scripts/ci/build_hypopg_image.sh`
- Create `tests/release/test_integration_gate.py`
- Modify `tests/integration/conftest.py` only if necessary to require HypoPG for designated tests

**Interfaces:**
- Consumes: Existing CI embedded PostgreSQL Dockerfile with `apt-get ... || true` and `MULTIDB_PG_IMAGE` pytest settings.
- Produces: Fail-fast PG16 and PG17 jobs with confirmed extension; an explicitly experimental PG18 job.

- [x] **Step 1: Write failing tests.** `test_missing_hypopg_fails` runs fake failing package installer and expects nonzero; `test_integration_matrix` expects PG16/17 mandatory and PG18 separately documented; `test_no_swallowed_hypopg_install` asserts no `|| true` in build script.

```python
from pathlib import Path
script = Path('scripts/ci/build_hypopg_image.sh').read_text()
assert 'set -euo pipefail' in script and '|| true' not in script
assert 'hypopg' in script
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_integration_gate.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Move inline Docker build to version-parameterized bash script, `set -euo pipefail`, assert `CREATE EXTENSION hypopg` succeeds and run true integration tests. Document PG18 optional until compatible base/image/extension is demonstrably available.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_integration_gate.py && bash -n scripts/ci/build_hypopg_image.sh && docker info`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: enforce PostgreSQL HypoPG integration prerequisites"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Guard release handoff behind all required jobs
**Files:**
- Modify `.github/workflows/ci.yml`
- Create `tests/release/test_ci_release_gate.py`
- Create temporary `.github/workflows/release.yml` stub with `workflow_call` only (expanded Plan 05)

**Interfaces:**
- Consumes: Checks jobs from Tasks 1-3.
- Produces: Release caller `if: github.event_name == push && github.ref == refs/heads/main`, `needs` all required jobs, `uses: ./.github/workflows/release.yml`.

- [x] **Step 1: Write failing tests.** `test_release_caller_requires_main_and_all_gates` parses YAML and verifies protected ref, event and `needs`; `test_pr_does_not_call_release` rejects publish-capable PR route; `test_release_workflow_is_reusable_only` ensures it cannot trigger independently on branch PR/tag.

```python
from pathlib import Path
ci = Path('.github/workflows/ci.yml').read_text()
assert 'refs/heads/main' in ci and 'workflow/release.yml' in ci
assert 'needs:' in ci
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_ci_release_gate.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Add release calling job to CI, only with required dependencies and least-privileged reusable workflow token scopes; stub must be safe no-op until Plan 05 enables delivery. Retain old workflows temporarily only if disabled from duplicate triggers.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_ci_release_gate.py tests/release/test_ci_workflow.py && actionlint .github/workflows/ci.yml .github/workflows/release.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: gate reusable release after successful main checks"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [x] Every task has its red/green test evidence and a scoped Conventional Commit.
- [x] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results (678 passed in unit, 37 passed in release).
- [x] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [x] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
