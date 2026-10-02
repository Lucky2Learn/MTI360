"""Redis-backed fixed-window rate limiting (T01-04, D09/D17; security.md §7).

Keys live in a dedicated namespace and never contain personal data: the
identifier (an IP address or a canonical email) is hashed with SHA-256::

    auth:ip:<action>:<sha256>        auth:account:<action>:<sha256>

Each call counts one attempt atomically (``INCR`` and, for the first hit of a
window, ``EXPIRE``, in one transaction). Exceeding the limit raises
:class:`RateLimitExceededError` with the seconds until the window resets.

Fail closed: if Redis cannot be reached, :class:`RateLimiterUnavailableError` is
raised and the caller refuses the operation. Only this module touches Redis
for rate limits (tenancy.md §6).
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Final, Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("app.ratelimit")

DEFAULT_NAMESPACE: Final = "auth"


@dataclass(frozen=True, slots=True)
class Limit:
    """At most ``attempts`` per ``window_seconds``."""

    attempts: int
    window_seconds: int


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after = retry_after


class RateLimiterUnavailableError(Exception):
    """The rate-limit store is unreachable; the operation must be refused."""


class RateLimiter(Protocol):
    async def hit(self, kind: str, action: str, identifier: str, limit: Limit) -> None:
        """Count one attempt; raise ``RateLimitExceededError`` or
        ``RateLimiterUnavailableError``."""
        ...

    async def close(self) -> None: ...


def rate_limit_key(namespace: str, kind: str, action: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{namespace}:{kind}:{action}:{digest}"


class RedisRateLimiter:
    """Fixed-window counters in Redis. ``namespace`` isolates key spaces (tests)."""

    def __init__(self, redis: Redis, *, namespace: str = DEFAULT_NAMESPACE) -> None:
        self._redis = redis
        self._namespace = namespace

    @classmethod
    def from_url(cls, url: str, *, namespace: str = DEFAULT_NAMESPACE) -> RedisRateLimiter:
        # Creating the client opens no connection; the first command does.
        redis = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
        return cls(redis, namespace=namespace)

    async def hit(self, kind: str, action: str, identifier: str, limit: Limit) -> None:
        key = rate_limit_key(self._namespace, kind, action, identifier)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, limit.window_seconds, nx=True)
                pipe.ttl(key)
                count, _, ttl = await pipe.execute()
        except (RedisError, OSError) as error:
            # Never the key (it is derived from an identifier) or the URL.
            logger.error("ratelimit.unavailable", extra={"error_type": type(error).__name__})
            raise RateLimiterUnavailableError from None
        if int(count) > limit.attempts:
            raise RateLimitExceededError(
                retry_after=int(ttl) if int(ttl) > 0 else limit.window_seconds
            )

    async def close(self) -> None:
        await self._redis.aclose()
