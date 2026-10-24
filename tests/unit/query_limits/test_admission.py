import asyncio
import time
from contextlib import asynccontextmanager

import pytest
from psycopg.errors import QueryCanceled

from postgres_mcp.query_limits.admission import QueryAdmission
from postgres_mcp.query_limits.admission import remaining_query_seconds
from postgres_mcp.security.errors import PublicToolError


@pytest.mark.asyncio
async def test_admission_before_pool_lease():
    admission = QueryAdmission(max_concurrency=4)
    release = asyncio.Event()
    entered = asyncio.Event()
    leases = 0
    total_leases = 0

    @asynccontextmanager
    async def registry_lease():
        nonlocal leases, total_leases
        leases += 1
        total_leases += 1
        if leases == 4:
            entered.set()
        try:
            yield
        finally:
            leases -= 1

    async def operation():
        async with registry_lease():
            await release.wait()

    tasks = [asyncio.create_task(admission.run(operation, timeout_seconds=5)) for _ in range(4)]
    try:
        await asyncio.wait_for(entered.wait(), 2)
        started = asyncio.get_running_loop().time()
        # Queue wait consumes the full request deadline; it has no separate grace period.
        with pytest.raises(PublicToolError) as error:
            await asyncio.wait_for(admission.run(operation, timeout_seconds=0.05), 1)
        assert error.value.code == "QUERY_TIMEOUT"
        assert asyncio.get_running_loop().time() - started < 0.5
        assert leases == 4
        assert total_leases == 4
    finally:
        release.set()
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_semaphore():
    admission = QueryAdmission(max_concurrency=1)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        entered.set()
        await release.wait()

    async def later():
        return "available"

    holder = asyncio.create_task(admission.run(hold, 5))
    waiter = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        waiter = asyncio.create_task(admission.run(later, 5))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
    finally:
        release.set()
        await holder
        if waiter is not None and not waiter.done():
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
    assert await admission.run(later, 1) == "available"


@pytest.mark.asyncio
async def test_execution_timeout_releases_permit_and_resets_deadline():
    admission = QueryAdmission(max_concurrency=1)
    cleaned = asyncio.Event()

    async def slow():
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    with pytest.raises(PublicToolError) as error:
        await admission.run(slow, 0.02)
    assert error.value.code == "QUERY_TIMEOUT"
    assert cleaned.is_set()
    assert remaining_query_seconds() is None

    async def later():
        assert 0 < remaining_query_seconds() <= 1
        return "available"

    assert await admission.run(later, 1) == "available"


@pytest.mark.asyncio
async def test_queue_and_execution_share_one_deadline():
    admission = QueryAdmission(max_concurrency=1)
    entered = asyncio.Event()
    release = asyncio.Event()
    remaining = []

    async def hold():
        entered.set()
        await release.wait()

    async def operation():
        remaining.append(remaining_query_seconds())
        await asyncio.sleep(0.2)

    holder = asyncio.create_task(admission.run(hold, 5))
    waiter = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        waiter = asyncio.create_task(admission.run(operation, 0.2))
        await asyncio.sleep(0.1)
        release.set()
        with pytest.raises(PublicToolError) as error:
            await waiter
        assert error.value.code == "QUERY_TIMEOUT"
        assert 0 < remaining[0] < 0.15
    finally:
        release.set()
        await holder
        if waiter is not None and not waiter.done():
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.asyncio
async def test_synchronous_work_cannot_return_after_deadline():
    async def serialize():
        time.sleep(0.03)
        return "late"

    with pytest.raises(PublicToolError) as error:
        await QueryAdmission(1).run(serialize, 0.01)
    assert error.value.code == "QUERY_TIMEOUT"


@pytest.mark.asyncio
async def test_postgres_timeout_has_sanitized_public_error():
    async def canceled_query():
        raise QueryCanceled("sensitive SQL and connection details")

    with pytest.raises(PublicToolError) as error:
        await QueryAdmission(1).run(canceled_query, 1)
    assert error.value.code == "QUERY_TIMEOUT"
    assert "sensitive" not in str(error.value)
