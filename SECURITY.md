# Security Policy

`postgres-mcp` takes security seriously. This document outlines our vulnerability reporting process, supply-chain security standards, and exception policies.

---

## 1. Reporting Security Vulnerabilities

If you discover a security vulnerability or sensitive defect in `postgres-mcp`, please **do not open a public GitHub issue**.

Instead, report it responsibly via:
- **GitHub Private Vulnerability Reporting**: Submit a private advisory through the repository's Security tab.
- **Maintainer Contact**: Contact the lead maintainer directly at `@Diaszano`.

We acknowledge receipt of security reports within 48 hours and provide status updates on remediation and coordinated release timelines.

---

## 2. Supply Chain Security and Artifact Attestations

All official release artifacts must satisfy strict supply-chain verification:

- **Immutable Package Registry**: Release images are published exclusively to GitHub Container Registry (`ghcr.io/diaszano/postgres-mcp`) with immutable digest references.
- **Software Bill of Materials (SBOM)**: Every published container release includes SPDX/CycloneDX SBOM attestations detailing installed system packages and Python dependencies.
- **Build Provenance**: Release images include SLSA-compliant build provenance attestations linking the container directly to the exact source commit SHA and GitHub Actions run.
- **Pinned Dependencies**: All dependencies are locked in `uv.lock`. Workflows pin all third-party GitHub Actions to immutable 40-character commit SHAs.

---

## 3. Vulnerability Waiver Policy

In rare circumstances where an upstream dependency contains a reported vulnerability without an available fix, and the vulnerability is verified to be non-exploitable in the context of `postgres-mcp`, a temporary waiver may be documented:

Every security waiver **must** explicitly document:
1. **Identifier**: Specific CVE or GHSA ID.
2. **Affected Package**: Name and exact version.
3. **Exploitability Analysis**: Detailed technical rationale explaining why the issue is non-exploitable in `postgres-mcp`.
4. **Reviewer Approval**: Sign-off from a repository owner (see [`.github/CODEOWNERS`](.github/CODEOWNERS)).
5. **Mandatory Expiration Date**: A strict waiver expiration date (maximum 30 days). Permanent or indefinite waivers are strictly prohibited and will fail automated CI security audits upon expiry.
