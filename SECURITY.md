# Security Policy

`pgscope` takes security seriously. This document outlines our vulnerability reporting process, supply-chain security standards, and exception policies.

---

## 1. Reporting Security Vulnerabilities

If you discover a security vulnerability or sensitive defect in `pgscope`, please **do not open a public GitHub issue**.

Instead, use GitHub Private Vulnerability Reporting from the repository's Security tab if it is enabled. Its current availability has not been verified. If it is unavailable, contact the maintainer through the GitHub profile linked from the repository. Please include a way to reproduce the issue and an affected version; the maintainer will respond as soon as possible.

---

## 2. Supply Chain Security and Artifact Attestations

The release workflows are configured for the following supply-chain checks. No published release artifacts or registry attestations were verified during the 2026-11-03 readiness review:

- **Package Registry**: The workflow targets GitHub Container Registry (`ghcr.io/diaszano/pgscope`); package visibility and published manifests remain unverified.
- **Software Bill of Materials (SBOM)**: Buildx is configured to generate an SBOM for each published image.
- **Build Provenance**: Buildx is configured to generate provenance linking the image to its build inputs.
- **Pinned Dependencies**: All dependencies are locked in `uv.lock`. Workflows pin all third-party GitHub Actions to immutable 40-character commit SHAs.

---

## 3. Vulnerability Waiver Policy

In rare circumstances where an upstream dependency contains a reported vulnerability without an available fix, and the vulnerability is verified to be non-exploitable in the context of `pgscope`, a temporary waiver may be documented:

Every security waiver **must** explicitly document:
1. **Identifier**: Specific CVE or GHSA ID.
2. **Affected Package**: Name and exact version.
3. **Exploitability Analysis**: Detailed technical rationale explaining why the issue is non-exploitable in `pgscope`.
4. **Maintainer Review**: Record review by a maintainer (see [`.github/CODEOWNERS`](.github/CODEOWNERS)); there is currently one observed maintainer, so this is not an independent approval requirement.
5. **Expiration Date**: Include a review date, preferably within 30 days. Reassess the waiver when a fix becomes available.

---

## 4. Repository Governance and Access Security

Detailed repository protection rules, branch security on `main`, release tag protections, and owner governance policies are documented in [`docs/github-settings.md`](docs/github-settings.md).
