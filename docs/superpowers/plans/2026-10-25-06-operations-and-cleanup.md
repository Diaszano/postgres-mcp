# Release Operations, Documentation and Repository Cleanup Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Make automated delivery safe for maintainers to operate, audit and roll back without manual version edits.
**Architecture:** Document operational choices and reflect the new provenance and release policy in READMEs, smoke tests and just recipes. Keep migration checks explicit, leaving GitHub administrative settings for owner review.
**Tech Stack:** Markdown, just, pytest, GitHub Releases, GHCR, uv
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
- **No GHCR image on release tag** (Task 1): Ops guide says partial publish, not successful rollout.
- **`latest` changes unexpectedly** (Task 2): Rollback recommends immutable tag/digest.
- **Existing upstream badges point to original project** (Task 3): Preserve upstream attribution but update fork-owned links.
- **Version in release checklist hardcoded** (Task 1): Current version obtained dynamically.
- **GitHub branch protection blocks release commit** (Task 2): Checklist explains narrow bypass and fallback.

---

### Task 1: Rewrite automated release checklist and guide
**Files:**
- Modify `docs/release-checklist.md`
- Create `docs/ci-cd.md`
- Create `tests/release/test_release_docs.py`

**Interfaces:**
- Consumes: PSR/GHCR graph, actual version in pyproject, repository settings.
- Produces: Version-agnostic checklist and step-by-step publication, incident and recovery docs.

- [ ] **Step 1: Write failing tests.** `test_checklist_no_hardcoded_version`, `test_guide_documents_uv_lock_and_tag`, `test_guide_documents_partial_release_recovery`, `test_guide_has_ghcr_pull_by_digest`.

```python
from pathlib import Path
checklist = Path('docs/release-checklist.md').read_text()
assert 'Release Version: `0.3.0`' not in checklist
assert 'ghcr.io/diaszano/postgres-mcp' in Path('docs/ci-cd.md').read_text()
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_release_docs.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Explain exact PR/main gates, release trigger examples, GHCR tag format, image digest verification, failures, PSR bootstrap, GHCR package visibility, maintainers’ responsibilities, first release decision and rollback.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_release_docs.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "docs(release): document automated release and recovery"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Document required GitHub owner settings and rollback
**Files:**
- Create `docs/github-settings.md`
- Modify `SECURITY.md`
- Create `tests/release/test_github_settings.py`

**Interfaces:**
- Consumes: GitHub current owner permissions; requirements for main PR protection, tags and package push.
- Produces: Owner-only configuration checklist for rulesets and GHCR: statuses, merge policy, narrow bypass, secrets, visibility.

- [ ] **Step 1: Write failing tests.** `test_settings_require_main_protection`, `test_settings_document_release_bot_push_permission`, `test_settings_restrict_force_tag_and_fork_secrets`, `test_rollback_by_digest_documented`.

```python
from pathlib import Path
settings = Path('docs/github-settings.md').read_text().lower()
assert 'branch protection' in settings or 'ruleset' in settings
assert 'github_token' in settings and 'tag' in settings
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_github_settings.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Document UI steps to require stable named checks, restrict pushes to main, protect `v*`, enforce squash/title policy, permit bot version bump narrowly (or GitHub App), choose `GITHUB_TOKEN` permissions, configure GHCR visibility/access; document override approval and rollback.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_github_settings.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "docs: record GitHub governance and rollback procedure"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Update READMEs and attribution without renaming package
**Files:**
- Modify `README.md` and `README.pt-BR.md`
- Modify `Dockerfile` OCI metadata
- Modify `justfile`
- Extend `tests/release/test_repository_governance.py`

**Interfaces:**
- Consumes: Fork and upstream links, current `postgres-mcp` Python packaging.
- Produces: Fork GHCR usage, build badges, accurate OCI repo source, current install examples and upstream credit.

- [ ] **Step 1: Write failing tests.** `test_readme_ghcr_commands_match_image`, `test_no_crystaldba_publish_target`, `test_docker_source_label_is_fork`, `test_license_copyright_preserved`, `test_justfile_has_no_manual_release`.

```python
from pathlib import Path
readme = Path('README.md').read_text()
assert 'ghcr.io/diaszano/postgres-mcp' in readme
assert 'Crystal Corp.' in Path('LICENSE').read_text()
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_repository_governance.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Change fork-specific install/pull commands, workflow badges and OCI source/vendor where appropriate; retain factual upstream credit and existing MIT LICENSE text; remove manual `just release` commands while preserving `lint`, `typecheck`, `release-smoke`, etc.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_repository_governance.py && uv run pytest -q tests/release/test_release_docs.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "docs: align fork documentation with automated GHCR releases"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Whole-delivery verification and handoff
**Files:**
- Update `docs/ci-cd.md` final verification section
- Extend `tests/release/test_smoke.py` or create `tests/release/test_cd_smoke.py`

**Interfaces:**
- Consumes: All 6 plans and unchanged app security/pagination tests.
- Produces: One recorded reproducible release gate and a reviewed handoff checklist.

- [ ] **Step 1: Write failing tests.** `test_cd_smoke` checks all expected workflows and docs exist, PSR/lock invariants, forks do not publish and no old DockerHub workflow remains; simulate no-op and failed scan.

```python
from pathlib import Path
workflows = Path('.github/workflows')
assert (workflows/'ci.yml').is_file()
assert (workflows/'release.yml').is_file()
assert not (workflows/'docker-build-dockerhub.yml').exists()
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_smoke.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Run final `uv lock --check`, Ruff, Pyright, unit, release, performance, Docker-backed integration PG16/17, `uv build`, actionlint, shellcheck and security scan. Verify no unexpected pglast/runtime changes; create PR with checklist and await GitHub owner rule changes before activating release.
- [ ] **Step 4: Confirm green.** Run: `uv lock --check && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q tests/unit tests/release && uv run pytest -q tests/performance --run-performance && uv build && actionlint .github/workflows/*.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "test(ci): verify automated delivery contracts end to end"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [ ] Every task has its red/green test evidence and a scoped Conventional Commit.
- [ ] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results.
- [ ] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [ ] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
