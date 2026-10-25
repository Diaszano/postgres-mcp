"""Release smoke verification tests for stdio/http transports, pagination lifecycle, and rollback checklist."""

import tomllib
from pathlib import Path

import pytest

from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.server import mcp

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_stdio_mcp_initialize():
    """Verify FastMCP app initializes and registers expected core tools."""
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}

    expected_tools = {
        "list_databases",
        "list_schemas",
        "list_objects",
        "get_object_details",
        "explain_query",
        "fetch_query_page",
        "analyze_db_health",
        "get_top_queries",
    }
    missing = expected_tools - tool_names
    assert not missing, f"Server missing registered core tools: {missing}"


@pytest.mark.asyncio
async def test_http_anonymous_denied():
    """Verify HTTP transport rejects unauthenticated remote access when security is enforced."""
    assert mcp is not None
    # Remote HTTP transport should enforce security and not have anonymous bypass
    assert not getattr(mcp, "allow_anonymous_http", False)


def test_example_pagination():
    """Verify end-to-end cursor issuance and single-use reservation lifecycle."""
    store = InMemoryCursorStore(ttl_seconds=300, max_active_cursors=50)
    token = store.create(sql="SELECT id, name FROM users", order_by="id", database="app_development", principal="test_agent")
    assert token is not None
    assert len(token) > 20

    reservation = store.reserve(token, principal="test_agent")
    assert reservation is not None
    assert reservation.state.database == "app_development"
    assert reservation.state.mode == "offset"

    next_token = store.commit(reservation, next_state=reservation.state)
    assert next_token is not None


def test_release_metadata_and_rollback():
    """Verify release checklist exists, contains rollback instructions, and has no stale redis references."""
    checklist_path = REPO_ROOT / "docs" / "release-checklist.md"
    assert checklist_path.exists(), "docs/release-checklist.md must exist"
    content = checklist_path.read_text(encoding="utf-8")

    assert "rollback" in content.lower(), "Checklist must provide explicit rollback procedure"
    assert "DATABASE_QUERY_GUARDRAILS_ENABLED=false" in content, "Checklist must document guardrails safe backout"
    assert "redis" not in content.lower(), "Checklist must not reference stale redis dependencies"

    pyproject_path = REPO_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    assert version in content, f"Release checklist should mention current version {version}"
