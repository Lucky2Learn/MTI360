"""S3-compatible object storage through boto3 (Phase 02-2; ADR-0021 §8-§9).

* boto3 is synchronous: every call runs in a worker thread (``anyio``).
* Path-style addressing and SigV4 (SeaweedFS locally; S3 in production with an
  ``https`` endpoint, enforced by the settings). Credentials stay inside the
  client; errors are logged by type only and re-raised as :class:`StorageError`.
* Creating the client opens no connection: ``/health`` stays dependency-free.
"""

import logging
from typing import Any

import anyio
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.integrations.storage.storage import ObjectNotFoundError, StorageError

logger = logging.getLogger("app.storage")
_MISSING = frozenset({"NoSuchKey", "404", "NotFound"})


class S3ObjectStorage:
    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def create(
        cls,
        *,
        endpoint_url: str | None,
        region: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        timeout_seconds: float = 10.0,
    ) -> S3ObjectStorage:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=timeout_seconds,
                read_timeout=timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        return cls(client, bucket)

    async def _call(self, operation: str, **kwargs: Any) -> Any:
        method = getattr(self._client, operation)
        try:
            return await anyio.to_thread.run_sync(lambda: method(Bucket=self._bucket, **kwargs))
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code in _MISSING:
                raise ObjectNotFoundError("object not found") from None
            logger.error("storage.failed", extra={"operation": operation, "error_code": code})
            raise StorageError("object storage request failed") from None
        except BotoCoreError as error:
            logger.error(
                "storage.unavailable",
                extra={"operation": operation, "error_type": type(error).__name__},
            )
            raise StorageError("object storage unavailable") from None

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        await self._call("put_object", Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        response = await self._call("get_object", Key=key)
        body = response["Body"]
        try:
            data: bytes = await anyio.to_thread.run_sync(body.read)
            return data
        except BotoCoreError as error:
            logger.error("storage.unavailable", extra={"error_type": type(error).__name__})
            raise StorageError("object storage unavailable") from None
        finally:
            body.close()

    async def delete(self, key: str) -> None:
        await self._call("delete_object", Key=key)
