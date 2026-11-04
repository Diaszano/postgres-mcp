import json

from mcp import types
from psycopg import OperationalError

from postgres_mcp.mcp_response import error_result
from postgres_mcp.mcp_response import format_mcp_result
from postgres_mcp.mcp_response import success_result
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.security.errors import SQLValidationError
from tests.type_helpers import text_at


def test_success_result_content_and_structured():
    payload = {"status": "ok", "rows": [1, 2, 3]}
    res = success_result(payload)
    assert isinstance(res, types.CallToolResult)
    assert res.isError is False
    assert res.structuredContent == payload
    assert len(res.content) == 1
    assert isinstance(res.content[0], types.TextContent)
    # Text fallback is JSON deserializable
    data = json.loads(text_at(res.content))
    assert data == payload


def test_error_result_content_and_structured():
    err = PublicToolError("DATABASE_NOT_ALLOWED", "Access denied", retryable=False)
    res = error_result(err, request_id="req-123")
    assert isinstance(res, types.CallToolResult)
    assert res.isError is True
    assert res.structuredContent == {
        "error": {
            "code": "DATABASE_NOT_ALLOWED",
            "message": "Access denied",
            "retryable": False,
            "request_id": "req-123",
        }
    }
    assert len(res.content) == 1
    assert "Access denied" in text_at(res.content)
    assert res.structuredContent is not None
    assert res.structuredContent["error"]["code"] == "DATABASE_NOT_ALLOWED"


def test_result_meta_uses_the_mcp_meta_field():
    metadata = {"trace_id": "req-123"}

    result = success_result({"status": "ok"}, meta=metadata)

    assert result.meta == metadata
    assert result.model_dump(by_alias=True)["_meta"] == metadata


def test_format_mcp_result_from_exception():
    exc = SQLValidationError("Forbidden syntax")
    res = format_mcp_result(exc, request_id="req-999")
    assert res.isError is True
    assert res.structuredContent is not None
    assert res.structuredContent["error"]["code"] == "SQL_VALIDATION_FAILED"
    assert "Forbidden syntax" not in text_at(res.content)
    assert "The SQL statement is not allowed." in text_at(res.content)


def test_format_mcp_result_from_unexpected_exception_hides_secrets():
    exc = OperationalError("connection to postgresql://user:secretpass@127.0.0.1:5432 failed")
    res = format_mcp_result(exc)
    assert res.isError is True
    assert res.structuredContent is not None
    assert res.structuredContent["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "secretpass" not in text_at(res.content)
    assert "secretpass" not in str(res.structuredContent)
