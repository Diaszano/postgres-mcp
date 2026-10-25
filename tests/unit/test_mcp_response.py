import json

from mcp import types
from psycopg import OperationalError

from postgres_mcp.mcp_response import error_result
from postgres_mcp.mcp_response import format_mcp_result
from postgres_mcp.mcp_response import success_result
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.security.errors import SQLValidationError


def test_success_result_content_and_structured():
    payload = {"status": "ok", "rows": [1, 2, 3]}
    res = success_result(payload)
    assert isinstance(res, types.CallToolResult)
    assert res.isError is False
    assert res.structuredContent == payload
    assert len(res.content) == 1
    assert isinstance(res.content[0], types.TextContent)
    # Text fallback is JSON deserializable
    data = json.loads(res.content[0].text)
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
    assert "Access denied" in res.content[0].text
    assert res.structuredContent["error"]["code"] == "DATABASE_NOT_ALLOWED"


def test_format_mcp_result_from_exception():
    exc = SQLValidationError("Forbidden syntax")
    res = format_mcp_result(exc, request_id="req-999")
    assert res.isError is True
    assert res.structuredContent["error"]["code"] == "SQL_VALIDATION_FAILED"
    assert "Forbidden syntax" not in res.content[0].text
    assert "The SQL statement is not allowed." in res.content[0].text


def test_format_mcp_result_from_unexpected_exception_hides_secrets():
    exc = OperationalError("connection to postgresql://user:secretpass@127.0.0.1:5432 failed")
    res = format_mcp_result(exc)
    assert res.isError is True
    assert res.structuredContent["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "secretpass" not in res.content[0].text
    assert "secretpass" not in str(res.structuredContent)
