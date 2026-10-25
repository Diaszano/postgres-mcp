# CI, Release and Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make installation, reproducible builds, ephemeral multi-version PostgreSQL/HypoPG testing, secure container metadata and bilingual usage instructions reliable.

**Architecture:** Keep the current uv project and src layout. Repair scripts, lock checks and CI incrementally with independent gating of tests requiring HypoPG and architecture-specific release smoke checks.

**Tech Stack:** uv, Ruff, Pyright, pytest, GitHub Actions, Docker Buildx, PostgreSQL 16/17/18

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-DX-01/02; AC-05/10/21/23/24

**Dependencies:** Can repair justfile/lock early; update API docs and release gates only after plans 01-06 land.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-05, AC-10, AC-21, AC-23, AC-24 (see parent design for normative definitions).

## File Structure & Ownership

- **Repair developer commands and locked dependencies:** `tests/unit/test_developer_commands.py`.
- **Enforce independent unit and PostgreSQL/HypoPG CI gates:** `tests/integration/test_ci_hypopg_requirement.py`.
- **Fix image metadata and add supply-chain checks:** `tests/unit/test_docker_metadata.py`.
- **Publish EN/pt-BR usage and migration documentation:** `docs/security-deployment.md`, `docs/migration-query-guardrails.md`, `examples/mcp-clients.md`, `tests/unit/test_documentation_contract.py`.
- **Run complete release smoke and rollback checklist:** `tests/release/test_smoke.py`, `docs/release-checklist.md`.

## Review Focus

- **Dependency lock remains consistent with declared ranges after changes** — Task 1.
- **CI cannot go green after skipping HypoPG-required tests** — Task 2.
- **Release image license and upstream credit are accurate** — Task 3.
- **README pt-BR and EN document identical options and guardrail semantics** — Task 4.
- **A released amd64/arm64 image really starts in stdio and guarded HTTP modes** — Task 5.

---

### Task 1: Repair developer commands and locked dependencies

**Files:**
- Modify: `justfile:1-36`
- Modify: `pyproject.toml:1-103`
- Modify: `uv.lock`
- Create: `tests/unit/test_developer_commands.py`

**Interfaces:** Do not claim pglast==7.11 unavailable: uv.lock contains published artifacts; test installation and wheel availability on supported runners first.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_just_commands_reference_real_package` — `just --list` includes lint/typecheck/test-unit/test-integration/build and commands target src/postgres_mcp.
  - `test_lock_matches_pyproject` — `uv lock --check` passes after uv lock update; no unreviewed pglast bump.
  - `test_python_and_ruff_consistency` — ruff target version aligns with Python >=3.12.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_developer_commands.py::test_just_commands_reference_real_package`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Fix outdated crystaldba package paths; add `just lint`, `just typecheck`, `just test-unit`, `just test-integration`, `just build`; regenerate lock only with actual `uv lock` and record environment availability.
- [x] **Step 4: Verify green.** Run ``just --list`; `uv lock --check`; `uv run ruff check .`; `uv run pyright``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "chore: align developer commands and dependency lock"`.

### Task 2: Enforce independent unit and PostgreSQL/HypoPG CI gates

**Files:**
- Modify: `.github/workflows/build.yml:1-51`
- Modify: `tests/integration/conftest.py:15-131`
- Modify: `tests/README.md`, `tests/README.pt-BR.md`
- Create: `tests/integration/test_ci_hypopg_requirement.py`

**Interfaces:** If PG18 image/extension unavailable, mark it pending unsupported and do not advertise PG18 validated or pass it as skipped.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_unit_job_never_requires_docker` — unit tests run without DB daemon.
  - `test_required_hypopg_missing_is_failure` — relevant integration tests fail rather than silently skip on postgres:16 fallback.
  - `test_ci_matrix_executes_pg16_17_18` — matrix per version where reproducible extension image exists, including tests for multi-database revocation + HypoPG.
  - `test_full_ci_fails_on_any_required_job` — branch protection can require lint/typecheck/unit/integration status.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_ci_hypopg_requirement.py::test_unit_job_never_requires_docker`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Split workflow into lint/typecheck/unit/integration jobs; build per-version throwaway PostgreSQL with HypoPG; explicitly gate support for versions whose images cannot be built; provide Docker cleanup.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit`; `uv run pytest -q tests/integration` on each supported matrix environment`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "ci: require PostgreSQL and HypoPG integration checks"`.

### Task 3: Fix image metadata and add supply-chain checks

**Files:**
- Modify: `Dockerfile:25-65`
- Modify: `.github/workflows/docker-build-dockerhub.yml:1-89`
- Create: `tests/unit/test_docker_metadata.py`

**Interfaces:** Repo uses MIT LICENSE while Dockerfile claims Apache-2.0; do not remove original contributor attribution.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_oci_labels_match_project` — license MIT, source fork URL, preserve upstream credits and correct image vendor.
  - `test_nonroot_and_no_uri_logging` — container launches unprivileged; entrypoint logs safe; secrets not in image labels.
  - `test_scan_job_reports_advisories` — dependency/container scans run as CI gates, false positives documented.
  - `test_arm64_amd64_manifest` — buildx manifest and smoke tests validate platforms.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_docker_metadata.py::test_oci_labels_match_project`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Correct OCI labels/license while retaining NOTICE/upstream attribution if required; pin trusted CI actions by reviewed SHA where practical and add dependency/image scanning and minimum permissions.
- [x] **Step 4: Verify green.** Run ``docker build -t postgres-mcp:test .`; inspect OCI labels; run CI scan and buildx smoke checks`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "build: harden multi-architecture Docker release"`.

### Task 4: Publish EN/pt-BR usage and migration documentation

**Files:**
- Modify: `README.md`
- Modify: `README.pt-BR.md`
- Modify: `tests/README.md`, `tests/README.pt-BR.md`
- Create: `docs/security-deployment.md`
- Create: `docs/migration-query-guardrails.md`
- Create: `examples/mcp-clients.md`
- Create: `tests/unit/test_documentation_contract.py`

**Interfaces:** Document `DATABASE_QUERY_GUARDRAILS_ENABLED=false` legacy compatibility during rollout and production profile enablement.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_documented_env_keys_match_parser` — extract env examples and compare with parser-used configuration; no stale key names.
  - `test_client_samples_have_no_secrets` — Claude Code, Codex, OpenCode snippets refer to env variables only.
  - `test_versioned_contract_examples` — max_rows, timeout_seconds, pagination, fetch_query_page, stale/unknown page and best-effort consistency documented.
  - `test_english_portuguese_parity` — both readmes explain same defaults/rollout/limits and no snapshot promises.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_documentation_contract.py::test_documented_env_keys_match_parser`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Write deployment/release notes: guardrail migration flag, old access modes, HTTP auth+TLS, SQL policy, pool lease vs physical session vs opaque cursor, 300s TTL/5000 total rows, at-most-once cursor usage.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_documentation_contract.py` (create the named checker as part of this task); README links validated`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "docs: document query budgets and cursor pagination"`.

### Task 5: Run complete release smoke and rollback checklist

**Files:**
- Create: `tests/release/test_smoke.py`
- Create: `docs/release-checklist.md`
- Modify: `.github/workflows/docker-build-dockerhub.yml`

**Interfaces:** Smoke test commands must point at disposable DB and avoid publishing artifacts or pushing tags without explicit approval.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_stdio_mcp_initialize` — released wheel/container accepts initialize and returns registered tools.
  - `test_http_anonymous_denied` — remote HTTP rejects anonymous access; authenticated ingress succeeds.
  - `test_example_pagination` — single successful first+continuation call against ephemeral fixture.
  - `test_release_metadata_and_rollback` — version/tags/doc migration/backout steps consistent, no stale redis dependency.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/release/test_smoke.py::test_stdio_mcp_initialize`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Create `just release-smoke` recipe calling test suite against built wheel and Docker image; add rollback procedure that disables paging/guardrails safely without hiding security warnings.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/release/test_smoke.py`; `uv build`; `docker build ...`; `uv lock --check``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "ci: require package and image release smoke tests"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
