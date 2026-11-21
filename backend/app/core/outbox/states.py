"""Outbox states and the retry schedule (Phase 02-4, ADR-0024). Pure rules."""

from datetime import timedelta
from enum import StrEnum
from typing import Final

KIND_MAX_LENGTH: Final = 64
ERROR_MAX_LENGTH: Final = 64
RETRY_BASE: Final = timedelta(minutes=1)
RETRY_CAP: Final = timedelta(hours=1)


class OutboxStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


def retry_delay(attempts: int) -> timedelta:
    """Wait before the next attempt after ``attempts`` failed ones: 1, 2, 4 … 60 minutes."""
    return min(RETRY_BASE * (1 << max(0, min(attempts - 1, 16))), RETRY_CAP)


def error_name(error: BaseException) -> str:
    """What ``last_error`` records: the exception class only, never its text."""
    return type(error).__name__[:ERROR_MAX_LENGTH]
