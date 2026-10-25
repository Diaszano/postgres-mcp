#!/usr/bin/env bash
# Vulnerability scanner for multi-platform container images before promotion.
# Fails closed on any HIGH/CRITICAL finding, missing scanner, or invalid digest.

set -euo pipefail

IMAGE_REF="${1:-}"

if [[ -z "${IMAGE_REF}" ]]; then
  echo "❌ Error: Missing required image reference argument (IMAGE@sha256:DIGEST)." >&2
  exit 1
fi

# Enforce immutable sha256 digest reference
if [[ ! "${IMAGE_REF}" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo "❌ Error: Target must specify an immutable @sha256: digest, got: '${IMAGE_REF}'." >&2
  exit 1
fi

# Fail closed if scanner is missing
if ! command -v trivy &>/dev/null; then
  echo "❌ Error: Security scanner 'trivy' is not available on this runner (failing closed)." >&2
  exit 1
fi

PLATFORMS=("linux/amd64" "linux/arm64")

for platform in "${PLATFORMS[@]}"; do
  echo "==> Scanning container image ${IMAGE_REF} for platform ${platform}..."
  trivy image \
    --severity HIGH,CRITICAL \
    --exit-code 1 \
    --platform "${platform}" \
    --scanners vuln \
    "${IMAGE_REF}"
done

echo "✅ Security scan passed for all platforms: ${IMAGE_REF}"
