# PostgreSQL MCP — Automated Releases, GHCR and Repository Governance Design

**Status:** Proposed for review; user selected Python Semantic Release and automatic release on eligible merges to `main`.
**Date:** 2026-10-25
**Target:** `Diaszano/postgres-mcp`, starting from `feature/security-query-pagination`.
**Supersedes:** Manual tag/Docker Hub release workflow; does not supersede the existing query-security/pagination specifications.
**Scope:** CI/CD, release provenance, repository organization, governance and documentation. No database behavior changes.

## 1. Intent

Provide one reproducible, secure path from a reviewed Conventional Commit change to a tested Python package, a GitHub Release tagged `vX.Y.Z`, and multi-platform images in `ghcr.io/diaszano/postgres-mcp`. Remove manual version bumps and historic `crystaldba` release destinations while preserving upstream copyright and attribution. Give maintainers predictable rollbacks and clean contributor workflows.

## 2. Repository baseline verified on 2026-10-25

| File or behavior | Current state in `feature/security-query-pagination` | Required evolution |
|---|---|---|
| `pyproject.toml` | `[project].version = "0.3.0"`, Python >=3.12, `uv.lock`, `pglast==7.11` | PSR governs version; preserve runtime constraints/pins |
| `.github/workflows/build.yml` | lint, pyright, unit, integration; PG 16/17 required and 18 experimental | Shared, stable PR+main gates; fail closed on required extension/tests |
| `.github/workflows/docker-build-dockerhub.yml` | manual/tag Docker Hub deployment to `crystaldba/postgres-mcp`; Trivy `exit-code: "0"` | Retire only after GHCR proven; remove stale secrets and destinations |
| `justfile` | `release` and `prerelease` hand-create tags and GitHub Release | Remove manual release commands; preview/check recipes only |
| `Dockerfile` | non-root final runtime, multi-stage, upstream OCI vendor/source metadata | Set fork image source/labels; keep upstream attribution in LICENSE/NOTICE |
| `docs/release-checklist.md` | hardcoded `Release Version: 0.3.0` | Version-independent operational procedure; release troubleshooting |
| `.github/` | workflows only | PR/issue templates, CODEOWNERS, Dependabot and workflow permissions |
| Package name | `postgres-mcp` | Keep published Python project identity; no PyPI publication authorized |

This design is based on current remote repository inspection; actual checks and GitHub permissions must be validated during implementation.

## 3. Outcomes, exclusions and constraints

### Required outcomes

- **CD-01:** All PRs into `main` receive relevant, required, stable-name quality gates without publishing or receiving write credentials.
- **CD-02:** Only successful CI for an actual push to `refs/heads/main` can invoke release logic, inside that same workflow run or a `workflow_call` chain.
- **CD-03:** Python Semantic Release (PSR) 10.7.0 initially, dependency/action version explicitly pinned, examines Conventional Commits on `main` and automatically decides whether a new release is eligible.
- **CD-04:** `fix` means patch, `feat` minor, `!` or `BREAKING CHANGE` breaking; non-release types (`docs`, `test`, `ci`, `build`, `refactor`, `chore`) do not publish *unless explicitly marked breaking*. No release on empty/no-bump/duplicate/rerun.
- **CD-05:** Stable tags follow `vMAJOR.MINOR.PATCH`; `project.version` stays unprefixed (`MAJOR.MINOR.PATCH`); first automated release bootstraps safely from verified reachable tags/project version. No re-tagging or rewriting historic releases.
- **CD-06:** Version, changelog and `uv.lock` are updated in one release commit, and `uv lock --check` succeeds without unrelated dependency churn; `pglast==7.11` stays unchanged unless a separately reviewed dependency PR alters it.
- **CD-07:** Build the wheel and sdist from the *released commit*, verify `METADATA Version` equals the tag, upload both to the matching GitHub Release. Do not publish to PyPI.
- **CD-08:** Build GHCR `linux/amd64` and `linux/arm64` from the *exact release tag SHA*; image source `https://github.com/Diaszano/postgres-mcp` and OCI revision/version reflect that release.
- **CD-09:** Publish stable GHCR aliases `vX.Y.Z`, `X.Y`, `X` and `latest` only once image scans and smoke tests succeed; digest and tag correspond to the same manifest. `latest` never points to PR/shas/prereleases.
- **CD-10:** Publish a non-semver staging reference `sha-<full release commit SHA>` first; scan amd64 and arm64 from that immutable digest; promote manifest by digest to version tags only after both pass.
- **CD-11:** No Docker Hub publishing, `DOCKERHUB_*` secrets, upstream registry tags or manual `just release` in the final pipeline; migration uses a verified cutover.
- **CD-12:** Block HIGH/CRITICAL vulnerabilities in the release image unless a narrow, reviewable, expiring exception is documented. SBOM and provenance accompany GHCR builds.
- **CD-13:** Workflow Actions are pinned to audited immutable SHAs (annotate human-readable versions), third-party dependencies are updated through PR review, jobs use least-privilege permissions, and no privileged `pull_request_target` execution of untrusted code is permitted.
- **CD-14:** CI must validate formatting/lint, Pyright, unit, release smoke, performance invariants, `uv lock --check`, wheel/sdist metadata and integration PG 16/17; PG 18 remains a separately identified experimental gate until dependencies are supported and proven.
- **CD-15:** HypoPG installation failures must not be swallowed with `|| true` on required integration jobs. Optional extension coverage reports clear skips and reasons; required tests fail on absent HypoPG.
- **CD-16:** PR title follows Conventional Commits, squash merge produces the semantic title in the `main` commit, and branch names follow Conventional Branch conventions; user-facing instructions and examples use English for source code, branches and commits.
- **CD-17:** Contributions are guided by `.editorconfig`, `.gitattributes`, `.dockerignore`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`, issue templates, CODEOWNERS and dependency bot configuration.
- **CD-18:** Upstream copyright holders, LICENSE, PyPI package identity and upstream credits are retained; fork-owned metadata/README links are corrected without pretending to own upstream copyright or upstream PyPI.
- **CD-19:** Branch protection/ruleset/settings changes that cannot be applied by repository code are documented as explicit manual steps; minimum viable release permissions and exception procedure are explained.
- **CD-20:** Operators can run a local deterministic no-push release preview; tests validate `fix/feat/breaking/no-op`, dirty working tree, version drift, duplicate tag, failed CI, bad auth and registry failures.
- **CD-21:** Failed Docker publication never updates `latest`, never claims that a published GitHub Release implies a passing Docker release, and supports resuming publication of an already-valid tag without calculating a new version.
- **CD-22:** Published releases expose immutable artifact digests and a reproducible rollback command by SemVer tag or digest; release checklist has no fixed literal version.
- **CD-23:** The migration does not silently introduce new license, packaging or database runtime behavior, nor auto-publish to registries beyond GitHub GHCR / GitHub Releases.
- **CD-24:** Documentation explains secret and permission setup, failure modes, security gates, initial bootstrap, release recovery, branch policy and exact verification commands in English with pt-BR update where deployment guidance already exists.

### Non-goals / anti-goals

- No PyPI upload, home server deployment, Kubernetes, staging infrastructure, supply-chain service account, or automated promotion outside GHCR.
- No new application runtime dependencies or forced refactor of SQL/MCP code.
- No personal-access-token requirement unless GitHub repo rules prevent `GITHUB_TOKEN` push; prefer appropriately scoped GitHub App installation token only if a bypass is indispensable.
- No mutation of immutable release tags or silent dependency version bumps during version stamp.
- No network-capable publishing from PRs, even for forks or Dependabot PRs.

## 4. Selected approach and considered alternatives

**Selected:** PSR invoked as a pinned runner CLI with `uv tool run --from python-semantic-release==10.7.0`, using the runner's pinned `uv`, so `build_command` can update `uv.lock` and build distributions in the same environment. A reusable `.github/workflows/release.yml` is invoked only from the gated `ci.yml` workflow on push to `main`, and then performs versioning, release asset publication, and GHCR staging/scanning/promotion in dependent jobs.

**Alternative A:** Official PSR Docker Action. Advantage: standard outputs (`released`, `tag`, `commit_sha`) and documented setup. Trade-off: its container does not supply `uv`, so the repo would need pinned `uv` bootstrap *inside* PSR `build_command`. Acceptable only if runner CLI integration proves problematic.

**Alternative B:** Release Please. Advantage: release PR approval; explicitly rejected by user in favor of automatic post-merge release.

**Alternative C:** Separate GHCR workflow triggered by a newly created tag. Rejected because GitHub's `GITHUB_TOKEN` generated tag event normally does **not** initiate a new workflow; avoids fragile event chaining.

**Pipeline topology:**

```text
PR opened/synchronized -> ci.yml: conventions + lint/types + unit + integration + package + smoke + security
                    \-> no write token, no publish
push main -----------> ci.yml: same required gates
                         \-> call release.yml (only after all gates pass)
                              \-> PSR version/changelog/uv.lock/build/tag/GitHub Release
                              \-> verify released tag SHA, release artifacts, immutable provenance
                              \-> GHCR multi-arch staging tag sha-<sha>, by-digest scan amd64 + arm64
                              \-> promote exact digest to vX.Y.Z, X.Y, X, latest (stable only)
```

All release jobs are serialized with `cancel-in-progress: false`; refuse stale upstream state or retry from the newest verified `main`. The GHCR job receives the PSR-reported/newly-created **tag and commit SHA**; it never checks out a moving `main` or trusts a user-supplied image tag.

## 5. Semantic version contract

| Commit on main | Bump | Example from v0.3.0 |
|---|---|---|
| `fix: handle cursor expiry` | patch | `v0.3.1` |
| `feat: add cursor metrics` | minor | `v0.4.0` |
| `feat!: change MCP query contract` or `BREAKING CHANGE:` footer | breaking | `v0.5.0` during v0 (see policy) |
| `docs: update usage` / `ci: improve matrix` | no release | unchanged |
| `chore(release): 0.3.1 [skip ci]` | no release | excluded from future scans |

Set `allow_zero_version = true` and `major_on_zero = false` while API is intentionally v0. Changing this to true for v1 is a separately reviewed change. Keep `tag_format = "v{version}"`, `commit_parser = "conventional"`, `version_toml = ["pyproject.toml:project.version"]`, `branch = "main"`, `commit_message = "chore(release): {version} [skip ci]"` (verify configuration and parser using PSR 10.7.0 in the plan tests). Document the initialization rules: discover all tags, inspect reachable tag ancestry, ensure metadata version matches latest adopted release, and **do not** reissue an existing `v0.3.0` even when its content differs; explicitly preflight the first automatic bump with an isolated git test repo.

`build_command` run while PSR has already stamped the new version:

```toml
[tool.semantic_release]
build_command = """
  uv lock --upgrade-package "$PACKAGE_NAME"
  git add uv.lock
  uv lock --check
  uv build
"""
```

The shell environment must make the pinned `uv` visible and fail on each command (prefer a tested shell script with `set -euo pipefail` invoked from `build_command` rather than trusting multiline shell defaults). Compare the lock file dependency resolutions before/after: only root project version and necessary lock metadata may change. Do not run unconstrained `uv lock --upgrade`.

GitHub publish assets are the wheel/sdist from the same release commit; `semantic-release publish --tag "$TAG"` is called with an explicit trusted tag. Verify metadata and release asset names before making stable GHCR aliases. A `GITHUB_TOKEN` push will not re-trigger CI/release; the current job must finish all jobs itself.

## 6. Repository and workflow map

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | PR/main checks; stable required job names; guarded reusable release caller |
| `.github/workflows/release.yml` | Trusted `workflow_call` orchestration, PSR, assets and GHCR gated promotion |
| `.github/workflows/security.yml` | Read-only scheduled/advisory code, dependency and Docker security; no release |
| `.github/workflows/docker-build-dockerhub.yml` | Remove after cutover (no longer active) |
| `.github/workflows/build.yml` | Replace after matching the existing PG matrix and checks |
| `.github/dependabot.yml` | Weekly uv and GitHub Actions updates, Docker if desired; PR group caps |
| `.github/CODEOWNERS` | Owner `@Diaszano` for workflows/security/release files |
| `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/*` | Contribution/change traceability |
| `.editorconfig`, `.gitattributes`, `.dockerignore`, `.pre-commit-config.yaml` | Cross-platform formatting, build context hygiene and fast local checks |
| `scripts/ci/check_version.py` | Validate tag vs `pyproject.toml`, wheel/sdist metadata, uv lock |
| `scripts/ci/validate_release.py` | Side-effect-free release/tag/OCI test helpers; callable in unit tests |
| `scripts/ci/scan_image.sh` | Fail-closed, per-platform digest vulnerability scans |
| `scripts/ci/promote_image.sh` | Verify digest/tag and sequentially create aliases when all gates succeeded |
| `scripts/release/build.sh` | Fail-fast PSR build command: update lock and wheel/sdist |
| `tests/release/*` | Regression tests for release state, scripts, workflow invariants and smoke |
| `pyproject.toml`, `uv.lock`, `justfile` | Single version source, repeatable commands; no manual release mutation |
| `Dockerfile` | Fork provenance/OCI labels, runtime image remains non-root |
| `docs/release-checklist.md`, `docs/ci-cd.md`, `CONTRIBUTING.md`, `SECURITY.md`, READMEs | Setup/rollback/operation instructions |

Do not create separate scripts unless they enforce nontrivial logic tested independently; small shell predicates belong in workflow steps.

## 7. Quality and release gates

1. PR title/commit convention and branch convention; squash-only merges recommended so the eventual `main` commit is the semantic title. Branch rules are enforced via the GitHub UI, not by text files alone.
2. `uv lock --check`, `uv sync --locked`, `ruff check .`, `ruff format --check .`, `pyright`, `pytest tests/unit`, `pytest tests/release/test_smoke.py`, `pytest tests/performance --run-performance` (bounded tests), `uv build`, wheel verification.
3. PG 16 and PG 17 integration are required. Install HypoPG deterministically and assert extension exists before integration. PG18 remains experimental only until its image/apt/extension/test path is validated; lack of availability is visible.
4. Scan checked-out repository for known vulnerabilities and accidental secrets; do not grant remote write tokens to PRs. No `|| true`, `continue-on-error: true` or Trivy exit-code 0 in mandatory gates.
5. GHCR scan: stage a multiarch image by a unique commit-SHA tag, resolve immutable manifest digest, run platform-specific scans, then promote by digest. If any architecture fails, leave stable tags and `latest` unchanged; registry may still have a staged SHA image for investigation.
6. Tag existence/version mismatch/unauthorized branch must fail closed. An expected no-release merge skips publication successfully, not via failure.
7. Archive artifacts and package manifest/digest evidence per release. Recovery of a valid existing tag is a trusted manual publish-only operation (not a forced version bump).

## 8. Security and GitHub settings

- Top-level `permissions: contents: read`; required `contents: write` only PSR job, `packages: write` only GHCR upload/promote jobs, `id-token: write` only if an attestation action requires it. Never pass credentials to untrusted PR code or to a local Docker build context.
- Prefer version/commit-SHA pinned, reviewed actions and use Dependabot to propose upgrades; set `persist-credentials: false` in PR checkouts where possible. Release checkout needs a limited-scoped credential for the version push.
- `GITHUB_TOKEN` should be sufficient for GHCR when package permissions/repository access are correct; no Docker Hub token or PAT required by default.
- **Protection tension:** A strict `main` rule requiring PRs may block PSR's release commit push. Choose a narrow authorized GitHub Actions/installed-app bypass for only the release workflow *or* use a GitHub App token with suitable, narrowly scoped bypass; never broadly disable PR review protections. This is a repo-settings task that needs explicit owner action and a documented dry run.
- Protect release tag `v*` from deletion/mutation, limit force pushes and require CI checks; prefer a ruleset after bootstrap to avoid blocking the semantic-release bot.
- Apply safe concurrency so simultaneous merges cannot race the semantic tag, and re-evaluate upstream freshness before release.
- Preserve upstream LICENSE and attribution. Change fork-owned OCI source/URL to `Diaszano/postgres-mcp` and explicitly credit upstream in NOTICE/README.

## 9. Failure modes, recovery and release lifecycle

| Failure | Expected behavior |
|---|---|
| PR tests fail | No release, no GHCR tags |
| Merge has `docs:` only | CI succeeds, PSR no-op, no new tag |
| Duplicate tag / unsynced version | Explicit error, no rewriting tags |
| `uv.lock` dependency unexpectedly changes | Fail release before pushing tag |
| PSR lacks permission to push protected main | Fail with actionable repo-ruleset instructions, no admin scope escalation |
| GitHub Release succeeded but GHCR fails | Keep release/immutable tag; mark publication failure visibly; do not touch `latest`; retry publish-only by verified tag |
| amd64 passes, arm64 scan fails | Do not promote any stable aliases |
| Current `latest` existing from prior release | It stays valid until new release passes |
| workflow rerun on same SHA | No second version/tag; verified publish-only path for partial failures |
| critical scan exemption | Exact CVE/package justification, expiry/approval, never global scan bypass |

**Initial rollout:** First, add read-only quality gates and local PSR preview. Verify existing git tags, current project version and branch rules. Next, test the release workflow in a throwaway private fork and verify that tag, GH Release assets and GHCR point to the same SHA. Enable automatic publication for `main` only after the necessary protections and permissions are recorded. Retire Docker Hub workflow as final cutover. Publish or promote a real release only from explicitly reviewed code.

## 10. Verification and acceptance matrix

| Requirement IDs | Owning plan | Required proof |
|---|---|---|
| CD-01, CD-02, CD-14, CD-15 | Plan 02 | CI workflow fixture checks, PG integration jobs, mandatory gates |
| CD-03–07, CD-20 | Plan 03 | PSR integration in isolated temp Git repo + version/lock/dist tests |
| CD-08–10, CD-21–22 | Plan 05 | Buildx manifest/provenance and failure-injection promotion simulation |
| CD-12–13 | Plan 04 | Action pins, Trivy exit gates, no credential leak, SBOM |
| CD-11, CD-16–18 | Plan 01 + Plan 06 | Repo governance fixtures, cleanup scans, README checks |
| CD-19, CD-23–24 | Plan 06 | Operator runbook, rollback dry-run and manual settings checklist |

## 11. Implementation sequence

1. `2026-10-25-01-repository-conventions.md` — contribution/PR conventions without changing existing CD.
2. `2026-10-25-02-ci-quality-gates.md` — required CI replacement, release caller isolated/disabled until approved.
3. `2026-10-25-03-semantic-versioning.md` — PSR and consistent Python artifact version; local dry run.
4. `2026-10-25-04-supply-chain-security.md` — security policy, verified scan utilities, workflow permission baseline.
5. `2026-10-25-05-ghcr-delivery.md` — reusable release workflow + multiarch GHCR staging/scan/promotion; controlled cutover.
6. `2026-10-25-06-operations-and-cleanup.md` — release docs, upstream attribution cleanup and rollback/DR.

All plans implement this spec via TDD/checkable steps and Conventional Commit commits in English. **Do not implement production code or enable publishing until design/plan review and the owner-only GitHub settings checklist are complete.**

## References verified 2026-10-25

- PSR 10.7.0 configuration: https://python-semantic-release.readthedocs.io/en/stable/configuration/configuration.html
- PSR integration with uv: https://python-semantic-release.readthedocs.io/en/stable/configuration/configuration-guides/uv_integration.html
- PSR GitHub Actions: https://python-semantic-release.readthedocs.io/en/stable/configuration/automatic-releases/github-actions.html
- GitHub token event chaining: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- Docker attestations: https://docs.docker.com/build/ci/github-actions/attestations/
- Dependabot uv: https://docs.astral.sh/uv/guides/integration/dependabot/
- Current repo: https://github.com/Diaszano/postgres-mcp/tree/feature/security-query-pagination
