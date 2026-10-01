"""Pagination, sorting and schema conventions (T01-01)."""

import pytest
from pydantic import ValidationError

from app.core.errors import ValidationFailedError
from app.core.pagination import SortField, parse_sort, sort_param
from app.core.schemas import MAX_STRING_LENGTH, ListEnvelope, RequestModel

ALLOWED = {"name", "created_at", "code"}


def test_sort_defaults_and_parses_direction() -> None:
    assert parse_sort(None, allowed=ALLOWED, default="name") == (SortField("name"),)
    assert parse_sort("-created_at, name", allowed=ALLOWED, default="name") == (
        SortField("created_at", descending=True),
        SortField("name"),
    )


@pytest.mark.parametrize(
    "value",
    ["password_hash", "name,name", "name,-name", "name,code,created_at,-x", "", " , "],
)
def test_invalid_sort_is_rejected_without_echoing_the_value(value: str) -> None:
    if not value.strip():
        # Blank means "use the default".
        assert parse_sort(value, allowed=ALLOWED, default="name") == (SortField("name"),)
        return
    with pytest.raises(ValidationFailedError) as error:
        parse_sort(value, allowed=ALLOWED, default="name")

    detail = error.value.details[0]
    assert detail.field == "sort"
    assert "password_hash" not in detail.message


def test_more_than_three_sort_fields_are_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        parse_sort("name,code,created_at,-name", allowed=ALLOWED, default="name")
    with pytest.raises(ValidationFailedError):
        parse_sort(
            "name,code,created_at,updated_at",
            allowed=ALLOWED | {"updated_at"},
            default="name",
        )


def test_sort_param_rejects_an_invalid_default_at_definition_time() -> None:
    with pytest.raises(ValidationFailedError):
        sort_param(allowed=ALLOWED, default="not_allowed")


class _Campus(RequestModel):
    name: str


def test_request_models_forbid_unknown_fields_such_as_tenant_id() -> None:
    with pytest.raises(ValidationError) as error:
        _Campus.model_validate({"name": "Kochi", "tenant_id": "0199..."})

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_request_models_bound_and_strip_strings() -> None:
    assert _Campus(name="  Kochi  ").name == "Kochi"
    with pytest.raises(ValidationError):
        _Campus(name="x" * (MAX_STRING_LENGTH + 1))


def test_list_envelope_carries_page_meta() -> None:
    envelope = ListEnvelope[str].build(["a", "b"], total=12, limit=2, offset=4)

    assert envelope.model_dump() == {
        "data": ["a", "b"],
        "meta": {"page": {"limit": 2, "offset": 4, "total": 12}},
    }
