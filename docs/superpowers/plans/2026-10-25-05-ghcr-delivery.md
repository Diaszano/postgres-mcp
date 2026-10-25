# GHCR Multiarch Automated Delivery Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** Promote a verified Python Semantic Release tag into GHCR immutable images and stable aliases after all security gates.
**Architecture:** The trusted `workflow_call` release job publishes PSR version commit, tag, assets and GH Release. A dependent job builds the exact release SHA into a staging manifest, validates per-platform content and promotes the same digest to stable semver aliases.
**Tech Stack:** GitHub Actions, PSR, uv, Docker Buildx/QEMU, GHCR, Trivy, Bash
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
- **GITHUB_TOKEN does not trigger another workflow** (Task 1): Same caller/reusable execution runs all downstream jobs.
- **Release succeeded, image failed** (Task 3): latest never changes; rerun publish-only possible.
- **Multiarch manifest contains mixed versions** (Task 2): Each image reports exact tag and SHA.
- **Concurrent merges** (Task 1): Serialization and upstream SHA verification avoid races.
- **Registry permissions disallow package publication** (Task 4): Fail clearly, no fallback PAT/DockerHub.

---

### Task 1: Implement trusted reusable semantic release job
**Files:**
- Replace stub `.github/workflows/release.yml`
- Extend `tests/release/test_ci_release_gate.py`
- Create `tests/release/test_release_workflow.py`

**Interfaces:**
- Consumes: CI caller from Plan 02; PSR policy/build script from Plan 03; fork action/permission policy from Plan 04.
- Produces: Workflow `workflow_call` outputs `released`, `tag`, `release_sha`, `version`; PSR produces GitHub Release plus wheel/sdist, guarded `GH_TOKEN`.

- [ ] **Step 1: Write failing tests.** `test_release_only_callable_after_gates`, `test_workflow_uses_uv_and_pinned_psr`, `test_release_job_serialized`, `test_release_checkout_matches_trigger_sha`, `test_release_outputs_never_derive_from_untrusted_inputs`; validate empty/no bump as success.

```python
from pathlib import Path
release = Path('.github/workflows/release.yml').read_text()
assert 'workflow_call' in release
assert 'semantic-release' in release and 'GH_TOKEN' in release
assert 'contents: write' in release
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_ci_release_gate.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Check out exactly triggering `main` SHA with full tags; reject moved/re-written upstream; run pinned PSR CLI (via uv), capture git commit/tag before and after, verify new tag points at actual HEAD and version metadata, call `semantic-release publish --tag <validated-tag>`, expose trusted outputs. `GITHUB_TOKEN` is not used as an event trigger. No release from workflow_dispatch on this job.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_release_workflow.py && actionlint .github/workflows/release.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "feat(ci): release verified main commits with semantic versioning"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 2: Build and stage immutable GHCR multiarch artifacts
**Files:**
- Modify `.github/workflows/release.yml`
- Modify `Dockerfile`
- Create `tests/release/test_ghcr_manifest.py`

**Interfaces:**
- Consumes: `needs.release.outputs.release_sha`, `tag`, `released=true`; fork repo GHCR permissions.
- Produces: GHCR `ghcr.io/diaszano/postgres-mcp:sha-<release SHA>` multiarch manifest and captured `sha256` digest with SBOM/provenance.

- [ ] **Step 1: Write failing tests.** `test_docker_push_from_exact_release_sha` verifies checkout tag + sha consistency; `test_image_platforms` expects amd64 and arm64; `test_oci_labels_use_fork_and_revision` verifies image labels; `test_staging_tag_full_sha` rejects short/floating base.

```python
from pathlib import Path
release = Path('.github/workflows/release.yml').read_text()
assert 'linux/amd64,linux/arm64' in release
assert 'provenance:' in release and 'sbom:' in release
assert 'ghcr.io/diaszano/postgres-mcp' in release
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_ghcr_manifest.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Use docker/login-action via `GITHUB_TOKEN`, setup-buildx/setup-qemu, metadata-action plus build-push-action pinned SHAs; build exact version-tag commit for `linux/amd64,linux/arm64`, `provenance: true`, `sbom: true`; capture digest from build output; validate manifest with `buildx imagetools inspect`.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_ghcr_manifest.py && docker buildx version`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "feat(ci): stage attested multiarch images in GitHub registry"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 3: Scan immutable digest then promote stable aliases
**Files:**
- Create `scripts/ci/promote_image.sh`
- Modify `.github/workflows/release.yml`
- Create `tests/release/test_image_promotion.py`

**Interfaces:**
- Consumes: Full validated tag, corresponding release SHA, image digest, `scan_image.sh` from Plan 04.
- Produces: `promote_image.sh ghcr.io/diaszano/postgres-mcp sha256:<digest> vX.Y.Z` builds aliases `vX.Y.Z`, `X.Y`, `X`, `latest` on successful verified stable releases.

- [ ] **Step 1: Write failing tests.** `test_promotion_refuses_bad_tag`, `test_promotion_refuses_unverified_digest`, `test_no_latest_when_arm64_scan_fails`, `test_latest_points_at_identical_digest`, `test_promote_is_idempotent` use fake `docker buildx imagetools` and fake scan commands.

```python
from pathlib import Path
promotion = Path('scripts/ci/promote_image.sh').read_text()
assert 'imagetools' in promotion and 'sha256:' in promotion
assert 'latest' in promotion
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_image_promotion.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Use immutable staged manifest digest; run required Trivy scans for both architectures prior to any stable alias; use `buildx imagetools create --tag ... source@sha256` with version aliases before latest; validate final digest/aliases; fail nonzero if any check fails. No mutable build context or re-build during promotion.
- [ ] **Step 4: Confirm green.** Run: `bash -n scripts/ci/promote_image.sh && uv run pytest -q tests/release/test_image_promotion.py`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "feat(ci): promote scanned release image to semver GHCR tags"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 4: Build publish-only recovery and failure visibility
**Files:**
- Modify `.github/workflows/release.yml` to add guarded recovery entry or add `.github/workflows/retry-publish.yml`
- Create `scripts/ci/validate_release_ref.py`
- Create `tests/release/test_publish_recovery.py`

**Interfaces:**
- Consumes: Existing immutable tag, verified GitHub Release and project metadata; trusted manual workflow_dispatch.
- Produces: Publish-only job accepts an existing `vX.Y.Z` and never calls PSR version; only deploys same SHA/digest after all scans.

- [ ] **Step 1: Write failing tests.** `test_retry_never_bumps_version`, `test_retry_rejects_non_main_ancestry`, `test_retry_rejects_tag_mismatch`, `test_retry_requires_existing_release`, `test_retry_cannot_modify_existing_different_digest`.

```python
from pathlib import Path
recovery = Path('scripts/ci/validate_release_ref.py').read_text()
assert 'tag' in recovery and 'version' in recovery
assert 'release' in recovery
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_publish_recovery.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Implement manual recovery isolated from automated versioning; validate tag via Git API commit ancestry, metadata, release existence and protected branch; recreate missing GHCR aliases from verified digest if available; no force tagging. Report partial GitHub Release success clearly in Actions summary and operator docs.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release/test_publish_recovery.py && actionlint .github/workflows/release.yml`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "fix(ci): make partial GHCR publication recoverable"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

### Task 5: Run controlled remote release dry run and cut over
**Files:**
- Modify `.github/workflows/ci.yml`
- Remove `.github/workflows/docker-build-dockerhub.yml`
- Remove `.github/workflows/build.yml`
- Create `tests/release/test_cutover.py`
- Update `docs/release-checklist.md` after Plan 06

**Interfaces:**
- Consumes: Green branch CI, proven release workflow from tasks 1-4, owner-confirmed repository settings.
- Produces: Single active CI/release path and audit record with digest/tag/assets/platforms.

- [ ] **Step 1: Write failing tests.** `test_only_one_main_release_entry`, `test_no_dockerhub_references_in_workflows`, `test_ghcr_primary_image`, `test_no_release_on_failed_gates`; smoke test dry run in fork or controlled temporary repository.

```python
from pathlib import Path
workflows = Path('.github/workflows')
assert not (workflows / 'docker-build-dockerhub.yml').exists()
assert not (workflows / 'build.yml').exists()
assert (workflows / 'ci.yml').is_file()
```
- [ ] **Step 2: Confirm red.** Run `uv run pytest -q tests/release/test_ci_release_gate.py`. Expected: nonzero until the task behavior is implemented. For workflow changes also run `actionlint .github/workflows/*.yml`. Record the failure before implementation.
- [ ] **Step 3: Implement.** Preflight repository rulesets and GHCR package access. Exercise automatic patch/minor/no-op in throwaway fork, verify CI and traceable manifest digest, then remove older workflows and enable main publishing. DO NOT create real tags in upstream without owner-approved rollout.
- [ ] **Step 4: Confirm green.** Run: `uv run pytest -q tests/release && actionlint .github/workflows/*.yml && uv lock --check`. Expected: exit status 0 and all listed regression assertions passing. If external Docker/GitHub access is unavailable, mark that check pending; do not claim it passed.
- [ ] **Step 5: Commit.** Stage only the files listed for this task (plus generated lock if required) and run `git commit -m "ci: retire Docker Hub release workflow after GHCR verification"`.
- [ ] **Step 6: Review.** Request fresh task-scoped code review, verify no unrelated behavior or secret changes, and address findings before the next task.

## Completion Gate
- [ ] Every task has its red/green test evidence and a scoped Conventional Commit.
- [ ] Existing `pytest tests/unit` and `pytest tests/release` remain green; record the real counts, not assumed results.
- [ ] No release or registry publication is triggered by this plan alone unless Plan 05 controlled cutover explicitly authorizes it.
- [ ] Whole-plan review checks spec requirements and failure scenarios, then hand off to the next plan via `README.md`.
