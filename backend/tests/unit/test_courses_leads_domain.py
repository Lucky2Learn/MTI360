"""Course and lead rules (Phase 02-1; blueprint §4-§11, ADR-0020).

Pure rules: transition tables (every pair), reasons, duplicate targets,
duplicate keys, the duration pair and the code format; and the shared
campus visibility predicate, compared with ``authorize()`` over every
combination.
"""

import itertools
import uuid
from datetime import date

import pytest
from sqlalchemy import Column, MetaData, Table, Uuid, select
from sqlalchemy.dialects import postgresql

from app.core.activity import ActivityDetailsError, activity_details
from app.core.authz import (
    Permission,
    PermissionScope,
    authorize,
    campus_visibility,
    campus_visible,
)
from app.core.context import Realm, RequestContext
from app.core.errors import NotFoundError
from app.core.transitions import TransitionTable
from app.modules.courses.domain import (
    COURSE_TRANSITIONS,
    CourseStatus,
    DurationUnit,
    duration_valid,
    normalize_code,
)
from app.modules.leads.domain import (
    APPLICATION_START,
    CLOSED_STATUSES,
    LEAD_TRANSITIONS,
    OPEN_STATUSES,
    PIPELINE,
    PROGRESSED_STATUSES,
    LeadStatus,
    TransitionProblem,
    birth_date_valid,
    clean_email,
    clean_mobile,
    mobile_key,
    search_digits,
    transition_problem,
)

S = LeadStatus

# --- Courses -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("source", "target"), list(itertools.product(CourseStatus, CourseStatus)))
def test_course_transitions(source: CourseStatus, target: CourseStatus) -> None:
    allowed = {
        (CourseStatus.DRAFT, CourseStatus.ACTIVE),
        (CourseStatus.DRAFT, CourseStatus.ARCHIVED),
        (CourseStatus.ACTIVE, CourseStatus.ARCHIVED),
        (CourseStatus.ARCHIVED, CourseStatus.ACTIVE),
    }
    assert COURSE_TRANSITIONS.allows(source, target) is ((source, target) in allowed)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("gpr", "GPR"),
        ("  stcw-bst ", "STCW-BST"),
        ("DNS2", "DNS2"),
        ("-GPR", None),
        ("G P R", None),
        ("GPR_1", None),
        ("", None),
        ("A" * 33, None),
        ("A" * 32, "A" * 32),
    ],
)
def test_course_codes_follow_the_campus_code_format(raw: str, expected: str | None) -> None:
    assert normalize_code(raw) == expected


def test_a_duration_needs_both_value_and_unit() -> None:
    assert duration_valid(None, None)
    assert duration_valid(6, DurationUnit.MONTHS)
    assert not duration_valid(6, None)
    assert not duration_valid(None, DurationUnit.DAYS)
    assert not duration_valid(0, DurationUnit.DAYS)
    assert not duration_valid(1001, DurationUnit.DAYS)


# --- Lead statuses -----------------------------------------------------------------------------


def test_the_status_groups_partition_the_vocabulary() -> None:
    assert set(LeadStatus) == OPEN_STATUSES | PROGRESSED_STATUSES | CLOSED_STATUSES
    assert len(OPEN_STATUSES) + len(PROGRESSED_STATUSES) + len(CLOSED_STATUSES) == len(LeadStatus)
    assert PIPELINE == (S.NEW, S.CONTACTED, S.QUALIFIED, S.COUNSELLING, S.INTERESTED)


@pytest.mark.parametrize(("source", "target"), list(itertools.product(LeadStatus, LeadStatus)))
def test_lead_transitions(source: LeadStatus, target: LeadStatus) -> None:
    expected = source != target and (
        (source in OPEN_STATUSES and target in OPEN_STATUSES | CLOSED_STATUSES)
        or (source in CLOSED_STATUSES and target in OPEN_STATUSES)
    )
    assert LEAD_TRANSITIONS.allows(source, target) is expected
    # APPLICATION / ADMITTED are never reachable, or left, through the staff endpoint.
    if PROGRESSED_STATUSES & {source, target}:
        assert not LEAD_TRANSITIONS.allows(source, target)


def test_only_open_leads_can_start_an_application() -> None:
    for status in LeadStatus:
        assert APPLICATION_START.allows(status, S.APPLICATION) is (status in OPEN_STATUSES)
    assert not APPLICATION_START.allows(S.NEW, S.ADMITTED)


@pytest.mark.parametrize("target", [S.NOT_ELIGIBLE, S.LOST, S.DEFERRED])
def test_closing_needs_a_reason(target: LeadStatus) -> None:
    problem = transition_problem(S.QUALIFIED, target, reason=None, has_duplicate_target=False)
    assert problem is TransitionProblem.REASON_REQUIRED
    assert transition_problem(S.QUALIFIED, target, reason="Age", has_duplicate_target=False) is None


def test_a_duplicate_needs_its_original_and_no_reason() -> None:
    no_target = transition_problem(S.NEW, S.DUPLICATE, reason=None, has_duplicate_target=False)
    assert no_target is TransitionProblem.DUPLICATE_TARGET
    assert transition_problem(S.NEW, S.DUPLICATE, reason=None, has_duplicate_target=True) is None


def test_reopening_needs_a_reason_and_open_moves_do_not() -> None:
    reopen = transition_problem(S.LOST, S.CONTACTED, reason=None, has_duplicate_target=False)
    assert reopen is TransitionProblem.REASON_REQUIRED
    assert (
        transition_problem(S.LOST, S.CONTACTED, reason="Called back", has_duplicate_target=False)
        is None
    )
    assert transition_problem(S.NEW, S.CONTACTED, reason=None, has_duplicate_target=False) is None
    assert transition_problem(S.QUALIFIED, S.NEW, reason=None, has_duplicate_target=False) is None


@pytest.mark.parametrize(
    ("source", "target"),
    [(S.NEW, S.NEW), (S.NEW, S.APPLICATION), (S.NEW, S.ADMITTED), (S.LOST, S.DEFERRED)],
)
def test_invalid_moves_are_reported_first(source: LeadStatus, target: LeadStatus) -> None:
    problem = transition_problem(source, target, reason="x", has_duplicate_target=True)
    assert problem is TransitionProblem.INVALID


def test_a_transition_table_never_allows_staying_put() -> None:
    table = TransitionTable[str]({"a": {"a", "b"}})
    assert table.targets("a") == {"b"}
    assert not table.allows("a", "a")
    assert table.targets("z") == frozenset()


# --- Duplicate keys and contact rules ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["+91 98200 10234", "098200 10234", "9820010234", "+91-98200-10234", "(0) 98200 10234"],
)
def test_mobile_variants_share_one_key(raw: str) -> None:
    assert mobile_key(clean_mobile(raw)) == "9820010234"


def test_short_numbers_keep_all_digits_and_implausible_ones_are_refused() -> None:
    assert mobile_key(clean_mobile("02352 2201")) == "023522201"
    assert clean_mobile("  ") is None
    for raw in ("call me", "12345", "+91 98200 10234 ext 5", "1" * 16):
        with pytest.raises(ValueError, match="phone"):
            clean_mobile(raw)


def test_emails_are_matched_case_insensitively_and_kept_as_entered() -> None:
    assert clean_email("  Ravi.Kumar@Example.com ") == (
        "Ravi.Kumar@Example.com",
        "ravi.kumar@example.com",
    )
    assert clean_email("") is None
    with pytest.raises(ValueError, match="email"):
        clean_email("ravi.kumar")


def test_search_digits_only_for_phone_like_terms() -> None:
    assert search_digits("98200 10") == "9820010"
    assert search_digits("982") is None
    assert search_digits("GPR 2026") is None


def test_birth_dates_are_in_the_past() -> None:
    today = date(2026, 10, 8)
    assert birth_date_valid(None, today)
    assert birth_date_valid(date(2007, 5, 1), today)
    assert not birth_date_valid(today, today)
    assert not birth_date_valid(date(1899, 12, 31), today)


# --- Activity details --------------------------------------------------------------------------


def test_activity_details_are_flat_and_bounded() -> None:
    lead = uuid.uuid7()
    assert activity_details({"from": "NEW", "duplicate_of": lead, "fields": ["city"]}) == {
        "from": "NEW",
        "duplicate_of": str(lead),
        "fields": ["city"],
    }
    for bad in ({"Bad Key": 1}, {"nested": {"a": 1}}, {"text": "x" * 5000}):
        with pytest.raises(ActivityDetailsError):
            activity_details(bad)


# --- Campus visibility == authorize() ----------------------------------------------------------

CAMPUS_A, CAMPUS_B = uuid.uuid7(), uuid.uuid7()
TENANT = uuid.uuid7()
READ = Permission("lead.read", Realm.TENANT, PermissionScope.CAMPUS, "x", "test")


class _Resource:
    def __init__(self, campus_id: uuid.UUID | None) -> None:
        self.tenant_id = TENANT
        self.campus_id = campus_id


def _context(all_campuses: bool, campuses: frozenset[uuid.UUID]) -> RequestContext:
    return RequestContext(
        realm=Realm.TENANT,
        request_id=uuid.uuid7(),
        principal_id=uuid.uuid7(),
        tenant_id=TENANT,
        permissions=frozenset({READ.code}),
        all_campuses=all_campuses,
        campus_ids=campuses,
    )


SCOPES = [
    (True, frozenset({CAMPUS_A, CAMPUS_B})),
    (False, frozenset({CAMPUS_A})),
    (False, frozenset({CAMPUS_A, CAMPUS_B})),
    (False, frozenset()),
]


def _authorized(context: RequestContext, campus_id: uuid.UUID | None) -> bool:
    try:
        authorize(context, READ, _Resource(campus_id))
    except NotFoundError:
        return False
    return True


def _sql_matches(context: RequestContext, campus_id: uuid.UUID | None) -> bool:
    """Evaluate the predicate as compiled SQL against one row (bound parameters inlined)."""
    table = Table("probe", MetaData(), Column("campus_id", Uuid, nullable=True))
    predicate = campus_visibility(table.c.campus_id, context)
    sql = str(
        select(table)
        .where(predicate)
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})  # type: ignore[no-untyped-call]
    )
    where = sql.split("WHERE", 1)[1].strip() if "WHERE" in sql else "true"
    value = "NULL" if campus_id is None else f"'{campus_id}'"
    expression = (
        where.replace("probe.campus_id IS NULL", "IS_NULL")
        .replace("probe.campus_id", value)
        .replace("IS_NULL", str(campus_id is None).lower())
    )
    return _evaluate(expression)


def _evaluate(expression: str) -> bool:
    """A tiny evaluator for the predicates ``campus_visibility`` produces."""
    expression = expression.strip()
    if expression in ("true", "false"):
        return expression == "true"
    if " OR " in expression:
        return any(_evaluate(part.strip("() ")) for part in expression.split(" OR "))
    if " IN " in expression:
        value, values = expression.split(" IN ", 1)
        return value.strip() != "NULL" and value.strip() in values
    raise AssertionError(f"unexpected predicate: {expression}")


@pytest.mark.parametrize(("all_campuses", "campuses"), SCOPES)
@pytest.mark.parametrize("campus_id", [None, CAMPUS_A, CAMPUS_B])
def test_the_list_predicate_equals_authorize(
    all_campuses: bool, campuses: frozenset[uuid.UUID], campus_id: uuid.UUID | None
) -> None:
    context = _context(all_campuses, campuses)
    expected = _authorized(context, campus_id)
    assert campus_visible(campus_id, context) is expected
    assert _sql_matches(context, campus_id) is expected
