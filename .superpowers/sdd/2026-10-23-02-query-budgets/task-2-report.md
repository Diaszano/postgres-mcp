# Task 2: Strict query budget overrides

## Changes

- Added frozen `QueryLimits` and `resolve_query_limits` with exact integer validation, default resolution, hard-limit rejection, and disabled-mode override rejection.
- Appended `max_rows` and `timeout_seconds` to `execute_sql` after its existing `database` parameter and resolve limits before `get_sql_driver`.
- Preserved constructed `PublicToolError` instances in the safe public error mapper so stable budget error codes survive response formatting.
- Added policy tests and updated the existing `execute_sql` signature assertion to verify argument order and defaults.

## RED

Command:

```sh
uv run --frozen --group dev pytest -q tests/unit/query_limits/test_policy.py::test_agent_override_within_ceilings
```

Result before implementation:

```text
FAILED tests/unit/query_limits/test_policy.py::test_agent_override_within_ceilings
KeyError: 'max_rows'
1 failed in 0.12s
```

The failure showed the public tool did not yet expose the budget argument contract. The frozen environment collected the test successfully.

## GREEN

Focused policy tests:

```sh
uv run --frozen --group dev pytest -q tests/unit/query_limits/test_policy.py
.........                                                                [100%]
9 passed in 0.04s
```

Query limit and multi-database compatibility tests:

```sh
uv run --frozen --group dev pytest -q tests/unit/query_limits tests/unit/test_multidb_server.py
84 passed in 0.51s
```

Full unit suite:

```sh
uv run --frozen --group dev pytest -q tests/unit
501 passed, 1 xfailed in 75.54s
```

## Scope and concerns

The policy resolves and validates per-call budgets before driver checkout. This task does not yet apply resolved row or timeout limits to SQL execution; later query execution tasks consume the `QueryLimits` contract. No database or integration test requiring PostgreSQL was run.

Ruff check on changed Python files: passed.

## Round 1 review fix: strict MCP input validation

The registered FastMCP tool previously declared ordinary `int | None` fields. Added `Field(strict=True)` to the `Annotated` types for both budget inputs. The boundary test registers `execute_sql` with FastMCP and calls its `ToolManager.call_tool`, then verifies text, float, and bool inputs fail before the mocked driver is called, while integer and null inputs pass validation and reach the driver.

RED command:

```sh
uv run --frozen --group dev pytest -q tests/unit/query_limits/test_policy.py::test_registered_tool_rejects_coercive_budget_inputs
```

Result before the strict annotations:

```text
Failed: DID NOT RAISE <class 'mcp.server.fastmcp.exceptions.ToolError'>
1 failed in 0.15s
```

GREEN boundary test:

```sh
uv run --frozen --group dev pytest -q tests/unit/query_limits/test_policy.py::test_registered_tool_rejects_coercive_budget_inputs
.                                                                        [100%]
1 passed in 0.03s
```

Regression tests and lint after the fix:

```text
uv run --frozen --group dev pytest -q tests/unit/query_limits tests/unit/test_multidb_server.py
85 passed in 0.48s

uv run --frozen --group dev ruff check --output-format concise src/postgres_mcp/server.py tests/unit/query_limits/test_policy.py
All checks passed!
```
