# PostgreSQL MCP Release Checklist & Rollback Procedure

Release Version: `0.3.0`

## Pre-Release Verification Checklist

Execute the following verification gates before tagging and publishing any release:

- [ ] **Dependency Lock**: Run `uv lock --check` to ensure `uv.lock` is consistent with `pyproject.toml`.
- [ ] **Lint and Formatting**: Run `just lint` (`uv run ruff check .` and `uv run ruff format --check .`).
- [ ] **Static Type Analysis**: Run `just typecheck` (`uv run pyright`).
- [ ] **Unit Test Suite**: Run `just test-unit` (`uv run pytest -q tests/unit`).
- [ ] **Integration Test Suite**: Run `just test-integration` across PostgreSQL 16 and 17 with HypoPG extension containers.
- [ ] **Performance Benchmarks**: Run `uv run --group dev pytest -q tests/performance --run-performance`.
- [ ] **Smoke Tests**: Run `uv run pytest -q tests/release/test_smoke.py`.
- [ ] **Package Build**: Run `uv build` and inspect wheel contents under `dist/`.
- [ ] **Container Build**: Verify multi-architecture container build for `linux/amd64` and `linux/arm64`.

## Production Rollback & Emergency Backout Procedure

If regressions, unexpected query rejections, or client incompatibilities emerge in production:

1. **Disable Query Guardrails**:
   Set `DATABASE_QUERY_GUARDRAILS_ENABLED=false` in the server environment. This immediately restores legacy statement behavior without breaking connection pools or dropping security warnings.
2. **Disable Cursor Pagination**:
   Set `DATABASE_PAGINATION_ENABLED=false` if clients have issues consuming continuation tokens.
3. **In-Memory Store Isolation**:
   The cursor cache is strictly in-process and memory-bounded with zero external storage dependencies (no external cache services or broker daemons required). Restarting the container or process cleanly flushes active cursor state without persistent corruption.
4. **Binary / Container Rollback**:
   Re-deploy the previous container tag or wheel release.
