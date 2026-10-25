#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPOSITORY="${1:-}"
IMAGE_DIGEST="${2:-}"
TAG="${3:-}"

if [[ -z "${IMAGE_REPOSITORY}" || -z "${IMAGE_DIGEST}" || -z "${TAG}" ]]; then
  echo "Usage: $0 <image-repository> <sha256-digest> <semver-tag>" >&2
  echo "Example: $0 ghcr.io/diaszano/postgres-mcp sha256:abcd... v0.3.0" >&2
  exit 1
fi

# Validate digest format strictly
if [[ ! "${IMAGE_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "Error: Invalid image digest format '${IMAGE_DIGEST}'. Expected sha256:<64 hex chars>." >&2
  exit 1
fi

# Validate release tag format strictly (vX.Y.Z)
if [[ ! "${TAG}" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "Error: Invalid release tag '${TAG}'. Must strictly follow 'vX.Y.Z'." >&2
  exit 1
fi

VERSION="${TAG#v}"
IFS='.' read -r MAJOR MINOR PATCH <<< "${VERSION}"

SOURCE_REF="${IMAGE_REPOSITORY}@${IMAGE_DIGEST}"

echo "==> Running fail-closed security scan on multiarch digest prior to promotion: ${SOURCE_REF}"
SCRIPTPATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPTPATH}/scan_image.sh" "${SOURCE_REF}"

echo "==> Promoting immutable digest to stable SemVer aliases:"
echo "    - ${IMAGE_REPOSITORY}:${TAG}"
echo "    - ${IMAGE_REPOSITORY}:${VERSION}"
echo "    - ${IMAGE_REPOSITORY}:${MAJOR}.${MINOR}"
echo "    - ${IMAGE_REPOSITORY}:${MAJOR}"
echo "    - ${IMAGE_REPOSITORY}:latest"

docker buildx imagetools create \
  --tag "${IMAGE_REPOSITORY}:${TAG}" \
  --tag "${IMAGE_REPOSITORY}:${VERSION}" \
  --tag "${IMAGE_REPOSITORY}:${MAJOR}.${MINOR}" \
  --tag "${IMAGE_REPOSITORY}:${MAJOR}" \
  --tag "${IMAGE_REPOSITORY}:latest" \
  "${SOURCE_REF}"

echo "✅ Successfully promoted ${SOURCE_REF} to release tags."
