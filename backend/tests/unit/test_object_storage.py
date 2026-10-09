"""The object-storage boundary (Phase 02-2; ADR-0021 §8): the S3 adapter and the fake.

The S3 adapter is exercised against botocore's ``Stubber`` (no network): the
right bucket, key and content type are sent; a missing object is
:class:`ObjectNotFoundError`; any other failure is a generic
:class:`StorageError` whose message names no key, bucket or endpoint.
"""

import io

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.integrations.storage import (
    InMemoryObjectStorage,
    ObjectNotFoundError,
    S3ObjectStorage,
    StorageError,
)

pytestmark = pytest.mark.anyio
KEY = "tenants/00000000-0000-0000-0000-000000000001/files/00000000-0000-0000-0000-000000000002"


def _storage() -> tuple[S3ObjectStorage, Stubber]:
    storage = S3ObjectStorage.create(
        endpoint_url="http://127.0.0.1:1",
        region="us-east-1",
        bucket="private-bucket",
        access_key_id="test-access",
        secret_access_key="test-secret",
    )
    stubber = Stubber(storage._client)
    return storage, stubber


async def test_put_get_and_delete_address_the_private_bucket() -> None:
    storage, stubber = _storage()
    stubber.add_response(
        "put_object",
        {},
        {
            "Bucket": "private-bucket",
            "Key": KEY,
            "Body": b"%PDF-1.7",
            "ContentType": "application/pdf",
        },
    )
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(b"%PDF-1.7"), 8)},
        {"Bucket": "private-bucket", "Key": KEY},
    )
    stubber.add_response("delete_object", {}, {"Bucket": "private-bucket", "Key": KEY})
    with stubber:
        await storage.put(KEY, b"%PDF-1.7", content_type="application/pdf")
        assert await storage.get(KEY) == b"%PDF-1.7"
        await storage.delete(KEY)
    stubber.assert_no_pending_responses()


async def test_failures_are_generic_and_never_name_the_key() -> None:
    storage, stubber = _storage()
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    stubber.add_client_error("put_object", service_error_code="AccessDenied", http_status_code=403)
    with stubber:
        with pytest.raises(ObjectNotFoundError):
            await storage.get(KEY)
        with pytest.raises(StorageError) as raised:
            await storage.put(KEY, b"x", content_type="image/png")
    assert KEY not in str(raised.value)
    assert "private-bucket" not in str(raised.value)


async def test_the_fake_behaves_like_the_store_and_can_fail() -> None:
    fake = InMemoryObjectStorage()
    await fake.put(KEY, b"data", content_type="image/png")
    assert await fake.get(KEY) == b"data"
    await fake.delete(KEY)
    with pytest.raises(ObjectNotFoundError):
        await fake.get(KEY)
    fake.fail = True
    with pytest.raises(StorageError):
        await fake.put(KEY, b"data", content_type="image/png")
