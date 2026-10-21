"""Pure parsing and validation of the multi-database configuration."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict
from psycopg.conninfo import make_conninfo

_BOOLS = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}


@dataclass(frozen=True)
class DatabaseConfig:
    database_uri: str
    auto_discover: bool
    default_database: str | None
    allowed_databases: tuple[str, ...]
    excluded_databases: tuple[str, ...]
    discovery_ttl_seconds: int
    max_pools: int
    pool_max_size: int
    pool_idle_seconds: int
    access_mode: str


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    return value.strip() if value and value.strip() else None


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _get(env, name)
    if raw is None:
        return default
    if raw.lower() not in _BOOLS:
        raise ValueError(f"{name} must be one of true/false, 1/0, yes/no; got {raw!r}")
    return _BOOLS[raw.lower()]


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer; got {raw!r}") from None
    if value < 1:
        raise ValueError(f"{name} must be >= 1; got {value}")
    return value


def _names(env: Mapping[str, str], name: str) -> tuple[str, ...]:
    raw = _get(env, name)
    if raw is None:
        return ()
    if raw.startswith("["):
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"{name} is not a valid JSON array: {e}") from None
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            raise ValueError(f"{name} must be a JSON array of strings")
        return tuple(items)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def parse_database_config(env: Mapping[str, str], database_url: str | None, access_mode_option: str | None) -> DatabaseConfig:
    """Build a validated config. access_mode_option=None means --access-mode was omitted."""
    uri = _get(env, "DATABASE_URI") or database_url
    if not uri:
        raise ValueError("DATABASE_URI environment variable or a database URL argument is required")

    auto_discover = _bool(env, "DATABASE_AUTO_DISCOVER", False)
    allowed = _names(env, "DATABASE_ALLOWED_DATABASES")
    excluded = _names(env, "DATABASE_EXCLUDED_DATABASES")
    ttl = _int(env, "DATABASE_DISCOVERY_TTL_SECONDS", 60)
    max_pools = _int(env, "DATABASE_MAX_POOLS", 8)
    pool_max_size = _int(env, "DATABASE_POOL_MAX_SIZE", 5)
    idle = _int(env, "DATABASE_POOL_IDLE_SECONDS", 600)

    try:
        uri_dbname = conninfo_to_dict(uri).get("dbname")
    except ProgrammingError:
        # Fixed message: psycopg's text may echo the URI, including the password.
        raise ValueError("DATABASE_URI is not a valid PostgreSQL connection URI") from None
    default = _get(env, "DATABASE_DEFAULT_DATABASE") or uri_dbname
    if auto_discover:
        if not default:
            raise ValueError("DATABASE_DEFAULT_DATABASE or an explicit dbname in DATABASE_URI is required when DATABASE_AUTO_DISCOVER=true")
        if default in excluded:
            raise ValueError(f"Default database {default!r} is excluded by DATABASE_EXCLUDED_DATABASES")
        if allowed and default not in allowed:
            raise ValueError(f"Default database {default!r} is not in DATABASE_ALLOWED_DATABASES")

    access_mode = access_mode_option or ("restricted" if auto_discover else "unrestricted")
    return DatabaseConfig(uri, auto_discover, default, allowed, excluded, ttl, max_pools, pool_max_size, idle, access_mode)


def build_database_conninfo(config: DatabaseConfig, name: str) -> str:
    """Return a libpq conninfo for database `name`, keeping every other bootstrap option.

    Authorization is the caller's job (registry, after catalog.authorize).
    """
    try:
        return make_conninfo(config.database_uri, dbname=name)
    except (ProgrammingError, ValueError):
        # Fixed message: psycopg's text may echo the DSN or the database name.
        raise ValueError("Could not build a connection string for the requested database") from None
