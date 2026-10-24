from dataclasses import dataclass

from ..security.errors import PublicToolError
from .config import QueryBudgetConfig


@dataclass(frozen=True)
class QueryLimits:
    max_rows: int
    timeout_seconds: int


def resolve_query_limits(
    config: QueryBudgetConfig,
    max_rows: object,
    timeout_seconds: object,
) -> QueryLimits:
    if not config.enabled and (max_rows is not None or timeout_seconds is not None):
        raise PublicToolError("INVALID_QUERY_OPTIONS", "Query guardrails must be enabled before setting query limits.")

    values = (
        ("max_rows", max_rows, config.default_max_rows, config.hard_max_rows),
        ("timeout_seconds", timeout_seconds, config.default_timeout_seconds, config.hard_timeout_seconds),
    )
    resolved = []
    for name, value, default, hard_limit in values:
        if value is None:
            resolved.append(default)
        elif type(value) is not int or value <= 0:
            raise PublicToolError("INVALID_QUERY_OPTIONS", f"{name} must be a positive integer.")
        elif value > hard_limit:
            raise PublicToolError("LIMIT_EXCEEDED", f"{name} exceeds the configured limit.")
        else:
            resolved.append(value)
    return QueryLimits(*resolved)
