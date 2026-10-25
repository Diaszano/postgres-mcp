#!/usr/bin/env bash
# Build and verify a PostgreSQL container image with HypoPG extension installed.
# Fails fast if the package or extension is missing or cannot be activated.

set -euo pipefail

PG_VERSION="${1:-16}"
IMAGE_TAG="postgres-hypopg:${PG_VERSION}"

echo "==> Building PostgreSQL ${PG_VERSION} image with HypoPG (${IMAGE_TAG})..."

docker build -t "${IMAGE_TAG}" - <<EOF
FROM postgres:${PG_VERSION}
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-${PG_VERSION}-hypopg && \
    rm -rf /var/lib/apt/lists/*
EOF

echo "==> Verifying HypoPG extension activation in ${IMAGE_TAG}..."
docker run --rm \
  -e POSTGRES_PASSWORD=postgres \
  "${IMAGE_TAG}" \
  bash -c '
    set -euo pipefail
    docker-entrypoint.sh postgres &
    PID=$!
    for i in {1..30}; do
      if pg_isready -U postgres -h 127.0.0.1; then
        break
      fi
      sleep 0.5
    done
    psql -U postgres -h 127.0.0.1 -c "CREATE EXTENSION IF NOT EXISTS hypopg;"
    psql -U postgres -h 127.0.0.1 -c "SELECT hypopg_reset();"
    kill -SIGTERM "$PID"
    wait "$PID"
  '

echo "✅ PostgreSQL ${PG_VERSION} image with HypoPG verified successfully: ${IMAGE_TAG}"
