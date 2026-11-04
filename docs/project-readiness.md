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
| Checks and recent runs | Mixed | Latest `main` commit had seven completed Dependabot checks (six `Dependabot`, one `.github/dependabot.yml`), all successful. The 10 most recent Actions runs were CI pushes from Dependabot branches and all were completed with failure; example: [run 41661206742](https://github.com/Diaszano/pgscope/actions/runs/41661206742). | Inspect failure causes while handling CI/release tasks; don't infer that all CI runs fail from this sample alone. |
| Releases and GHCR | Pending | Releases API returned an empty list. GHCR package listing failed with 403 because the active credential lacks `read:packages`; package existence, visibility and manifests remain unknown. | Verify GHCR through an authorized read path in Task 7/8; do not assume a published image. |

## Prioritized findings

1. **Installation blocker (resolved in Task 2):** `pyproject.toml` now uses `pglast==7.22` from PyPI; the previously pinned source archive failed to compile because `postgres_deparse.h` was absent. Dependency-backed checks now run.
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
- `uv run ruff check .` and `uv run ruff format --check .` now run with the project environment. `uvx --from . pgscope --help` succeeds.
- `uv run pyright` runs but exits 1 with 292 diagnostics across 34 files: 35 in four source files and 257 in 30 test files. Most repeat a few categories (MCP content union typing, test mocks, optional AST fields, and protected test access). No runtime defect was demonstrated from those diagnostics, and the existing behavioral suites exercise the affected paths; broad annotation cleanup or suppressions are outside Task 3's evidence-based scope. Pyright remains a known failing check for Task 8.
- Wheel smoke, run from the repository root:

  ```bash
  uv build
  wheel_test=$(mktemp -d /tmp/pgscope-wheel.XXXXXX)
  uv venv --python 3.12 "$wheel_test/venv"
  uv pip install --python "$wheel_test/venv/bin/python" "$PWD/dist/pgscope-0.3.0-py3-none-any.whl"
  (cd "$wheel_test" && "$wheel_test/venv/bin/pgscope" --help && "$wheel_test/venv/bin/python" -c 'import importlib.metadata, pathlib, pgscope; print(importlib.metadata.version("pgscope")); print(pathlib.Path(pgscope.__file__).resolve())')
  ```

  Result: help exits 0, version is `0.3.0`, and the module path is under the temporary venv's `site-packages`.
- The first local Docker build failed because `.dockerignore` excluded the `README.md` required by package metadata. The ignore list now re-includes `README.md`; `docker build --tag pgscope:readiness --build-arg REVISION=local-readiness .` and `docker run --rm pgscope:readiness --help` both exit 0. No image was pushed.
- `bash scripts/ci/build_hypopg_image.sh 16` built and verified the disposable PostgreSQL 16 image. `uv run pytest -q tests/integration/test_mcp_result_wire.py tests/integration/test_restricted_security.py` passed 15 tests; this includes a real MCP client session against the disposable database, tool discovery, a permitted SELECT, a blocked INSERT, and an error response with no password.
- `uv run pytest -q tests/unit/test_documentation_contract.py tests/release/test_smoke.py` passed 8 tests. `uv run pytest -q tests/unit/test_query_service.py tests/unit/sql/test_safe_sql.py tests/unit/security/test_sql_policy.py tests/unit/test_mcp_response.py tests/unit/test_error_contract.py` passed 143 tests.
- The wire test initially exposed that FastMCP rejected the server's structured error against the inferred list output schema. `format_error_response` now includes the expected `result` content alongside its structured error; success output and tool signatures remain unchanged. The regression passed after this correction.

## Task 3 verification

- The existing developer-command test still asserted `pglast==7.11` after Task 2's required dependency fix. It now compares the locked pglast version with the exact dependency declared in `pyproject.toml`.
- `justfile` now has `lock-check`, and `test-unit` runs both `tests/unit` and `tests/release`, matching CI. CONTRIBUTING lists CI's lock, lint, format, type, unit/release, version metadata, and build commands. `just` is not installed in this environment, so `just --list` could not be run.
- `uv run pytest -q tests/unit tests/release`: 804 passed, 1 xfailed, with one stale governance test failure requiring a GHCR image in both READMEs. That assertion was updated to check the verified local Docker build instructions and absence of an unverified GHCR reference; its focused governance tests pass.
- `uv run pyright --outputjson`: exit 1, 292 diagnostics (35 source, 257 tests). The reported source issues are type-contract mismatches and optional-value analysis; no additional runtime correction was justified by an owner test. This remains an explicit readiness gap rather than a passing check.

## Task 4 verification

- `pull_request` CI now runs on `opened`, `synchronize`, `reopened`, and `edited`, so changing a PR title reruns validation. Bot-branch validation receives `github.event.pull_request.user.login`; a human editing or rerunning a Dependabot PR does not replace its author identity.
- The release caller grants `contents: write` and `packages: write` only to its job gated on a push to `main`. Reusable workflow permissions remain read-only by default; semantic release gets contents write, while image build/promotion get packages write. No `id-token: write` permission is requested because these jobs do not use OIDC.
- CI and release use uv 0.13.7. This exact version successfully ran `uv lock --check` against the current lockfile. Astral documents lockfile schema compatibility by version and that revisions remain backward-compatible; see [uv lockfile compatibility](https://docs.astral.sh/uv/concepts/resolution/) and [uv versioning](https://docs.astral.sh/uv/reference/policies/versioning/).
- CONTRIBUTING now lists `revert/` as a supported branch category, documents squash-title validation and Dependabot author semantics, and retains the verified local test commands.
- `uv run pytest -q tests/release/test_pr_metadata.py tests/release/test_ci_workflow.py tests/release/test_ci_release_gate.py tests/release/test_dependabot_config.py tests/release/test_action_security.py`: 28 passed. Ruff lint/format checks for the changed Python files and `uv lock --check` passed. Workflow behavior was validated from YAML; no GitHub workflow was dispatched.

## Task 5 verification

- The previous release step ran `version --print || true`, then compared the unchanged project version to itself. The workflow now checks the proposed version without suppressing errors, treats an unchanged version as a successful no-release, and otherwise runs the mutating `version` command before verifying the stamped project version and publishing assets for the exact tag. Python Semantic Release 10.7.0 documents that `--print` exits with the current version when no release is planned, while `version` creates/ pushes version changes by default and `publish --tag` uploads release assets. See [CLI commands](https://python-semantic-release.readthedocs.io/en/latest/api/commands.html).
- The scheduled Trivy repository scan now sets `exit-code: "1"` for HIGH/CRITICAL findings; no `continue-on-error` suppresses tool failures.
- `uv run pytest -q tests/release/test_release_workflow.py tests/release/test_release_bootstrap.py tests/release/test_release_build.py tests/release/test_release_metadata.py tests/release/test_security_failures.py`: 23 passed. The tests execute the actual workflow shell block with fake tools for version failure, no version change, and successful version/publish output sequencing.
- `uvx --from python-semantic-release==10.7.0 semantic-release --noop version --print` exited 0 without modifying the worktree; on this implementation branch the tool correctly reported that the branch is outside the configured release groups. No write token was used. A live release on `main` was not dispatched.

## Task 6 verification

- `promote_image.sh` and `scan_image.sh` are exercised as real subprocesses with fake Docker and Trivy executables. Invalid refs, absent Trivy, either architecture failing, changed immutable tags, registry inspection errors, and unknown alias version metadata all stop before promotion. Successful promotion records the exact digest and tags passed to `docker buildx imagetools create`.
- Recovery inspects floating aliases and reads `org.opencontainers.image.version` from every image platform. It updates an alias only when its current version is not newer than the requested release; unknown or inconsistent version metadata fails closed. Version tags may be repaired when absent or already at the same digest, and cannot be retargeted to another digest. The same concurrency group serializes release and recovery promotion.
- The Docker image now carries the release version label. Both release and retry builds pass the version associated with the exact checked-out commit, and the promotion script is run from that commit. Retry inputs are passed through environment variables and validated before use; the checked out commit must equal the requested tag commit.
- Trivy is installed in both promotion jobs from pinned `aquasecurity/setup-trivy` commit `81e514348e19b6112ce2a7e3ecbafe19c1e1f567` and fixed binary version `v0.76.1`. The scheduled repository scan uses pinned `trivy-action` commit `57a97c7e7821a5776cebc9bb87c984fa69cba8f1` and the same scanner version. These postdate the official [Trivy supply-chain advisory](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23); setup-trivy documents SHA-pinned installation and fixed version inputs at its [official README](https://github.com/aquasecurity/setup-trivy/blob/main/README.md).
- The changed Dockerfile built locally with `VERSION=0.3.0`; `docker image inspect` returned label `0.3.0`. No image was pushed.
- Required Task 6 suite: 37 passed; `bash -n` passed on both edited shell scripts; Ruff lint/format and `git diff --check` passed. The GHCR state remains unverified due missing `read:packages`, so no remote recovery or promotion was run.

## Task 7 verification

- Re-read remote Actions runs and check-runs on 2026-11-03. The latest `main` CI run was [41660883533](https://github.com/Diaszano/pgscope/actions/runs/41660883533); it failed before emitting any job entries. Its commit's visible checks were six Dependabot checks and `.github/dependabot.yml`, all successful. Therefore no successful CI status context was available to confirm exact check-run display names. `docs/github-settings.md` gives the workflow-declared job names as proposed contexts and requires confirming them on a successful run before enforcing them.
- GitHub ruleset documentation lists GitHub Apps among eligible bypass actors. Repository-specific availability of the built-in GitHub Actions app was not verified, so the PR ruleset is explicitly held in Evaluate until that exact bypass is verified or the release flow changes. No commit-message bypass or new credential is proposed.
- Governance docs now account for the sole observed admin, distinguish CODEOWNERS routing from enforced independent approval, and mark GHCR package access/publication as unverified. Release rollback digests are explicitly labeled placeholders. `SECURITY.md`, the PR template, CI/CD guide, release checklist, and plans index were reconciled to the changes in Tasks 2–6.
- Required Task 7 command: `uv run pytest -q tests/release/test_github_settings.py tests/release/test_release_docs.py tests/release/test_repository_governance.py tests/release/test_repository_conventions.py tests/unit/test_documentation_contract.py` — 26 passed.

## Task 8 final verification

Implementation verification was run from committed code at `b6ba76eca4251a19f1dae27bafdd675787cd064f` on 2026-11-03. This evidence is local unless marked remote.

| Check | Command or evidence | Result |
|---|---|---|
| Dependency lock | `uv lock --check` | Passed; 83 packages resolved. |
| Ruff | `uv run ruff check .`; `uv run ruff format --check .` | Passed; all checks passed, 147 files formatted. |
| Static analysis | `uv run pyright --outputjson` | Failed with 292 errors, 0 warnings, across 147 analyzed files. This is the known gap recorded in Task 2. |
| Unit and release suites | `uv run pytest -q tests/unit tests/release` | 833 passed, 1 xfailed. |
| Package build | `uv build` | Passed; built sdist and wheel for 0.3.0. |
| PostgreSQL 16 integration | `bash scripts/ci/build_hypopg_image.sh 16`; `MULTIDB_PG_IMAGE=postgres-hypopg:16 uv run pytest -q tests/integration` | Image and HypoPG activation passed; 86 passed, 18 skipped, 1 xfailed. |
| PostgreSQL 17 integration | `bash scripts/ci/build_hypopg_image.sh 17`; `MULTIDB_PG_IMAGE=postgres-hypopg:17 uv run pytest -q -rs tests/integration` | Image and HypoPG activation passed; 86 passed, 18 skipped, 1 xfailed. All skips were DTA cases with no generated recommendations or explicitly deferred scenarios. |
| Wheel smoke | Install built wheel into a clean Python 3.12 venv; run `pgscope --help`; inspect module path and package metadata | Passed; version 0.3.0, module loaded from the temporary venv's `site-packages`. |
| Container smoke | `docker build --tag pgscope:readiness-final --build-arg REVISION=readiness-final --build-arg VERSION=0.3.0 .`; `docker run --rm pgscope:readiness-final --help`; inspect OCI version label | Passed; help returned successfully and label is 0.3.0. No image was pushed. |
| Diff hygiene | `git diff --check` | Passed. |


The independent final review confirmed a readiness blocker: `.github/workflows/ci.yml` requires the `typecheck` job before the release handoff, and Pyright currently exits with 292 errors. Keep this CI gate intact; do not enforce the proposed branch check set or treat delivery as ready until the Pyright diagnostics are resolved and the gate passes.

### Remote status and pending work

- **Validated on GitHub:** Repository metadata, branch protection/rulesets, collaborator permission, check runs, releases, and recent Actions runs were inspected on 2026-11-03. `main` is unprotected; the only observed collaborator has admin access. The latest CI run failed before creating jobs, so successful CI check-context names remain unconfirmed. The [latest `main` CI run](https://github.com/Diaszano/pgscope/actions/runs/41660883533) is recorded above. GitHub releases API returned an empty list.
- **Pending access/remote verification:** GHCR package existence, visibility, Actions write permission, manifests, digests, and attestations; private vulnerability reporting availability; whether the built-in GitHub Actions app can be selected as a ruleset bypass actor; and exact status-check display names from a successful run.
- **Not applied:** No branch/tag rules, merge settings, GHCR settings, release, image promotion, or publication were changed. The settings guide is a proposal for owner review. Do not declare end-to-end CD validated until the release and registry path has succeeded remotely.
