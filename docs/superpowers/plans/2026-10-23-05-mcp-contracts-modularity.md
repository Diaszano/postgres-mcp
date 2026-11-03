# Structured MCP Contracts and Modularity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver machine-readable MCP success/error semantics with backward-compatible text fallbacks and extract testable services without an all-at-once rewrite.

**Architecture:** Use an SDK-confirmed CallToolResult formatter and thin adapters in server.py. Incrementally move tool orchestration into services, and use explicit lifespan runtime dependencies only after existing CLI/tool compatibility is characterized.

**Tech Stack:** MCP Python SDK pinned by uv.lock, Pydantic, Python asyncio, pytest

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-MCP-01; FR-ARCH-01; FR-QRY-05; AC-09/10

**Dependencies:** Plans 01 and 02 for shared error/QueryExecutionService contracts; plan 04 for pagination success models (can implement first tasks earlier).

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-09, AC-10 (see parent design for normative definitions).

## File Structure & Ownership

- **Establish the real FastMCP return behavior:** `tests/integration/test_mcp_result_wire.py`, `src/postgres_mcp/mcp_response.py`, `tests/unit/test_mcp_response.py`.
- **Apply response adapter to SQL and diagnostics:** `tests/unit/test_error_contract.py`.
- **Extract thin service functions without renaming tools:** `src/postgres_mcp/application/database_service.py`, `src/postgres_mcp/application/health_service.py`, `tests/unit/test_application_services.py`.
- **Move mutable runtime into explicit app lifespan:** `src/postgres_mcp/app.py`, `src/postgres_mcp/runtime.py`, `tests/unit/test_app_lifespan.py`.

## Review Focus

- **SDK native structuredContent and isError are actually visible to an MCP client, not nested JSON strings** — Task 1.
- **Old clients can still consume text content** — Task 1.
- **No tool disappears or changes required/default arguments after modularization** — Tasks 2 and 3.
- **Restricted versus unrestricted execute_sql annotations remain correct** — Task 2.
- **Startup and shutdown do not leave pools/cursors referenced by stale globals** — Task 4.

---

### Task 1: Establish the real FastMCP return behavior

**Files:**
- Create: `tests/integration/test_mcp_result_wire.py`
- Create: `src/postgres_mcp/mcp_response.py`
- Create: `tests/unit/test_mcp_response.py`

**Interfaces:** If FastMCP version serializes CallToolResult incorrectly, use supported tool registration handler instead of returning nested model. Define schemas for SQL and page results.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_tool_error_is_error_on_wire` — client session sees CallToolResult.isError=True and structured error code.
  - `test_structured_success_has_text_fallback` — schema-valid structuredContent and TextContent JSON fallback both present.
  - `test_unexpected_exception_is_sanitized` — INTERNAL_ERROR without secret/trace.
  - `test_sdk_compatibility_pinned` — compatible MCP SDK behavior using uv.lock instead of assuming transport support.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/integration/test_mcp_result_wire.py::test_tool_error_is_error_on_wire`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `success_result(payload: Mapping[str,Any]) -> types.CallToolResult` and `error_result(error: PublicToolError, request_id: str | None=None) -> types.CallToolResult`, after proving FastMCP tool return handling in installed SDK.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_mcp_response.py tests/integration/test_mcp_result_wire.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: return structured MCP tool results and errors"`.

### Task 2: Apply response adapter to SQL and diagnostics

**Files:**
- Modify: `src/postgres_mcp/server.py:116-123,126-641`
- Create: `tests/unit/test_error_contract.py`
- Modify: `tests/unit/test_multidb_server.py`

**Interfaces:** Public result `content` remains a text list for compatibility; never advertise read-only on write-capable mode.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_execute_sql_safe_error_on_wire` — known database/pool/SQL failures include stable code and isError=true.
  - `test_existing_read_only_annotations` — 10 existing tools + fetch_query_page preserve accurate annotations.
  - `test_legacy_text_fallback` — success path for old clients stays text consumable.
  - `test_expected_health_errors` — health expected errors and unexpected exceptions both correctly mapped.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_error_contract.py::test_execute_sql_safe_error_on_wire`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Upgrade legacy `format_error_response` call sites to `error_result(to_public_error(exc))` and success to `success_result` where schema is defined; map all nine original tools and list_databases without raw exception text.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_error_contract.py tests/unit/test_multidb_server.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: standardize MCP error signaling"`.

### Task 3: Extract thin service functions without renaming tools

**Files:**
- Create: `src/postgres_mcp/application/database_service.py`
- Create: `src/postgres_mcp/application/health_service.py`
- Modify: `src/postgres_mcp/server.py:126-641`
- Create: `tests/unit/test_application_services.py`

**Interfaces:** Existing `QueryExecutionService` is not duplicated; preserve return types when migrating small-result formatting.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_database_service_contract` — list_schemas/list_objects/get_object_details target selected driver and preserve exact payload.
  - `test_health_and_top_queries_service` — cross-database health signals stay labeled instance-wide; extension probing DB local.
  - `test_tool_parameter_contract` — all old names, default values and positional invocation verified unchanged.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_application_services.py::test_database_service_contract`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Create `DatabaseInspectionService` and `HealthService` accepting a driver factory/context manager; leave FastMCP decorators/parameter declarations in server.py as thin wrappers.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_application_services.py tests/unit/test_multidb_server.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "refactor: separate database inspection from MCP handlers"`.

### Task 4: Move mutable runtime into explicit app lifespan

**Files:**
- Create: `src/postgres_mcp/app.py`
- Create: `src/postgres_mcp/runtime.py`
- Modify: `src/postgres_mcp/server.py:60-115,643-790`
- Create: `tests/unit/test_app_lifespan.py`
- Modify: `tests/unit/test_transport.py`

**Interfaces:** Avoid circular imports; decide how module-global `mcp` test fixture is migrated without modifying public CLI entrypoint.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_two_app_instances_are_isolated` — different injected configs do not share pools, cursor state or access mode.
  - `test_signal_and_shutdown_close_once` — stopping service idempotently closes registry and cursor store, no `sys.exit` from request context.
  - `test_tools_resolve_runtime_from_context` — client tool requests bound to correct app lifecycle.
  - `test_stdio_sse_http_startup_unchanged` — existing transport selection and ports preserved.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/test_app_lifespan.py::test_two_app_instances_are_isolated`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `AppRuntime(config, registry, query_service, pagination_service, access_mode, ...)` and `create_mcp_app(runtime: AppRuntime) -> FastMCP`; migrate globals incrementally using supported SDK lifespan/context injection and provide compatibility shim for existing main().
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/test_app_lifespan.py tests/unit/test_transport.py tests/unit/test_multidb_server.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "refactor: isolate MCP runtime in application lifespan"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
