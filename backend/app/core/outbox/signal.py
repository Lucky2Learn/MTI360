"""Wake the outbox worker through Redis (Phase 02-4, ADR-0024).

A hint only: the database is the source of truth and the worker also polls,
so a lost or failed signal delays delivery by at most one poll interval.
``notify`` never raises; ``wait`` falls back to sleeping when Redis is down.
The list holds at most one token and no data.
"""

import logging
from typing import Final

import anyio
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("app.outbox")

WAKE_KEY: Final = "outbox:wake"


class OutboxSignal:
    def __init__(self, redis: Redis, *, key: str = WAKE_KEY) -> None:
        self._redis = redis
        self._key = key

    @classmethod
    def from_url(cls, url: str, *, key: str = WAKE_KEY) -> OutboxSignal:
        # Creating the client opens no connection; the first command does.
        return cls(Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2), key=key)

    async def notify(self) -> None:
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.lpush(self._key, "1")
                pipe.ltrim(self._key, 0, 0)
                await pipe.execute()
        except (RedisError, OSError) as error:
            logger.warning("outbox.signal_failed", extra={"error_type": type(error).__name__})

    async def wait(self, timeout_seconds: float) -> None:
        """Return when signalled or after ``timeout_seconds``."""
        try:
            await self._redis.blpop([self._key], timeout=timeout_seconds)
        except RedisError, OSError:
            await anyio.sleep(timeout_seconds)

    async def close(self) -> None:
        await self._redis.aclose()
