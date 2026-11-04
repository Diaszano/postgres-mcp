"""Standardized MCP tool results with structured content and text fallbacks."""

import json
from collections.abc import Mapping
from typing import Any

from mcp import types

from pgscope.security.errors import PublicToolError
from pgscope.security.errors import to_public_error


class ToolResult(types.CallToolResult):
    """CallToolResult compatible with legacy code expecting indexed contents."""

    def __getitem__(self, index: int) -> types.ContentBlock:
        return self.content[index]

    def __len__(self) -> int:
        return len(self.content)


def success_result(
    payload: Mapping[str, Any],
    *,
    meta: Mapping[str, Any] | None = None,
) -> ToolResult:
    """Format a successful operation as an MCP CallToolResult with text fallback."""
    structured = dict(payload)
    text = json.dumps(structured, default=str, indent=2)
    return ToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=structured,
        isError=False,
        _meta=dict(meta) if meta else None,
    )


def error_result(
    error: PublicToolError,
    *,
    request_id: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> ToolResult:
    """Format a sanitized public error with isError=True and structured error payload."""
    error_payload: dict[str, Any] = {
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        }
    }
    if request_id is not None:
        error_payload["error"]["request_id"] = request_id

    text = f"Error: {error.message}"
    return ToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent=error_payload,
        isError=True,
        _meta=dict(meta) if meta else None,
    )


def format_mcp_result(
    result_or_exc: Any,
    *,
    request_id: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> ToolResult:
    """Convert an arbitrary handler result or exception into a standardized ToolResult."""
    if isinstance(result_or_exc, ToolResult):
        return result_or_exc
    if isinstance(result_or_exc, types.CallToolResult):
        return ToolResult(
            content=result_or_exc.content,
            structuredContent=result_or_exc.structuredContent,
            isError=result_or_exc.isError,
            _meta=result_or_exc.meta,
        )

    if isinstance(result_or_exc, BaseException):
        public_err = to_public_error(result_or_exc)
        return error_result(public_err, request_id=request_id, meta=meta)

    if isinstance(result_or_exc, Mapping):
        return success_result(result_or_exc, meta=meta)

    text = str(result_or_exc)
    return ToolResult(
        content=[types.TextContent(type="text", text=text)],
        structuredContent={"result": result_or_exc},
        isError=False,
        _meta=dict(meta) if meta else None,
    )
