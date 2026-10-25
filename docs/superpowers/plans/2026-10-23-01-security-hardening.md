# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate credential disclosure, fail closed on unsafe SQL and unauthorized remote access, and establish sanitized public error categories without breaking local stdio users.

**Architecture:** Keep legacy tools and database routing intact. Introduce small security/error adapters; enforce restricted SQL behavior with PostgreSQL privileges and explicit, verified remote ingress policy, not parser allowlists alone.

**Tech Stack:** Python 3.12, Bash, psycopg 3, pglast, FastMCP, pytest, Docker PostgreSQL

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-SEC-01/02; FR-QRY-05; FR-MCP-01 (safe error foundation); AC-01/02/03/04/05

**Dependencies:** None; execute first. Query budgets (plan 02) and structured responses (plan 05) consume the error and logging policy.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-01, AC-02, AC-03, AC-04, AC-05 (see parent design for normative definitions).

## File Structure & Ownership

- **Sanitize entrypoint and make Docker host rewriting opt-in:** `tests/security/test_docker_entrypoint.py`.
- **Introduce stable sanitized application errors:** `src/postgres_mcp/security/errors.py`, `tests/unit/security/test_errors.py`.
- **Tighten restricted SQL policy with DB enforcement:** `tests/unit/security/test_sql_policy.py`, `tests/integration/test_restricted_security.py`.
- **Make remote HTTP startup fail closed and document authenticated ingress:** `src/postgres_mcp/security/transport.py`, `tests/unit/security/test_transport_policy.py`.

## Review Focus

- **Positional PostgreSQL URI with URL-encoded password is never echoed by startup or failed remapping** — Task 1.
- **Unrestricted transport bind does not accidentally expose unauthenticated tools to the LAN** — Task 4.
- **Restricted SQL with untrusted function resolution cannot escalate via a writable schema** — Task 3.
- **A failing psycopg connection cannot leak libpq details through tool text, chained traceback or log** — Task 2.
- **An existing legacy stdio invocation remains unchanged when hardening flags are absent** — Tasks 1 and 4.

---

### Task 1: Sanitize entrypoint and make Docker host rewriting opt-in

**Files:**
- Modify: `docker-entrypoint.sh:6-99`
- Create: `tests/security/test_docker_entrypoint.py`
- Modify: `README.md`, `README.pt-BR.md`

**Interfaces:** `DATABASE_DOCKER_REMAP_LOCALHOST` default `false` (proposed opt-in). Preserves argv and DATABASE_URI except requested host remap.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_entrypoint_never_logs_database_uri` — subprocess Bash with fake postgres-mcp binary, positional URI and DATABASE_URI including percent-escaped characters: assert secret absent from stdout/stderr, command still receives exact URI.
  - `test_entrypoint_remapping_is_opt_in` — default no remap; `DATABASE_DOCKER_REMAP_LOCALHOST=true` remaps only hostname and does not echo DSN; invalid values fail.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/security/test_docker_entrypoint.py::test_entrypoint_never_logs_database_uri`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Update Bash entrypoint: no raw command echo or DSN logging; implement explicitly gated remap with parameter-safe parse/replacement (avoid substituting secret substrings), `exec` original argv, sanitized diagnostics.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/security/test_docker_entrypoint.py` and `bash -n docker-entrypoint.sh``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: prevent database credentials in Docker logs"`.

**Review notes:** Before implementation check whether Docker entrypoint can use python/libpq for safe URI rewriting rather than Bash string substitution.

### Task 2: Introduce stable sanitized application errors

**Files:**
- Create: `src/postgres_mcp/security/errors.py`
- Create: `tests/unit/security/test_errors.py`
- Modify: `src/postgres_mcp/server.py:116-123,134-640`
- Modify: `src/postgres_mcp/sql/sql_driver.py:15-135`
- Modify: `src/postgres_mcp/explain/explain_plan.py`
- Modify: `src/postgres_mcp/sql/safe_sql.py`
- Modify: `src/postgres_mcp/index/index_opt_base.py`

**Interfaces:** `to_public_error(exc)` is plan-02/05 shared taxonomy; safe stable codes `DATABASE_NOT_ALLOWED`, `DATABASE_UNAVAILABLE`, `SQL_VALIDATION_FAILED`, `POOL_CAPACITY_EXCEEDED`, `INTERNAL_ERROR`.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_public_errors_hide_dsn_and_bind_params` — OperationalError embedding secret URI, SQL literal, and nested exception maps to `INTERNAL_ERROR` or `DATABASE_UNAVAILABLE` with no secret.
  - `test_expected_errors_preserve_safe_code` — map `PoolCapacityError`, `DiscoveryUnavailableError`, SQL policy error to exact stable codes; no exception trace serialized.
  - `test_logger_uses_allowlisted_fields_only` — caplog has operation/request id + error class, not original exception text.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/security/test_errors.py::test_public_errors_hide_dsn_and_bind_params`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `PublicToolError(code: str, message: str, retryable: bool=False)` and `to_public_error(exc: BaseException) -> PublicToolError`; centralize catch policy while retaining text-compatible transport until plan 05 upgrades MCP `isError`.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/security/test_errors.py tests/unit/test_multidb_server.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: sanitize public SQL and connection errors"`.

**Review notes:** Preserve safe fixed messages for already-known errors. Audit all module logging of SQL text or exception strings, not just server.py. Document note: format_error_response still text-only until plan 05.

### Task 3: Tighten restricted SQL policy with DB enforcement

**Files:**
- Modify: `src/postgres_mcp/sql/safe_sql.py:90-125,881-1042`
- Modify: `src/postgres_mcp/sql/sql_driver.py:237-288`
- Create: `tests/unit/security/test_sql_policy.py`
- Create: `tests/integration/test_restricted_security.py`

**Interfaces:** `validate_restricted_sql(sql)` rejects forbidden AST and untrusted function calls; transaction read-only and DB least-privilege remain independent mandatory barriers.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_restricted_rejects_write_ast_and_data_modifying_ctes` — UPDATE/DELETE/CREATE EXTENSION/VACUUM/EXPLAIN ANALYZE and writable CTE rejected before execution.
  - `test_restricted_does_not_trust_shadowed_functions` — disposable DB role can create a shadowed SQL function; untrusted resolution is rejected or role/transaction prevents effect.
  - `test_readonly_transaction_prevents_real_writes` — non-superuser role cannot mutate table even if AST validation fails to reject.
  - `test_legacy_select_still_works` — SELECT against existing public schema remains possible where role permits.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/security/test_sql_policy.py::test_restricted_rejects_write_ast_and_data_modifying_ctes`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Extract narrow `validate_restricted_sql(sql: str) -> None` policy from `SafeSqlDriver.validate` with explicit unsupported nodes/functions; ensure transaction-level READ ONLY and safe search_path/function resolution without breaking ordinary qualified tables.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/security/test_sql_policy.py tests/unit/sql/test_safe_sql.py` then `uv run pytest -q tests/integration/test_restricted_security.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "fix: enforce restricted SQL policy defense in depth"`.

**Review notes:** Do not replace current validator wholesale. Function safety must be verified against PostgreSQL name resolution; avoid simplistic “all SELECT are safe” assumptions.

### Task 4: Make remote HTTP startup fail closed and document authenticated ingress

**Files:**
- Modify: `src/postgres_mcp/server.py:643-764`
- Create: `src/postgres_mcp/security/transport.py`
- Create: `tests/unit/security/test_transport_policy.py`
- Modify: `tests/unit/test_transport.py`
- Modify: `README.md`, `README.pt-BR.md`

**Interfaces:** `HttpAuthConfig` validated from explicit env vars; its authentication/principal interface must be selected only after SDK capability spike and tests, not fabricated.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_default_http_bind_is_loopback` — SSE and Streamable HTTP default host remains localhost.
  - `test_public_bind_without_auth_policy_rejected` — attempt to bind 0.0.0.0 without verified auth policy fails before MCP starts.
  - `test_verified_authenticated_ingress` — authenticated ingress integration supplies principal; anonymous calls fail; verify Origin/Host checks with SDK-supported primitives.
  - `test_stdio_unaffected` — stdio never requires HTTP credentials.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/security/test_transport_policy.py::test_default_http_bind_is_loopback`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `validate_http_deployment(transport: str, host: str, auth: HttpAuthConfig) -> None`; use actual installed MCP SDK auth/middleware integration or a tested trusted-ingress adapter, require loopback or proven authentication for public binds; document HTTPS at ingress and rate limiting.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/security/test_transport_policy.py tests/unit/test_transport.py` plus authenticated transport integration test`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: require authenticated remote MCP deployment"`.

**Review notes:** Stage breaking non-loopback behavior behind migration note. An env var claiming “trusted ingress” without verified request enforcement is insufficient. Revise older tests expecting public binds.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
