#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPOSITORY="${1:-}"
IMAGE_DIGEST="${2:-}"
TAG="${3:-}"

if [[ -z "${IMAGE_REPOSITORY}" || -z "${IMAGE_DIGEST}" || -z "${TAG}" ]]; then
  echo "Usage: $0 <image-repository> <sha256-digest> <semver-tag>" >&2
  exit 1
fi

if [[ ! "${IMAGE_REPOSITORY}" =~ ^[a-z0-9]+([.-][a-z0-9]+)*(:[0-9]+)?(/[a-z0-9]+([._-][a-z0-9]+)*)+$ ]]; then
  echo "Error: Invalid image repository '${IMAGE_REPOSITORY}'." >&2
  exit 1
fi

if [[ ! "${IMAGE_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
  echo "Error: Invalid image digest format '${IMAGE_DIGEST}'. Expected sha256:<64 hex chars>." >&2
  exit 1
fi

if [[ ! "${TAG}" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  echo "Error: Invalid release tag '${TAG}'. Must strictly follow 'vX.Y.Z'." >&2
  exit 1
fi

VERSION="${TAG#v}"
IFS='.' read -r MAJOR MINOR PATCH <<< "${VERSION}"
SOURCE_REF="${IMAGE_REPOSITORY}@${IMAGE_DIGEST}"
SCRIPTPATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Running fail-closed security scan on multiarch digest: ${SOURCE_REF}"
bash "${SCRIPTPATH}/scan_image.sh" "${SOURCE_REF}"

inspect_digest() {
  local ref="$1" output digest
  if output=$(docker buildx imagetools inspect "${ref}" 2>&1); then
    digest="$(awk '$1 == "Digest:" { print $2 }' <<< "${output}")"
    if [[ ! "${digest}" =~ ^sha256:[a-f0-9]{64}$ ]]; then
      echo "Error: Could not read a valid manifest digest for ${ref}." >&2
      return 2
    fi
    printf '%s\n' "${digest}"
    return 0
  fi

  if [[ "${output,,}" == *"manifest unknown"* || "${output,,}" == *"not found"* || "${output,,}" =~ reference\ .+\ not\ found ]]; then
    return 1
  fi
  echo "Error: Could not inspect ${ref}: ${output}" >&2
  return 2
}

inspect_version() {
  local ref="$1" image_json version
  if ! image_json=$(docker buildx imagetools inspect --format '{{json .Image}}' "${ref}" 2>&1); then
    echo "Error: Could not inspect version metadata for ${ref}: ${image_json}" >&2
    return 1
  fi
  if ! version=$(PYTHONPATH="${SCRIPTPATH}/../.." python3 -c '
import json
import sys
from scripts.ci.validate_release import compare_release_versions

versions = []
def visit(value):
    if isinstance(value, dict):
        config = value.get("config")
        labels = config.get("Labels", {}) if isinstance(config, dict) else {}
        if isinstance(labels, dict) and labels.get("org.opencontainers.image.version"):
            versions.append(labels["org.opencontainers.image.version"])
        for child in value.values():
            visit(child)
    elif isinstance(value, list):
        for child in value:
            visit(child)

visit(json.load(sys.stdin))
if not versions or len(set(versions)) != 1:
    raise SystemExit(1)
compare_release_versions(versions[0], versions[0])
print(versions[0])
' <<< "${image_json}"); then
    echo "Error: Could not determine one stable image version for ${ref}." >&2
    return 1
  fi
  printf '%s\n' "${version}"
}

compare_versions() {
  PYTHONPATH="${SCRIPTPATH}/../.." python3 -c \
    'import sys; from scripts.ci.validate_release import compare_release_versions; print(compare_release_versions(sys.argv[1], sys.argv[2]))' \
    "$1" "$2"
}

TAGS_TO_PROMOTE=()

# Version tags are immutable: repair only a missing tag or one already at this digest.
for version_tag in "${TAG}" "${VERSION}"; do
  ref="${IMAGE_REPOSITORY}:${version_tag}"
  if current_digest=$(inspect_digest "${ref}"); then
    if [[ "${current_digest}" != "${IMAGE_DIGEST}" ]]; then
      echo "Error: Refusing to change immutable version tag ${ref} from ${current_digest}." >&2
      exit 1
    fi
  else
    inspect_status=$?
    if (( inspect_status != 1 )); then
      exit 1
    fi
    TAGS_TO_PROMOTE+=("${ref}")
  fi
done

# Floating aliases can move forward, but recovery cannot move them back.
for alias in "${MAJOR}.${MINOR}" "${MAJOR}" latest; do
  ref="${IMAGE_REPOSITORY}:${alias}"
  if current_digest=$(inspect_digest "${ref}"); then
    if [[ "${current_digest}" == "${IMAGE_DIGEST}" ]]; then
      continue
    fi
    current_version=$(inspect_version "${ref}") || exit 1
    comparison=$(compare_versions "${current_version}" "${VERSION}") || {
      echo "Error: Could not compare current image version ${current_version} with ${VERSION}." >&2
      exit 1
    }
    if (( comparison > 0 )); then
      echo "Keeping ${ref} at newer version ${current_version}."
      continue
    fi
  else
    inspect_status=$?
    if (( inspect_status != 1 )); then
      exit 1
    fi
  fi
  TAGS_TO_PROMOTE+=("${ref}")
done

if ((${#TAGS_TO_PROMOTE[@]})); then
  echo "==> Promoting ${SOURCE_REF} to: ${TAGS_TO_PROMOTE[*]}"
  create_args=()
  for ref in "${TAGS_TO_PROMOTE[@]}"; do
    create_args+=(--tag "${ref}")
  done
  docker buildx imagetools create "${create_args[@]}" "${SOURCE_REF}"
else
  echo "All requested version tags and aliases already point to ${IMAGE_DIGEST}."
fi

echo "✅ Successfully promoted ${SOURCE_REF}."
