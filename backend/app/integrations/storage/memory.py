"""In-memory object storage for tests (Phase 02-2). Never used by the running application."""

from dataclasses import dataclass, field

from app.integrations.storage.storage import ObjectNotFoundError, StorageError


@dataclass
class InMemoryObjectStorage:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    fail: bool = False
    """When true every call raises :class:`StorageError` (an unavailable store)."""

    def _check(self) -> None:
        if self.fail:
            raise StorageError("object storage unavailable")

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self._check()
        self.objects[key] = (bytes(data), content_type)

    async def get(self, key: str) -> bytes:
        self._check()
        if key not in self.objects:
            raise ObjectNotFoundError("object not found")
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        self._check()
        self.objects.pop(key, None)
