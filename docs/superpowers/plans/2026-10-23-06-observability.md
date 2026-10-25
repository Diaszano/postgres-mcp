# Operational Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pool, query, pagination and degraded-state behavior diagnosable through opt-in low-cardinality metrics and safe request logging.

**Architecture:** Define a no-op metrics port with optional Prometheus adapter and instrument existing Registry/QueryExecutionService/PaginationService at boundaries; no global metrics from individual SQL values.

**Tech Stack:** Python 3.12, contextvars, Prometheus client optional extra, pytest

**Spec:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md` — FR-OPS-01/02; AC-20/22

**Dependencies:** Plans 02 and 04 for query/pagination events; plan 05 for runtime injection. Can land after them as an independent optional feature.

**Status:** Fully implemented, verified, and complete.

## Global Constraints

- Base all changes on `feature/multi-database`; compare live HEAD, `main...HEAD`, tool signatures and CI before editing; do not redo implemented pool sizing or revocation checks.
- Python >=3.12; preserve `DATABASE_URI`, legacy single-database behavior, `DATABASE_AUTO_DISCOVER`, PostgreSQL same-instance scope, and existing named/positional MCP parameters.
- English code, tests, documentation identifiers and Conventional Commit messages; public README content also in pt-BR where required.
- TDD for each code task: red test, minimal implementation, green focused tests, independent review gate, English Conventional Commit. Do not claim unexecuted tests passed.
- Never operate on user/production databases: integration tests start isolated disposable Docker PostgreSQL; HypoPG tests require an image with the extension installed (skips are not success).
- Never log connection URIs, raw SQL parameters, query rows, secrets or unredacted exceptions; cancellation and errors must release locks, sessions and pools.
- The spec is a PROPOSED design; planning is requested, but implementation, commits, publication and deployment still require explicit approval. Resolve owner-gated policy decisions before implementation.

**Acceptance criteria covered:** AC-20, AC-22 (see parent design for normative definitions).

## File Structure & Ownership

- **Define metrics adapter and optional export:** `src/postgres_mcp/observability/metrics.py`, `tests/unit/observability/test_metrics.py`.
- **Instrument registry, query admission and cursors:** `tests/unit/observability/test_instrumentation.py`.
- **Add safe operation identifiers and readiness signals:** `src/postgres_mcp/observability/logging.py`, `src/postgres_mcp/observability/status.py`, `tests/unit/observability/test_logging_status.py`.
- **Benchmark under modest-memory and concurrency constraints:** `tests/performance/test_query_budget_benchmark.py`, `tests/performance/test_pool_fairness.py`, `tests/performance/conftest.py`.

## Review Focus

- **Metrics do not contain database URI, SQL text, PII, row values or arbitrary database-name labels** — Task 1.
- **Bounded cardinality despite many discovered database names** — Tasks 1 and 2.
- **Startup readiness is distinct from a database currently unavailable** — Task 3.
- **Cancellation increments outcome counters once and releases inflight gauges** — Task 2.
- **Disabled metrics do not add network listener or meaningful overhead** — Task 1.

---

### Task 1: Define metrics adapter and optional export

**Files:**
- Create: `src/postgres_mcp/observability/metrics.py`
- Create: `tests/unit/observability/test_metrics.py`
- Modify: `pyproject.toml`, `uv.lock`

**Interfaces:** Export listener loopback-only or integrated with authenticated ingress; no public unauthenticated metrics endpoint.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_noop_metrics_by_default` — with metrics disabled no listener, counters or external dependency required.
  - `test_prometheus_labels_are_allowlisted` — only operation/outcome/mode labels; no raw DB names, SQL, cursor token, host, role or URI.
  - `test_instrumentation_cardinality_fixed` — 1000 DB names do not create 1000 series.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/observability/test_metrics.py::test_noop_metrics_by_default`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Create `MetricsSink` Protocol and `NoopMetrics` with `record_query`, `record_pool`, `record_cursor` methods; optional `PrometheusMetrics` adapter behind explicit configuration.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/observability/test_metrics.py` and `uv lock --check``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: add opt-in low-cardinality metrics"`.

### Task 2: Instrument registry, query admission and cursors

**Files:**
- Modify: `src/postgres_mcp/sql/database_registry.py:69-278`
- Modify: `src/postgres_mcp/application/query_service.py`
- Modify: `src/postgres_mcp/pagination/cursors.py`
- Create: `tests/unit/observability/test_instrumentation.py`

**Interfaces:** No per-query SQL, role, database name or user ID labels.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_registry_lifecycle_gauges` — opening/open/closing/failed pool states and active leases reflect scripted transitions.
  - `test_queries_histogram_and_errors` — duration, rejects, timeouts, truncated outcomes recorded exactly once.
  - `test_cursor_expiration_metrics` — token issue/consume/expiry/eviction counted without token labels.
  - `test_cancel_decrements_inflight` — cancelled task leaves zero active gauge.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/observability/test_instrumentation.py::test_registry_lifecycle_gauges`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Inject `MetricsSink` into existing services as an optional constructor dependency and call it only at stable lifecycle transitions; no additional DB queries to collect metrics.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/observability/test_instrumentation.py tests/unit/sql/test_database_registry.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: instrument database query and cursor lifecycle"`.

### Task 3: Add safe operation identifiers and readiness signals

**Files:**
- Create: `src/postgres_mcp/observability/logging.py`
- Create: `src/postgres_mcp/observability/status.py`
- Modify: `src/postgres_mcp/app.py`
- Create: `tests/unit/observability/test_logging_status.py`

**Interfaces:** No new unauthenticated remote status endpoint; status may surface via loopback metrics/authorized tool.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_request_id_per_tool_operation` — contextvar trace id propagates through async call; no cross-request contamination.
  - `test_readiness_not_equal_database_health` — running MCP with transient failed discovery reports ready+degraded rather than falsely healthy database.
  - `test_sanitized_failure_logging` — log fields include error code and class only; no plaintext SQL or credentials.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/unit/observability/test_logging_status.py::test_request_id_per_tool_operation`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Implement `operation_context(request_id: str)` contextmanager and `RuntimeStatus` model containing ready/degraded per system; annotate safe metrics/logs, document health modes.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/unit/observability/test_logging_status.py``. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "feat: report degraded database status safely"`.

### Task 4: Benchmark under modest-memory and concurrency constraints

**Files:**
- Create: `tests/performance/test_query_budget_benchmark.py`
- Create: `tests/performance/test_pool_fairness.py`
- Create: `tests/performance/conftest.py`
- Modify: `tests/README.md`

**Interfaces:** Benchmark results need measured hardware/versions, not invented SLA or absolute latency claims.

- [x] **Step 1: Write failing focused tests** covering these exact scenarios/assertions:
  - `test_large_result_memory_bound` — assert peak memory remains bounded rather than scaling with 1 million rows.
  - `test_pool_fairness_under_paginated_load` — page requests and long HypoPG work make progress without starvation.
  - `test_metrics_cost_budget` — capture overhead relative to disabled metrics and document measured range.
- [x] **Step 2: Verify red.** Run `uv run --group dev pytest -q tests/performance/test_query_budget_benchmark.py::test_large_result_memory_bound`. Expected: FAIL for missing behavior or contract (not an import/dependency setup failure).
- [x] **Step 3: Implement minimal production change.** Add opt-in performance suite with repeatable fixture and thresholds selected from measured CI baseline; it must not make regular unit tests flaky.
- [x] **Step 4: Verify green.** Run ``uv run pytest -q tests/performance --run-performance` after implementing named pytest marker/flag`. Expected: each named command completes successfully; if environment unavailable, record blocker and do not claim passing.
- [x] **Step 5: Commit (English Conventional Commit).** Stage only task files; `git commit -m "perf: benchmark bounded SQL execution and pools"`.

## Whole-Plan Verification Gate

1. Re-run the branch baseline and task-specific suites; Docker-required integration is a real gate, not a soft skip.
2. Run `uv lock --check`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, and `uv run pytest -q tests/unit` (report exact results, including any blocker).
3. Run applicable `uv run pytest -q tests/integration` with ephemeral PostgreSQL (and HypoPG when required).
4. Run `git diff --check main...HEAD` and inspect `git status --short`; verify no secrets/credentials in logs or commits.
5. Review all referenced spec acceptance criteria, old-tool compatibility tests, rollback notes, and a separate reviewer gate before merge.
6. Summarize commits, observed red/green tests, remaining risks and unverified assumptions. Do **not** publish, deploy or merge without explicit authorization.

## Execution Handoff

Have the owner review this plan alongside the parent spec before any production-code changes. Prefer **subagent-driven development** because security, connection-session correctness and tool contracts benefit from independent review after every task; use `superpowers:executing-plans` only if the owner chooses native execution.
