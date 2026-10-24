"""Bounded query result collection and JSON encoding."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..security.errors import PublicToolError


@dataclass
class BoundedQueryResult:
    rows: list[dict[str, Any]]
    returned_rows: int
    truncated: bool
    limit_reached: str | None
    execution_time_ms: int
    timeout_seconds: int


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def encode_bounded_result(result: BoundedQueryResult, max_result_bytes: int) -> bytes:
    try:
        encoded = json.dumps(result.__dict__, ensure_ascii=False, separators=(",", ":"), default=_json_default).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PublicToolError("RESULT_TOO_LARGE", "The query result could not be encoded within the response limit.") from exc
    if len(encoded) > max_result_bytes:
        raise PublicToolError("RESULT_TOO_LARGE", "The query result exceeds the response size limit.")
    return encoded


async def read_bounded_result(
    cursor: Any,
    *,
    max_rows: int,
    max_result_bytes: int,
    timeout_seconds: int,
    safe_row_yielding: bool = True,
    chunk_size: int = 100,
) -> BoundedQueryResult:
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    truncated = False
    limit_reached = None
    ended = False

    while len(rows) < max_rows and not ended:
        chunk = await cursor.fetchmany(min(chunk_size, max_rows - len(rows)))
        if not chunk:
            ended = True
            break
        for row in chunk:
            candidate = BoundedQueryResult(
                rows=[*rows, dict(row)],
                returned_rows=len(rows) + 1,
                truncated=False,
                limit_reached=None,
                execution_time_ms=int((time.monotonic() - started) * 1000),
                timeout_seconds=timeout_seconds,
            )
            try:
                encode_bounded_result(candidate, max_result_bytes)
            except PublicToolError:
                if not rows:
                    raise
                truncated, limit_reached = True, "max_result_bytes"
                ended = True
                break
            rows.append(dict(row))

    if not ended and len(rows) == max_rows:
        if safe_row_yielding:
            extra = await cursor.fetchmany(1)
            truncated = bool(extra)
        else:
            truncated = True
        if truncated:
            limit_reached = "max_rows"

    result = BoundedQueryResult(
        rows=rows,
        returned_rows=len(rows),
        truncated=truncated,
        limit_reached=limit_reached,
        execution_time_ms=int((time.monotonic() - started) * 1000),
        timeout_seconds=timeout_seconds,
    )
    while True:
        try:
            encode_bounded_result(result, max_result_bytes)
            return result
        except PublicToolError:
            if not result.rows:
                raise
            result.rows.pop()
            result.returned_rows = len(result.rows)
            result.truncated = True
            result.limit_reached = "max_result_bytes"
