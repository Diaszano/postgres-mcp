# Multi-database Review Fixes Implementation Plan

**Execution note (2026-10-23):** Task 1 was a false positive: `_default_factory()` already used `pool_max_size`, and its proposed regression test passed before any edit. Task 2 was implemented in `cc9d828`; final review found that an idle revoked pool also needed immediate cleanup, fixed in `6827c80`. Unit tests passed locally with `pglast==7.21`; the pinned `7.11` could not be installed because that release is absent from PyPI. The Docker integration suite did not finish in this environment.

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Track each step with its checkbox.

**Goal:** Honor the configured per-pool connection limit and reject a database removed by a catalog refresh before granting a new lease.

**Architecture:** Keep both fixes in `DatabaseRegistry`. Its factory already owns pool construction, and `acquire()` already reads the catalog after `authorize()`; the latter only needs to use that fresh result before `_lease()`.

**Tech Stack:** Python 3.12+, asyncio, pytest/pytest-asyncio, psycopg pool.

**Spec:** The two findings in the 2026-10-23 review of `main...feat-multi-database` in this conversation.

## Global Constraints

- Keep the existing configuration names, registry interface, authorization errors, and pool lifecycle.
- Add no dependency or configuration option.
- Make the change in the `feat-multi-database` worktree; the original registered worktree path is unavailable in this environment.

## Files

- Modify `src/postgres_mcp/sql/database_registry.py`: pass the configured pool size and check the latest authorized names.
- Modify `tests/unit/sql/test_database_registry.py`: cover the pool constructor arguments and catalog revocation between the two reads.

## Review Focus

- A pool limit different from the registry limit reaches `DbConnPool` unchanged (Task 1 test).
- A newly requested bank removed after `authorize()` does not open a pool (Task 2 test).
- An already open bank removed after `authorize()` receives no new lease (Task 2 test).
- A still-authorized bank continues to acquire normally (existing registry tests, run in Task 2).
- A revoked pool with an existing lease drains after that lease ends (existing revocation test, run in Task 2).

---

### Task 1: Apply the per-pool connection limit

**Files:** `src/postgres_mcp/sql/database_registry.py:85`, `tests/unit/sql/test_database_registry.py`

**Interfaces:** `_default_factory(name: str) -> DbConnPool` consumes `DatabaseConfig.pool_max_size` for `DbConnPool.max_size`; `DatabaseConfig.max_pools` remains the registry entry limit.

- [x] Add `test_default_factory_uses_pool_max_size`: create a config with `max_pools=8` and `pool_max_size=5`, replace `database_registry.DbConnPool` with a mock, call `_default_factory("app_testing")`, and assert `min_size=0` and `max_size=5` in the constructor call.
- [x] Run `uv run --python 3.12 --group dev pytest tests/unit/sql/test_database_registry.py::test_default_factory_uses_pool_max_size -q`; expect failure showing `max_size=8`.
- [x] Change `_default_factory` to pass `self._config.pool_max_size` as `max_size`.
- [x] Run the same test; expect one pass.
- [x] Commit the two files as `fix: honor per-database pool size`.

### Task 2: Recheck authorization after a catalog refresh

**Files:** `src/postgres_mcp/sql/database_registry.py:113`, `tests/unit/sql/test_database_registry.py`

**Interfaces:** `acquire(database: str | None = None)` must raise the same `ValueError("Database <name> is not available")` as `DatabaseCatalog.authorize()` when the second `names()` result omits the requested name. It must not call `_lease()` in that case.

- [x] Add a parametrized `test_refresh_revocation_blocks_new_lease` for `already_open=False/True`: arrange an authorized first read and a second `names()` result excluding `app_development`; assert the new `acquire("app_development")` raises `ValueError`, does not create a pool when closed, and does not increase `active_leases` when open.
- [x] Run `uv run --python 3.12 --group dev pytest tests/unit/sql/test_database_registry.py::test_refresh_revocation_blocks_new_lease -q`; expect both cases to fail because `acquire()` proceeds to `_lease()`.
- [x] In `acquire()`, after the second `names()` call and before `_lease()`, reject `name` when it is absent from `names`; retain the existing `_sweep()` behavior for revoked pools.
- [x] Run `uv run --python 3.12 --group dev pytest tests/unit/sql/test_database_registry.py -q`; expect all registry tests to pass, including the new cases and existing revocation tests.
- [x] Commit the two files as `fix: reject databases revoked during acquisition`.

### Task 3: Verify the branch

**Files:** No changes expected.

- [x] Run `uv run --python 3.12 --group dev pytest tests/unit/sql/test_database_catalog.py tests/unit/sql/test_database_registry.py tests/unit/test_multidb_server.py -q`; expect all tests to pass.
- [x] Run `git diff --check main...HEAD` and `git status --short`; expect no whitespace errors and only intended changes.
- [x] If `uv` still cannot resolve `pglast==7.11` in this environment, record the dependency blocker and do not report the tests as passing.
