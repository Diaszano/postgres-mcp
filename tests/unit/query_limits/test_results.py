import importlib.util
import json
from decimal import Decimal

import pytest

from postgres_mcp.security.errors import PublicToolError


class GeneratedCursor:
    def __init__(self, count, row=None):
        self.count = count
        self.row = row
        self.fetched = 0
        self.requests = []

    async def fetchmany(self, size):
        self.requests.append(size)
        count = min(size, self.count - self.fetched)
        rows = [self.row if self.row is not None else {"id": self.fetched + i} for i in range(count)]
        self.fetched += count
        return rows

    async def fetchall(self):
        pytest.fail("Bounded queries must never fetchall")


def results_module():
    assert importlib.util.find_spec("postgres_mcp.query_limits.results") is not None, "A bounded cursor reader must cap SQL results"
    from postgres_mcp.query_limits import results

    return results


@pytest.mark.asyncio
async def test_large_query_fetches_bounded_rows():
    results = results_module()
    cursor = GeneratedCursor(1_000_000)
    result = await results.read_bounded_result(cursor, max_rows=200, max_result_bytes=2_097_152, timeout_seconds=15, safe_row_yielding=True)
    assert result.returned_rows == len(result.rows) == 200
    assert cursor.fetched == 201
    assert max(cursor.requests) <= 200
    assert result.truncated is True
    assert result.limit_reached == "max_rows"


@pytest.mark.asyncio
@pytest.mark.parametrize("count, truncated", [(0, False), (199, False), (200, False), (201, True)])
async def test_truncation_is_explicit(count, truncated):
    results = results_module()
    result = await results.read_bounded_result(
        GeneratedCursor(count),
        max_rows=200,
        max_result_bytes=2_097_152,
        timeout_seconds=15,
        safe_row_yielding=True,
    )
    assert result.returned_rows == min(count, 200)
    assert result.truncated is truncated
    assert result.limit_reached == ("max_rows" if truncated else None)


@pytest.mark.asyncio
async def test_utf8_and_metadata_included_in_byte_budget():
    results = results_module()
    cursor = GeneratedCursor(5_000, {"accent": "ação😀" * 300, "decimal": Decimal("1.25")})
    result = await results.read_bounded_result(cursor, max_rows=5_000, max_result_bytes=2_097_152, timeout_seconds=15)
    encoded = results.encode_bounded_result(result, max_result_bytes=2_097_152)
    payload = json.loads(encoded)
    assert len(encoded) <= 2_097_152
    assert len(encoded) > len(encoded.decode("utf-8"))
    assert payload["rows"][0]["accent"] == "ação😀" * 300
    assert payload["rows"][0]["decimal"] == "1.25"
    assert payload["returned_rows"] == len(payload["rows"]) < 5_000
    assert payload["truncated"] is True
    assert payload["limit_reached"] == "max_result_bytes"
    assert payload["timeout_seconds"] == 15
    assert payload["execution_time_ms"] >= 0


@pytest.mark.asyncio
async def test_first_row_too_big_is_typed_error():
    results = results_module()
    with pytest.raises(PublicToolError) as error:
        await results.read_bounded_result(GeneratedCursor(1, {"oversized": "x" * 1_000}), max_rows=200, max_result_bytes=300, timeout_seconds=15)
    assert error.value.code == "RESULT_TOO_LARGE"
    assert "x" * 20 not in str(error.value)


def test_encoder_rejects_oversized_existing_result():
    results = results_module()
    result = results.BoundedQueryResult([{"value": 1}], 1, False, None, 12, 15)
    with pytest.raises(PublicToolError) as error:
        results.encode_bounded_result(result, 1)
    assert error.value.code == "RESULT_TOO_LARGE"


@pytest.mark.asyncio
async def test_unproven_rows_are_reported_incomplete_without_lookahead():
    results = results_module()
    cursor = GeneratedCursor(201)
    result = await results.read_bounded_result(cursor, max_rows=200, max_result_bytes=2_097_152, timeout_seconds=15, safe_row_yielding=False)
    assert cursor.fetched == 200
    assert result.truncated is True
    assert result.limit_reached == "max_rows"


@pytest.mark.asyncio
async def test_lookahead_is_disabled_by_default():
    results = results_module()
    cursor = GeneratedCursor(201)
    result = await results.read_bounded_result(cursor, max_rows=200, max_result_bytes=2_097_152, timeout_seconds=15)
    assert cursor.fetched == 200
    assert result.truncated is True


@pytest.mark.asyncio
async def test_final_truncation_metadata_does_not_drop_first_row():
    results = results_module()
    with pytest.raises(PublicToolError) as error:
        await results.read_bounded_result(
            GeneratedCursor(1, {"value": "x" * 100}),
            max_rows=1,
            max_result_bytes=223,
            timeout_seconds=15,
            safe_row_yielding=False,
        )
    assert error.value.code == "RESULT_TOO_LARGE"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_encoder_rejects_non_json_float_values(value):
    results = results_module()
    result = results.BoundedQueryResult([{"value": value}], 1, False, None, 0, 15)
    with pytest.raises(PublicToolError) as error:
        results.encode_bounded_result(result, 2_097_152)
    assert error.value.code == "RESULT_TOO_LARGE"
