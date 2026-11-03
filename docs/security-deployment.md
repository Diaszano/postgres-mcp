# Security and Production Deployment Guide

This document outlines the security architecture and deployment requirements for the **Postgres MCP Server**.

## 1. Least-Privilege Database Roles

Never connect the Postgres MCP Server using the `postgres` superuser account or an account with `CREATEDB` / `CREATEROLE` privileges.

### Recommended Role Permissions:
```sql
-- Create dedicated unprivileged MCP role
CREATE ROLE mcp_agent WITH LOGIN PASSWORD '${DB_PASSWORD}';

-- Grant connection only to specific application databases
GRANT CONNECT ON DATABASE app_production TO mcp_agent;

-- Grant read-only table access where required
GRANT USAGE ON SCHEMA public TO mcp_agent;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_agent;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_agent;

-- Grant stats inspection for performance diagnostics
GRANT pg_read_all_stats TO mcp_agent;
```

## 2. Multi-Database Isolation and Access Control

When `DATABASE_AUTO_DISCOVER=true`, the server dynamically lists and switches connection pools between PostgreSQL databases on the same host:

- `DATABASE_ALLOWED_DATABASES`: Comma-separated list of database names the MCP server is allowed to connect to.
- `DATABASE_EXCLUDED_DATABASES`: Comma-separated list of prohibited database names.
- `DATABASE_MAX_POOLS`: Maximum simultaneous connection pools (default: 4).
- `DATABASE_POOL_MAX_SIZE`: Connections per database pool (default: 2).
- `DATABASE_POOL_IDLE_SECONDS`: Idle connection pool reclamation threshold (default: 600).

## 3. Query Execution Guardrails

To prevent accidental denial-of-service, runaway full-table scans, or out-of-memory errors caused by LLM-generated SQL queries, enable query guardrails:

- `DATABASE_QUERY_GUARDRAILS_ENABLED`: Set to `true` to enforce execution limits (default: `false` during rollout for backward compatibility).
- `DATABASE_QUERY_DEFAULT_MAX_ROWS`: Default row limit per query (default: `200`).
- `DATABASE_QUERY_HARD_MAX_ROWS`: Maximum allowable row cap that clients cannot override (default: `5000`).
- `DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS`: Execution timeout in seconds (default: `15`).
- `DATABASE_QUERY_HARD_TIMEOUT_SECONDS`: Absolute query timeout ceiling (default: `60`).
- `DATABASE_QUERY_MAX_RESULT_BYTES`: Maximum byte size of JSON result encoding (default: `2097152` / 2MB).
- `DATABASE_QUERY_MAX_CONCURRENCY`: In-flight query limit per pool (default: `4`).

## 4. Cursor-Based Pagination

For large datasets, results are delivered in capped pages using the `fetch_query_page` tool:

- `DATABASE_PAGINATION_ENABLED`: Set to `true` to enable pagination (default: `true`).
- `DATABASE_PAGINATION_DEFAULT_PAGE_SIZE`: Default page size (default: `100`).
- `DATABASE_PAGINATION_MAX_PAGE_SIZE`: Maximum page size (default: `1000`).
- `DATABASE_PAGINATION_CURSOR_TTL_SECONDS`: Cursor lifetime before expiration (default: `300`).
- `DATABASE_PAGINATION_MAX_ACTIVE_CURSORS`: Memory-bounded active cursor capacity (default: `100`).

## 5. Network Ingress and Transport Security

When running with HTTP / SSE transport (`--transport=sse` or `--transport=streamable-http`):
- Run behind a TLS-terminating reverse proxy (e.g. Nginx, Envoy, Cloudflare).
- Enforce authentication on all remote HTTP endpoints. Anonymous ingress is strictly prohibited in production.
- Keep `DATABASE_METRICS_ENABLED=true` bound to loopback or protected administrative networks.

## 6. Supply Chain Security and GHCR Artifact Integrity

All container images and release artifacts published to GitHub Container Registry (GHCR) adhere to strict supply chain security standards:

- **GHCR Provenance & SLSA Attestations**: Container builds generate cryptographic SLSA provenance attestations linked to GitHub release commits.
- **SBOM Generation**: Each image release attaches a Software Bill of Materials (SBOM) in standard SPDX format, detailing exact dependency trees and licenses.
- **Immutable Digest Promotion**: Production promotion relies exclusively on immutable `sha256:[a-f0-9]{64}` image digests from staging builds, eliminating floating tag race conditions.
- **Action Pinning & Least Privilege**: CI/CD pipelines use explicit read-only token permissions (`contents: read`) and pin all third-party GitHub Actions to 40-character commit SHAs.
- **Continuous Vulnerability Scanning**: Fail-closed container vulnerability scans run on multi-arch images before promotion, blocking deployments on HIGH or CRITICAL findings.

