# PostgreSQL MCP — Security, Query Controls, Pagination, and Evolution Design

> **Superpowers design specification**  
> **Status:** PROPOSED — requires owner review and explicit approval before an implementation plan or code changes  
> **Date:** 2026-10-23  
> **Repository:** [Diaszano/postgres-mcp](https://github.com/Diaszano/postgres-mcp)  
> **Target branch:** [`feature/multi-database`](https://github.com/Diaszano/postgres-mcp/tree/feature/multi-database)  
> **Expected location:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md`  
> **Implementation:** Not authorized by this document. Separate, small Superpowers implementation plans must follow approval.

## 1. Intent and motivation

Evolve the existing PostgreSQL MCP server into a secure, reliable, resource-bounded, AI-friendly service for multiple databases **within one PostgreSQL instance**, while retaining its current tool contract wherever possible. Give AI agents explicit per-call query limits and an opt-in, cursor-based way to navigate large result sets without holding PostgreSQL connections open between MCP requests.

This document also consolidates the architectural, security, correctness, observability, documentation, and delivery improvements identified in the review of `feature/multi-database`. **A finding derived from code inspection is not automatically a reproduced bug**; tests must establish behavior before fixes are claimed.

### 1.1 Current baseline — do not reimplement

The target branch already provides:

- `DatabaseConfig` with validated multi-database environment settings.
- `DatabaseCatalog` with single-instance discovery, allowlist/denylist, TTL, refresh, and stale snapshots.
- `DatabaseRegistry` with lazy per-database pools, per-call leases, bounded pool count, LRU eviction, and cancellation-conscious lifecycle.
- An optional `database` parameter across the existing SQL, inspection, health, and index tools; the legacy single-database path remains.
- `list_databases`, a restricted-by-default **discovery** mode, and numerous unit/integration tests.
- The configured `pool_max_size` is already applied; the catalog is rechecked before a new lease. These are **not outstanding requirements**.

Relevant sources: [`database_config.py`](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/database_config.py), [`database_catalog.py`](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/database_catalog.py), [`database_registry.py`](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/database_registry.py), [`server.py`](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/server.py).

### 1.2 Verified static observations requiring attention

1. `docker-entrypoint.sh` prints the original/remapped database URL and full command line, potentially exposing credentials.
2. `SqlDriver._execute_with_connection` performs an unbounded `fetchall()`, and `execute_sql` serializes all rows.
3. Most tool failures return ordinary text (`"Error: ..."`) instead of MCP tool results with `isError: true`; several paths log raw exception strings.
4. Pool leases prevent eviction but **do not pin one physical connection**. HypoPG state is session-local, while parts of the tuning flow make multiple independent SQL calls.
5. The SQL validator permits some statement nodes whose semantics require further review against the restricted-mode policy. SQL function names alone are not a security boundary.
6. Remote HTTP transports are configurable, but the project does not supply a complete, documented production authentication/deployment policy.
7. `justfile`, Docker metadata, CI/dependency metadata, and integration-test gating contain maintenance inconsistencies worth fixing.

These items are design inputs, not claims that every suspected failure has been reproduced in a live database.

## 2. Goals, non-goals, and anti-goals

### Goals

- **G-01:** Prevent credential leakage and unsafe disclosure of internal SQL/driver errors.
- **G-02:** Bound rows, response bytes, execution time, and concurrency with server-owned hard ceilings.
- **G-03:** Allow AI agents to choose **per-call** row and timeout limits without bypassing ceilings.
- **G-04:** Add explicit offset and keyset pagination with opaque expiring MCP continuation tokens.
- **G-05:** Retain correct PostgreSQL session affinity for HypoPG operations and other session-local state.
- **G-06:** Produce structured MCP success/error responses usable by Claude Code, Codex, OpenCode, and other compliant clients.
- **G-07:** Strengthen restricted mode, HTTP deployment security, tests, and operational visibility.
- **G-08:** Evolve modularly without a broad DDD rewrite; preserve existing tools and single-instance multi-database semantics.

### Non-goals for the initial delivery

- Federated queries or routing across multiple PostgreSQL hosts/clusters.
- Persistent SQL result caching or storing full result sets in Redis.
- Holding native PostgreSQL server-side cursors or transactions open across MCP calls.
- Guaranteeing snapshot-consistent pagination across mutations in the database.
- Allowing the AI to increase administrator ceilings or change database credentials.
- Auto-executing schema migrations, CREATE INDEX, writes, or EXPLAIN ANALYZE in restricted mode.
- Replacing the current MCP tools or forcing all clients to adopt pagination immediately.

### Anti-goals

- Silently truncate output without telling the model.
- Silently clamp a requested limit larger than the hard maximum.
- Manufacture a stable order when a query lacks one.
- Claim that AST allowlists alone make arbitrary SQL safe.
- Make database selection or continuation-token data a mechanism to select an arbitrary host or DSN.
- Break production setups through unreviewed changes to defaults.

## 3. Approaches and proposed choice

| Approach | Advantages | Tradeoffs | Decision |
|---|---|---|---|
| A. Add limits and `LIMIT/OFFSET` directly inside `server.py` | Fastest patch | More coupling; unsafe for arbitrary SQL; weak cursor lifecycle | Reject |
| **B. Central `QueryExecutionService` with policy, bounded fetching and short-lived opaque pagination state** | Reusable, testable, fits registry design; no connection retained between calls | Requires new service, token store, structured result contract | **Recommended — proposed, pending approval** |
| C. Native PostgreSQL cursors preserved across MCP requests | Stronger single-query streaming semantics | Holds connections/transactions, fragile in stateless HTTP, pool starvation | Reject for normal pagination |

**Proposed implementation direction:** Approach B. Maintain `DatabaseRegistry` for pool lifetime, add short-lived **physical** session leases within a single MCP call where required, and use **application-level** continuation tokens for subsequent pages. This is a proposal, not a decision already approved by the owner.

Because this umbrella specification spans independent subsystems, execution should use **separate implementation plans** for: (1) security + query budgets, (2) session affinity, (3) pagination, (4) MCP contracts/architecture, (5) observability + delivery, and (6) advanced features. The order and gates are in §11.

## 4. Compatibility and rollout policy

- Preserve existing tool names and existing required/positional argument semantics. Add only optional parameters to `execute_sql`, and introduce `fetch_query_page` as a new tool.
- `pagination="none"` is the default. Calling `execute_sql` without pagination continues to act as a single tool call.
- Existing small successful results should remain consumable as text. Structured results are **additive**, with a textual compatibility representation as required by the MCP specification.
- Enforcing a new default output cap on previously unbounded queries is a **behavioral change** even without a signature change. It must be documented, tested and rolled out through `DATABASE_QUERY_GUARDRAILS_ENABLED` during migration. Production hardening profiles must enable it. Do not silently change all existing installations without migration/release notes.
- In new guarded mode, exceeding limits produces an explicit truncated result or a typed limit error as defined below; it must never appear to be a complete result.
- Keep the legacy `DATABASE_AUTO_DISCOVER=false` path and existing `DATABASE_URI` semantics.
- Keep `DATABASE_AUTO_DISCOVER=true` defaulting to `restricted`; keep the legacy access-mode behavior during the migration, with a prominent production warning when unrestricted.
- Target supported PostgreSQL versions by verified CI matrix; do not assume a dependency version can be changed without compatibility tests.

### 4.1 Example environment contract (proposed defaults)

```dotenv
# Query guardrails (enable explicitly during staged migration)
DATABASE_QUERY_GUARDRAILS_ENABLED=true
DATABASE_QUERY_DEFAULT_MAX_ROWS=200
DATABASE_QUERY_HARD_MAX_ROWS=5000
DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS=15
DATABASE_QUERY_HARD_TIMEOUT_SECONDS=60
DATABASE_QUERY_MAX_RESULT_BYTES=2097152
DATABASE_QUERY_MAX_CONCURRENCY=4

# Pagination (opt-in per MCP tool call)
DATABASE_PAGINATION_ENABLED=true
DATABASE_PAGINATION_DEFAULT_PAGE_SIZE=100
DATABASE_PAGINATION_MAX_PAGE_SIZE=1000
DATABASE_PAGINATION_CURSOR_TTL_SECONDS=300
DATABASE_PAGINATION_MAX_ACTIVE_CURSORS=100
```

The numbers above are **proposed configuration defaults**, not measurements. Validate on disposable PostgreSQL and modest hardware before production. Define whether `DATABASE_QUERY_MAX_RESULT_BYTES` is per MCP response, and include metadata/warnings inside the byte budget (proposal: **yes**). Strict positive-integer parsing, upper-bound consistency, and startup failure on invalid configs are required. When guardrails are disabled for compatibility, remote production deployment must surface an unsafe-configuration warning.

## 5. Query execution and AI-configurable limits

### FR-QRY-01 — Optional agent-controlled inputs

Preserve the existing `execute_sql(sql, database=None)` call pattern and append:

```python
async def execute_sql(
    sql: str,
    database: str | None = None,
    max_rows: int | None = None,
    timeout_seconds: int | None = None,
    page_size: int | None = None,
    pagination: Literal["none", "offset", "keyset"] = "none",
) -> ResponseType:
    ...
```

The specific MCP/Pydantic return type can be refined during implementation; the **public parameter names and semantics** above are the contract. `page_size` must be omitted in `none` mode. `max_rows` means the **maximum number of rows in the logical paginated request**, not the number of rows per page. With `pagination="none"`, it is the per-call row maximum.

### FR-QRY-02 — Strict precedence and validation

- Missing request limits use server defaults.
- Explicit request values are accepted only when strictly positive and **no greater** than the administrator's hard ceiling.
- Reject over-limit requests with `LIMIT_EXCEEDED`; include allowed maxima, without executing SQL.
- Reject unknown modes, invalid types (including booleans coerced to integers), zero, and negative values as `INVALID_QUERY_OPTIONS`.
- Effective `page_size` defaults to the server page size when pagination is enabled; it cannot exceed `DATABASE_PAGINATION_MAX_PAGE_SIZE`, the current remaining row budget, or the response-byte ceiling.
- The AI cannot set `DATABASE_QUERY_MAX_RESULT_BYTES`, concurrency limits, pool counts/sizes, credentials, or cursor TTL through a request.
- Existing connection and authorization restrictions apply before execution.

### FR-QRY-03 — Execution boundaries

- Use a monotonic deadline for application processing **and** PostgreSQL `statement_timeout` scoped to the individual operation/transaction, not global session state accidentally leaking through pooled connections.
- Apply read-only transactions where required, least-privilege database roles, and appropriate server-side transaction-scoped settings. Roll back and clean up reliably on cancellation or exceptions.
- Bound memory by streaming/fetching batches rather than `fetchall()` for agent-facing large results; stop after one look-ahead row **only if** needed to establish `has_more`.
- Bound serialized bytes using a serializer-aware size budget; do not assume the input characters equal UTF-8 bytes.
- Enforce concurrent execution admission and bounded wait/fail responses. Do not hold a database pool lease while indefinitely waiting on unrelated queues.
- Distinguish `QUERY_TIMEOUT`, `RESULT_TOO_LARGE`, `POOL_CAPACITY_EXCEEDED`, `DATABASE_UNAVAILABLE`, `DATABASE_NOT_ALLOWED`, and `SQL_VALIDATION_FAILED`.
- Logging must not include raw bound parameters, passwords, or unredacted SQL by default.

### FR-QRY-04 — Size and truncation semantics

- A successful bounded query returns rows and metadata: `returned_rows`, `truncated`, `limit_reached`, `timeout_seconds`, and `execution_time_ms`.
- If row limit is reached and existence of more rows is known, set `truncated=true` and `limit_reached="max_rows"` (or `page_size` for an ordinary page). If existence of more rows is unknown due to a byte cap, explicitly mark the result as incomplete/unknown rather than asserting `has_more=false`.
- A query exceeding the byte limit before any meaningful row fits returns a typed `RESULT_TOO_LARGE` error with remediation; never return invalid partial JSON.
- `timeout_seconds` applies per execution/page. Total rows are additionally capped across all pages; **no unbounded series of pages** may bypass the logical request cap.
- Avoid unbounded data conversion before serialization. Tool summaries/metadata count against response limits.

### FR-QRY-05 — SQL execution policy

- The restricted tool remains read-only at both application policy and PostgreSQL transaction/privilege levels.
- Review statement/AST allowlists, `CREATE EXTENSION`, `ANALYZE`, prepared statements, session-altering functions, `search_path`, function shadowing and schema-qualified function resolution.
- Reject multiple SQL statements in a paginated request. For unrestricted, non-paginated behavior, preserve documented multi-statement compatibility until a separately approved policy change.
- Do not rely on `LiteralString` typing for runtime SQL safety. Bind values with psycopg parameters and quote identifiers with psycopg SQL composition.

## 6. Pagination and opaque continuation cursors

### FR-PAG-01 — Opt-in modes

- `pagination="none"` remains the default.
- `pagination="offset"` is for safely pageable, deterministic SELECT queries, including compatible complex SELECT statements.
- `pagination="keyset"` is preferred where a **verified unique, immutable-enough, non-null sort key** provides deterministic seek pagination.
- These are **MCP continuation tokens**, not native PostgreSQL server cursors.
- A request for pagination on an unsupported SQL shape must be rejected with `PAGINATION_NOT_SUPPORTED`, including an actionable reason. Never silently fall back to a weaker strategy unless the AI explicitly requests it.

### FR-PAG-02 — Eligibility and SQL rewriting

- Only one top-level, validated read-only `SELECT` (including safe `WITH ... SELECT`) is eligible; reject data-modifying CTEs and commands producing side effects.
- Require an explicit deterministic `ORDER BY`. For offset mode, accept only when a stable total order can be demonstrated or explicitly verified by a documented SQL contract; explain that mutable data can still shift pages. Do not synthesize an arbitrary order.
- Parse/rewrite with the existing `pglast` infrastructure; **never append untrusted `LIMIT/OFFSET` text** or wrap arbitrary SQL in a way that can lose outer ordering/semantics.
- Validate and resolve existing `LIMIT`, `OFFSET`, locking clauses, parameter placeholders, `DISTINCT`, aggregates, set operations and nested SELECTs; for initially unsupported combinations, refuse rather than guess.
- For the first keyset milestone, support **single-table SELECT, one ascending, non-null unique/primary-key column, and simple filtering**. Validate uniqueness using PostgreSQL catalog metadata, not model assertions. Later broaden to composite/directional/null-aware keys after dedicated tests.
- Keyset seek values must be bound parameters, never concatenated into SQL.
- No extra privilege or cross-database access is granted by pagination.

### FR-PAG-03 — Continuation tool

```python
async def fetch_query_page(
    cursor: str,
    page_size: int | None = None,
) -> ResponseType:
    ...
```

- `fetch_query_page` **must not accept or change** SQL text, database name, pagination strategy, or hard limits.
- A page-size override may be accepted if positive, within administrative caps **and** remaining row budget; the originally authorized query remains unchanged.
- Each page consumes its own timeout budget; the cursor tracks cumulative returned rows and bytes, effective limits, ordered position, expiration, and completed state.
- Advance state only after a valid result is fully produced. Concurrent requests using the same cursor must be serialized or one rejected deterministically (e.g. `CURSOR_BUSY`).
- Emit a fresh next cursor after a successful page and invalidate the consumed token. This prevents accidental duplicate advancement; retries after uncertain delivery should be handled with clearly documented at-most-once semantics (or idempotent caching if introduced later).

### FR-PAG-04 — Cursor storage and security

- Use a cryptographically strong **opaque random token** (at least 128 bits; recommend 256) as a lookup handle to bounded server-side state. Never embed credentials, raw SQL, or user data in a base64-decoded client-readable token.
- Store a hash of the token as a lookup key where practical. State may hold bounded query text/query digest, validated options, last seek key or offset, issued/expires timestamps, connection identity/policy identity, and budget counters.
- Bind tokens to the authenticated principal for HTTP; bind to the current process/session identity for stdio. Do not treat a database name or cursor token alone as HTTP authentication.
- Revalidate current catalog authorization, access policy, and revocation on **every** subsequent page. Reject changed/unauthorized databases, expired tokens, tampering, server restart/lost state, and completed cursors.
- In-memory TTL/LRU state is acceptable for a single-process first delivery. The server must not advertise cursor portability across worker processes. Optional Redis/Valkey can be designed later for horizontal deployment; do not make it a mandatory dependency.
- Enforce `DATABASE_PAGINATION_MAX_ACTIVE_CURSORS`, expiration and eviction; invalidate cursor on shutdown; do not pin PostgreSQL pool slots/connections between calls.
- Cursors do not promise stable snapshots across writes. Document consistency limitations prominently.

### FR-PAG-05 — First-page result contract

The following is an **illustrative** payload; real rows and token values are generated at runtime:

```json
{
  "database": "app_development",
  "rows": [{ "id": 101, "name": "Example A" }, { "id": 102, "name": "Example B" }],
  "metadata": {
    "returned_rows": 2,
    "total_returned_rows": 2,
    "max_rows": 1000,
    "page_size": 2,
    "truncated": false,
    "execution_time_ms": 25
  },
  "pagination": {
    "mode": "keyset",
    "has_more": true,
    "next_cursor": "<opaque-token>",
    "expires_in_seconds": 300,
    "consistency": "best_effort"
  }
}
```

For `pagination="none"`, use compatible text output plus metadata as allowed by rollout policy. For `pagination!="none"`, prefer MCP `structuredContent` with a matching output schema and duplicate a compact JSON representation in `TextContent` for clients that do not consume structured content. When `has_more=false`, `next_cursor=null`. Distinguish a page boundary (`has_more=true`) from a hard total-row cap (`has_more=false`, `truncated=true`, `limit_reached="max_rows"`).

### FR-PAG-06 — Workflow example

1. AI calls `execute_sql(sql="SELECT id, name FROM users ORDER BY id", database="app_development", max_rows=1000, page_size=100, pagination="keyset")`.
2. Server authenticates/authorizes, checks eligibility and limits, retrieves a bounded first page, and returns `next_cursor`.
3. AI calls `fetch_query_page(cursor=...)` until `has_more=false`, a total budget is reached, the token expires, or it has enough information.
4. Server releases each acquired physical connection before returning the MCP result.
5. Revocation, token expiration, restarted process, or exhausted capacity returns an actionable typed MCP error, not a silent fallback to the default database.

## 7. Session affinity and HypoPG correctness

### FR-SES-01 — Distinguish pool lease and physical connection

`DatabaseRegistry.acquire(database)` preserves the pool lifetime but cannot guarantee that repeated `SqlDriver.execute_query()` calls use the same PostgreSQL session. Introduce a short-lived `DatabaseSession` / `SqlSession` abstraction that **pins a single physical connection for the duration of one operation**. A session MUST be released or invalidated on success, error, cancellation, and shutdown.

### FR-SES-02 — Transaction and session-state behavior

- The session owns transaction boundaries and may expose `execute_query` to subcomponents without borrowing a fresh pool connection each time.
- Support restricted/read-only policies within the session, and cleanly roll back any failed operation.
- For HypoPG, group `hypopg_create_index`, inspection, `EXPLAIN`, and `hypopg_reset` on the **same** physical connection; ensure cleanup in `finally` and test sessions under concurrency.
- Prevent session-local settings, prepared state, temporary artifacts or HypoPG indexes from leaking into subsequent pooled consumers.
- Distinguish "pool already acquired" from "connection reserved" to avoid deadlocks or nested checkouts.

### FR-SES-03 — Scope of session use

Require physical-session affinity for existing HypoPG tuning and hypothetical-index EXPLAIN flows. Do **not** require persistent physical sessions for ordinary stateless `SELECT` pagination across MCP requests.

## 8. MCP contracts, security, and modularity

### FR-MCP-01 — Structured success and errors

- Use `CallToolResult` semantics with `isError=true` for tool execution errors and `structuredContent` for machine-readable data, plus text fallback.
- Use stable public codes such as `DATABASE_NOT_ALLOWED`, `DATABASE_UNAVAILABLE`, `QUERY_TIMEOUT`, `POOL_CAPACITY_EXCEEDED`, `SQL_VALIDATION_FAILED`, `LIMIT_EXCEEDED`, `RESULT_TOO_LARGE`, `PAGINATION_NOT_SUPPORTED`, `CURSOR_EXPIRED`, `CURSOR_INVALID`, `CURSOR_BUSY`, and `INTERNAL_ERROR`.
- Public errors include a safe message and optional `request_id` and `retryable`. Never pass raw libpq/psycopg exception text to agents or logs without sanitization.
- Preserve correct MCP read-only/destructive tool annotations; `execute_sql` annotations continue depending on access mode.

### FR-SEC-01 — Credentials and secrets

- Remove raw connection URI/command output from `docker-entrypoint.sh` and other logs. Test both positional URI and `DATABASE_URI`, quoted DSNs, URL-encoded passwords, and failures.
- Do not print SQL bind parameters, connection strings or secrets in telemetry.
- Do not rely only on regex-based redaction. Prefer structured, explicitly allowed diagnostic fields.
- Make automatic Docker `localhost` remapping explicit/opt-in rather than silently rewriting credentials-bearing connection strings.

### FR-SEC-02 — Remote transport deployment

- Document production HTTP security: bind to loopback by default, use TLS at trusted ingress, explicit authentication/authorization before exposing tools, validate origin/host as applicable, rate limit, and disable unauthorized anonymous remote access.
- For stdio, rely on local OS/process boundary; document who can read its configuration and credentials.
- Treat per-database access decisions as backend policies; do not trust tool annotations or client UI to authorize writes.
- Validate the MCP SDK's currently supported middleware/auth mechanisms before implementation; do not invent custom transport/security primitives when a supported solution exists.

### FR-ARCH-01 — Maintainable component boundaries

Refactor incrementally, preserving current public behavior. Proposed responsibilities (names may be refined in the implementation plan):

```text
src/postgres_mcp/
  app.py                       # application setup, lifespan and MCP transport
  config/                      # settings + validation
  tools/                       # thin MCP tool adapters
  application/                 # query, database inspection, health and tuning services
  infrastructure/postgres/     # catalog, registry, driver, physical sessions
  security/                    # SQL policy, authorization, redaction
  pagination/                  # eligibility, token store, offset/keyset strategies
  observability/               # structured logs and metrics
```

- At P0, introduce the minimal `QueryExecutionService` boundary behind the existing `server.py` functions; P2 extracts the remaining tool handlers and services. Avoid an all-at-once folder migration.
- Eliminate global mutable runtime state in a controlled follow-up by using explicit application/lifespan dependencies.
- Split `SafeSqlDriver`'s AST parsing/policy/execution responsibilities when the query service is introduced.
- Do not add heavyweight frameworks solely to match textbook DDD/hexagonal architecture.

## 9. Performance, observability, and developer experience

### FR-OPS-01 — Metrics and logging

Expose opt-in Prometheus-compatible metrics or a documented integration point:

- Active/opening/closing/failed pools and current leases; connection saturation and wait time.
- Query count, duration histogram, timeout count, rejected query count, truncated results, response bytes, pagination page count.
- Cursor count, expiration, eviction, invalid reuse, stale/revoked catalog hits.
- Sanitized request/operation IDs and database aliases; avoid raw SQL, credentials, row data, and high-cardinality personal labels.
- Startup readiness (can serve MCP), and database health/degraded states must be distinct.

### FR-OPS-02 — Pool and concurrency controls

Preserve per-database max connection pools and bounded number of pools. Verify cancellation, single-flight creation, eviction, shutdown while leases are active, and fairness under simultaneous pagination/long-running tuning. Consider idle cleanup timers only if observed operational problems justify complexity.

### FR-DX-01 — Tests and CI

- Test unit behavior without Docker, and Docker integration behavior on ephemeral PostgreSQL databases with generated credentials; never use developer or production databases.
- Require a PostgreSQL+HypoPG test image for relevant session-affinity tests; no success reported when those tests were skipped.
- Add an explicit matrix for supported PostgreSQL versions (initial proposal: 16, 17, 18, subject to dependency/image availability).
- Validate `uv.lock` against `pyproject.toml`, including MCP constraint changes; do not assume pin compatibility by inspection only.
- Update `justfile` commands for actual `src/postgres_mcp` layout and provide `just lint`, `just typecheck`, `just test-unit`, `just test-integration`, and `just build`.
- Fix accurate project/vendor/license metadata in `Dockerfile` without stripping upstream copyright or attribution.
- Add static security/dependency scans, minimum-priority CI check gating, and release smoke tests for amd64/arm64 where feasible.

### FR-DX-02 — Documentation

- Update English and pt-BR READMEs with complete config examples, secure deployment profiles, all tool signatures, pagination limitations and migration instructions.
- Document resource/response guarantees and the difference between DB pool leases, physical sessions and stateless MCP continuation tokens.
- Include real-world Claude Code, Codex, and OpenCode configuration samples with no credentials checked into git.
- Document read-only guarantees precisely: `restricted` mode **plus** PostgreSQL role privilege enforcement, not a universal promise based on a SQL parser alone.

## 10. Optional advanced features (separate specs/plans, after core stabilization)

### ADV-01 — Database profiles

Allow named per-database policies, possibly credentials/roles, separate read/write grants, timeouts, and quotas. This expands beyond the current single-bootstrap-role design and requires a separate security review. No policy escalation based on AI-supplied names.

### ADV-02 — MCP Resources

Expose schema/table metadata via stable resource URIs alongside—not instead of—existing tools; respect per-database authorization and output budgets.

### ADV-03 — Compact database overview

Provide a token-efficient `get_database_overview` (schema names, relevant tables/relationships, key extensions, selective statistics) with explicit omission/truncation metadata and no private row samples by default.

### ADV-04 — Explain/tuning intelligence

Combine `EXPLAIN`, catalog/index context, planner estimates and measured statistics where permitted. Clearly distinguish suggestions from executed changes; require explicit approval for DDL or expensive `EXPLAIN ANALYZE` in any unrestricted flow. Do not feed confidential SQL/data to external LLMs without opt-in and a documented data boundary.

### ADV-05 — Shared cursor store / multi-instance

When multiple HTTP server processes are supported, evaluate Redis/Valkey-backed cursor state with encryption as needed, principal binding and atomic consumption. Remains **optional**; in-memory mode must remain simple for local stdio usage.

## 11. Delivery roadmap and approval gates

| Phase | Scope | Dependencies | Ship gate |
|---|---|---|---|
| **P0 — Security and query budget** | Secret-safe logging, safe errors, bounded fetching/bytes, strict per-call limits, timeout/concurrency enforcement | Existing registry/driver | Sensitive-data tests; bounded-result tests; compatibility migration reviewed |
| **P1 — Session correctness** | Physical session abstraction, HypoPG same-session execution/cleanup | P0 query execution boundary | Concurrent HypoPG integration tests with required extension |
| **P1 — Pagination** | Offset + first supported keyset shape, cursor state and `fetch_query_page` | P0 query budgets, P1 sessions interface finalized | End-to-end paging, TTL, revocation, replay/concurrency, cancellation tests |
| **P2 — MCP/API and modularity** | Structured responses/errors, extracted services, explicit lifecycle | P0 error taxonomy | All existing tool-contract tests and new MCP transport tests |
| **P2 — Operations and delivery** | Metrics, CI matrix, docs, Docker/justfile/lock consistency | P0/P1 stable | PR CI, release smoke tests, clean docs |
| **P3 — Advanced separate initiatives** | Profiles, Resources, overview, richer SQL advisor, shared cursor backend | Core stabilized | Each its own reviewed design + plan |

**Process:** After owner approval of this design, invoke `superpowers:writing-plans` **separately for each independently testable phase/subsystem**; implement via `superpowers:subagent-driven-development` (recommended for security-critical work) or `superpowers:executing-plans`. Each implementation task uses TDD, independent review, verification commands, and English Conventional Commits. Avoid implementing and merging the entire roadmap in one PR.

## 12. Acceptance criteria

### Security and configuration

- **AC-01:** No plaintext secret appears in Docker startup logs, failure logs, MCP errors, or default metrics across fixture tests.
- **AC-02:** Bad configuration fails closed with a sanitized message; an AI cannot request a higher-than-hard limit or mutate admin-only caps.
- **AC-03:** Unauthorized, excluded, newly revoked, and unknown database selections never acquire/query an unauthorized database.
- **AC-04:** Restricted mode prevents writes with both policy checks and a minimally privileged PostgreSQL role; prohibited SQL fails prior to executing its effects.
- **AC-05:** Remote HTTP deployment cannot be considered production-ready without a tested authentication/authorization and TLS deployment guide.

### SQL execution and MCP contract

- **AC-06:** `max_rows` and `timeout_seconds` are optional; omissions use configured defaults in guarded mode, valid agent values override defaults, and requests above hard ceilings are rejected before SQL.
- **AC-07:** 1M-row fixtures cannot cause 1M rows to be materialized or serialized by `execute_sql` when the configured cap is 200/5,000; results explicitly indicate incompleteness.
- **AC-08:** Oversized serialized rows/UTF-8 payloads, slow queries, cancellation, and concurrency saturation have safe, deterministic outcomes with no leaked connections.
- **AC-09:** Tool failures set MCP `isError=true` and provide stable codes; structured successes have schema-valid `structuredContent` and a text fallback.
- **AC-10:** Legacy tool names, positional arguments, default DB behavior, access-mode annotations and small-result handling still pass contract tests; material changes are covered by migration notes.

### Pagination

- **AC-11:** `pagination="none"` is backward-compatible; paging is opt-in and a `page_size` by itself cannot silently alter SQL behavior.
- **AC-12:** A supported ordered SELECT returns exactly the configured number of rows per page (except the last page), an explicit `has_more`, and an opaque token; no page exceeds the bytes/rows cap.
- **AC-13:** A keyset query with verified non-null unique ascending key advances without duplicate rows on a static fixture and never accepts unvalidated arbitrary SQL as keyset-eligible.
- **AC-14:** Missing/unstable ordering, unsupported AST nodes, multi-statement SQL, invalid pagination options and over-large page sizes are rejected clearly.
- **AC-15:** Invalid, expired, replayed, unauthorized, revoked, completed, or process-lost cursors fail with typed errors; no cursor grants authority beyond the original request.
- **AC-16:** Fetching multiple pages does not keep any physical PostgreSQL connection open between requests; registry leases and active cursor counts remain bounded.
- **AC-17:** Cursor reuse concurrently cannot advance twice; limit enforcement accounts for cumulative row budgets across pages, not just one page.
- **AC-18:** Documented best-effort consistency does not claim repeatable snapshot semantics when the database changes between pages.

### Session affinity, operations and delivery

- **AC-19:** HypoPG create/list/explain/reset operate on the same physical session within a tuning call; cancellation and exceptions clean state before the connection is reused.
- **AC-20:** Parallel calls to different authorized databases remain isolated; one unavailable DB or exhausted pool does not route the request to another database.
- **AC-21:** Ephemeral integration tests exercise a real HypoPG-equipped PostgreSQL instance; relevant tests are not silently skipped and CI distinguishes unit from integration.
- **AC-22:** Metrics do not include credentials, SQL bind data, raw rows, or unbounded-cardinality identifiers; operational failures are diagnosable.
- **AC-23:** Docker license/vendor/source labels, `justfile`, dependency lock, CI, and English/pt-BR documentation are consistent with the shipped fork.
- **AC-24:** Each implementation phase has its own plan, tests, reviewer gate and rollback/migration notes. No functionality is marked complete solely because a specification exists.

## 13. Mandatory risk review before implementation

1. **Offset pagination correctness:** Even with `ORDER BY`, inserts/deletes can shift positions. Document this instead of promising full consistency.
2. **Keyset eligibility:** Determinism, uniqueness, `NULL`, sort direction, composite keys, existing `LIMIT`/`OFFSET`, joins and user-defined expressions require explicit acceptance/refusal rules.
3. **Cursor identity:** stdio local sessions and HTTP authenticated principals differ. Never expose cross-user continuation tokens through a shared store.
4. **Response compatibility:** MCP `structuredContent` is additive, but changing an existing string representation or row count can still break clients. Stage and test.
5. **Physical sessions:** Holding one connection during long index analysis is intentional but needs timeouts, pool admission policy and cleanup guarantees.
6. **Error redaction:** psycopg exceptions, Python exception chains, logger interpolation, and Docker shell traces can expose secrets even when the top-level response is sanitized.
7. **SQL safety:** Read-only transaction, parser allowlist, function resolution, extension behavior, SQL budgets and role privileges form multiple layers; no one layer is sufficient alone.
8. **Configuration migration:** The strict defaults proposed in §4 are not permission to enable them abruptly in an existing release. Approve the rollout separately.

## 14. Verification strategy

**Preflight:** read branch HEAD, diff against `main`, `pyproject.toml`, `uv.lock`, tool signatures, CI workflows and current tests; establish a known-green/known-red baseline before edits.

**Unit tests:** policy parsing; boundaries; token entropy/state/TTL; AST eligibility; offset/keyset generation; pagination response metadata; byte-budget serializer; MCP structured errors; redaction; lease/cancellation semantics.

**Integration tests:** throwaway Docker PostgreSQL, isolated databases with distinct markers, least-privilege role, temporary schema, HypoPG in required runs, parallel cross-DB work, mid-pagination revocation, restart/TTL, very large queries, statement_timeout, explicit DB mismatch, shutdown.

**Transport tests:** stdio existing contract; streamable HTTP auth/principal-binding and TLS behind test ingress; error/structured-output compatibility with representative MCP clients.

**Verification commands** (to be pinned/adjusted in each implementation plan):

```bash
uv lock --check
uv sync --locked --group dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q tests/unit
uv run pytest -q tests/integration
```

Do not claim these commands passed unless actually executed with their exit status recorded. For integrations, absence of Docker or required HypoPG is a **failed verification gate**, not permission to report success.

## 15. References

- [Target feature branch](https://github.com/Diaszano/postgres-mcp/tree/feature/multi-database)
- [Current server and MCP tool definitions](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/server.py)
- [Database registry](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/database_registry.py)
- [Database catalog](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/database_catalog.py)
- [SQL driver](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/sql_driver.py)
- [Safe SQL driver](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/sql/safe_sql.py)
- [HypoPG tuning flow](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/src/postgres_mcp/index/dta_calc.py)
- [Docker entrypoint](https://github.com/Diaszano/postgres-mcp/blob/feature/multi-database/docker-entrypoint.sh)
- [MCP specification: tool result, `structuredContent`, `isError`](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [Psycopg: concurrent/session behavior](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
- [Psycopg: async pool connection context](https://www.psycopg.org/psycopg3/docs/api/pool.html)
- [PostgreSQL: LIMIT and OFFSET](https://www.postgresql.org/docs/current/queries-limit.html)
- [PostgreSQL: DECLARE cursor](https://www.postgresql.org/docs/current/sql-declare.html)

## 16. Approval checkpoint

**Owner review required** on the proposed decisions: Approach B; initial keyset eligibility limited to one non-null ascending unique column; strict rejection vs clamping; in-memory cursor state with 300s TTL; cumulative 5,000-row ceiling; guarded rollout for legacy callers; authentication requirements for remote HTTP; phase boundaries. After design approval, prepare one independent `superpowers:writing-plans` implementation plan per deliverable. **Do not implement, commit, publish, or deploy based solely on this draft.**
