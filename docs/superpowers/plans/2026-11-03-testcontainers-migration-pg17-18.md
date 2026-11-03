# Testcontainers Migration and PostgreSQL 17/18 Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the test container infrastructure to `testcontainers-python` for unified, leak-free container lifecycle management and expand test coverage to include PostgreSQL 17 and 18.

**Architecture:** Replace manual Docker SDK loops and ad-hoc container lifecycle tracking across `tests/utils.py` and `tests/integration/conftest.py` with `testcontainers-python` (`PostgresContainer` and `DockerContainer`). Leverage Testcontainers' automatic Ryuk reaper to guarantee resource cleanup even on crashes or abrupt cancellations, and update the test version parametrization to test PG 12, 15, 16, 17, and 18.

**Tech Stack:** Python 3.12, `uv`, `testcontainers[postgres]>=4.9.0`, Docker, PostgreSQL (12, 15, 16, 17, 18), `psycopg[binary]>=3.3.2`, `pytest`, `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-11-03-testcontainers-migration-pg17-18-design.md`

## Global Constraints

- Must use `uv` package management (`uv sync --group dev`, `uv lock --check`).
- Python version floor is `>=3.12` with Pyright static type checking in standard mode and Ruff linting rules (`line-length = 150`).
- No modifications to application code under `src/postgres_mcp/`.
- Must retain support for required PostgreSQL extensions (`hypopg` and `pg_stat_statements`) across all tested PG versions.
- Docker availability checks must fail clearly or skip gracefully when Docker daemon is not running, but never silently pass without executing tests.

## Review Focus

1. **Docker daemon unavailable:** When Docker is unreachable, unit/class fixtures in `tests/utils.py` must call `pytest.skip` rather than crashing unexpectedly, whereas integration tests in `tests/integration/conftest.py` must fail explicitly per existing project policy.
2. **Postgres readiness detection timeout:** If a container starts slowly, Testcontainers readiness wait strategy must give sufficient grace period (up to 60-90s) before timing out, surfacing useful container log output on failure.
3. **Connection URL driver format:** Ensure connection strings produced by Testcontainers helpers format as standard `postgresql://...` rather than defaulting to `postgresql+psycopg2://`, matching `psycopg3` compatibility throughout the test suite.
4. **Custom command arguments persistence:** Verify that PostgreSQL custom runtime flags (`-c shared_preload_libraries=pg_stat_statements`, `-c pg_stat_statements.track=all`) are properly passed to Testcontainers so extensions load at database boot.
5. **Image build caching:** Ensure custom `postgres-hypopg:{version}` images are built only when missing from local Docker image storage, preventing redundant recompilation on consecutive test runs.

---

### Task 1: Add Testcontainers Dependency to Project

**Files:**
- Modify: `pyproject.toml:34-43`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: None
- Produces: `testcontainers` and `testcontainers.postgres` available in the dev environment.

- [ ] **Step 1: Add testcontainers dependency to pyproject.toml**

Update `pyproject.toml` under `[dependency-groups.dev]` to include `"testcontainers[postgres]>=4.9.0"`.

- [ ] **Step 2: Sync and lock dependencies with uv**

Run: `uv add --dev "testcontainers[postgres]>=4.9.0"` or `uv sync --group dev`
Expected: Lockfile `uv.lock` updated, packages installed cleanly.

- [ ] **Step 3: Verify import and lockfile integrity**

Run: `uv run python -c "import testcontainers.postgres; print('testcontainers ready')"`
Expected: Prints `testcontainers ready` with exit code 0.
Run: `uv lock --check`
Expected: Passes with exit code 0.

- [ ] **Step 4: Commit dependency update**

```bash
git add pyproject.toml uv.lock
git commit -m "build(deps): add testcontainers[postgres] to dev dependencies"
```

---

### Task 2: Verify and Update HypoPG Build Support for PostgreSQL 17 and 18

**Files:**
- Modify: `tests/Dockerfile.postgres-hypopg:1-21`
- Modify: `scripts/ci/build_hypopg_image.sh:1-39`

**Interfaces:**
- Consumes: Docker engine with base images `postgres:17` and `postgres:18`.
- Produces: Verified Docker image tags `postgres-hypopg:17` and `postgres-hypopg:18`.

- [ ] **Step 1: Check and ensure Dockerfile.postgres-hypopg and build script support PG 17 and 18**

Verify that `tests/Dockerfile.postgres-hypopg` and `scripts/ci/build_hypopg_image.sh` handle PG 17 and 18 without build errors or missing apt packages. Ensure `postgresql-${PG_VERSION}-hypopg` is installed correctly.

- [ ] **Step 2: Test build of PG 17 and PG 18 images**

Run: `bash scripts/ci/build_hypopg_image.sh 17`
Expected: Image `postgres-hypopg:17` builds and verifies successfully with output ending in `✅ PostgreSQL 17 image with HypoPG verified successfully: postgres-hypopg:17`.
Run: `bash scripts/ci/build_hypopg_image.sh 18`
Expected: Image `postgres-hypopg:18` builds and verifies successfully with output ending in `✅ PostgreSQL 18 image with HypoPG verified successfully: postgres-hypopg:18`.

- [ ] **Step 3: Commit image build script changes if modified**

```bash
git add tests/Dockerfile.postgres-hypopg scripts/ci/build_hypopg_image.sh
git commit -m "ci: ensure hypopg image build supports postgres 17 and 18"
```

---

### Task 3: Refactor tests/utils.py and tests/conftest.py to Use Testcontainers

**Files:**
- Modify: `tests/utils.py:1-155`
- Modify: `tests/conftest.py:20-24`
- Test: `tests/unit/test_sql_execution.py` (or existing tests using `test_postgres_connection_string`)

**Interfaces:**
- Consumes: `testcontainers.postgres.PostgresContainer`, `postgres-hypopg:{version}`
- Produces: `create_postgres_container(version: str) -> Generator[Tuple[str, str], None, None]` yielding `(connection_string, version)` with automatic cleanup and expanded PG 17 & 18 matrix.

- [ ] **Step 1: Write a unit test verifying create_postgres_container with Testcontainers**

Create a fast test in `tests/unit/test_container_lifecycle.py` that verifies `create_postgres_container` yields a valid URI and cleans up after exit:
```python
def test_create_postgres_container_yields_connection():
    from tests.utils import create_postgres_container
    gen = create_postgres_container("postgres:16")
    uri, version = next(gen)
    assert uri.startswith("postgresql://")
    assert version == "postgres:16"
    try:
        next(gen)
    except StopIteration:
        pass
```

- [ ] **Step 2: Run test to check current behavior or failure**

Run: `uv run pytest tests/unit/test_container_lifecycle.py -v`

- [ ] **Step 3: Refactor create_postgres_container in tests/utils.py**

Refactor `create_postgres_container` to:
1. Ensure image `postgres-hypopg:{pg_version}` exists (building it via `docker` client if missing).
2. Instantiate `PostgresContainer(image=custom_image_name, port=5432, dbname="test_db", user="postgres", password="test_password")`.
3. Configure command flags for `shared_preload_libraries=pg_stat_statements` and `pg_stat_statements.track=all`.
4. Replace manual while-loop with Testcontainers context management / readiness probe, resolving connection string with `driver=None` or `get_connection_url(driver=None)`.
5. Remove `tests/unit/test_container_lifecycle.py` after verification if redundant.

- [ ] **Step 4: Update test_postgres_connection_string params in tests/conftest.py**

Update line 20 of `tests/conftest.py`:
```python
@pytest.fixture(scope="class", params=["postgres:12", "postgres:15", "postgres:16", "postgres:17", "postgres:18"])
def test_postgres_connection_string(request) -> Generator[tuple[str, str], None, None]:
    yield from create_postgres_container(request.param)
```

- [ ] **Step 5: Run tests against the expanded version matrix**

Run: `uv run pytest tests/unit/test_sql_driver.py -k "postgres" -v` (or representative unit test using the fixture)
Expected: Tests pass against PostgreSQL 12, 15, 16, 17, and 18.

- [ ] **Step 6: Commit test harness refactoring**

```bash
git add tests/utils.py tests/conftest.py
git commit -m "test: migrate create_postgres_container to testcontainers and add pg17/18"
```

---

### Task 4: Unify Integration Test Harness in tests/integration/conftest.py

**Files:**
- Modify: `tests/integration/conftest.py:80-138`
- Test: `tests/integration/test_multidb_connectivity.py`

**Interfaces:**
- Consumes: `testcontainers.core.container.DockerContainer` or `PostgresContainer`
- Produces: `_multidb_container(client, image) -> Generator[MultiDbPostgres, None, None]` or refactored Testcontainer fixture yielding `MultiDbPostgres`.

- [ ] **Step 1: Refactor _multidb_container to use Testcontainers**

Replace `client.containers.run(...)` and manual polling in `_multidb_container` with a Testcontainer instance (`DockerContainer` or `PostgresContainer`) using:
- `image`: configured from `IMAGE = os.environ.get("MULTIDB_PG_IMAGE", "postgres-hypopg:16")`
- `environment`: `{"POSTGRES_PASSWORD": admin_password}`
- `command`: `["-c", "shared_preload_libraries=pg_stat_statements", "-c", "pg_stat_statements.track=all"]`
- `ports`: exposed port `5432`
- wait strategy waiting for PostgreSQL ready or standard testcontainer postgres probe.
Yield configured `MultiDbPostgres` object with dynamic host, mapped port, and server version.

- [ ] **Step 2: Run integration tests to verify multi-database setup**

Run: `MULTIDB_PG_IMAGE=postgres-hypopg:16 uv run pytest tests/integration/test_multidb_connectivity.py -v`
Expected: All tests pass with 0 failures.

- [ ] **Step 3: Run integration tests with PG 17 and PG 18**

Run: `MULTIDB_PG_IMAGE=postgres-hypopg:17 uv run pytest tests/integration/test_multidb_connectivity.py -v`
Expected: Passes.
Run: `MULTIDB_PG_IMAGE=postgres-hypopg:18 uv run pytest tests/integration/test_multidb_connectivity.py -v`
Expected: Passes.

- [ ] **Step 4: Commit unified integration harness**

```bash
git add tests/integration/conftest.py
git commit -m "test: unify integration multidb container harness with testcontainers"
```

---

### Task 5: Quality Gates, Static Analysis, and Full Test Suite Verification

**Files:**
- Modify: `tests/README.md` (if documenting testcontainers usage)
- Modify: `tests/README.pt-BR.md`

**Interfaces:**
- Consumes: All updated test files, pyproject.toml, CI scripts.
- Produces: Clean pass across lint, formatting, type checking, and test suites.

- [ ] **Step 1: Run Ruff format and lint checks**

Run: `uv run ruff format --check .`
Run: `uv run ruff check .`
Expected: 0 errors, all checks pass.

- [ ] **Step 2: Run Pyright static type analysis**

Run: `uv run pyright`
Expected: 0 errors.

- [ ] **Step 3: Run Unit and Release test suites**

Run: `uv run pytest -q tests/unit tests/release`
Expected: All unit and release tests pass.

- [ ] **Step 4: Update test documentation**

Update `tests/README.md` and `tests/README.pt-BR.md` to mention `testcontainers-python` and the support for PostgreSQL 17 and 18.

- [ ] **Step 5: Final commit for documentation and verification**

```bash
git add tests/README.md tests/README.pt-BR.md
git commit -m "docs: document testcontainers adoption and pg 17/18 test matrix"
```
