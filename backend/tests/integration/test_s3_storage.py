"""The S3 adapter against a real S3-compatible store (Phase 02-2; ADR-0021 §8).

Runs only when ``TEST_S3_ENDPOINT_URL``, ``TEST_S3_BUCKET``,
``TEST_S3_ACCESS_KEY_ID`` and ``TEST_S3_SECRET_ACCESS_KEY`` are set (for
example the local SeaweedFS of ``pnpm infra:up``); otherwise it is skipped. It
writes one object under a random ``mti360-tests/`` key and deletes it again,
and checks that anonymous access to the bucket is refused.
"""

import os
import urllib.error
import urllib.request
import uuid

import pytest

from app.integrations.storage import ObjectNotFoundError, S3ObjectStorage

pytestmark = pytest.mark.anyio
_NAMES = (
    "TEST_S3_ENDPOINT_URL",
    "TEST_S3_BUCKET",
    "TEST_S3_ACCESS_KEY_ID",
    "TEST_S3_SECRET_ACCESS_KEY",
)


@pytest.fixture
def s3() -> tuple[S3ObjectStorage, str, str]:
    values = {name: os.environ.get(name, "") for name in _NAMES}
    if not all(values.values()):
        pytest.skip("S3 not configured (set TEST_S3_*; see ADR-0021 §8)")
    storage = S3ObjectStorage.create(
        endpoint_url=values["TEST_S3_ENDPOINT_URL"],
        region="us-east-1",
        bucket=values["TEST_S3_BUCKET"],
        access_key_id=values["TEST_S3_ACCESS_KEY_ID"],
        secret_access_key=values["TEST_S3_SECRET_ACCESS_KEY"],
    )
    return storage, values["TEST_S3_ENDPOINT_URL"], values["TEST_S3_BUCKET"]


async def test_round_trip_against_the_real_store(s3: tuple[S3ObjectStorage, str, str]) -> None:
    storage, endpoint, bucket = s3
    key = f"mti360-tests/{uuid.uuid7()}"
    data = b"%PDF-1.7\n% admission document test\n"
    await storage.put(key, data, content_type="application/pdf")
    try:
        assert await storage.get(key) == data
        anonymous = urllib.request.Request(f"{endpoint}/{bucket}/{key}")  # noqa: S310
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(anonymous, timeout=5)  # noqa: S310 - local test endpoint
        refused.value.close()
        assert refused.value.code in {401, 403}
    finally:
        await storage.delete(key)
    with pytest.raises(ObjectNotFoundError):
        await storage.get(key)
