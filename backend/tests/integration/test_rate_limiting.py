"""Redis rate limiting against a real Redis (T01-04, D09/D17)."""

import uuid
from collections.abc import AsyncIterator

import anyio
import pytest
from redis.asyncio import Redis

from app.core.ratelimit import (
    Limit,
    RateLimiterUnavailableError,
    RateLimitExceededError,
    RedisRateLimiter,
    rate_limit_key,
)

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


@pytest.fixture
async def limiter(redis_url: str) -> AsyncIterator[tuple[RedisRateLimiter, str]]:
    namespace = f"test:{uuid.uuid7().hex}:auth"
    limiter = RedisRateLimiter.from_url(redis_url, namespace=namespace)
    try:
        yield limiter, namespace
    finally:
        await limiter.close()


async def test_attempts_beyond_the_limit_are_refused_with_a_retry_time(
    limiter: tuple[RedisRateLimiter, str],
) -> None:
    rate_limiter, _ = limiter
    limit = Limit(attempts=3, window_seconds=120)

    for _ in range(3):
        await rate_limiter.hit("ip", "login", "198.51.100.7", limit)
    with pytest.raises(RateLimitExceededError) as exceeded:
        await rate_limiter.hit("ip", "login", "198.51.100.7", limit)

    assert 0 < exceeded.value.retry_after <= 120
    # Another identifier, action or kind has its own counter.
    await rate_limiter.hit("ip", "login", "198.51.100.8", limit)
    await rate_limiter.hit("ip", "recovery", "198.51.100.7", limit)
    await rate_limiter.hit("account", "login", "198.51.100.7", limit)


async def test_windows_expire(limiter: tuple[RedisRateLimiter, str]) -> None:
    rate_limiter, _ = limiter
    limit = Limit(attempts=1, window_seconds=1)
    await rate_limiter.hit("ip", "login", "203.0.113.5", limit)
    with pytest.raises(RateLimitExceededError):
        await rate_limiter.hit("ip", "login", "203.0.113.5", limit)

    await anyio.sleep(1.2)

    await rate_limiter.hit("ip", "login", "203.0.113.5", limit)


async def test_keys_are_namespaced_and_contain_no_personal_data(
    limiter: tuple[RedisRateLimiter, str], redis_url: str
) -> None:
    rate_limiter, namespace = limiter
    email = "captain.rao@westernmaritime.example"
    await rate_limiter.hit("account", "login", email, Limit(10, 60))

    redis = Redis.from_url(redis_url)
    try:
        keys = [key.decode() async for key in redis.scan_iter(match=f"{namespace}:*")]
    finally:
        await redis.aclose()

    assert keys == [rate_limit_key(namespace, "account", "login", email)]
    assert keys[0].startswith(f"{namespace}:account:login:")
    assert email not in keys[0]


async def test_an_unreachable_redis_fails_closed() -> None:
    limiter = RedisRateLimiter.from_url("redis://127.0.0.1:9/0")
    try:
        with pytest.raises(RateLimiterUnavailableError):
            await limiter.hit("ip", "login", "198.51.100.7", Limit(10, 60))
    finally:
        await limiter.close()
