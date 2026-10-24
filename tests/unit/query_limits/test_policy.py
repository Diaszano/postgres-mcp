from unittest.mock import patch

import pytest

from postgres_mcp.query_limits.config import QueryBudgetConfig
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.server import execute_sql


def test_agent_override_within_ceilings():
    from postgres_mcp.query_limits.policy import resolve_query_limits

    config = QueryBudgetConfig(enabled=True)
    assert resolve_query_limits(config, 1000, 20).max_rows == 1000
    assert resolve_query_limits(config, None, None).max_rows == config.default_max_rows
    assert resolve_query_limits(config, None, None).timeout_seconds == config.default_timeout_seconds


@pytest.mark.asyncio
@pytest.mark.parametrize(("max_rows", "timeout_seconds"), [(5001, None), (None, 61)])
async def test_hard_limits_rejected_before_checkout(monkeypatch, max_rows, timeout_seconds):
    import postgres_mcp.server as server
    from postgres_mcp.query_limits.policy import resolve_query_limits

    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))
    with pytest.raises(PublicToolError) as exc:
        resolve_query_limits(server.query_budget_config, max_rows, timeout_seconds)
    assert exc.value.code == "LIMIT_EXCEEDED"

    with patch("postgres_mcp.server.get_sql_driver") as get_driver:
        response = await execute_sql("SELECT 1", None, max_rows, timeout_seconds)

    assert "exceeds the configured limit" in response[0].text
    get_driver.assert_not_called()


@pytest.mark.parametrize("value", [True, 0, -1, 1.2, "100"])
def test_invalid_agent_values_are_rejected_without_coercion(value):
    from postgres_mcp.query_limits.policy import resolve_query_limits

    with pytest.raises(PublicToolError) as exc:
        resolve_query_limits(QueryBudgetConfig(enabled=True), value, None)

    assert exc.value.code == "INVALID_QUERY_OPTIONS"


def test_disabled_guardrails_reject_explicit_override():
    from postgres_mcp.query_limits.policy import resolve_query_limits

    config = QueryBudgetConfig(enabled=False)

    assert resolve_query_limits(config, None, None).max_rows == config.default_max_rows
    with pytest.raises(PublicToolError, match="enabled") as exc:
        resolve_query_limits(config, 100, None)

    assert exc.value.code == "INVALID_QUERY_OPTIONS"
