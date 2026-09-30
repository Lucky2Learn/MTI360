"""Database infrastructure: engine, base model, mixins and transaction settings."""

from app.core.db.base import (
    NAMING_CONVENTION,
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionedMixin,
)
from app.core.db.engine import create_engine, create_sessionmaker
from app.core.db.settings import apply_transaction_settings

__all__ = [
    "NAMING_CONVENTION",
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "VersionedMixin",
    "apply_transaction_settings",
    "create_engine",
    "create_sessionmaker",
]
