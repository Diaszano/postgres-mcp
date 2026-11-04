from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryBudgetConfig:
    enabled: bool = False
    default_max_rows: int = 200
    hard_max_rows: int = 5000
    default_timeout_seconds: int = 15
    hard_timeout_seconds: int = 60
    max_result_bytes: int = 2097152
    max_concurrency: int = 4


def parse_query_budget_config(env: Mapping[str, str]) -> QueryBudgetConfig:
    def positive_int(name: str, default: int, maximum: int) -> int:
        raw = env.get(name, str(default))
        if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal():
            raise ValueError(f"{name} must be a positive integer")
        value = int(raw)
        if not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
        return value

    raw_enabled = env.get("DATABASE_QUERY_GUARDRAILS_ENABLED", "false")
    if not isinstance(raw_enabled, str) or raw_enabled.lower() not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError("DATABASE_QUERY_GUARDRAILS_ENABLED must be a boolean")
    enabled = raw_enabled.lower() in {"true", "1", "yes"}
    hard_rows = positive_int("DATABASE_QUERY_HARD_MAX_ROWS", 5000, 10_000_000)
    default_rows = positive_int("DATABASE_QUERY_DEFAULT_MAX_ROWS", 200, 10_000_000)
    hard_timeout = positive_int("DATABASE_QUERY_HARD_TIMEOUT_SECONDS", 60, 3600)
    default_timeout = positive_int("DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS", 15, 3600)
    if default_rows > hard_rows:
        raise ValueError("DATABASE_QUERY_DEFAULT_MAX_ROWS cannot exceed DATABASE_QUERY_HARD_MAX_ROWS")
    if default_timeout > hard_timeout:
        raise ValueError("DATABASE_QUERY_DEFAULT_TIMEOUT_SECONDS cannot exceed DATABASE_QUERY_HARD_TIMEOUT_SECONDS")

    return QueryBudgetConfig(
        enabled=enabled,
        default_max_rows=default_rows,
        hard_max_rows=hard_rows,
        default_timeout_seconds=default_timeout,
        hard_timeout_seconds=hard_timeout,
        max_result_bytes=positive_int("DATABASE_QUERY_MAX_RESULT_BYTES", 2097152, 67_108_864),
        max_concurrency=positive_int("DATABASE_QUERY_MAX_CONCURRENCY", 4, 256),
    )
