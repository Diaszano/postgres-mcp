# GitHub Repository Settings Proposal

This is a proposed configuration; it has not been applied. Remote observations below were collected on 2026-11-03 and are summarized in [project readiness](project-readiness.md).

## Current remote evidence

- `main` is the default branch. No branch protection rules or repository rulesets are configured.
- The authenticated account is the only collaborator observed and has admin access. Do not require an approving review: the sole maintainer cannot approve their own pull request.
- The latest `main` CI run failed before producing job checks. Visible checks on that commit are Dependabot checks, so GitHub has not supplied successful CI status contexts to select yet.
- The CI workflow declares these job names: `Validate PR Conventions`, `Lint & Code Style`, `Static Type Analysis`, `Unit & Release Tests`, `Package Build & Version Gate`, `Integration (PG 16)`, and `Integration (PG 17)`. When a successful CI run exists, select the exact displayed contexts from its Checks page; require both stable integration jobs. Do not require experimental `Integration (PG 18)`.
- GHCR package visibility, package Actions access, and published manifests could not be verified with the available registry permissions. No release artifacts were observed; that does not establish that none exist.

## Proposed repository settings

### Pull requests and merges

- Allow squash merging only and set the default squash message to the pull request title and body. Disable merge commits and rebase merging so the merge commit follows the validated title convention.
- Delete head branches after merge.
- Keep auto-merge enabled; GitHub should merge only after the applicable required checks pass.
- Keep `.github/CODEOWNERS` as an ownership and reviewer-routing record. Do not require approval while there is one maintainer. Revisit an approval requirement only after another independent maintainer has write access.
- Require conversation resolution and up-to-date branches for merging. Block force pushes and deletion of `main`.
- Require the CI job contexts listed above only after confirming their exact check names from a successful run. Both PostgreSQL 16 and 17 integrations are required; PostgreSQL 18 remains experimental.

### Release bot and ruleset compatibility

The release workflow uses the repository-provided `GITHUB_TOKEN` with `contents: write` to create the semantic release commit/tag. The Actions setting that lets workflows create and approve pull requests can remain disabled; this workflow pushes the release commit directly and does not open a PR.

A `main` rule requiring every update to come through a PR can block that push. GitHub rulesets support bypass entries for eligible GitHub Apps, but the repository has not verified that its built-in GitHub Actions app can be selected and can bypass this exact rule. Before enforcing the PR rule, verify that option in repository settings or run a controlled release-automation check. Do not use a commit-message pattern as a bypass: `[skip ci]` only affects workflow triggering and does not grant ruleset permission. Do not create a new credential as part of this proposal.

If the built-in app cannot be granted a narrowly scoped bypass, keep the PR requirement in Evaluate mode until the release flow is changed to publish from a PR merge without a direct push. Do not enable a broad human-role bypass as a substitute for bot access.

### Release tags and GHCR

- Add a tag ruleset for `v*` that prevents updates and deletions after creation. The release automation needs permission to create tags; confirm the selected ruleset does not prevent the semantic release workflow from creating them.
- Verify that `ghcr.io/diaszano/postgres-mcp` exists, confirm intended visibility, and grant the repository Actions access needed for `GITHUB_TOKEN` package writes. Record the resulting package settings; they remain unverified today.
- Keep repository-wide Actions defaults read-only. The workflows declare narrow per-job `contents: write` or `packages: write` only where release work requires them. No `id-token: write` permission is used.

## Rollback

Deploy a previously verified digest, replacing the explicit placeholder below with a digest recorded from an actual trusted release:

```bash
docker pull ghcr.io/diaszano/postgres-mcp@sha256:<verified-release-digest>
```

Do not rewrite published version tags. For a fix, merge a conventional `fix:` change and let the release workflow publish a new patch version. For interrupted image delivery, use the documented [retry-publish workflow](ci-cd.md#4-partial-release-recovery-procedure), which checks both architectures and preserves immutable version tags.
