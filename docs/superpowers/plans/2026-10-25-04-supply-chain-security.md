# Supply Chain and CI Security Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Enforce least-privileged, reviewable supply-chain security gates before GHCR promotion.
**Architecture:** Use one source-controlled image scanner with platform-aware checks, plus workflow tests validating pinned actions and permissions. Keep actionable security and exception policy outside the runtime package.
**Tech Stack:** GitHub Actions, Trivy, Docker Buildx, pytest, Bash, Dependabot
**Spec:** `docs/superpowers/specs/2026-10-25-ci-cd-semantic-release-ghcr-design.md`
## Global Constraints
- Baseline branch: `feature/security-query-pagination`; default release branch: `main`.
- Runtime Python >=3.12; uv is the package manager and `uv.lock` is committed.
- No changes to SQL/MCP runtime or existing pinned `pglast==7.11` except separately reviewed work.
- Package metadata version is unprefixed; public releases use `vX.Y.Z`; image is `ghcr.io/diaszano/postgres-mcp`.
- Use Conventional Commits and Conventional Branch names in English; apply TDD and frequent scoped commits.
- Do not publish to PyPI or Docker Hub; preserve upstream license and attribution.
- On PRs use read-only credentials; no privileged `pull_request_target` builds.
- Release only when gated push to `main` succeeds. PSR version is pinned to 10.7.0 initially.
- Protect history and tags: never force-rewrite a published tag or bypass tests silently.
## Review Focus
Five expected edge conditions; their owning tasks below must include the named regression.
- **Malicious fork PR** (Task 1): No secrets/write scopes are reachable.
- **Action tag suddenly changes** (Task 1): Every uses reference must resolve to immutable SHA.
- **Scanner missing on runner** (Task 2): Fail closed, never assume green.
- **Image has one vulnerable platform** (Task 2): Both platforms must pass before promotion.
- **Waiver without expiry** (Task 3): Policy rejects broad/expired exceptions.

---

### Task 1: Pin actions and verify job permission boundaries
**Files:**
- Create `tests/release/test_action_security.py`
- Modify `.github/workflows/ci.yml`
- Modify `.github/workflows/release.yml` when introduced by Plan 02

**Interfaces:**
- Consumes: List of currently used third-party Actions and reusable jobs.
- Produces: All `uses` from external repos at audited 40-digit commit SHAs; narrow read/write permissions.

- [ ] **Step 1: Write failing tests.** `test_actions_are_pinned_to_full_sha` regex matches `uses: owner/repo@<40hex>`; `test_no_pull_request_target`, `test_release_write_only_in_release_jobs`, `test_no_secrets_in_pr_jobs` inspect parsed workflow graph.

```python
from pathlib import Path
import re
ci = Path('.github/workflows/ci.yml').read_text()
assert 'pull_request_target' not in ci
for action in re.findall(r'uses:\s+([^\s]+)', ci):
    if not action.startswith('./'):
        assert re.search(r'@[0-9a-f]{40}$', action)
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_action_security.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Resolve current audited SHAs using official release tags and document trailing version comments; `permissions: contents: read` globally, per-job elevated only where required. Do not use `secrets: inherit` if unnecessary.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_action_security.py && actionlint .github/workflows/ci.yml .github/workflows/release.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci(security): pin actions and minimize token privileges"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Add fail-closed digest and architecture scans
**Files:**
- Create `scripts/ci/scan_image.sh`
- Create `tests/release/test_image_scan.py`

**Interfaces:**
- Consumes: Registry image digest and validated `linux/amd64`, `linux/arm64` platform tuple.
- Produces: `scan_image.sh IMAGE@sha256:DIGEST` scans both platforms with pinned Trivy version; nonzero when either scan fails.

- [ ] **Step 1: Write failing tests.** `test_scan_fails_when_trivy_missing`, `test_scan_fails_on_high_critical`, `test_scan_checks_both_platforms`, `test_scan_never_uses_exit_code_zero`; use fake executables via PATH and no network.

```python
from pathlib import Path
script = Path('scripts/ci/scan_image.sh').read_text()
assert 'HIGH,CRITICAL' in script and '--exit-code 1' in script
assert 'linux/amd64' in script and 'linux/arm64' in script
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_image_scan.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Implement fail-closed Bash `set -euo pipefail`, digest syntax validation and per-platform scan commands with `--severity HIGH,CRITICAL --exit-code 1`. Prefer explicit allowlisted, pinned ignore policy rather than `ignore-unfixed` blanket; never parse untrusted artifact name as shell.
- [ ] **Step 4: Confirm green.** Run: `bash -n scripts/ci/scan_image.sh && uv run pytest -q tests/release/test_image_scan.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci(security): block vulnerable multiarch image promotion"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Define credential, vulnerability and SBOM policies
**Files:**
- Create `SECURITY.md`
- Create `.github/workflows/security.yml`
- Create `tests/release/test_security_policy.py`
- Modify `Dockerfile` labels only after Plan 05 provenance decision

**Interfaces:**
- Consumes: Current Dockerfile non-root, GitHub source settings, token policies.
- Produces: Advisory read-only scheduled workflow and documented disclosure, waiver, provenance policy.

- [ ] **Step 1: Write failing tests.** `test_security_workflow_has_no_write_permissions`, `test_security_policy_requires_waiver_expiry`, `test_sbom_attestations_required_by_release` inspects release contract fixture (wire fully in Plan 05).

```python
from pathlib import Path
policy = Path('SECURITY.md').read_text().lower()
assert 'expiry' in policy or 'expiration' in policy
assert 'sbom' in policy and 'provenance' in policy
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_security_policy.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Schedule read-only code/dependency scanning, supply-chain SBOM attestation requirement and valid exceptions with CVE/package/expires/reviewer. The scheduled workflow never tags/releases or changes `main`.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_security_policy.py && actionlint .github/workflows/security.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "docs(security): define vulnerability and artifact attestation policy"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Supply chain threat regression suite
**Files:**
- Create `tests/release/test_security_failures.py`
- Update `docs/security-deployment.md` with GHCR provenance trust note

**Interfaces:**
- Consumes: CI and release workflow graph plus scanner utility.
- Produces: Tests that prove no promotions after errors or untrusted inputs.

- [ ] **Step 1: Write failing tests.** `test_release_has_no_pr_trigger`, `test_false_positive_scan_denied`, `test_staging_digest_required`, `test_no_dockerhub_secrets`, `test_untrusted_tag_not_shell_evaluated` as table-driven mocks/static assertions.

```python
from pathlib import Path
release = Path('.github/workflows/release.yml').read_text()
assert 'pull_request_target' not in release
assert 'secrets: inherit' not in release
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_security_failures.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Add regression tests for permission escalation, Trivy failure and malicious tag strings; keep PR workflows sandboxed; coordinate with Plan 05 promotion utility signature.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_security_failures.py tests/release/test_action_security.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "test(security): cover pipeline trust boundaries"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [ ] Every task has its red/green test evidence and a scoped Conventional Commit.
- [ ] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results.
- [ ] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [ ] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
