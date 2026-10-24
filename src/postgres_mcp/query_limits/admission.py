import asyncio
from collections.abc import Awaitable
from collections.abc import Callable
from contextvars import ContextVar
from typing import TypeVar

from psycopg.errors import QueryCanceled

from postgres_mcp.security.errors import PublicToolError

T = TypeVar("T")
_query_deadline: ContextVar[float | None] = ContextVar("query_deadline", default=None)


def remaining_query_seconds() -> float | None:
    deadline = _query_deadline.get()
    if deadline is None:
        return None
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise PublicToolError("QUERY_TIMEOUT", "The query exceeded its time limit.", retryable=True)
    return remaining


class QueryAdmission:
    def __init__(self, max_concurrency: int):
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(self, operation: Callable[[], Awaitable[T]], timeout_seconds: int) -> T:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        token = _query_deadline.set(deadline)
        try:
            async with asyncio.timeout_at(deadline):
                async with self._semaphore:
                    remaining_query_seconds()
                    task = asyncio.ensure_future(operation())
                    try:
                        result = await asyncio.shield(task)
                    except asyncio.CancelledError:
                        task.cancel()
                        # Hold the permit until pool return finishes, even if shutdown cancels us again.
                        while True:
                            try:
                                await asyncio.shield(task)
                            except asyncio.CancelledError:
                                if not task.done():
                                    continue
                            except Exception:
                                pass
                            break
                        raise
                    # Synchronous serialization may finish before asyncio schedules cancellation.
                    remaining_query_seconds()
                    return result
        except (TimeoutError, QueryCanceled) as error:
            raise PublicToolError("QUERY_TIMEOUT", "The query exceeded its time limit.", retryable=True) from error
        finally:
            _query_deadline.reset(token)
