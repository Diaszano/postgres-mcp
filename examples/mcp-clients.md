# MCP Client Configuration Examples

This guide provides tested, secure configuration snippets for connecting various LLM clients to **Postgres MCP**.

> **Security Note:** All connection strings below use environment variable expansion (`${DATABASE_URI}`). Never hardcode plaintext database passwords in client configuration files.

---

## 1. Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uvx",
      "args": ["postgres-mcp"],
      "env": {
        "DATABASE_URI": "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}",
        "DATABASE_AUTO_DISCOVER": "true",
        "DATABASE_QUERY_GUARDRAILS_ENABLED": "true"
      }
    }
  }
}
```

---

## 2. Claude Code (`config.json`)

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["run", "--package", "postgres-mcp", "postgres-mcp"],
      "env": {
        "DATABASE_URI": "postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/app_development",
        "DATABASE_QUERY_GUARDRAILS_ENABLED": "true"
      }
    }
  }
}
```

---

## 3. Cursor IDE (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "postgres-local": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "DATABASE_URI",
        "-e", "DATABASE_QUERY_GUARDRAILS_ENABLED=true",
        "crystaldba/postgres-mcp:latest"
      ],
      "env": {
        "DATABASE_URI": "postgresql://${DB_USER}:${DB_PASSWORD}@host.docker.internal:5432/${DB_NAME}"
      }
    }
  }
}
```

---

## 4. OpenCode / Codex CLI

```json
{
  "mcp": {
    "servers": {
      "postgres": {
        "type": "stdio",
        "command": "postgres-mcp",
        "env": {
          "DATABASE_URI": "${DATABASE_URI}",
          "DATABASE_AUTO_DISCOVER": "true",
          "DATABASE_PAGINATION_ENABLED": "true"
        }
      }
    }
  }
}
```
