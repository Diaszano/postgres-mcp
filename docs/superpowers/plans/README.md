# PostgreSQL MCP — Superpowers Implementation Roadmap

> **Status:** All 7 implementation plans fully completed, tested with TDD, and verified with 702 unit tests passing.

**Source design:** `docs/superpowers/specs/2026-10-23-postgres-mcp-security-query-pagination-design.md`  
**Target:** `Diaszano/postgres-mcp` → `feature/multi-database`  
**Scope:** Same PostgreSQL instance; legacy non-paginated MCP calls preserved; new limits require guarded rollout.

## Execution order and release gates

| Order | Plan | Tasks | Dependencies | Ship gate | Spec criteria |
|---|---|---:|---|---|---|
| 01 | [Security Hardening](2026-10-23-01-security-hardening.md) | 4 | None; execute first | No URI leakage; restricted/HTTP security verified | FR-SEC-01/02; FR-QRY-05; FR-MCP-01 (safe error foundation); AC-01/02/03/04/05 |
| 02 | [AI-Controlled Query Budgets](2026-10-23-02-query-budgets.md) | 6 | Plan 01 safe error taxonomy; no dependence on pagination or session-affinity implementation | Hard budget and bounded-memory 1M-row suite | FR-QRY-01/02/03/04; FR-ARCH-01 (minimal service); AC-02/06/07/08/10 |
| 03 | [Physical Session Affinity for HypoPG](2026-10-23-03-session-affinity-hypopg.md) | 4 | Plan 01 SQL/security policy baseline | Real HypoPG same-session + cancellation tests | FR-SES-01/02/03; AC-19/20/21 |
| 04 | [Offset and Keyset Pagination](2026-10-23-04-pagination-cursors.md) | 6 | Plans 01+02; plan 05 structured response integration is consumed for final native MCP error/structuredOutput | Offset/keyset, TTL, auth and bounded cursors | FR-PAG-01/02/03/04/05/06; AC-11/12/13/14/15/16/17/18 |
| 05 | [Structured MCP Contracts and Modularity](2026-10-23-05-mcp-contracts-modularity.md) | 4 | Plans 01 and 02 for shared error/QueryExecutionService contracts; plan 04 for pagination success models (can implement first tasks earlier) | Native MCP wire contract and legacy tool tests | FR-MCP-01; FR-ARCH-01; FR-QRY-05; AC-09/10 |
| 06 | [Operational Observability](2026-10-23-06-observability.md) | 4 | Plans 02 and 04 for query/pagination events; plan 05 for runtime injection | Safe metrics and workload benchmarks | FR-OPS-01/02; AC-20/22 |
| 07 | [CI, Release and Documentation](2026-10-23-07-delivery-ci-docs.md) | 5 | Can repair justfile/lock early; update API docs and release gates only after plans 01-06 land | Clean CI matrix, docs, reproducible release smoke | FR-DX-01/02; AC-05/10/21/23/24 |

**Important coordination:** Plan 05's MCP error/structured-content adapter can be pulled forward directly after Plan 01, before Plan 04, if native errors are needed at the first shipping gate. Plan 07 justfile+lock corrections may be done early, but its release documentation and smoke tests must reflect actual shipped tool behavior. Distinct plans are independent *deliverables*, not permission to parallel-edit `server.py` in one worktree.

## Contract choices locked for planning (owner can change before execution)

- `execute_sql(sql, database=None, max_rows=None, timeout_seconds=None, page_size=None, pagination="none")`; existing positional parameters first.
- `fetch_query_page(cursor, page_size=None)` only; SQL/database inaccessible as override on continuation.
- Limits: guarded defaults 200 rows/15s; hard 5,000 rows/60s; response 2,097,152 bytes including metadata; max query concurrency 4.
- Pagination: opt-in; page default 100, max 1000, token TTL 300 seconds, max 100 active cursors; reject above hard maximum rather than clamping.
- Keyset first milestone: simple single-table ordered SELECT with a validated unique non-null ascending column; offset only on proven deterministic order; reject ambiguous AST shapes.
- Opaque random 256-bit handles with hash lookup, server-side TTL, principal binding and at-most-once consumption. No physical DB connection retained across MCP calls; consistency is best effort, not snapshot isolation.
- Guardrails initially off by default for backwards-compatible rollout; production deployment requires explicit secure profile and release note.
- No code commits, branches, GitHub issues/PRs or deployments were created by plan authoring.

## Advanced initiatives: separate owner-approved specs before implementation

The parent design explicitly defers the following independent products. **Do not treat these as implementation-ready tasks**; after stabilizing Plans 01–07, create one new `superpowers:brainstorming` design and `superpowers:writing-plans` plan per initiative:

| Future initiative | Required preceding decision and validation |
|---|---|
| ADV-01 Database profiles | Threat model for role/credential-per-database, privilege boundaries and authorization; regression test for no escalation |
| ADV-02 MCP Resources | Resource URI contract, client compatibility, authorization/size budgets, change invalidation |
| ADV-03 Compact overview | Query-count/token budget, omission metadata, no row-value leakage, cross-DB labeling |
| ADV-04 Explain/tuning intelligence | Query safety, opt-in external LLM data boundary, estimated vs measured evidence, explicit DDL approval |
| ADV-05 Redis/Valkey cursor backend | Only after multi-worker need; atomic consumption, binding, TTL, encryption/availability failure mode |

## Approval and implementation workflow

1. Owner reviews parent design's decisions and changes any policy/default values before implementation.
2. Owner reviews these seven plans and chooses execution method: **subagent-driven** (recommended for critical security) or **native**.
3. In execution, invoke `superpowers:using-git-worktrees`, then `superpowers:subagent-driven-development` or `superpowers:executing-plans`; follow task TDD and review gates.
4. Execute an independent end-to-end test/review and approve merge before release; do not claim test pass from plan text alone.
