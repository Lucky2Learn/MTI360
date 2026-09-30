"""API schema conventions (T01-01; ARCHITECTURE.md §36, security.md §8).

* :class:`RequestModel` — every request body and query model. Unknown fields
  are rejected (``extra="forbid"``): a ``tenant_id``, ``status``, ``role`` or
  ``version`` that a schema does not declare can never be mass-assigned.
  Strings are bounded; each field should declare its own tighter limit.
* :class:`ResponseModel` — every response item; builds from ORM objects.
* :class:`Envelope` / :class:`ListEnvelope` — the success envelope
  ``{"data": …, "meta": {…}}``. Lists carry ``meta.page``.
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_STRING_LENGTH = 10_000
"""Upper bound for any string in a request (fields declare tighter limits)."""


class RequestModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_max_length=MAX_STRING_LENGTH,
        str_strip_whitespace=True,
        frozen=True,
    )


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Envelope[T](BaseModel):
    """Single-resource success response."""

    data: T
    meta: dict[str, Any] = Field(default_factory=dict)


class PageMeta(BaseModel):
    limit: int
    offset: int
    total: int


class ListMeta(BaseModel):
    page: PageMeta


class ListEnvelope[T](BaseModel):
    """Collection success response (offset pagination, T01-00 decision D13)."""

    data: list[T]
    meta: ListMeta

    @classmethod
    def build(cls, items: Sequence[T], *, total: int, limit: int, offset: int) -> ListEnvelope[T]:
        return cls(
            data=list(items),
            meta=ListMeta(page=PageMeta(limit=limit, offset=offset, total=total)),
        )
