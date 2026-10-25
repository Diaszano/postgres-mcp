# Repository Conventions and Contribution Governance Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Establish predictable contribution files and commit/branch validation without changing release behavior.
**Architecture:** Use files under `.github/` for PR metadata, templates and ownership; keep repo-wide format conventions small. Add lightweight deterministic validators exercised by pytest before connecting them to the CI workflow.
**Tech Stack:** Python 3.12, uv, pytest, GitHub Actions, standard Markdown/YAML
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
- **Fork PRs and Dependabot branches** (Task 2): Automation branch exception is explicit; it never gets release permissions.
- **A Conventional Commit breaking indicator** (Task 2): `feat(api)!: ...` is accepted.
- **Malformed YAML in templates** (Task 1): Workflow/templates parser fails fast.
- **Original authors/license** (Task 3): LICENSE and upstream credit remain intact.
- **Untrusted PR-controlled title** (Task 2): Use as data only, never interpolate into shell.

---

### Task 1: Create project style and build-context conventions
**Files:**
- Create `.editorconfig`, `.gitattributes`, `.dockerignore`
- Modify `.gitignore` only for missing generated artifacts
- Create `tests/release/test_repository_conventions.py`

**Interfaces:**
- Consumes: Existing Dockerfile copies the repository and requires `uv.lock`, `pyproject.toml`, `src/` and `docker-entrypoint.sh`.
- Produces: Ignore and newline policies; `test_docker_context_keeps_runtime_inputs()` and `test_no_secrets_in_image_context()`.

- [x] **Step 1: Write failing tests.** `test_docker_context_keeps_runtime_inputs` checks `.dockerignore` does not exclude `uv.lock`, `pyproject.toml`, `src`, or `docker-entrypoint.sh`; `test_no_secrets_in_image_context` confirms `.env*`, `.git`, `.venv`, `dist` are excluded, with a documented allowlist for examples.

```python
from pathlib import Path
ignore = Path('.dockerignore').read_text()
assert '.git' in ignore and '.venv' in ignore and 'dist' in ignore
assert 'uv.lock' not in ignore and 'pyproject.toml' not in ignore
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_repository_conventions.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Create minimal `.editorconfig` with UTF-8/LF, Python 4-space indent, Markdown whitespace exception and Make/just shell preservation; configure `.gitattributes` text eol normalization and `.dockerignore` with targeted exclusions.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_repository_conventions.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "chore(repo): standardize formatting and Docker build context"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Add PR title and branch validators
**Files:**
- Create `scripts/ci/check_pr_metadata.py`
- Create `tests/release/test_pr_metadata.py`
- Create `.github/PULL_REQUEST_TEMPLATE.md`
- Create `.github/ISSUE_TEMPLATE/bug_report.yml` and `.github/ISSUE_TEMPLATE/feature_request.yml`

**Interfaces:**
- Consumes: Pull request title and source branch name from GitHub context; no secrets.
- Produces: `validate_pr(title: str, head_ref: str, actor: str) -> list[str]` returning human-readable validation errors and CLI nonzero exit on errors.

- [x] **Step 1: Write failing tests.** Parameterize `validate_pr`: accept `feat(api)!: add policy`, `fix: correct ttl` with `feature/foo`/`bugfix/foo`; reject `update stuff`, `foo bar`; accept `dependabot/...` only for permitted bot actor; shell-looking title is treated as literal input.

```python
from scripts.ci.check_pr_metadata import validate_pr
assert validate_pr('feat(api)!: add policy', 'feature/policy', 'Diaszano') == []
assert validate_pr('update things', 'feature/policy', 'Diaszano')
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_pr_metadata.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Create pure Python validation from approved Conventional Commit title pattern (`feat|fix|docs|test|ci|build|perf|refactor|chore|revert` plus scope and `!`) and Conventional Branch category pattern. `--title`, `--head-ref`, `--actor` are CLI args, but in workflow prefer `env:` not shell string interpolation.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_pr_metadata.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: validate conventional pull request metadata"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Define code ownership and responsible upstream attribution
**Files:**
- Create `.github/CODEOWNERS`
- Create `CONTRIBUTING.md`
- Create `NOTICE.md`
- Create `tests/release/test_repository_governance.py`

**Interfaces:**
- Consumes: GitHub owner `@Diaszano`, existing `LICENSE`, original PyPI/project attribution.
- Produces: Documented maintainer review responsibilities; file-based owner policy and credits.

- [x] **Step 1: Write failing tests.** `test_workflow_codeowners` requires owners for `.github/workflows/`, `scripts/ci/`, `pyproject.toml`; `test_upstream_credit_preserved` verifies LICENSE text not replaced and NOTICE identifies original project.

```python
from pathlib import Path
owners = Path('.github/CODEOWNERS').read_text()
assert '.github/workflows/' in owners and '@Diaszano' in owners
assert 'Crystal Corp.' in Path('LICENSE').read_text()
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_repository_governance.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Write `.github/CODEOWNERS` assigning sensitive paths to `@Diaszano`; define English contribution, Conventional Commit, squash merge, branch naming and review checklist in CONTRIBUTING; preserve MIT copyright and upstream origin in NOTICE.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_repository_governance.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "docs: document contribution rules and upstream attribution"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Add bot-managed dependency updates
**Files:**
- Create `.github/dependabot.yml`
- Create `tests/release/test_dependabot_config.py`
- Update `CONTRIBUTING.md`

**Interfaces:**
- Consumes: `uv.lock`, GitHub Actions and Dockerfile as update ecosystems.
- Produces: Weekly uv, github-actions and docker dependency PR schedules, caps/group policy.

- [x] **Step 1: Write failing tests.** `test_dependabot_uses_uv_ecosystem` parses YAML and expects uv `/`, github-actions `/` and docker `/`; `test_dependabot_open_pr_limit` prevents unbounded update PRs.

```python
from pathlib import Path
import yaml
config = yaml.load(Path('.github/dependabot.yml').read_text(), Loader=yaml.BaseLoader)
ecosystems = {item['package-ecosystem'] for item in config['updates']}
assert {'uv', 'github-actions', 'docker'} <= ecosystems
```
- [x] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_dependabot_config.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [x] **Step 3: Implement.** Configure `package-ecosystem: uv` (not pip), github-actions and docker weekly; tune groups and open-pull-requests-limit; require tests and human review for updates.
- [x] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_dependabot_config.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [x] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "build: automate dependency update pull requests"`.
- [x] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [x] Every task has its red/green test evidence and a scoped Conventional Commit.
- [x] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results (678 passed in unit, 27 passed in release).
- [x] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [x] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
