# Plan 02 Task 3 report

Base: `094f8990f6236d35c98f2dba60833c4fc6142c50`.

## Implementation and interfaces

- `QueryAdmission(max_concurrency: int).run(operation: Callable[[], Awaitable[T]], timeout_seconds: int) -> T` admits work through one semaphore before invoking the operation. Task 5 must put the registry lease, checkout, execution and serialization inside that operation and reuse one admission instance per service.
- Queue waiting consumes the same monotonic request deadline as execution. Its bounded wait policy is the entire remaining request deadline, without a separate queue grace period. The fifth request at concurrency four cannot invoke its operation or acquire a registry lease while waiting.
- The only context variable is a private optional monotonic deadline. Its token is reset in `finally`, including timeout and external cancellation. `remaining_query_seconds() -> float | None` returns `None` outside admission, returns a positive remaining duration inside it, and raises sanitized `PublicToolError(code="QUERY_TIMEOUT", retryable=True)` after expiry.
- `asyncio.timeout_at` cancels overdue asynchronous work; semaphore context cleanup releases permits. PostgreSQL `QueryCanceled` and Python deadline expiry map to the same sanitized `QUERY_TIMEOUT`. External `CancelledError` propagates. A final clock check rejects a synchronous serialization result that completed after its deadline.
- `SqlDriver.execute_query` retains its signature. When called inside admission, it starts a transaction if needed, reads the remaining budget after checkout/transaction setup, and executes parameterized `SELECT pg_catalog.set_config('statement_timeout', %s, true)`. Milliseconds round up to at least one, so an almost exhausted deadline cannot disable PostgreSQL's timeout with zero.
- Existing commit/rollback paths clean up the transaction and clear the local timeout. Restricted execution installs the timer before function-resolution validation. Calls outside admission keep their existing SQL and transaction behavior.

Production scope is the new admission module and 13 added driver lines. Tests are the new unit admission and Docker integration timeout files. Existing SQL-driver callers, unit tests, safe-error mapping, configuration and tool signatures were checked; server orchestration belongs to Task 5.

## TDD evidence

1. `uv run --frozen --group dev pytest -q tests/unit/query_limits/test_admission.py::test_admission_before_pool_lease`

   RED: `1 failed in 0.11s`. The initial test used an explicit feature-contract assertion before importing the absent module: `AssertionError: QueryAdmission must bound work before a registry lease`. This was an assertion failure for the missing contract, not an import/dependency setup error. Once the module existed, tests were simplified to ordinary imports.

2. `uv run --frozen --group dev pytest -q tests/unit/query_limits/test_admission.py tests/integration/test_query_timeouts.py::test_statement_timeout_is_transaction_local`

   After admission implementation, RED for the driver: `1 failed, 6 passed in 2.30s`. The new Docker integration test observed zero milliseconds rather than a positive scoped timeout: `AssertionError: assert 0 < Decimal('0.000000')`.

3. `uv run --frozen --group dev pytest -q tests/unit/query_limits/test_admission.py tests/integration/test_query_timeouts.py tests/unit/sql/test_sql_driver.py`

   First GREEN: `19 passed in 2.51s`. After strengthening the fifth-lease assertion and adding a pool-checkout deadline test plus an INSERT rollback assertion, final focused GREEN: `20 passed in 3.74s`.

   A test-only edit temporarily placed an import inside a function, producing `IndentationError` during collection; it was corrected before the final focused run. No dependency or production workaround was involved.

## Coverage and disposable database

Six admission unit tests cover saturation before lease acquisition, cancelled waiters, permit cleanup/deadline reset, shared queue/execution time, synchronous completion after expiry, and sanitized PostgreSQL cancellation errors. Five integration cases cover local timeout restoration, slow-query cleanup in both ordinary and restricted mode, actual rollback of an INSERT on PostgreSQL cancellation, and reduction of SQL's timeout by prior pool waiting. Nine existing driver unit tests also pass.

All new integration tests use the repository's `multidb_postgres` fixture and a one-connection test pool. The fixture creates a disposable Docker PostgreSQL server with generated credentials and a non-superuser MCP role; the available image is `postgres-hypopg:16`. No user or production database is used. Docker has no blocker, and the focused run has no skips.

## Additional verification

- `uv run --frozen --group dev ruff check src/postgres_mcp/query_limits/admission.py src/postgres_mcp/sql/sql_driver.py tests/unit/query_limits/test_admission.py tests/integration/test_query_timeouts.py`: `All checks passed!`
- `uv run --frozen --group dev ruff format --check src/postgres_mcp/query_limits/admission.py src/postgres_mcp/sql/sql_driver.py tests/unit/query_limits/test_admission.py tests/integration/test_query_timeouts.py`: `4 files already formatted`.
- `uv run --frozen --group dev pyright src/postgres_mcp/query_limits/admission.py src/postgres_mcp/sql/sql_driver.py`: `0 errors, 0 warnings, 0 informations`. Pyright also prints an installed-version update notice.
- `git diff --check`: no output, exit zero.
- Full suite: `uv run --frozen --group dev pytest -q > /tmp/plan02-task3-full-pytest.log 2>&1` exited zero: `552 passed, 9 skipped, 1 xfailed in 158.07s (0:02:38)`. The nine skips occur in the existing DTA integration tests (`test_multi_column_indexes`, `test_storage_cost_tradeoff`, and `test_pareto_optimal_index_selection`, each on PostgreSQL 12/15/16). They are reported as skips, not successful validation; `-q` does not include their reason text. All five Task 3 integration cases passed.
- After the full suite, `docker ps --format '{{.Names}}'` showed only the two pre-existing unrelated containers (`vaio-fe16-test-vmhost`, `headroom-default`): test fixtures removed their disposable PostgreSQL containers.

## Limits and remaining work

Task 5 still needs to wrap the full service operation in admission; Task 6 owns broader registry/shutdown lifecycle coverage. Synchronous Python work cannot be preempted by asyncio; this task checks its deadline before returning a result. Policy/configuration already validate public integer options; fractional durations are used only inside focused tests to keep timeout fixtures short. No lockfile or dependency changes were needed.

Commit message: `feat: enforce SQL execution deadlines and concurrency`. This report is included in the Task 3 commit.
