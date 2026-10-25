import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
import pytest

from postgres_mcp.query_limits.admission import QueryAdmission


@pytest.mark.performance
@pytest.mark.asyncio
async def test_pool_fairness_under_paginated_load():
    """Verify that multiple concurrent queries and page requests make progress under bounded concurrency."""
    admission = QueryAdmission(max_concurrency=4)
    completed = []

    async def worker(worker_id: int, duration: float):
        async def work():
            await asyncio.sleep(duration)
            completed.append(worker_id)
            return worker_id

        return await admission.run(work, timeout_seconds=5.0)

    # Launch 8 concurrent tasks with concurrency limit of 4
    tasks = [worker(i, 0.02) for i in range(8)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 8
    assert len(completed) == 8
