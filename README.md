<div align="center">

<img src="assets/postgres-mcp-pro.png" alt="Postgres MCP Pro Logo" width="600"/>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PyPI - Version](https://img.shields.io/pypi/v/postgres-mcp)](https://pypi.org/project/postgres-mcp/)
[![Discord](https://img.shields.io/discord/1336769798603931789?label=Discord)](https://discord.gg/4BEHC7ZM)
[![Twitter Follow](https://img.shields.io/twitter/follow/auto_dba?style=flat)](https://x.com/auto_dba)
[![Contributors](https://img.shields.io/github/contributors/crystaldba/postgres-mcp)](https://github.com/crystaldba/postgres-mcp/graphs/contributors)

<h3>A Postgres MCP server with index tuning, explain plans, health checks, and safe sql execution.</h3>

<div class="toc">
  <a href="#overview">Overview</a> •
  <a href="#demo">Demo</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#technical-notes">Technical Notes</a> •
  <a href="#mcp-server-api">MCP API</a> •
  <a href="#related-projects">Related Projects</a> •
  <a href="#frequently-asked-questions">FAQ</a>
</div>

</div>

> **English** | [Português (Brasil)](README.pt-BR.md)

## Overview

**Postgres MCP Pro** is an open source Model Context Protocol (MCP) server built to support you and your AI agents throughout the **entire development process**—from initial coding, through testing and deployment, and to production tuning and maintenance.

Postgres MCP Pro does much more than wrap a database connection.

Features include:

- **🔍 Database Health** - analyze index health, connection utilization, buffer cache, vacuum health, sequence limits, replication lag, and more.
- **⚡ Index Tuning** - explore thousands of possible indexes to find the best solution for your workload, using industrial-strength algorithms.
- **📈 Query Plans** - validate and optimize performance by reviewing EXPLAIN plans and simulating the impact of hypothetical indexes.
- **🧠 Schema Intelligence** - context-aware SQL generation based on detailed understanding of the database schema.
- **🛡️ Safe SQL Execution** - configurable access control, including support for read-only mode and safe SQL parsing, making it usable for both development and production.

Postgres MCP Pro supports both the [Standard Input/Output (stdio)](https://modelcontextprotocol.io/docs/concepts/transports#standard-input%2Foutput-stdio) and [Server-Sent Events (SSE)](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse) transports, for flexibility in different environments.

For additional background on why we built Postgres MCP Pro, see [our launch blog post](https://www.crystaldba.ai/blog/post/announcing-postgres-mcp-server-pro).

## Demo

*From Unusable to Lightning Fast*
- **Challenge:** We generated a movie app using an AI assistant, but the SQLAlchemy ORM code ran painfully slow.
- **Solution:** Using Postgres MCP Pro with Cursor, we fixed the performance issues in minutes.

What we did:
- 🚀 Fixed performance - including ORM queries, indexing, and caching
- 🛠️ Fixed a broken page - by prompting the agent to explore the data, fix queries, and add related content.
- 🧠 Improved the top movies - by exploring the data and fixing the ORM query to surface more relevant results.

See the video below or read the [play-by-play](examples/movie-app.md).

https://github.com/user-attachments/assets/24e05745-65e9-4998-b877-a368f1eadc13




## Quick Start

### Prerequisites

Before getting started, ensure you have:
1. Access credentials for your database.
2. Docker *or* Python 3.12 or higher.

#### Access Credentials
 You can confirm your access credentials are valid by using `psql` or a GUI tool such as [pgAdmin](https://www.pgadmin.org/).


#### Docker or Python

The choice to use Docker or Python is yours.
We generally recommend Docker because Python users can encounter more environment-specific issues.
However, it often makes sense to use whichever method you are most familiar with.


### Installation

Choose one of the following methods to install Postgres MCP Pro:

#### Option 1: Using Docker

Pull the Postgres MCP Pro MCP server Docker image.
This image contains all necessary dependencies, providing a reliable way to run Postgres MCP Pro in a variety of environments.

```bash
docker pull crystaldba/postgres-mcp
```


#### Option 2: Using Python

If you have `pipx` installed you can install Postgres MCP Pro with:

```bash
pipx install postgres-mcp
```

Otherwise, install Postgres MCP Pro with `uv`:

```bash
uv pip install postgres-mcp
```

If you need to install `uv`, see the [uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).


### Configure Your AI Assistant

We provide full instructions for configuring Postgres MCP Pro with Claude Desktop.
Many MCP clients have similar configuration files, you can adapt these steps to work with the client of your choice.

#### Claude Desktop Configuration

You will need to edit the Claude Desktop configuration file to add Postgres MCP Pro.
The location of this file depends on your operating system:
- MacOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

You can also use `Settings` menu item in Claude Desktop to locate the configuration file.

You will now edit the `mcpServers` section of the configuration file.

##### If you are using Docker

```json
{
  "mcpServers": {
    "postgres": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "DATABASE_URI",
        "-e",
        "DATABASE_DOCKER_REMAP_LOCALHOST",
        "crystaldba/postgres-mcp",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname",
        "DATABASE_DOCKER_REMAP_LOCALHOST": "true"
      }
    }
  }
}
```

Docker hostname remapping is disabled by default. Set `DATABASE_DOCKER_REMAP_LOCALHOST=true` in the container environment to remap a `localhost` database host. The entrypoint uses `host.docker.internal` on MacOS/Windows or `172.17.0.1` on Linux when reachable.

##### If you are using `uvx`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uvx",
      "args": [
        "postgres-mcp",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### If you are using `pipx`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "postgres-mcp",
      "args": [
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### If you are using `uv`

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": [
        "run",
        "postgres-mcp",
        "--access-mode=unrestricted"
      ],
      "env": {
        "DATABASE_URI": "postgresql://username:password@localhost:5432/dbname"
      }
    }
  }
}
```


##### Connection URI

Replace `postgresql://...` with your [Postgres database connection URI](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING-URIS).


##### Access Mode

Postgres MCP Pro supports multiple *access modes* to give you control over the operations that the AI agent can perform on the database:
- **Unrestricted Mode**: Allows full read/write access to modify data and schema. It is suitable for development environments.
- **Restricted Mode**: Limits operations to read-only transactions and imposes constraints on resource utilization (presently only execution time). Only `SELECT`, `EXPLAIN` (without `ANALYZE`), `SHOW`, and `ANALYZE` statements are allowed; `VACUUM` is rejected because it cannot run inside a transaction block. A rejected statement returns an error that states the reason. It is suitable for production environments.

To use restricted mode, replace `--access-mode=unrestricted` with `--access-mode=restricted` in the configuration examples above.


#### Other MCP Clients

Many MCP clients have similar configuration files to Claude Desktop, and you can adapt the examples above to work with the client of your choice.

- If you are using Cursor, you can use navigate from the `Command Palette` to `Cursor Settings`, then open the `MCP` tab to access the configuration file.
- If you are using Windsurf, you can navigate to from the `Command Palette` to `Open Windsurf Settings Page` to access the configuration file.
- If you are using Goose run `goose configure`, then select `Add Extension`.
- If you are using Qodo Gen, open the Chat panel, click `Connect more tools`, click `+ Add new MCP`, then add the new configuration.

## SSE Transport

Postgres MCP Pro supports the [SSE transport](https://modelcontextprotocol.io/docs/concepts/transports#server-sent-events-sse), which allows multiple MCP clients to share one server, possibly a remote server.
To use the SSE transport, you need to start the server with the `--transport=sse` option.

For a local client, run the server on the same host:

```bash
DATABASE_URI='postgresql://username:password@localhost:5432/dbname' \
  uvx postgres-mcp --access-mode=restricted --transport=sse
```

Then update your MCP client configuration to call the the MCP server.
For example, in Cursor's `mcp.json` or Cline's `cline_mcp_settings.json` you can put:

```json
{
    "mcpServers": {
        "postgres": {
            "type": "sse",
            "url": "http://localhost:8000/sse"
        }
    }
}
```

For Windsurf, the format in `mcp_config.json` is slightly different:

```json
{
    "mcpServers": {
        "postgres": {
            "type": "sse",
            "serverUrl": "http://localhost:8000/sse"
        }
    }
}
```

## Authenticated HTTP deployment

**Migration:** SSE and Streamable HTTP still bind to `localhost` by default. Non-loopback binds, including `0.0.0.0`, `::`, private IPs and hostnames other than `localhost`, now fail before database connections or HTTP startup unless all three variables below are valid. Stdio ignores HTTP settings and requires no HTTP credentials. `DATABASE_URI`, access modes and tool parameters are unchanged.

| Variable | Required value for authenticated HTTP |
| --- | --- |
| `MCP_HTTP_AUTH_TOKEN` | A randomly generated bearer secret of at least 32 printable ASCII characters, without spaces. Keep it out of command arguments and source control. |
| `MCP_HTTP_ALLOWED_HOSTS` | Comma-separated exact Host headers, including ports when clients send them, such as `mcp.example.com` or `mcp.example.com:8443`. Wildcards and URLs are rejected. |
| `MCP_HTTP_ALLOWED_ORIGINS` | Comma-separated exact HTTPS origins, such as `https://client.example.com`. Paths, credentials and wildcards are rejected. |

Configure the secret through your service's secret store or environment, then run behind a TLS-terminating HTTPS proxy:

```bash
export MCP_HTTP_ALLOWED_HOSTS='mcp.example.com'
export MCP_HTTP_ALLOWED_ORIGINS='https://client.example.com'
# MCP_HTTP_AUTH_TOKEN and DATABASE_URI are supplied securely by the service environment.
uvx postgres-mcp --access-mode=restricted --transport=streamable-http
```

Use `/mcp` for Streamable HTTP or `--transport=sse` with `/sse` and `/messages/` for SSE. Clients must send `Authorization: Bearer <secret>` on every HTTP request, including SSE message POSTs. Anonymous or invalid-token requests receive 401. Authenticated requests with an unlisted Host receive 421, and those with an unlisted Origin receive 403. Native clients may omit Origin. The MCP SDK exposes the stable principal `configured-http-client`; all holders of this shared secret have the same database access. This is a pre-provisioned bearer credential, without an OAuth login or per-user authorization service. Rotate it by changing the secret and restarting the process.

The proxy must preserve Authorization, the public Host and any Origin header. Terminate TLS at the proxy, expose only its HTTPS listener, rate-limit connections and requests (including concurrent SSE streams), and prevent direct access to the backend with loopback binding or firewall rules. Do not log Authorization headers, secrets or database payloads at the proxy. A trusted-ingress declaration alone cannot enable public binding or bypass bearer verification. For a private container/backend bind, pass `--streamable-http-host=0.0.0.0` or `--sse-host=0.0.0.0` **with the same authentication variables** and restrict its network access to the ingress. Publishing a container port alone does not expose a process bound to the container's loopback interface.

The authentication, principal and Host/Origin path is exercised against MCP SDK 1.25.0 in the focused transport tests. TLS termination, proxy isolation and rate limits are deployment responsibilities; no proxy deployment is installed or verified by this repository.

## Multiple Databases (Optional)

By default Postgres MCP Pro talks to the single database named in `DATABASE_URI`, exactly as before.
Set `DATABASE_AUTO_DISCOVER=true` to let the agent discover and choose among the databases of the same PostgreSQL instance.
Every tool accepts an optional `database` argument; when it is omitted the default database is used, never the one used by a previous call.

### Legacy mode (default)

```bash
DATABASE_URI='postgresql://user:password@localhost:5432/app_development' uvx postgres-mcp
```

- One connection pool, to the database in the URI (a URI passed as a command-line argument still works).
- Default access mode stays `unrestricted`.
- `database` is accepted only when it equals the URI database; any other name is rejected with an error (no discovery, no fallback).
- `list_databases` returns only that database. If the URI has no database name, `name` is `null`.
- `DATABASE_ALLOWED_DATABASES`, `DATABASE_EXCLUDED_DATABASES` and the other variables below have no effect.

### Discovery mode

```bash
DATABASE_URI='postgresql://dev:password@localhost:5432/postgres'
DATABASE_AUTO_DISCOVER=true
DATABASE_DEFAULT_DATABASE=app_development
DATABASE_ALLOWED_DATABASES=app_development,app_testing,analytics
DATABASE_EXCLUDED_DATABASES=postgres

uvx postgres-mcp
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASE_URI` | required | Bootstrap URI. It is used to query `pg_database`, and its host, port, user, password, TLS and other options are reused for every database; only `dbname` changes. |
| `DATABASE_AUTO_DISCOVER` | `false` | `true`/`false`, `1`/`0` or `yes`/`no`. Enables discovery and the `database` argument. |
| `DATABASE_DEFAULT_DATABASE` | `dbname` of `DATABASE_URI` | Database used when `database` is omitted. Required if the URI has no `dbname`. |
| `DATABASE_ALLOWED_DATABASES` | empty (all eligible) | Allowlist of exact, case-sensitive names. |
| `DATABASE_EXCLUDED_DATABASES` | empty | Denylist of exact names. It wins over the allowlist. |
| `DATABASE_DISCOVERY_TTL_SECONDS` | `60` | How long the discovered list is cached. |
| `DATABASE_MAX_POOLS` | `4` | Maximum number of database pools open at the same time. |
| `DATABASE_POOL_MAX_SIZE` | `2` | Maximum connections per database pool. |
| `DATABASE_POOL_IDLE_SECONDS` | `600` | Idle time after which an unused pool may be closed. |
| `DATABASE_QUERY_GUARDRAILS_ENABLED` | `false` | Enables SQL query budgets. Remote transports warn at startup while disabled. |
| `DATABASE_QUERY_DEFAULT_MAX_ROWS` | `200` | Default maximum rows returned by one query. |
| `DATABASE_QUERY_HARD_MAX_ROWS` | `5000` | Maximum row limit a tool call may request. |
| `DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS` | `15` | Default query timeout in seconds. |
| `DATABASE_QUERY_HARD_TIMEOUT_SECONDS` | `60` | Maximum timeout a tool call may request. |
| `DATABASE_QUERY_MAX_RESULT_BYTES` | `2097152` | Maximum serialized result size in bytes; maximum configurable value is 64 MiB. |
| `DATABASE_QUERY_MAX_CONCURRENCY` | `4` | Maximum concurrent budgeted SQL executions; maximum configurable value is 256. |

Both list variables accept a comma-separated list (`app,testing`, spaces around names are trimmed) or, when the value starts with `[`, a JSON array of strings (`["app", "name,with,comma"]`).
Use the JSON form for names that contain commas. Names are never lower-cased or otherwise normalized.
Numeric variables must be integers of at least 1; invalid values stop the server at startup with an error that never includes the URI or password. Query guardrail settings are strict positive integers; default row and timeout values cannot exceed their hard limits. Row limits are capped at 10,000,000 and timeout limits at 3,600 seconds. Guardrails default to disabled during migration.

**What is discoverable.** A database is listed only if it is not a template, accepts connections, the role has `CONNECT` on it, and it passes the allow and deny lists.
The database in `DATABASE_URI` is only the bootstrap connection: it is not special.
It is usable by the tools only if it is also eligible, so the URI may point at `postgres` while `postgres` is excluded.
The default database must itself be eligible: if the filters exclude it, or it does not exist or is not connectable, the server fails with a configuration error instead of silently picking another database.

**Access mode.** With `DATABASE_AUTO_DISCOVER=true` and no `--access-mode`, the server runs in `restricted` mode.
Writes are enabled only by an explicit `--access-mode=unrestricted`, which logs a warning at startup and is still limited by the real privileges of the PostgreSQL role.
Without discovery the default remains `unrestricted`.
The mode is global to the server process, not per database.
`restricted` is an extra layer, not a substitute for a least-privilege PostgreSQL role.

**Lazy pools, limits and idle cleanup.**
- No pool is opened at startup and `list_databases` never opens one; a pool is created on the first tool call that targets a database (`min_size=0`, up to `DATABASE_POOL_MAX_SIZE` connections).
- At most `DATABASE_MAX_POOLS` pools are open. Reaching the limit closes the least recently used pool that has no call in progress. If every pool is in use, the call fails with an explicit capacity error and nothing is closed.
- A pool is held for the whole duration of a tool call, so it is never closed under a running call.
- Idle pools older than `DATABASE_POOL_IDLE_SECONDS` are closed opportunistically on later calls and catalog refreshes; there is no background timer.
- Databases that disappear from the catalog stop accepting new calls and their pool is closed when running calls finish.
- A connection failure on one database is reported for that database only; other databases and the pool of the failing one keep working after the problem is fixed. Ordinary SQL errors do not invalidate a pool.
- Calls that wait for a pool that is being opened share that open's result. If the open fails, they get the same error instead of each retrying the connection in turn.

**Refresh.** The list is cached for `DATABASE_DISCOVERY_TTL_SECONDS`. A database created later is picked up by `list_databases` with `refresh=true`, or by the first call after the TTL expires, without restarting the server.
Asking for an unknown name forces a refresh before the call is rejected.
Forced refreshes (`refresh=true` or an unknown name) run at most once every 5 seconds; inside that window the cached list is used, and concurrent requests share one in-flight discovery.
A discovery query that does not finish within 10 seconds counts as a failed refresh.
If a refresh fails, the previous list is served for a short grace period (at most 300 seconds), without admitting new names, and `list_databases` reports `catalog_stale: true`.
If there is no valid list yet, the call fails with a "discovery is unavailable" error.
If the bootstrap database is unreachable at startup the server still starts, in a degraded state.

**Same-instance restriction.** All databases come from the instance addressed by `DATABASE_URI`. The `database` argument takes only a database name, never a DSN, host or schema, so there is no way to reach another server, and a name is never spliced into SQL. Nothing connects to a database that was not discovered and authorized.
Databases are separate connections: there is no cross-database SQL.

**Instance-wide metrics.**
- `get_top_queries` and the index tuning tools read `pg_stat_statements` only for the selected database (filtered by `dbid`). The extension must be installed in each database you query; a missing extension is reported for that database.
- `analyze_db_health`: the `connection` and `replication` checks describe the whole instance and are labelled `[instance-wide]` in the output; the other checks run against the selected database.

### Choosing a database

`list_databases` takes an optional `refresh` argument and returns JSON like:

```json
[
  {"name": "analytics", "is_default": false, "connection_state": "not_connected", "catalog_stale": false},
  {"name": "app_development", "is_default": true, "connection_state": "connected", "catalog_stale": false}
]
```

`connection_state` is `connected` (pool open), `not_connected` (no pool yet) or `unavailable` (the last attempt to open a pool failed).
Example prompts:

> Which databases can you see? Refresh the list first.

> List the tables of the `public` schema in `app_testing`, then compare them with `analytics`.

> Run `SELECT current_database()` on `analytics`.

The same call, as tool arguments: `{"sql": "SELECT current_database()", "database": "analytics"}`.

## Postgres Extension Installation (Optional)

To enable index tuning and comprehensive performance analysis you need to load the `pg_stat_statements` and `hypopg` extensions on your database.

- The `pg_stat_statements` extension allows Postgres MCP Pro to analyze query execution statistics.
For example, this allows it to understand which queries are running slow or consuming significant resources.
- The `hypopg` extension allows Postgres MCP Pro to simulate the behavior of the Postgres query planner after adding indexes.

### Installing extensions on AWS RDS, Azure SQL, or Google Cloud SQL

If your Postgres database is running on a cloud provider managed service, the `pg_stat_statements` and `hypopg` extensions should already be available on the system.
In this case, you can just run `CREATE EXTENSION` commands using a role with sufficient privileges:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS hypopg;
```

### Installing extensions on self-managed Postgres

If you are managing your own Postgres installation, you may need to do additional work.
Before loading the `pg_stat_statements` extension you must ensure that it is listed in the `shared_preload_libraries` in the Postgres configuration file.
The `hypopg` extension may also require additional system-level installation (e.g., via your package manager) because it does not always ship with Postgres.

## Usage Examples

### Get Database Health Overview

Ask:
> Check the health of my database and identify any issues.

### Analyze Slow Queries

Ask:
> What are the slowest queries in my database? And how can I speed them up?

### Get Recommendations On How To Speed Things Up

Ask:
> My app is slow. How can I make it faster?

### Generate Index Recommendations

Ask:
> Analyze my database workload and suggest indexes to improve performance.

### Optimize a Specific Query

Ask:
> Help me optimize this query: SELECT \* FROM orders JOIN customers ON orders.customer_id = customers.id WHERE orders.created_at > '2023-01-01';

## MCP Server API

The [MCP standard](https://modelcontextprotocol.io/) defines various types of endpoints: Tools, Resources, Prompts, and others.

Postgres MCP Pro provides functionality via [MCP tools](https://modelcontextprotocol.io/docs/concepts/tools) alone.
We chose this approach because the [MCP client ecosystem](https://modelcontextprotocol.io/clients) has widespread support for MCP tools.
This contrasts with the approach of other Postgres MCP servers, including the [Reference Postgres MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), which use [MCP resources](https://modelcontextprotocol.io/docs/concepts/resources) to expose schema information.


Postgres MCP Pro Tools (all except `list_databases` accept an optional `database` argument, see [Multiple Databases](#multiple-databases-optional)):

| Tool Name | Description |
|-----------|-------------|
| `list_databases` | Lists the databases the server can use, the default, connection state and whether the list is stale (`refresh` forces a new query). Never opens connections. |
| `list_schemas` | Lists all database schemas available in the PostgreSQL instance. |
| `list_objects` | Lists database objects (tables, views, sequences, extensions) within a specified schema. |
| `get_object_details` | Provides information about a specific database object, for example, a table's columns, constraints, and indexes. |
| `execute_sql` | Executes SQL statements on the database, with read-only limitations when connected in restricted mode. |
| `explain_query` | Gets the execution plan for a SQL query describing how PostgreSQL will process it and exposing the query planner's cost model. Can be invoked with hypothetical indexes to simulate the behavior after adding indexes. |
| `get_top_queries` | Reports the slowest SQL queries based on total execution time using `pg_stat_statements` data. |
| `analyze_workload_indexes` | Analyzes the database workload to identify resource-intensive queries, then recommends optimal indexes for them. |
| `analyze_query_indexes` | Analyzes a list of specific SQL queries (up to 10) and recommends optimal indexes for them. |
| `analyze_db_health` | Performs comprehensive health checks including: buffer cache hit rates, connection health, constraint validation, index health (duplicate/unused/invalid), sequence limits, and vacuum health. |


## Related Projects

**Postgres MCP Servers**
- [Query MCP](https://github.com/alexander-zuev/supabase-mcp-server). An MCP server for Supabase Postgres with a three-tier safety architecture and Supabase management API support.
- [PG-MCP](https://github.com/stuzero/pg-mcp-server). An MCP server for PostgreSQL with flexible connection options, explain plans, extension context, and more.
- [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres). A simple MCP Server implementation exposing schema information as MCP resources and executing read-only queries.
- [Supabase Postgres MCP Server](https://github.com/supabase-community/supabase-mcp). This MCP Server provides Supabase management features and is actively maintained by the Supabase community.
- [Nile MCP Server](https://github.com/niledatabase/nile-mcp-server). An MCP server providing access to the management API for the Nile's multi-tenant Postgres service.
- [Neon MCP Server](https://github.com/neondatabase-labs/mcp-server-neon). An MCP server providing access to the management API for Neon's serverless Postgres service.
- [Wren MCP Server](https://github.com/Canner/wren-engine). Provides a semantic engine powering business intelligence for Postgres and other databases.

**DBA Tools (including commercial offerings)**
- [Aiven Database Optimizer](https://aiven.io/solutions/aiven-ai-database-optimizer). A tool that provides holistic database workload analysis, query optimizations, and other performance improvements.
- [dba.ai](https://www.dba.ai/). An AI-powered database administration assistant that integrates with GitHub to resolve code issues.
- [pgAnalyze](https://pganalyze.com/). A comprehensive monitoring and analytics platform for identifying performance bottlenecks, optimizing queries, and real-time alerting.
- [Postgres.ai](https://postgres.ai/). An interactive chat experience combining an extensive Postgres knowledge base and GPT-4.
- [Xata Agent](https://github.com/xataio/agent). An open-source AI agent that automatically monitors database health, diagnoses issues, and provides recommendations using LLM-powered reasoning and playbooks.

**Postgres Utilities**
- [Dexter](https://github.com/DexterDB/dexter). A tool for generating and testing hypothetical indexes on PostgreSQL.
- [PgHero](https://github.com/ankane/pghero). A performance dashboard for Postgres, with recommendations.
Postgres MCP Pro incorporates health checks from PgHero.
- [PgTune](https://github.com/le0pard/pgtune?tab=readme-ov-file). Heuristics for tuning Postgres configuration.

## Frequently Asked Questions

*How is Postgres MCP Pro different from other Postgres MCP servers?*
There are many MCP servers allow an AI agent to run queries against a Postgres database.
Postgres MCP Pro does that too, but also adds tools for understanding and improving the performance of your Postgres database.
For example, it implements a version of the [Anytime Algorithm of Database Tuning Advisor for Microsoft SQL Server](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/06/Anytime-Algorithm-of-Database-Tuning-Advisor-for-Microsoft-SQL-Server.pdf), a modern industrial-strength algorithm for automatic index tuning.

| Postgres MCP Pro | Other Postgres MCP Servers |
|--------------|----------------------------|
| ✅ Deterministic database health checks | ❌ Unrepeatable LLM-generated health queries |
| ✅ Principled indexing search strategies | ❌ Gen-AI guesses at indexing improvements |
| ✅ Workload analysis to find top problems | ❌ Inconsistent problem analysis |
| ✅ Simulates performance improvements | ❌ Try it yourself and see if it works |

Postgres MCP Pro complements generative AI by adding deterministic tools and classical optimization algorithms
The combination is both reliable and flexible.


*Why are MCP tools needed when the LLM can reason, generate SQL, etc?*
LLMs are invaluable for tasks that involve ambiguity, reasoning, or natural language.
When compared to procedural code, however, they can be slow, expensive, non-deterministic, and sometimes produce unreliable results.
In the case of database tuning, we have well established algorithms, developed over decades, that are proven to work.
Postgres MCP Pro lets you combine the best of both worlds by pairing LLMs with classical optimization algorithms and other procedural tools.

*How do you test Postgres MCP Pro?*
Testing is critical to ensuring that Postgres MCP Pro is reliable and accurate.
We are building out a suite of AI-generated adversarial workloads designed to challenge Postgres MCP Pro and ensure it performs under a broad variety of scenarios.

*What Postgres versions are supported?*
Our testing presently focuses on Postgres 15, 16, and 17.
We plan to support Postgres versions 13 through 17.

*Who created this project?*
This project is created and maintained by [Crystal DBA](https://www.crystaldba.ai).

## Roadmap

*TBD*

You and your needs are a critical driver for what we build.
Tell us what you want to see by opening an [issue](https://github.com/crystaldba/postgres-mcp/issues) or a [pull request](https://github.com/crystaldba/postgres-mcp/pulls).
You can also contact us on [Discord](https://discord.gg/4BEHC7ZM).

## Technical Notes

This section includes a high-level overview technical considerations that influenced the design of Postgres MCP Pro.

### Index Tuning

Developers know that missing indexes are one of the most common causes of database performance issues.
Indexes provide access methods that allow Postgres to quickly locate data that is required to execute a query.
When tables are small, indexes make little difference, but as the size of the data grows, the difference in algorithmic complexity between a table scan and an index lookup becomes significant (typically *O*(*n*) vs *O*(*log* *n*), potentially more if joins on multiple tables are involved).

Generating suggested indexes in Postgres MCP Pro proceeds in several stages:

1. *Identify SQL queries in need of tuning*.
    If you know you are having a problem with a specific SQL query you can provide it.
    Postgres MCP Pro can also analyze the workload to identify index tuning targets.
    To do this, it relies on the `pg_stat_statements` extension, which records the runtime and resource consumption of each query.

    A query is a candidate for index tuning if it is a top resource consumer, either on a per-execution basis or in aggregate.
    At present, we use execution time as a proxy for cumulative resource consumption, but it may also make sense to look at specifics resources, e.g., the number of blocks accessed or the number of blocks read from disk.
    The `analyze_query_workload` tool focuses on slow queries, using the mean time per execution with thresholds for execution count and mean execution time.
    Agents may also call `get_top_queries`, which accepts a parameter for mean vs. total execution time, then pass these queries `analyze_query_indexes` to get index recommendations.

    Sophisticated index tuning systems use "workload compression" to produce a representative subset of queries that reflects the characteristics of the workload as a whole, reducing the problem for downstream algorithms.
    Postgres MCP Pro performs a limited form of workload compression by normalizing queries so that those generated from the same template appear as one.
    It weights each query equally, a simplification that works when the benefits to indexing are large.

2. *Generate candidate indexes*
    Once we have a list of SQL queries that we want to improve through indexing, we generate a list of indexes that we might want to add.
    To do this, we parse the SQL and identify any columns used in filters, joins, grouping, or sorting.

    To generate all possible indexes we need to consider combinations of these columns, because Postgres supports [multicolumn indexes](https://www.postgresql.org/docs/current/indexes-multicolumn.html).
    In the present implementation, we include only one permutation of each possible multicolumn index, which is selected at random.
    We make this simplification to reduce the search space because permutations often have equivalent performance.
    However, we hope to improve in this area.

3. *Search for the optimal index configuration*.
    Our objective is to find the combination of indexes that optimally balances the performance benefits against the costs of storing and maintaining those indexes.
    We estimate the performance improvement by using the "what if?" capabilities provided by the `hypopg` extension.
    This simulates how the Postgres query optimizer will execute a query after the addition of indexes, and reports changes based on the actual Postgres cost model.

    One challenge is that generating query plans generally requires knowledge of the specific parameter values used in the query.
    Query normalization, which is necessary to reduce the queries under consideration, removes parameter constants.
    Parameter values provided via bind variables are similarly not available to us.

    To address this problem, we produce realistic constants that we can provide as parameters by sampling from the table statistics.
    In version 16, Postgres added [generic explain plan functionality](https://www.postgresql.org/docs/current/sql-explain.html), but it has limitations, for example around `LIKE` clauses, which our implementation does not have.

    Search strategy is critical because evaluating all possible index combinations feasible only in simple situations.
    This is what most sets apart various indexing approaches.
    Adapting the approach of Microsoft's Anytime algorithm, we employ a greedy search strategy, i.e., find the best one-index solution, then find the best index to add to that to produce a two-index solution.
    Our search terminates when the time budget is exhausted or when a round of exploration fails to produce any gains above the minimum improvement threshold of 10%.

4. *Cost-benefit analysis*.
    When posed with two indexing alternatives, one which produces better performance and one which requires more space, how do we decide which to choose?
    Traditionally, index advisors ask for a storage budget and optimize performance with respect to that storage budget.
    We also take a storage budget, but perform a cost-benefit analysis throughout the optimization.

    We frame this as the problem of selecting a point along the [Pareto front](https://en.wikipedia.org/wiki/Pareto_front)—the set of choices for which improving one quality metric necessarily worsens another.
    In an ideal world, we might want to assess the cost of the storage and the benefit of improved performance in monetary terms.
    However, there is a simpler and more practical approach: to look at the changes in relative terms.
    Most people would agree that a 100x performance improvement is worth it, even if the storage cost is 2x.
    In our implementation, we use a configurable parameter to set this threshold.
    By default, we require the change in the log (base 10) of the performance improvement to be 2x the difference in the log of the space cost.
    This works out to allowing a maximum 10x increase in space for a 100x performance improvement.

Our implementation is most closely related to the [Anytime Algorithm](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/06/Anytime-Algorithm-of-Database-Tuning-Advisor-for-Microsoft-SQL-Server.pdf) found in Microsoft SQL Server.
Compared to [Dexter](https://github.com/ankane/dexter/), an automatic indexing tool for Postgres, we search a larger space and use different heuristics.
This allows us to generate better solutions at the cost of longer runtime.

We also show the work done in each round of the search, including a comparison of the query plans before and after the addition of each index.
This give the LLM additional context that it can use when responding to the indexing recommendations.

### Experimental: Index Tuning by LLM

Postgres MCP Pro includes an experimental index tuning feature based on [Optimization by LLM](https://arxiv.org/abs/2309.03409).
Instead of using heuristics to explore possible index configurations, we provide the database schema and query plans to an LLM and ask it to propose index configurations.
We then use `hypopg` to predict performance with the proposed indexes, then feed those results back into the LLM to produce a new set of suggestions.
We repeat this process until multiple rounds of iteration produce no further improvements.

Index optimization by LLM is has advantages when the index search space is large, or when indexes with many columns need to be considered.
Like traditional search-based approaches, it relies on the accuracy of the `hypopg` performance predictions.

In order to perform index optimization by LLM, you must provide an OpenAI API key by setting the `OPENAI_API_KEY` environment variable.


### Database Health

Database health checks identify tuning opportunities and maintenance needs before they lead to critical issues.
In the present release, Postgres MCP Pro adapts the database health checks directly from [PgHero](https://github.com/ankane/pghero).
We are working to fully validate these checks and may extend them in the future.

- *Index Health*. Looks for unused indexes, duplicate indexes, and indexes that are bloated. Bloated indexes make inefficient use of database pages.
  Postgres autovacuum cleans up index entries pointing to dead tuples, and marks the entries as reusable. However, it does not compact the index pages and, eventually, index pages may contain few live tuple references.
- *Buffer Cache Hit Rate*. Measures the proportion of database reads that are served from the buffer cache instead of disk.
  A low buffer cache hit rate must be investigated as it is often not cost-optimal and leads to degraded application performance.
- *Connection Health*. Checks the number of connections to the database and reports on their utilization.
  The biggest risk is running out of connections, but a high number of idle or blocked connections can also indicate issues.
- *Vacuum Health*. Vacuum is important for many reasons.
  A critical one is preventing transaction id wraparound, which can cause the database to stop accepting writes.
  The Postgres multi-version concurrency control (MVCC) mechanism requires a unique transaction id for each transaction.
  However, because Postgres uses a 32-bit signed integer for transaction ids, it needs to reuse transaction ids after after a maximum of 2 billion transactions.
  To do this it "freezes" the transaction ids of historical transactions, setting them all to a special value that indicates distant past.
  When records first go to disk, they are written visibility for a range of transaction ids.
  Before re-using these transaction ids, Postgres must update any on-disk records, "freezing" them to remove the references to the transaction ids to be reused.
  This check looks for tables that require vacuuming to prevent transaction id wraparound.
- *Replication Health*. Checks replication health by monitoring lag between primary and replicas, verifying replication status, and tracking usage of replication slots.
- *Constraint Health*. During normal operation, Postgres rejects any transactions that would cause a constraint violation.
  However, invalid constraints may occur after loading data or in recovery scenarios. This check looks for any invalid constraints.
- *Sequence Health*. Looks for sequences that are at risk of exceeding their maximum value.


### Postgres Client Library

Postgres MCP Pro uses [psycopg3](https://www.psycopg.org/) to connect to Postgres using asynchronous I/O.
Under the hood, psycopg3 uses the [libpq](https://www.postgresql.org/docs/current/libpq.html) library to connect to Postgres, providing access to the full Postgres feature set and an underlying implementation fully supported by the Postgres community.

Some other Python-based MCP servers use [asyncpg](https://github.com/MagicStack/asyncpg), which may simplify installation by eliminating the `libpq` dependency.
Asyncpg is also probably [faster](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/) than psycopg3, but we have not validated this ourselves.
[Older benchmarks](https://gistpreview.github.io/?0ed296e93523831ea0918d42dd1258c2) report a larger performance gap, suggesting that the newer psycopg3 has closed the gap as it matures.

Balancing these considerations, we selected `psycopg3` over `asyncpg`.
We remain open to revising this decision in the future.


### Connection Configuration

Like the [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), Postgres MCP Pro takes Postgres connection information at startup.
This is convenient for users who always connect to the same database but can be cumbersome when users switch databases.

An alternative approach, taken by [PG-MCP](https://github.com/stuzero/pg-mcp-server), is provide connection details via MCP tool calls at the time of use.
This is more convenient for users who switch databases, and allows a single MCP server to simultaneously support multiple end-users.

There must be a better approach than either of these.
Both have security weaknesses—few MCP clients store the MCP server configuration securely (an exception is Goose), and credentials provided via MCP tools are passed through the LLM and stored in the chat history.
Both also have usability issues in some scenarios.


### Schema Information

The purpose of the schema information tool is to provide the calling AI agent with the information it needs to generate correct and performant SQL.
For example, suppose a user asks, "How many flights took off from San Francisco and landed in Paris during the past year?"
The AI agent needs to find the table that stores the flights, the columns that store the origin and destinations, and perhaps a table that maps between airport codes and airport locations.


*Why provide schema information tools when LLMs are generally capable of generating the SQL to retrieve this information from Postgres directly?*

Our experience using Claude indicates that the calling LLM is very good at generating SQL to explore the Postgres schema by querying the [Postgres system catalog](https://www.postgresql.org/docs/current/catalogs.html) and the [information schema](https://www.postgresql.org/docs/current/information-schema.html) (an ANSI-standardized database metadata view).
However, we do not know whether other LLMs do so as reliably and capably.

*Would it be better to provide schema information using [MCP resources](https://modelcontextprotocol.io/docs/concepts/resources) rather than [MCP tools](https://modelcontextprotocol.io/docs/concepts/tools)?*

The [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres) uses resources to expose schema information rather than tools.
Navigating resources is similar to navigating a file system, so this approach is natural in many ways.
However, resource support is less widespread than tool support in the MCP client ecosystem (see [example clients](https://modelcontextprotocol.io/clients)).
In addition, while the MCP standard says that resources can be accessed by either AI agents or end-user humans, some clients only support human navigation of the resource tree.


### Protected SQL Execution

AI amplifies longstanding challenges of protecting databases from a range of threats, ranging from simple mistakes to sophisticated attacks by malicious actors.
Whether the threat is accidental or malicious, a similar security framework applies, with aims that fall into three categories: confidentiality, integrity, and availability.
The familiar tension between convenience and safety is also evident and pronounced.

Postgres MCP Pro's protected SQL execution mode focuses on integrity.
In the context of MCP, we are most concerned with LLM-generated SQL causing damage—for example, unintended data modification or deletion, or other changes that might circumvent an organization's change management process.

The simplest way to provide integrity is to ensure that all SQL executed against the database is read-only.
One way to do this is by creating a database user with read-only access permissions.
While this is a good approach, many find this cumbersome in practice.
Postgres does not provide a way to place a connection or session into read-only mode, so Postgres MCP Pro uses a more complex approach to ensure read-only SQL execution on top of a read-write connection.

Postgres MCP Provides a read-only transaction mode that prevents data and schema modifications.
Like the [Reference PostgreSQL MCP Server](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres), we use read-only transactions to provide protected SQL execution.

To make this mechanism robust, we need to ensure that the SQL does not somehow circumvent the read-only transaction mode, say by issuing a `COMMIT` or `ROLLBACK` statement and then beginning a new transaction.

For example, the LLM can circumvent the read-only transaction mode by issuing a `ROLLBACK` statement and then beginning a new transaction.
For example:
```sql
ROLLBACK; DROP TABLE users;
```

To prevent cases like this, we parse the SQL before execution using the [pglast](https://pglast.readthedocs.io/) library.
We reject any SQL that contains `commit` or `rollback` statements.
Helpfully, the popular Postgres stored procedure languages, including PL/pgSQL and PL/Python, do not allow for `COMMIT` or `ROLLBACK` statements.
If you have unsafe stored procedure languages enabled on your database, then our read-only protections could be circumvented.

At present, Postgres MCP Pro provides two levels of protection for the database, one at either extreme of the convenience/safety spectrum.
- "Unrestricted" provides maximum flexibility.
It is suitable for development environments where speed and flexibility are paramount, and where there is no need to protect valuable or sensitive data.
- "Restricted" provides a balance between flexibility and safety.
It is suitable for production environments where the database is exposed to untrusted users, and where it is important to protect valuable or sensitive data.

Unrestricted mode aligns with the approach of [Cursor's auto-run mode](https://docs.cursor.com/chat/tools#auto-run), where the AI agent operates with limited human oversight or approvals.
We expect auto-run to be deployed in development environments where the consequences of mistakes are low, where databases do not contain valuable or sensitive data, and where they can be recreated or restored from backups when needed.

We designed restricted mode to be conservative, erring on the side of safety even though it may be inconvenient.
Restricted mode is limited to read-only operations, and we limit query execution time to prevent long-running queries from impacting system performance.
We may add measures in the future to make sure that restricted mode is safe to use with production databases.


## Postgres MCP Pro Development

The instructions below are for developers who want to work on Postgres MCP Pro, or users who prefer to install Postgres MCP Pro from source.

### Local Development Setup

1. **Install uv**:

   ```bash
   curl -sSL https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository**:

   ```bash
   git clone https://github.com/crystaldba/postgres-mcp.git
   cd postgres-mcp
   ```

3. **Install dependencies**:

   ```bash
   uv pip install -e .
   uv sync
   ```

4. **Run the server**:
   ```bash
   uv run postgres-mcp "postgres://user:password@localhost:5432/dbname"
   ```
