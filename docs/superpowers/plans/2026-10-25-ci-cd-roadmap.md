# Automated CI/CD — Superpowers Execution Roadmap

**Target:** `Diaszano/postgres-mcp` at `feature/security-query-pagination` → protected `main`.
**Design:** `docs/superpowers/specs/2026-10-25-ci-cd-semantic-release-ghcr-design.md`
**Decision:** Automatic Python Semantic Release 10.7.0 after eligible merges to `main`; GitHub Releases and multi-arch `ghcr.io/diaszano/postgres-mcp`; no PyPI or Docker Hub publication.

| Order | Plan | Scope | Tasks | Dependency |
|---|---|---|---:|---|
| 01 | [Repository Conventions and Contribution Governance](2026-10-25-01-repository-conventions.md) | Establish predictable contribution files and commit/branch validation without changing release behavior. | 4 | None |
| 02 | [Continuous Integration Quality Gates](2026-10-25-02-ci-quality-gates.md) | Replace the inherited CI with required, deterministic PR/main verification and a guarded handoff to delivery. | 4 | Plan 01 |
| 03 | [Python Semantic Release and uv Synchronization](2026-10-25-03-semantic-versioning.md) | Compute vX.Y.Z automatically from conventional commits and create consistent Python release artifacts without dependency drift. | 4 | Plan 01 |
| 04 | [Supply Chain and CI Security](2026-10-25-04-supply-chain-security.md) | Enforce least-privileged, reviewable supply-chain security gates before GHCR promotion. | 4 | Plan 02 |
| 05 | [GHCR Multiarch Automated Delivery](2026-10-25-05-ghcr-delivery.md) | Promote a verified Python Semantic Release tag into GHCR immutable images and stable aliases after all security gates. | 5 | Plan 02, Plan 03, Plan 04 |
| 06 | [Release Operations, Documentation and Repository Cleanup](2026-10-25-06-operations-and-cleanup.md) | Make automated delivery safe for maintainers to operate, audit and roll back without manual version edits. | 4 | Plan 01, Plan 05 |

## Non-negotiable gates

1. Keep CI read-only for PRs; enforce title/branch rules and stable status names.
2. A full successful `push main` CI **invokes the reusable release job in the same workflow run**; `GITHUB_TOKEN`-created tag events do not cause a second workflow.
3. Before the first release, validate reachable historical tags, `pyproject.toml` version, PSR permissions and branch protection; test on a temporary fork.
4. Use build script to stamp `project.version`, update only root package version in `uv.lock`, build/inspect wheel and sdist, commit and tag.
5. Image staging by full release SHA -> capture digest -> two architecture scans -> stable version aliases -> `latest` last.
6. If GHCR publish fails, never alter `latest`; use validated publish-only recovery on the same tag.
7. Post-merge remote publishing requires GitHub owner confirmation of branch rulesets and GHCR permissions. The generated docs/plans are not repository commits.

## Suggested execution

- **Recommended:** Superpowers subagent-driven-development task by task with independent review on each sensitive workflow boundary.
- If tool support is unavailable, use `superpowers:executing-plans` in an isolated worktree.
- All changes are proposed until approved and actually executed; tests in the plans are requirements, not completed verification.

## Requirements coverage

| Requirement | Plan |
|---|---|
| CD-01 CD-02 CD-14 CD-15 | 02 |
| CD-03 CD-04 CD-05 CD-06 CD-07 CD-20 | 03, 05 |
| CD-08 CD-09 CD-10 CD-21 CD-22 | 05, 06 |
| CD-12 CD-13 | 04 |
| CD-11 CD-16 CD-17 CD-18 | 01, 05, 06 |
| CD-19 CD-23 CD-24 | 06 |
