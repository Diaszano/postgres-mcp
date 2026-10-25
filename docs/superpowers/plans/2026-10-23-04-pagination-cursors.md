# Offset and Keyset Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide optional deterministic offset/keyset paging and secure, expiring opaque MCP continuation tokens with cumulative budgets and no PostgreSQL connection retained between tool calls.

**Architecture:** Create pagination modules for eligibility, SQL rewriting, cursor state and coordinator. Reuse QueryExecutionService budget/serializer and Registry auth; only a conservative SQL subset is supported initially, all ambiguous cases fail with PAGINATION_NOT_SUPPORTED.

**Tech Stack:** Python 3.12, pglast, psycopg 3, asyncio, secrets/hashlib, FastMCP, pytest, Docker PostgreSQL

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-PAG-01/02/03/04/05/06; AC-11/12/13/14/15/16/17/18

**Dependencies:** Plans 01+02; plan 05 structured response integration is consumed for final native MCP error/structuredOutput. No dependence on native cursor sessions.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18 (see parent design for normative definitions).

## File Structure & Ownership

- **Build strict pagination SQL eligibility checker:** `src/postgres_mcp/pagination/eligibility.py`, `tests/unit/pagination/test_eligibility.py`.
- **Create safe offset and keyset page plans:** `src/postgres_mcp/pagination/planner.py`, `tests/unit/pagination/test_planner.py`, `tests/integration/test_pagination_sql.py`.
- **Implement opaque TTL cursor store and atomic consumption:** `src/postgres_mcp/pagination/cursors.py`, `tests/unit/pagination/test_cursors.py`.
- **Coordinate page budgets, authorization and continued SQL:** `src/postgres_mcp/pagination/service.py`, `tests/unit/pagination/test_service.py`, `tests/integration/test_pagination_security.py`.
- **Register MCP continuation tool and maintain legacy contract:** `tests/unit/pagination/test_mcp_contract.py`.
- **Run disposable pagination integration matrix and document consistency:** `tests/integration/test_pagination_end_to_end.py`.

## Review Focus

- **Mutable dataset shifts offset pages; docs never claim snapshot consistency** — Tasks 2 and 6.
- **Keyset never applies to nonunique, nullable, compound, descending or expression sorts in first release** — Task 1.
- **Token replay or concurrent continuation cannot increment state twice** — Task 3.
- **Revoked DB and changed HTTP principal invalidate subsequent pages** — Task 4.
- **Request byte cap includes cursor/metadata and total rows never exceed max_rows** — Tasks 4 and 5.

---

### Task 1: Build strict pagination SQL eligibility checker

**Files:**
- Create: `src/postgres_mcp/pagination/eligibility.py`
- Create: `tests/unit/pagination/test_eligibility.py`
- Modify: `src/postgres_mcp/sql/safe_sql.py`

**Interfaces:** Offset initial subset can be broader only when deterministic total order is proven. Do not silently synthesize ORDER BY or accept user assertions of uniqueness.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_rejects_missing_unstable_order` — SELECT without ORDER BY, nonunique ORDER BY, NULL-bearing order rejected.
  - `test_keyset_accepts_only_simple_unique_ascending_column` — single-table SELECT id ORDER BY id; metadata verifies non-null primary/unique index.
  - `test_unsafe_ast_fails_closed` — data-modifying CTE, multi-statement, locking, existing incompatible LIMIT/OFFSET, DISTINCT, UNION and unsupported joins rejected.
  - `test_database_catalog_scoped` — uniqueness metadata fetched only from requested authorized DB.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/pagination/test_eligibility.py::test_rejects_missing_unstable_order`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `async def inspect_pageable_select(sql: str, mode: Literal["offset","keyset"], sql_driver: SqlDriver) -> PageableQuery`; use `pglast` AST with allowlist and catalog verification for key uniqueness.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/pagination/test_eligibility.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: validate SQL eligibility for pagination"`.

### Task 2: Create safe offset and keyset page plans

**Files:**
- Create: `src/postgres_mcp/pagination/planner.py`
- Create: `tests/unit/pagination/test_planner.py`
- Create: `tests/integration/test_pagination_sql.py`

**Interfaces:** Initial support excludes existing top-level LIMIT/OFFSET and ambiguous shapes until reviewed. Never append raw `LIMIT` to arbitrary user SQL.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_offset_pages_progress_in_order` — stable 250-row fixture yields 100/100/50 without duplicates.
  - `test_keyset_uses_bound_last_seen_value` — WHERE id > %s (or AST equivalent) with psycopg bind parameters, never text interpolation.
  - `test_existing_filter_preserved` — SELECT ... WHERE active = true ORDER BY id respects filter after rewrite.
  - `test_bad_identifiers_and_strings_are_safe` — SQL containing semicolon in string/comment or hostile identifier never concatenated into executable SQL.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/pagination/test_planner.py::test_offset_pages_progress_in_order`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `build_page_query(query: PageableQuery, *, offset: int | None, last_key: object | None, limit: int) -> PageQuery(sql: str | Composable, params: tuple[object,...])`; preserve outer ordering via AST transforms and quote/bind values safely.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/pagination/test_planner.py` then `uv run pytest -q tests/integration/test_pagination_sql.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: generate deterministic offset and keyset pages"`.

### Task 3: Implement opaque TTL cursor store and atomic consumption

**Files:**
- Create: `src/postgres_mcp/pagination/cursors.py`
- Create: `tests/unit/pagination/test_cursors.py`

**Interfaces:** Use atomic async lock or per-token lock; cursor is never serialized with SQL or credentials; log token digests only if needed, never raw. At-most-once semantics documented.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_token_is_opaque_and_random` — token generated via secrets.token_urlsafe(32), no SQL/DSN exposed and only SHA256 token hash stored as lookup key.
  - `test_expiry_eviction_and_capacity` — TTL=300, capacity=100, monotonic clock fixture; errors CURSOR_EXPIRED/CURSOR_INVALID; old cursors evicted.
  - `test_one_time_concurrent_use` — two consumers racing on same token: one wins and other CURSOR_BUSY or CURSOR_INVALID; no double advance.
  - `test_auth_and_stdio_binding` — principal identity and stdio process/session owner validated; wrong principal cannot consume.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/pagination/test_cursors.py::test_token_is_opaque_and_random`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement immutable `CursorState` and `InMemoryCursorStore` with `issue(state) -> str`, `reserve(token, principal) -> CursorReservation`, `commit(reservation, next_state) -> str | None`, `release_on_error(reservation) -> None`, `invalidate_all() -> None`.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/pagination/test_cursors.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: add expiring principal-bound query cursors"`.

### Task 4: Coordinate page budgets, authorization and continued SQL

**Files:**
- Create: `src/postgres_mcp/pagination/service.py`
- Modify: `src/postgres_mcp/application/query_service.py`
- Create: `tests/unit/pagination/test_service.py`
- Create: `tests/integration/test_pagination_security.py`

**Interfaces:** Use safe `has_more`: one lookahead row when possible, otherwise unknown/incomplete; no false `has_more=false` when byte cap stops read early. Per-page timeout; cumulative row budget.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_first_page_and_continuation_budget` — max_rows=250, page_size=100 yields cumulative 100/200/250 and final has_more false with max_rows reached.
  - `test_resume_rechecks_authorization` — revoke DB between pages -> DATABASE_NOT_ALLOWED without fallback or cursor advancement.
  - `test_failed_page_does_not_advance_cursor` — timeout/serialization error preserves or invalidates token deterministically per documented error policy.
  - `test_no_connection_held_between_pages` — after every MCP call registry.active_leases(db)==0; all cursors remain app-state only.
  - `test_response_byte_budget_includes_metadata` — 2MiB inclusive structured/text result and cursor metadata.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/pagination/test_service.py::test_first_page_and_continuation_budget`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `PaginationService.first_page(sql, database, max_rows, timeout_seconds, page_size, mode, principal) -> PageResult` and `next_page(cursor, page_size, principal) -> PageResult`; reuse per-page QueryExecutionService, authorization, bounded result serializer and cursor reservations.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/pagination/test_service.py` then `uv run pytest -q tests/integration/test_pagination_security.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: enforce cumulative limits across query pages"`.

### Task 5: Register MCP continuation tool and maintain legacy contract

**Files:**
- Modify: `src/postgres_mcp/server.py:491-505,690-718`
- Modify: `tests/unit/test_multidb_server.py:769-828`
- Create: `tests/unit/pagination/test_mcp_contract.py`
- Modify: `README.md`, `README.pt-BR.md`

**Interfaces:** Update old exact-tool-count tests for one new tool; maintain existing required parameters and positional argument order, including `execute_sql.sql` default `all`.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_legacy_call_is_not_paginated` — execute_sql(sql, database) works identically with pagination none.
  - `test_page_size_without_mode_is_invalid` — page_size=100 with pagination none -> INVALID_QUERY_OPTIONS.
  - `test_fetch_page_accepts_only_cursor_and_page_size` — no SQL/database/mode arguments; readOnlyHint=true.
  - `test_paging_disabled_rejected` — when DATABASE_PAGINATION_ENABLED=false, explicit pagination returns stable error.
  - `test_success_metadata_and_text` — page returns rows, returned_rows, total_returned_rows, max_rows, page_size, truncated, has_more, next_cursor, expires_in_seconds.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/pagination/test_mcp_contract.py::test_legacy_call_is_not_paginated`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Expose `execute_sql(..., max_rows=None, timeout_seconds=None, page_size=None, pagination="none")` and `fetch_query_page(cursor: str, page_size: int | None=None)`; route to PaginationService only in paginated mode and preserve access-mode-specific execute_sql annotations.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/pagination/test_mcp_contract.py tests/unit/test_multidb_server.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: expose cursor pagination through MCP tools"`.

### Task 6: Run disposable pagination integration matrix and document consistency

**Files:**
- Create: `tests/integration/test_pagination_end_to_end.py`
- Modify: `src/postgres_mcp/pagination/service.py`
- Modify: `README.md`, `README.pt-BR.md`

**Interfaces:** Capture timings/memory for modest hardware; do not increase default caps without recorded evidence.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_static_fixture_offset_and_keyset` — 250 rows, ordered unique keys, full coverage with no duplicates.
  - `test_midstream_insertion_documents_best_effort` — simulate insertion between pages; verify observed behavior matches documented no-snapshot guarantee.
  - `test_cursor_expiry_restart_and_replay` — expired/lost/reused state yields CURSOR_EXPIRED/CURSOR_INVALID.
  - `test_cross_database_parallel_continuations` — no DB context mixing, no pool lease survives response.
  - `test_truncated_total_budget` — max_rows reached and more data exists -> truncated true, has_more false, limit_reached max_rows.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_pagination_end_to_end.py::test_static_fixture_offset_and_keyset`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Fix only defects revealed by integration; include warning that offset may duplicate/skip under writes and keyset requires verified stable key. Document at-most-once continuation failure semantics.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/integration/test_pagination_end_to_end.py tests/integration/test_multi_database_integration.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "test: cover cursor pagination end to end"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
