# AI-Controlled Query Budgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add request-level row/time bounds enforced by administrator ceilings and bounded-memory/byte results, while keeping legacy behavior behind an explicit rollout flag.

**Architecture:** Introduce a minimal QueryExecutionService behind execute_sql, with validated budget policy, concurrency admission before database leases, scoped PostgreSQL timeouts, and streaming bounded serializer.

**Tech Stack:** Python 3.12, asyncio, psycopg 3, Pydantic, pytest, Docker PostgreSQL

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-QRY-01/02/03/04; FR-ARCH-01 (minimal service); AC-02/06/07/08/10

**Dependencies:** Plan 01 safe error taxonomy; no dependence on pagination or session-affinity implementation.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-02, AC-06, AC-07, AC-08, AC-10 (see parent design for normative definitions).

## File Structure & Ownership

- **Parse and validate administrator guardrail settings:** `src/postgres_mcp/query_limits/config.py`, `tests/unit/query_limits/test_config.py`.
- **Resolve strictly typed agent budget overrides:** `src/postgres_mcp/query_limits/policy.py`, `tests/unit/query_limits/test_policy.py`.
- **Bound concurrency and install scoped PostgreSQL timeouts:** `src/postgres_mcp/query_limits/admission.py`, `tests/unit/query_limits/test_admission.py`, `tests/integration/test_query_timeouts.py`.
- **Fetch bounded rows and JSON bytes without `fetchall`:** `src/postgres_mcp/query_limits/results.py`, `tests/unit/query_limits/test_results.py`, `tests/integration/test_large_results.py`.
- **Wire QueryExecutionService behind existing MCP tool:** `src/postgres_mcp/application/query_service.py`, `tests/unit/test_query_service.py`.
- **Exercise cancellation, shutdown and error boundaries:** `tests/integration/test_query_budget_lifecycle.py`.

## Review Focus

- **Boolean `true` is never accepted as integer `max_rows=1`** — Task 2.
- **A single huge multibyte UTF-8 row cannot force invalid JSON or oversized responses** — Task 4.
- **Cancellation and timeout return a pool connection in clean state** — Tasks 3 and 6.
- **Queue saturation does not reserve a DB pool lease while waiting** — Task 3.
- **Legacy no-argument SQL behavior remains until guardrails are enabled** — Task 5.

---

### Task 1: Parse and validate administrator guardrail settings

**Files:**
- Create: `src/postgres_mcp/query_limits/config.py`
- Create: `tests/unit/query_limits/test_config.py`
- Modify: `src/postgres_mcp/server.py:689-707`
- Modify: `README.md`, `README.pt-BR.md`

**Interfaces:** Fields: `enabled`, `default_max_rows`, `hard_max_rows`, `default_timeout_seconds`, `hard_timeout_seconds`, `max_result_bytes`, `max_concurrency`.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_query_guardrails_defaults` — flag defaults false during migration; defaults rows=200/hard=5000, timeout=15/hard=60, bytes=2097152, concurrency=4.
  - `test_bad_query_budget_env_fails_closed` — noninteger, booleans, <=0, default>hard, impractical byte setting raise sanitized ValueError.
  - `test_disabled_mode_warning_on_remote` — disabled guardrails flag emits unsafe deployment warning; never logs secrets.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/query_limits/test_config.py::test_query_guardrails_defaults`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement frozen `QueryBudgetConfig` and `parse_query_budget_config(env: Mapping[str,str]) -> QueryBudgetConfig`; use strict positive integer and consistent bounds; guard against overflow/unreasonably large values.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/query_limits/test_config.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: validate SQL budget configuration"`.

### Task 2: Resolve strictly typed agent budget overrides

**Files:**
- Create: `src/postgres_mcp/query_limits/policy.py`
- Create: `tests/unit/query_limits/test_policy.py`
- Modify: `src/postgres_mcp/server.py:491-505`

**Interfaces:** Reject instead of silently clamping agent values. Public execute_sql args appended after `database`.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_agent_override_within_ceilings` — max_rows=1000 and timeout_seconds=20 accepted; omissions use defaults.
  - `test_hard_limits_rejected_before_checkout` — 5001 or 61 raises `LIMIT_EXCEEDED` and never calls get_sql_driver.
  - `test_bool_zero_negative_float_and_text_rejected` — values such as true/0/-1/1.2/"100" rejected `INVALID_QUERY_OPTIONS` without implicit Pydantic coercion.
  - `test_disabled_guardrails_reject_explicit_override` — legacy calls unchanged; explicit budget when flag disabled gets clear configuration error.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/query_limits/test_policy.py::test_agent_override_within_ceilings`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement frozen `QueryLimits(max_rows: int, timeout_seconds: int)` and `resolve_query_limits(config: QueryBudgetConfig, max_rows: object, timeout_seconds: object) -> QueryLimits`; validate before any I/O.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/query_limits/test_policy.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: support safe per-call query limits"`.

### Task 3: Bound concurrency and install scoped PostgreSQL timeouts

**Files:**
- Create: `src/postgres_mcp/query_limits/admission.py`
- Modify: `src/postgres_mcp/sql/sql_driver.py:217-288`
- Create: `tests/unit/query_limits/test_admission.py`
- Create: `tests/integration/test_query_timeouts.py`

**Interfaces:** Acquire semaphore before entering registry lease; remaining time applies to checkout/execution/serialization. Bounded wait policy must be recorded in tests, default at most remaining deadline.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_admission_before_pool_lease` — 5th call at max_concurrency=4 fails bounded wait without acquiring registry slot.
  - `test_statement_timeout_is_transaction_local` — query checks `SHOW statement_timeout` inside operation and next checkout sees original value.
  - `test_server_deadline_cancels_slow_statement` — pg_sleep beyond 15/short fixture deadline maps QUERY_TIMEOUT; transaction is rolled back.
  - `test_cancelled_waiter_does_not_leak_semaphore` — cancelled pending task allows later work.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/query_limits/test_admission.py::test_admission_before_pool_lease`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `QueryAdmission.run(operation: Callable[[], Awaitable[T]], timeout_seconds: int) -> T` using semaphore and monotonic deadline; add transaction-local statement_timeout via parameter-safe setting and robust cleanup. Never `SET` unscoped timeout in pooled connections.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/query_limits/test_admission.py` then `uv run pytest -q tests/integration/test_query_timeouts.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: enforce SQL execution deadlines and concurrency"`.

### Task 4: Fetch bounded rows and JSON bytes without `fetchall`

**Files:**
- Create: `src/postgres_mcp/query_limits/results.py`
- Modify: `src/postgres_mcp/sql/sql_driver.py:237-288`
- Create: `tests/unit/query_limits/test_results.py`
- Create: `tests/integration/test_large_results.py`

**Interfaces:** `fetchmany()` or async iteration over psycopg cursor; one-row lookahead only when safe for row-yielding statements. Preserve multi-statement unrestricted legacy behavior when guardrails disabled.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_large_query_fetches_bounded_rows` — 1 million logical rows but 200 cap fetches at most 201 with lookahead, never `fetchall`.
  - `test_utf8_and_metadata_included_in_byte_budget` — result including metadata, accents/emoji and 2MiB ceiling stays within exact UTF-8 budget.
  - `test_first_row_too_big_is_typed_error` — raises RESULT_TOO_LARGE without half-valid JSON.
  - `test_truncation_is_explicit` — 200 of >200 -> truncated true; known more rows; equality at exactly 200 without more -> truncated false.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/query_limits/test_results.py::test_large_query_fetches_bounded_rows`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `BoundedQueryResult(rows, returned_rows, truncated, limit_reached, execution_time_ms, timeout_seconds)` and async bounded cursor reader with chunking plus serializer-aware `encode_bounded_result(...) -> bytes`; cap metadata/warnings as well as rows.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/query_limits/test_results.py` then `uv run pytest -q tests/integration/test_large_results.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: cap SQL row and response payload size"`.

### Task 5: Wire QueryExecutionService behind existing MCP tool

**Files:**
- Create: `src/postgres_mcp/application/query_service.py`
- Modify: `src/postgres_mcp/server.py:491-505,643-762`
- Create: `tests/unit/test_query_service.py`
- Modify: `tests/unit/test_multidb_server.py`

**Interfaces:** `page_size` and `pagination` appear as future optional interface but only `none` supported until plan 04; reject non-none rather than silently ignore. IMPORTANT: existing `execute_sql.sql` default is the string `all`; preserve that default and its optional schema even if the spec example shows a required str.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_execute_sql_schema_adds_optional_args` — max_rows/timeout_seconds optional and prior signature defaults/positions intact.
  - `test_guarded_small_result_preserves_text_fallback` — legacy no-pagination result remains consumable as text; metadata additive in guarded mode.
  - `test_database_selection_and_access_mode_unchanged` — selected DB and restricted wrapper retained; unknown DB never falls back.
  - `test_rollout_off_is_behaviorally_legacy` — guardrails disabled with omitted arguments returns original result shape.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_query_service.py::test_execute_sql_schema_adds_optional_args`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Create `QueryExecutionService.execute(sql: str, database: str | None, limits: QueryLimits) -> BoundedQueryResult`; adapt `execute_sql(sql, database=None, max_rows=None, timeout_seconds=None, page_size=None, pagination="none")` but reject paging until plan 04 is installed and enabled.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_query_service.py tests/unit/test_multidb_server.py tests/unit/test_access_mode.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: integrate guarded query execution with MCP"`.

### Task 6: Exercise cancellation, shutdown and error boundaries

**Files:**
- Create: `tests/integration/test_query_budget_lifecycle.py`
- Modify: `src/postgres_mcp/application/query_service.py`
- Modify: `src/postgres_mcp/query_limits/admission.py`

**Interfaces:** Add exit criteria: hard limits and memory caps proven under disposable high-row fixture; no claims until Docker suite passes.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_cancellation_releases_pool_and_semaphore` — cancel while fetching and subsequent SELECT 1 succeeds with no active leases.
  - `test_connection_failure_is_sanitized` — failed pool open returns DATABASE_UNAVAILABLE without creds.
  - `test_unrestricted_dml_respects_timeout` — write path preserves transaction correctness and timeout without unbounded result materialization.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_query_budget_lifecycle.py::test_cancellation_releases_pool_and_semaphore`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Adjust service cleanup `try/finally` and cancellation boundaries from failing integration tests; preserve explicit SQL-transaction semantics and do not auto-retry side-effecting SQL.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/integration/test_query_budget_lifecycle.py` and `uv run pytest -q tests/unit/query_limits``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: clean up bounded SQL operations on cancellation"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
