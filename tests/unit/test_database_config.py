import pytest

from postgres_mcp.database_config import parse_database_config

URI = "postgresql://u:p@localhost/postgres"


def test_legacy_defaults_to_unrestricted():
    assert parse_database_config({"DATABASE_URI": URI}, None, None).access_mode == "unrestricted"


def test_legacy_without_dbname_still_works():
    config = parse_database_config({"DATABASE_URI": "postgresql://u:p@localhost"}, None, None)
    assert config.auto_discover is False
    assert config.default_database is None


def test_discovery_defaults_to_restricted():
    env = {"DATABASE_URI": URI, "DATABASE_AUTO_DISCOVER": "true"}
    assert parse_database_config(env, None, None).access_mode == "restricted"


def test_explicit_unrestricted_overrides():
    env = {"DATABASE_URI": URI, "DATABASE_AUTO_DISCOVER": "true"}
    assert parse_database_config(env, None, "unrestricted").access_mode == "unrestricted"


def test_uri_env_takes_precedence_and_positional_fallback():
    assert parse_database_config({"DATABASE_URI": URI}, "postgresql://x/other", None).database_uri == URI
    assert parse_database_config({}, "postgresql://x/other", None).database_uri == "postgresql://x/other"
    with pytest.raises(ValueError, match="DATABASE_URI"):
        parse_database_config({}, None, None)


def test_parses_csv_and_json_names_verbatim():
    env = {
        "DATABASE_URI": URI,
        "DATABASE_AUTO_DISCOVER": "yes",
        "DATABASE_DEFAULT_DATABASE": "App_Test",
        "DATABASE_ALLOWED_DATABASES": " App_Test , b ",
        "DATABASE_EXCLUDED_DATABASES": '["x,y", "Z"]',
    }
    config = parse_database_config(env, None, None)
    assert config.default_database == "App_Test"
    assert config.allowed_databases == ("App_Test", "b")
    assert config.excluded_databases == ("x,y", "Z")
    assert (config.discovery_ttl_seconds, config.max_pools, config.pool_max_size, config.pool_idle_seconds) == (60, 8, 5, 600)


@pytest.mark.parametrize(
    "extra",
    [
        {"DATABASE_AUTO_DISCOVER": "maybe"},
        {"DATABASE_DISCOVERY_TTL_SECONDS": "0"},
        {"DATABASE_DISCOVERY_TTL_SECONDS": "abc"},
        {"DATABASE_MAX_POOLS": "0"},
        {"DATABASE_POOL_MAX_SIZE": "0"},
        {"DATABASE_POOL_IDLE_SECONDS": "-1"},
        {"DATABASE_ALLOWED_DATABASES": '["a", 1]'},
        {"DATABASE_ALLOWED_DATABASES": "[not json"},
        {"DATABASE_EXCLUDED_DATABASES": '["a"]x'},
    ],
)
def test_rejects_invalid_booleans_limits_lists(extra):
    with pytest.raises(ValueError):
        parse_database_config({"DATABASE_URI": URI, **extra}, None, None)


def test_default_excluded_rejected():
    env = {
        "DATABASE_URI": URI,
        "DATABASE_AUTO_DISCOVER": "true",
        "DATABASE_DEFAULT_DATABASE": "app",
        "DATABASE_EXCLUDED_DATABASES": "app",
    }
    with pytest.raises(ValueError, match="app"):
        parse_database_config(env, None, None)


def test_default_outside_allowlist_rejected():
    env = {
        "DATABASE_URI": URI,
        "DATABASE_AUTO_DISCOVER": "true",
        "DATABASE_DEFAULT_DATABASE": "app",
        "DATABASE_ALLOWED_DATABASES": "other",
    }
    with pytest.raises(ValueError, match="app"):
        parse_database_config(env, None, None)


def test_discovery_requires_explicit_default():
    with pytest.raises(ValueError, match="DATABASE_DEFAULT_DATABASE"):
        parse_database_config({"DATABASE_URI": "postgresql://u:p@localhost", "DATABASE_AUTO_DISCOVER": "1"}, None, None)


def test_bootstrap_excluded_with_allowed_default():
    env = {
        "DATABASE_URI": URI,
        "DATABASE_AUTO_DISCOVER": "true",
        "DATABASE_DEFAULT_DATABASE": "app",
        "DATABASE_ALLOWED_DATABASES": "app",
        "DATABASE_EXCLUDED_DATABASES": "postgres",
    }
    config = parse_database_config(env, None, None)
    assert config.default_database == "app"
    assert config.excluded_databases == ("postgres",)


def test_malformed_uri_error_hides_password():
    with pytest.raises(ValueError) as exc:
        parse_database_config({"DATABASE_URI": "postgresql://u:s3cr3tPW@[host/db"}, None, None)
    assert "s3cr3tPW" not in str(exc.value)
    assert exc.value.__cause__ is None
