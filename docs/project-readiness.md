# Project readiness baseline

Baseline captured on 2026-11-03 from local commit `cdb81019c61a2cb1f1590e4b42af79b0ff8b95ee` on `docs/project-readiness-implementation`. This is a point-in-time check; the repository's remote `main` was `764c0a4e59639e43c1a502e287d227631d131bdc` when inspected.

## Evidence matrix

| Area | State | Evidence | Next action |
|---|---|---|---|
| Lockfile | Verified | `uv lock --check` — exit 0; 83 packages resolved. | Keep this check in local and CI verification. |
| Lint and formatting | Verified outside project sync | `uvx --from ruff==0.14.13 ruff check .` — exit 0; `ruff format --check .` — exit 0, 147 files. | Restore `uv run` checks after resolving the runtime dependency build failure below. |
| Type and unit/release tests | Blocked | `uv run pyright` and `uv run pytest -q tests/unit tests/release` — exit 1 before execution: locked `pglast` source fails to compile because `postgres_deparse.h` is missing. The same install failure prevents the planned `uv run ruff` commands from starting. | Inspect the pinned source artifact and supported distribution in Task 3; do not treat blocked checks as passes. |
| Package build | Verified | `uv build` — exit 0; produced sdist and wheel for version 0.3.0. This does not install runtime dependencies. | Task 2 must install the built wheel in a clean environment and verify the installed module path. |
| Local tools | Partial | Host default: Python 3.15.2; `uv` 0.13.7 installed from Astral's installer after no executable was found in PATH or standard local install paths. `uv` selected CPython 3.12.3 for this project. Docker 29.1.3 client and daemon respond. `gh auth status` confirmed an active account; token values were not recorded. | Run the disposable PostgreSQL and container flows in Task 2. |
| Repository and merge settings | Verified remotely | GitHub metadata: public, active, default branch `main`; squash, merge and rebase are enabled; auto-merge is enabled. Only `Diaszano` appears in the collaborator list and has admin permission. | Align repository proposal with a single active collaborator in Task 7. |
| Branch protection | Verified absent for `main` | GitHub rulesets endpoint returned `[]`; `gh api .../branches/main/protection` returned 404 `Branch not protected`. | Propose concrete settings in Task 7; do not apply them during this work. |
| Checks and recent runs | Mixed | Latest `main` commit had seven completed Dependabot checks (six `Dependabot`, one `.github/dependabot.yml`), all successful. The 10 most recent Actions runs were CI pushes from Dependabot branches and all were completed with failure; example: [run 41661206742](https://github.com/Diaszano/postgres-mcp/actions/runs/41661206742). | Inspect failure causes while handling CI/release tasks; don't infer that all CI runs fail from this sample alone. |
| Releases and GHCR | Pending | Releases API returned an empty list. GHCR package listing failed with 403 because the active credential lacks `read:packages`; package existence, visibility and manifests remain unknown. | Verify GHCR through an authorized read path in Task 7/8; do not assume a published image. |

## Prioritized findings

1. **Installation and verification blocker:** `pyproject.toml` pins `pglast==7.11` to a source archive. During dependency sync, compilation fails at `pg_query.h:7` because `postgres_deparse.h` is absent. Lint, type and test commands invoked through `uv run` therefore never reached their checks. The separate Ruff tool runs pass, but they do not make the blocked commands green.
2. **Delivery confidence gap:** the recent Actions sample contains repeated failed Dependabot CI runs, and no release is listed. The cause of those runs and any image publication must be confirmed before claiming delivery is healthy.
3. **Governance gap:** `main` has no branch protection or rulesets. The repository has one listed collaborator, so any review requirement must account for a sole maintainer.
4. **Remote visibility gap:** the available GitHub credential cannot read GHCR packages. Image state remains unknown, not absent.

## Remote evidence

- Repository metadata, rulesets, branch protection, releases, workflow runs, checks and collaborator permission were read from GitHub on 2026-11-03. The collaborator list was read with `gh` because the GitHub plugin did not expose that collection.
- Branch protection was readable with `gh` even though the GitHub plugin returned 403 for that endpoint. The authenticated CLI reported `Branch not protected` (404).
- GHCR inspection was attempted with `gh`; GitHub denied it for missing `read:packages` scope. No credential was changed.
- No database connection strings, tokens, or raw command logs are included here.

## Task 2 verification

- The install blocker was a `pglast` 7.11 source archive missing `postgres_deparse.h`. This repository now uses `pglast==7.22` from PyPI and no longer pins the broken direct source URL. The upstream changelog documents the missing-header fix in 7.17; the project's `pglast` v7 line targets PostgreSQL 17. See [pglast changes](https://github.com/lelit/pglast/blob/v8/CHANGES.rst) and [pglast project](https://github.com/lelit/pglast).
- `uv run ruff check .` and `uv run ruff format --check .` now run with the project environment. `uvx --from . postgres-mcp --help` succeeds.
- `uv run pyright` now runs but exits 1 with 292 errors across 34 files. The Task 1 run could not start because dependency installation failed, so this is the first measured type-check result; determine its scope and fix the blocking causes in Task 3.
- Wheel smoke, run from the repository root:

  ```bash
  uv build
  wheel_test=$(mktemp -d /tmp/postgres-mcp-wheel.XXXXXX)
  uv venv --python 3.12 "$wheel_test/venv"
  uv pip install --python "$wheel_test/venv/bin/python" "$PWD/dist/postgres_mcp-0.3.0-py3-none-any.whl"
  (cd "$wheel_test" && "$wheel_test/venv/bin/postgres-mcp" --help && "$wheel_test/venv/bin/python" -c 'import importlib.metadata, pathlib, postgres_mcp; print(importlib.metadata.version("postgres-mcp")); print(pathlib.Path(postgres_mcp.__file__).resolve())')
  ```

  Result: help exits 0, version is `0.3.0`, and the module path is under the temporary venv's `site-packages`.
- The first local Docker build failed because `.dockerignore` excluded the `README.md` required by package metadata. The ignore list now re-includes `README.md`; `docker build --tag postgres-mcp:readiness --build-arg REVISION=local-readiness .` and `docker run --rm postgres-mcp:readiness --help` both exit 0. No image was pushed.
- `bash scripts/ci/build_hypopg_image.sh 16` built and verified the disposable PostgreSQL 16 image. `uv run pytest -q tests/integration/test_mcp_result_wire.py tests/integration/test_restricted_security.py` passed 15 tests; this includes a real MCP client session against the disposable database, tool discovery, a permitted SELECT, a blocked INSERT, and an error response with no password.
- `uv run pytest -q tests/unit/test_documentation_contract.py tests/release/test_smoke.py` passed 8 tests. `uv run pytest -q tests/unit/test_query_service.py tests/unit/sql/test_safe_sql.py tests/unit/security/test_sql_policy.py tests/unit/test_mcp_response.py tests/unit/test_error_contract.py` passed 143 tests.
- The wire test initially exposed that FastMCP rejected the server's structured error against the inferred list output schema. `format_error_response` now includes the expected `result` content alongside its structured error; success output and tool signatures remain unchanged. The regression passed after this correction.
