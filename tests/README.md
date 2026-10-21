# PostgreSQL MCP Tests

This directory contains tests for the PostgreSQL MCP package.

## Running Tests

To run all tests:

```bash
uv run pytest
```

To run a specific test file:

```bash
uv run pytest tests/unit/test_obfuscate_password.py
```

To run a specific test:

```bash
uv run pytest tests/unit/test_db_conn_pool.py::test_pool_connect_success
```

## Test Structure

- **Unit Tests** (`tests/unit/`): Tests for individual components and functions
  - `test_obfuscate_password.py`: Tests for password obfuscation functionality
  - `test_db_conn_pool.py`: Tests for database connection pool
  - `test_sql_driver.py`: Tests for SQL driver and transaction handling

## Multi-database integration environment

`tests/integration/test_multi_database_integration.py` needs a running Docker daemon. The session fixture `multidb_postgres` (`tests/integration/conftest.py`) starts one throwaway PostgreSQL container on a random `127.0.0.1` port with a generated password, and removes it afterwards. It never connects to a local or user database, and a missing Docker daemon is a test error, not a skip.

- Databases: `app_development`, `app_testing`, `analytics` (visible) and `blocked_db` (`CONNECT` revoked from `PUBLIC` and from the MCP role). Each visible database has its own marker table.
- Role: `mcp_test_role` is not a superuser and has no `CREATEDB`. DDL, grants and `REVOKE` run only through the fixture's admin connection, inside the container.
- Image: `postgres-hypopg:16` if present locally (build it with `tests/utils.py` runs), otherwise `postgres:16`. Override with `MULTIDB_PG_IMAGE`. `pg_stat_statements` exists only in `app_development`. Tests that need `hypopg` skip individually when the image lacks it.

```bash
uv run --frozen --group dev pytest -q tests/integration/test_multi_database_integration.py
```
