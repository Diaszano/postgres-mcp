import logging

import pytest

from postgres_mcp.query_limits.config import parse_query_budget_config


def test_query_guardrails_defaults():
    config = parse_query_budget_config({})

    assert config.enabled is False
    assert config.default_max_rows == 200
    assert config.hard_max_rows == 5000
    assert config.default_timeout_seconds == 15
    assert config.hard_timeout_seconds == 60
    assert config.max_result_bytes == 2097152
    assert config.max_concurrency == 4


@pytest.mark.parametrize(
    "name,value",
    [
        ("DATABASE_QUERY_DEFAULT_MAX_ROWS", "secret"),
        ("DATABASE_QUERY_GUARDRAILS_ENABLED", "secret"),
        ("DATABASE_QUERY_MAX_CONCURRENCY", "true"),
        ("DATABASE_QUERY_MAX_RESULT_BYTES", "0"),
        ("DATABASE_QUERY_MAX_CONCURRENCY", "-1"),
        ("DATABASE_QUERY_MAX_CONCURRENCY", "1.2"),
        ("DATABASE_QUERY_DEFAULT_MAX_ROWS", "10000001"),
        ("DATABASE_QUERY_HARD_MAX_ROWS", "999999999999999999999"),
        ("DATABASE_QUERY_MAX_RESULT_BYTES", "67108865"),
    ],
)
def test_bad_query_budget_env_fails_closed(name, value):
    with pytest.raises(ValueError) as exc:
        parse_query_budget_config({name: value})
    assert "secret" not in str(exc.value)


def test_default_cannot_exceed_hard_limit():
    with pytest.raises(ValueError, match="cannot exceed"):
        parse_query_budget_config({"DATABASE_QUERY_DEFAULT_MAX_ROWS": "600", "DATABASE_QUERY_HARD_MAX_ROWS": "500"})


def test_disabled_mode_warning_on_remote(caplog):
    from postgres_mcp.server import warn_if_query_guardrails_disabled

    with caplog.at_level(logging.WARNING):
        warn_if_query_guardrails_disabled("streamable-http", parse_query_budget_config({}))

    assert "guardrails are disabled" in caplog.text.lower()
    assert "secret" not in caplog.text.lower()
