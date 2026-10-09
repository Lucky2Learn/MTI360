"""Object storage integration (Phase 02-2; ADR-0021 §8): the ObjectStorage boundary.

Application code depends on :class:`ObjectStorage` only. Adapters:
:class:`S3ObjectStorage` (any S3-compatible service: SeaweedFS locally, S3 in
production) and :class:`InMemoryObjectStorage` (tests).
"""

from app.integrations.storage.memory import InMemoryObjectStorage
from app.integrations.storage.s3 import S3ObjectStorage
from app.integrations.storage.storage import ObjectNotFoundError, ObjectStorage, StorageError

__all__ = [
    "InMemoryObjectStorage",
    "ObjectNotFoundError",
    "ObjectStorage",
    "S3ObjectStorage",
    "StorageError",
]
