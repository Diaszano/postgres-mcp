#!/usr/bin/env bash
# Synchronize uv.lock with stamped project version and build immutable distributions.
# Executed automatically by Python Semantic Release as build_command.

set -euo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-postgres-mcp}"

echo "==> Synchronizing uv.lock for ${PACKAGE_NAME}..."
uv lock --upgrade-package "${PACKAGE_NAME}"

echo "==> Staging updated lockfile..."
git add uv.lock

echo "==> Verifying lockfile integrity..."
uv lock --check

echo "==> Building distribution packages (wheel + sdist)..."
uv build

echo "✅ Release build and lockfile synchronization completed successfully."
