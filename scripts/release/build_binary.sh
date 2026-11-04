#!/usr/bin/env bash
set -euo pipefail

# Build standalone executable and release tarball for postgres-mcp
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Target OS (darwin, linux)
TARGET_OS="${1:-$(uname -s | tr '[:upper:]' '[:lower:]')}"

# Target Arch (amd64, arm64)
RAW_ARCH="${2:-$(uname -m)}"
case "${RAW_ARCH}" in
  x86_64|amd64) TARGET_ARCH="amd64" ;;
  aarch64|arm64) TARGET_ARCH="arm64" ;;
  *) echo "Error: Unsupported architecture ${RAW_ARCH}" >&2; exit 1 ;;
esac

OUTPUT_DIR="${3:-${REPO_ROOT}/dist}"
mkdir -p "${OUTPUT_DIR}"

# Extract version from pyproject.toml if not passed in environment
if [[ -z "${VERSION:-}" ]]; then
  VERSION=$(python3 -c '
import tomllib
from pathlib import Path
pyproject = Path("pyproject.toml")
with open(pyproject, "rb") as f:
    data = tomllib.load(f)
print(data["project"]["version"])
')
fi

echo "==> Building postgres-mcp standalone binary for ${TARGET_OS}_${TARGET_ARCH} (version: ${VERSION})"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

TEMP_DIST="${WORK_DIR}/bin"
mkdir -p "${TEMP_DIST}"

# Compile standalone executable with PyInstaller
uv run --with pyinstaller pyinstaller \
  --onefile \
  --name postgres-mcp \
  --collect-all postgres_mcp \
  --collect-all psycopg \
  --collect-all pglast \
  --collect-all instructor \
  --collect-all humanize \
  --collect-all mcp \
  --clean \
  --distpath "${TEMP_DIST}" \
  --workpath "${WORK_DIR}/build" \
  --specpath "${WORK_DIR}" \
  "${REPO_ROOT}/src/postgres_mcp/__main__.py"

# Package into .tar.gz archive
ARCHIVE_NAME="postgres-mcp_${VERSION}_${TARGET_OS}_${TARGET_ARCH}.tar.gz"
ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}"

echo "==> Creating archive ${ARCHIVE_PATH}"
tar -czf "${ARCHIVE_PATH}" -C "${TEMP_DIST}" postgres-mcp

# Compute sha256 checksum
echo "==> Generating sha256 checksum"
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${OUTPUT_DIR}" && sha256sum "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256")
elif command -v shasum >/dev/null 2>&1; then
  (cd "${OUTPUT_DIR}" && shasum -a 256 "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256")
else
  python3 -c '
import hashlib, sys
from pathlib import Path
path = Path(sys.argv[1])
h = hashlib.sha256(path.read_bytes()).hexdigest()
out = Path(sys.argv[2])
out.write_text(f"{h}  {path.name}\n", encoding="utf-8")
' "${ARCHIVE_PATH}" "${ARCHIVE_PATH}.sha256"
fi

echo "✅ Successfully built: ${ARCHIVE_PATH}"
cat "${ARCHIVE_PATH}.sha256"
