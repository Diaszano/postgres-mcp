# Physical Session Affinity for HypoPG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure HypoPG index creation, inspection, EXPLAIN and cleanup use one physical PostgreSQL session per tuning operation without pinning sessions across MCP requests.

**Architecture:** Keep pool leases in DatabaseRegistry. Create a short-lived physical session abstraction that wraps one checked-out connection, owns transaction state, and supplies a session-bound SqlDriver to existing tuning components.

**Tech Stack:** Python asyncio, psycopg AsyncConnectionPool, HypoPG, pytest-asyncio, Docker PostgreSQL

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-SES-01/02/03; AC-19/20/21

**Dependencies:** Plan 01 SQL/security policy baseline. Can run after plan 02, but must land before production pagination performance testing.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-19, AC-20, AC-21 (see parent design for normative definitions).

## File Structure & Ownership

- **Characterize existing HypoPG session behavior:** `tests/integration/test_hypopg_session_baseline.py`.
- **Introduce short-lived session-bound driver:** `src/postgres_mcp/sql/database_session.py`, `tests/unit/sql/test_database_session.py`.
- **Refactor hypothetical-index EXPLAIN to session scope:** `tests/unit/explain/test_hypopg_affinity.py`.
- **Pin tuning advisor session and prove real isolation:** `tests/integration/test_hypopg_tuning_sessions.py`.

## Review Focus

- **Pool lease does not imply one physical connection** — Tasks 1 and 2.
- **HypoPG create -> EXPLAIN -> reset is isolated under concurrent calls** — Task 4.
- **Cancellation leaves no session-state residue or checked-out connection** — Tasks 2 and 4.
- **Restricted transaction and HypoPG behavior cooperate** — Task 3.
- **Unavailable target DB never causes fallback to default DB** — Task 1.

---

### Task 1: Characterize existing HypoPG session behavior

**Files:**
- Create: `tests/integration/test_hypopg_session_baseline.py`
- Modify: `tests/integration/conftest.py:15-130`
- Modify: `tests/README.md`

**Interfaces:** Intentional characterization red test may remain failing until Tasks 2-3; commit fixture characterization only if stable and explicitly marked expected failure.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_hypopg_visibility_is_session_local` — two distinct psycopg connections: hypothetical index from connection A invisible in connection B.
  - `test_tuning_flow_requires_single_backend_pid` — record `pg_backend_pid()` across create/list/explain/reset and prove mismatch potential with pooled independent calls.
  - `test_hypopg_image_is_mandatory` — fail test setup if HypoPG fixture unavailable, never skip.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_hypopg_session_baseline.py::test_hypopg_visibility_is_session_local`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Create mandatory extension fixture using current postgres-hypopg image build path and least-privilege test role; do not edit application code until baseline is captured.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/integration/test_hypopg_session_baseline.py` (record known-red until fixed)`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "test: characterize HypoPG session locality"`.

### Task 2: Introduce short-lived session-bound driver

**Files:**
- Create: `src/postgres_mcp/sql/database_session.py`
- Modify: `src/postgres_mcp/sql/sql_driver.py:158-288`
- Modify: `src/postgres_mcp/sql/database_registry.py:113-152`
- Create: `tests/unit/sql/test_database_session.py`

**Interfaces:** Use existing registry.acquire(db) to hold pool lease; checkout `AsyncConnectionPool.connection()` once; session-scoped SQL driver shares it. For legacy mode use bootstrap pool.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_one_backend_connection_for_multiple_commands` — fake pool tracks one checkout across multiple execute_query calls.
  - `test_session_owns_transaction_boundary` — nested calls do not BEGIN/COMMIT independently and restricted session remains READ ONLY.
  - `test_release_on_error_cancel_shutdown` — rollback/reset/checkin occurs on success, failure and cancellation.
  - `test_registry_lease_outlives_physical_session` — pool LRU cannot close while session is active; no nested checkout or deadlock.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/sql/test_database_session.py::test_one_backend_connection_for_multiple_commands`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `@asynccontextmanager async def database_session(database: str | None, *, restricted: bool) -> AsyncIterator[SqlDriver]` at an adapter layer; add `SqlDriver` option for externally-owned transactions to avoid its current per-query COMMIT/ROLLBACK.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/sql/test_database_session.py tests/unit/sql/test_sql_driver.py tests/unit/sql/test_database_registry.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: add transaction-scoped PostgreSQL sessions"`.

### Task 3: Refactor hypothetical-index EXPLAIN to session scope

**Files:**
- Modify: `src/postgres_mcp/explain/explain_plan.py:83-242`
- Modify: `src/postgres_mcp/server.py:401-488`
- Create: `tests/unit/explain/test_hypopg_affinity.py`

**Interfaces:** Do not create physical indexes. Prove error handling when `hypopg_reset` also fails.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_explain_hypopg_uses_one_bound_driver` — record calls to reset/create/explain on same driver and connection.
  - `test_reset_runs_in_finally` — interrupted EXPLAIN invokes hypopg_reset then rollback/release.
  - `test_analyze_hypopg_combination_remains_rejected` — current explicit analyze+indexes restriction preserved.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/explain/test_hypopg_affinity.py::test_explain_hypopg_uses_one_bound_driver`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Make `ExplainPlanTool` accept a session-bound driver for hypothetical indexes; split compound `SELECT hypopg_reset();...;EXPLAIN` into discrete calls on same session; preserve public explain_query signature.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/explain/test_hypopg_affinity.py tests/unit/explain/test_server_integration.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: pin hypothetical EXPLAIN to one PostgreSQL session"`.

### Task 4: Pin tuning advisor session and prove real isolation

**Files:**
- Modify: `src/postgres_mcp/index/dta_calc.py:128-190`
- Modify: `src/postgres_mcp/index/index_opt_base.py:210-290`
- Modify: `src/postgres_mcp/server.py:507-568`
- Create: `tests/integration/test_hypopg_tuning_sessions.py`

**Interfaces:** Existing unit mocks may require explicit session factories; keep their names/signatures stable.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_tuning_sequence_uses_single_backend_pid` — real HypoPG image records same backend PID for create/list/explain/reset.
  - `test_parallel_tuning_does_not_share_hypopg_indexes` — two concurrent operations on one DB independent even with pool_max_size=2.
  - `test_cross_db_isolation` — two DBs with different schema only see their own hypothetical objects.
  - `test_cleanup_after_cancel_and_error` — no leftovers in subsequent session; pool continues responding.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_hypopg_tuning_sessions.py::test_tuning_sequence_uses_single_backend_pid`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Pass one bound SQL session through entire DTA workload lifecycle, not a fresh SqlDriver per nested operation; ensure reset and transaction cleanup `finally` on all exits.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/integration/test_hypopg_tuning_sessions.py tests/integration/test_multi_database_integration.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: isolate HypoPG tuning across concurrent analyses"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
