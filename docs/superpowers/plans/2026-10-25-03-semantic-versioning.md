# Python Semantic Release and uv Synchronization Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Compute vX.Y.Z automatically from conventional commits and create consistent Python release artifacts without dependency drift.
**Architecture:** PSR 10.7.0 runs as a pinned tool on the same runner as uv; project version is stamped in pyproject.toml, synchronized into uv.lock during build, and packaged once. Local isolated-git tests verify version progression without remote pushes.
**Tech Stack:** Python Semantic Release 10.7.0, uv, TOML, Git, pytest
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
- **Pre-v1 behavior** (Task 1): Explicit allow_zero_version and major_on_zero prevent accidental 1.0.0.
- **No semantic commit** (Task 2): PSR does not create a new tag or release.
- **Existing tag v0.3.0** (Task 4): Bootstrap tests do not retag or rewrite it.
- **Release commit loops** (Task 2): Generated chore(release) is ignored.
- **Unrelated uv dependency changes** (Task 3): Lock drift guard fails and never stages extra bumps.

---

### Task 1: Configure Semantic Release without publishing
**Files:**
- Modify `pyproject.toml`
- Create `tests/release/test_semantic_release_config.py`
- Modify `justfile` to add `release-preview` only

**Interfaces:**
- Consumes: Existing `[project].version=0.3.0`, upstream history/tags; `uv.lock`.
- Produces: PSR settings `commit_parser=conventional`, `version_toml=["pyproject.toml:project.version"]`, `tag_format="v{version}"`, `allow_zero_version=true`, `major_on_zero=false`, `commit_message="chore(release): {version} [skip ci]"`.

- [x] **Step 1: Write failing tests.** `test_psr_contract` loads toml and verifies exact fields and main branch; `test_no_manual_tagging` rejects commands in justfile that run `git tag` or `gh release create`.

```python
import tomllib
with open('pyproject.toml', 'rb') as f:
    cfg = tomllib.load(f)['tool']['semantic_release']
assert cfg['allow_zero_version'] is True
assert cfg['major_on_zero'] is False
assert cfg['tag_format'] == 'v{version}'
assert cfg['commit_parser'] == 'conventional'
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_semantic_release_config.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Pin PSR version 10.7.0 in release installation/preview and configure `[tool.semantic_release]`, `[tool.semantic_release.branches.main]` (match regex `^main$`); document v0 breaking maps to next minor.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_semantic_release_config.py && uv tool run --from python-semantic-release==10.7.0 semantic-release --help`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "build(release): configure semantic version policy"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Test commit semantics in isolated Git histories
**Files:**
- Create `tests/release/test_semantic_version_calculation.py`
- Create `scripts/ci/validate_release.py`

**Interfaces:**
- Consumes: PSR configuration and a temporary Git repository fixture.
- Produces: `validate_release_tag(tag: str, project_version: str) -> None` with strict SemVer; CLI `release-preview` dry-run output; integration fixtures for git history.

- [x] **Step 1: Write failing tests.** Tests build temporary Git repos with seed tag and commits `fix`, `feat`, `feat!`, `docs`, generated `chore(release)` and assert expected next versions/no-op; reject `v0.3`, `v0.3.0rc1` for stable release; reject untrusted arbitrary tag.

```python
from scripts.ci.validate_release import validate_release_tag
validate_release_tag('v0.3.1', '0.3.1')
import pytest
with pytest.raises(ValueError):
    validate_release_tag('v0.3.1rc1', '0.3.1')
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_semantic_version_calculation.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Create pure tag parser/metadata guard, add test fixture that invokes PSR in no-push/dry-run mode; never create GitHub releases or hit the network from test. If dry-run PSR CLI output varies, assert parsed reported version using official documented options.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_semantic_version_calculation.py && uv run pytest -q tests/release/test_semantic_release_config.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "test(release): verify conventional commit version bumps"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Keep uv.lock in sync and build immutable assets
**Files:**
- Create `scripts/release/build.sh`
- Modify `pyproject.toml` `build_command`
- Extend `tests/release/test_release_metadata.py`
- Create `tests/release/test_release_build.py`

**Interfaces:**
- Consumes: PSR build_command environment `$PACKAGE_NAME` and installed pinned uv binary.
- Produces: `scripts/release/build.sh` with `set -euo pipefail`, `uv lock --upgrade-package "$PACKAGE_NAME"`, `git add uv.lock`, `uv lock --check`, `uv build`; `build_command = "bash scripts/release/build.sh"`.

- [x] **Step 1: Write failing tests.** `test_lock_only_changes_project_version` compares before/after resolved dependency package/version tuples; `test_build_fails_on_bad_uv_lock` uses injected fake uv; `test_build_artifact_version` reads wheel METADATA and sdist PKG-INFO after a disposable version stamp.

```python
from pathlib import Path
script = Path('scripts/release/build.sh').read_text()
assert 'uv lock --upgrade-package "$PACKAGE_NAME"' in script
assert 'git add uv.lock' in script and 'uv build' in script
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_release_metadata.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Use fail-fast shell, stage uv.lock after refresh, constrain root package upgrade and detect any unrelated resolved dependency churn; verify artifacts match stamped version; ensure `pglast==7.11` untouched.
- [x] **Step 4: Confirm green.** Run: `bash -n scripts/release/build.sh && uv run pytest -q tests/release/test_release_build.py && uv lock --check && uv build`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "build(release): synchronize locked dependencies and package assets"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Bootstrap existing version/tag and define idempotent release identity
**Files:**
- Create `tests/release/test_release_bootstrap.py`
- Extend `scripts/ci/validate_release.py`
- Update `justfile` preview docs

**Interfaces:**
- Consumes: Remote git tags ancestry, starting project version 0.3.0.
- Produces: `validate_release_baseline(project_version: str, reachable_tags: list[str]) -> None`; `assert_tag_matches_commit(tag: str, sha: str) -> None` and no-retag checks.

- [x] **Step 1: Write failing tests.** `test_duplicate_tag_fails`, `test_missing_baseline_requires_explicit_bootstrap`, `test_wrong_release_sha_fails`, `test_repeat_on_same_head_is_noop`; explicitly test freshly initialized repo and existing reachable tag with differing version.

```python
import pytest
from scripts.ci.validate_release import validate_release_baseline
with pytest.raises(ValueError):
    validate_release_baseline('0.3.0', ['v0.3.0', 'v0.3.0'])
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_release_bootstrap.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Document an owner-reviewed one-time bootstrap of reachable stable tags; determine last release from ancestry; no auto-rewrite; enable release only once preflight passes on a throwaway fork.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_release_bootstrap.py tests/release/test_semantic_version_calculation.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "fix(release): validate existing tags before automated bootstrap"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [x] Every task has its red/green test evidence and a scoped Conventional Commit.
- [x] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results (678 passed in unit, 53 passed in release).
- [x] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [x] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
