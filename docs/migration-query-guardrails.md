# Query Guardrails & Cursor Pagination Migration Guide

This guide describes how to migrate to bounded query budgets and cursor pagination in **Postgres MCP**, while maintaining compatibility with legacy MCP clients.

## 1. Rollout and Backward Compatibility

By default, query guardrails are opt-in to avoid breaking legacy installations:

```bash
# Keep legacy behavior (unbounded row counts and default timeouts)
DATABASE_QUERY_GUARDRAILS_ENABLED=false

# Enforce production guardrails
DATABASE_QUERY_GUARDRAILS_ENABLED=true
```

When guardrails are enabled, queries exceeding the row ceiling are automatically truncated with a structured warning metadata envelope, rather than silently dropping rows or exhausting client memory.

## 2. Versioned Tool Contracts

### `execute_sql` & `read_query`
Clients can supply optional budget controls per tool call:
- `max_rows` (integer): Requested row limit for this execution (must be <= `DATABASE_QUERY_HARD_MAX_ROWS`).
- `timeout_seconds` (integer): Execution timeout in seconds (must be <= `DATABASE_QUERY_HARD_TIMEOUT_SECONDS`).

### `fetch_query_page`
When queries produce large result sets, the response includes an opaque continuation token `cursor`:

```json
{
  "rows": [...],
  "page": 1,
  "has_more": true,
  "cursor": "c3ViamVjdF9pZDoxMDA=",
  "truncated": false
}
```

To fetch subsequent rows:
```json
{
  "name": "fetch_query_page",
  "arguments": {
    "cursor": "c3ViamVjdF9pZDoxMDA="
  }
}
```

### Cursor Lifetime and Best-Effort Semantics
- **TTL**: Cursors expire after 300 seconds (`DATABASE_PAGINATION_CURSOR_TTL_SECONDS`). Stale or unknown cursor tokens return a structured `INVALID_CURSOR` error.
- **Single-use consumption**: Each cursor token is single-use; retrieving a page invalidates the previous token and returns a new one if more rows remain.
- **Best-Effort Consistency (No Snapshot Promises)**: Postgres MCP does not keep long-lived snapshot transactions open between HTTP or stdio requests to avoid transaction table bloat and lock contention. If rows are inserted, deleted, or modified between page requests, pagination operates on a best-effort basis without snapshot isolation guarantees across pages.
