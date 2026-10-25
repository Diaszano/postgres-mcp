# PostgreSQL MCP Tests

This directory contains tests for the PostgreSQL MCP package.

## Running Tests

To run all tests:

```bash
uv run --frozen --group dev pytest
```

To run a specific test file:

```bash
uv run --frozen --group dev pytest tests/unit/test_obfuscate_password.py
```

To run a specific test:

```bash
uv run --frozen --group dev pytest tests/unit/test_db_conn_pool.py::test_pool_connect_success
```

## Test Structure

- **Unit Tests** (`tests/unit/`): Tests for individual components and functions
  - `test_obfuscate_password.py`: Tests for password obfuscation functionality
  - `test_db_conn_pool.py`: Tests for database connection pool
  - `test_sql_driver.py`: Tests for SQL driver and transaction handling
  - `test_database_config.py`, `test_access_mode.py`, `test_transport.py`: Multi-database configuration, access mode defaults and transports
  - `test_multidb_server.py`: Multi-database routing, `list_databases`, restricted mode, per-database extension checks and the MCP tool contract (nine tools plus `list_databases`, optional `database`, annotations, legacy defaults)

## Multi-database integration environment

`tests/integration/test_multi_database_integration.py` needs a running Docker daemon. The session fixture `multidb_postgres` (`tests/integration/conftest.py`) starts one throwaway PostgreSQL container on a random `127.0.0.1` port with a generated password, and removes it afterwards. It never connects to a local or user database, and a missing Docker daemon is a test error, not a skip.

- Databases: `app_development`, `app_testing`, `analytics` (visible) and `blocked_db` (`CONNECT` revoked from `PUBLIC` and from the MCP role). Each visible database has its own marker table.
- Role: `mcp_test_role` is not a superuser and has no `CREATEDB`. DDL, grants and `REVOKE` run only through the fixture's admin connection, inside the container.
- Image: `postgres-hypopg:16` (or `MULTIDB_PG_IMAGE` override). The test harness strictly requires HypoPG; missing Docker or extension is an explicit failure, never a silent skip or fallback. `pg_stat_statements` exists only in `app_development`.

```bash
uv run --frozen --group dev pytest -q tests/integration/test_multi_database_integration.py
```

The full suite (`uv run --frozen --group dev pytest -q`) therefore also needs Docker; unit tests alone (`tests/unit`) do not.

## Performance Benchmarks

Performance and budget benchmark tests are located in `tests/performance/` and are skipped by default during regular unit test runs.

To run the performance benchmark suite:

```bash
uv run --group dev pytest -q tests/performance --run-performance
```

The performance suite benchmarks bounded memory usage during large result encoding, metrics overhead budgets, and concurrency admission fairness.

## HypoPG session baseline

`tests/integration/test_hypopg_session_baseline.py` uses the separate `hypopg_postgres` fixture.
It requires the local `postgres-hypopg:16` image (or `MULTIDB_PG_IMAGE` override) and an installed
HypoPG extension. Missing Docker, image, or extension fails setup; these tests never skip or
fall back to plain PostgreSQL. Build the image through the existing Dockerfile:

```bash
docker build -f tests/Dockerfile.postgres-hypopg --build-arg PG_VERSION=16 --build-arg PG_MAJOR=16 -t postgres-hypopg:16 tests
uv run --frozen --group dev pytest -q -rx tests/integration/test_hypopg_session_baseline.py
```

The fixture creates a disposable container, prepares extensions and grants as admin, then
runs the tests as `mcp_test_role` without superuser, `CREATEDB`, or `CREATEROLE` privileges.
The role has `SELECT` on `hypopg_list_indexes`. Two connections prove that creation and reset
affect only their own session. An overlapping pool checkout deterministically routes independent
list/explain/reset calls away from the creator. The single-backend contract is a strict expected
failure with a dedicated exception; unrelated assertions and setup errors still fail the suite.
This characterizes existing pooled calls, and does not test a future pinned-session API.
