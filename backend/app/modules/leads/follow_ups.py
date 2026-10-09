"""Follow-ups, notes and the lead timeline (Phase 02-1; blueprint §11-§12).

Everything is authorized through the parent lead (``lead.read`` to read,
``lead.update`` to change; campus rule, 404 outside it). Follow-ups are
lightweight tasks: no reminders, scheduler or messages. Overdue and the next
follow-up are derived, never stored. Follow-ups and notes are recorded in
``lead_activities`` only (not audited, ADR-0020 Y10). Notes are immutable.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Protocol, cast

from sqlalchemy import Table, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.activity import record_activity
from app.core.authz import campus_visible
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams
from app.modules.leads import repository as repo
from app.modules.leads.domain import (
    FOLLOW_UP_TEXT_MAX_LENGTH,
    NOTE_MAX_LENGTH,
    ActivityKind,
    FollowUpKind,
    FollowUpStatus,
    clean_text,
)
from app.modules.leads.models import Lead, LeadActivity, LeadFollowUp
from app.modules.leads.permissions import LEAD_READ, LEAD_UPDATE
from app.modules.leads.service import Caller, authorized_lead, caller, owner_eligible

ACTIVITIES = cast(Table, LeadActivity.__table__)
EARLIEST_DUE: Final = timedelta(days=1)
LATEST_DUE: Final = timedelta(days=366)
STALE = "This follow-up was changed by someone else. Reload and try again."
_ASSIGNMENT_KEYS = ("owner_from", "owner_to")
_CAMPUS_KEYS = ("campus_from", "campus_to")


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[ErrorDetail(field=field, code=code, message=message)])


def _text(value: str | None, field: str, limit: int) -> str | None:
    try:
        return clean_text(value, limit)
    except ValueError:
        raise _invalid(field, "too_long", f"Use at most {limit} characters.") from None


def _due(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise _invalid("due_at", "timezone_required", "Include the time zone.")
    now = datetime.now(UTC)
    if not now - EARLIEST_DUE <= value <= now + LATEST_DUE:
        raise _invalid("due_at", "out_of_range", "Choose a date within the next year.")
    return value


async def _activity(
    db: AsyncSession,
    who: Caller,
    lead_id: uuid.UUID,
    kind: ActivityKind,
    details: dict[str, object] | None = None,
    body: str | None = None,
) -> uuid.UUID:
    return await record_activity(
        db,
        ACTIVITIES,
        subject_column="lead_id",
        subject_id=lead_id,
        kind=kind.value,
        actor_membership_id=who.membership_id,
        details=details,
        body=body,
    )


def _follow_up_details(item: LeadFollowUp, **extra: object) -> dict[str, object]:
    return {"follow_up_id": item.id, "follow_up_kind": item.kind, **extra}


# --- Follow-ups ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FollowUpView:
    item: LeadFollowUp
    assignee_name: str | None
    completed_by_name: str | None
    overdue: bool


async def _views(db: AsyncSession, who: Caller, items: list[LeadFollowUp]) -> list[FollowUpView]:
    ids = {i.assignee_membership_id for i in items} | {
        i.completed_by_membership_id for i in items if i.completed_by_membership_id
    }
    names = await repo.display_names(db, who.tenant_id, ids)
    now = datetime.now(UTC)
    return [
        FollowUpView(
            item,
            names.get(item.assignee_membership_id),
            names.get(item.completed_by_membership_id) if item.completed_by_membership_id else None,
            item.status == FollowUpStatus.OPEN.value and item.due_at < now,
        )
        for item in items
    ]


async def list_follow_ups(
    db: AsyncSession, lead_id: uuid.UUID, status: FollowUpStatus | None
) -> list[FollowUpView]:
    who = await caller(db, LEAD_READ)
    await authorized_lead(db, who, lead_id, LEAD_READ)
    return await _views(db, who, await repo.follow_ups_of(db, who.tenant_id, lead_id, status))


async def _assignee(
    db: AsyncSession, who: Caller, lead: Lead, requested: uuid.UUID | None
) -> uuid.UUID:
    """The requested member if eligible; by default the lead owner (when still eligible),
    else the caller (blueprint §11)."""
    if requested is not None:
        if not await owner_eligible(db, who.tenant_id, requested, lead.campus_id):
            raise _invalid(
                "assignee_membership_id",
                "owner_not_eligible",
                "Choose an active team member who works with this campus.",
            )
        return requested
    owner = lead.owner_membership_id
    if owner is not None and await owner_eligible(db, who.tenant_id, owner, lead.campus_id):
        return owner
    return who.membership_id


async def schedule(
    db: AsyncSession,
    lead_id: uuid.UUID,
    *,
    due_at: datetime,
    kind: FollowUpKind,
    note: str | None,
    assignee: uuid.UUID | None,
) -> FollowUpView:
    who = await caller(db, LEAD_UPDATE)
    lead = await authorized_lead(db, who, lead_id, LEAD_UPDATE)
    item = LeadFollowUp(
        tenant_id=who.tenant_id,
        lead_id=lead.id,
        assignee_membership_id=await _assignee(db, who, lead, assignee),
        due_at=_due(due_at),
        kind=kind.value,
        note=_text(note, "note", FOLLOW_UP_TEXT_MAX_LENGTH),
        status=FollowUpStatus.OPEN.value,
        created_by_membership_id=who.membership_id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    await _activity(
        db,
        who,
        lead.id,
        ActivityKind.FOLLOW_UP_SCHEDULED,
        _follow_up_details(item, due_at=item.due_at.isoformat()),
    )
    return (await _views(db, who, [item]))[0]


async def _open_follow_up(
    db: AsyncSession, who: Caller, follow_up_id: uuid.UUID, version: int
) -> tuple[LeadFollowUp, Lead]:
    """The follow-up through its lead (``lead.update``; 404 outside the campus), still OPEN."""
    item = await repo.follow_up(db, who.tenant_id, follow_up_id)
    if item is None:
        raise NotFoundError()
    lead = await authorized_lead(db, who, item.lead_id, LEAD_UPDATE)
    if item.status != FollowUpStatus.OPEN.value:
        raise _invalid("status", "follow_up_closed", "This follow-up is already closed.")
    if item.version != version:
        raise ConflictError(STALE)
    return item, lead


async def reschedule(
    db: AsyncSession, follow_up_id: uuid.UUID, *, changes: dict[str, Any], version: int
) -> FollowUpView:
    who = await caller(db, LEAD_UPDATE)
    item, lead = await _open_follow_up(db, who, follow_up_id, version)
    if "due_at" in changes and changes["due_at"] is not None:
        item.due_at = _due(changes["due_at"])
    if "kind" in changes and changes["kind"] is not None:
        item.kind = FollowUpKind(changes["kind"]).value
    if "note" in changes:
        item.note = _text(changes["note"], "note", FOLLOW_UP_TEXT_MAX_LENGTH)
    if "assignee_membership_id" in changes:
        item.assignee_membership_id = await _assignee(
            db, who, lead, changes["assignee_membership_id"]
        )
    await db.flush()
    await db.refresh(item)
    await _activity(
        db,
        who,
        lead.id,
        ActivityKind.FOLLOW_UP_SCHEDULED,
        _follow_up_details(item, due_at=item.due_at.isoformat(), rescheduled=True),
    )
    return (await _views(db, who, [item]))[0]


async def _close(
    db: AsyncSession,
    follow_up_id: uuid.UUID,
    *,
    status: FollowUpStatus,
    outcome: str | None,
    version: int,
) -> FollowUpView:
    who = await caller(db, LEAD_UPDATE)
    item, lead = await _open_follow_up(db, who, follow_up_id, version)
    item.status = status.value
    item.outcome = _text(outcome, "outcome", FOLLOW_UP_TEXT_MAX_LENGTH)
    item.completed_at = func.now()
    item.completed_by_membership_id = who.membership_id
    await db.flush()
    await db.refresh(item)
    kind = (
        ActivityKind.FOLLOW_UP_COMPLETED
        if status is FollowUpStatus.DONE
        else ActivityKind.FOLLOW_UP_CANCELLED
    )
    await _activity(db, who, lead.id, kind, _follow_up_details(item))
    return (await _views(db, who, [item]))[0]


async def complete(
    db: AsyncSession, follow_up_id: uuid.UUID, *, outcome: str | None, version: int
) -> FollowUpView:
    return await _close(
        db, follow_up_id, status=FollowUpStatus.DONE, outcome=outcome, version=version
    )


async def cancel(db: AsyncSession, follow_up_id: uuid.UUID, *, version: int) -> FollowUpView:
    return await _close(
        db, follow_up_id, status=FollowUpStatus.CANCELLED, outcome=None, version=version
    )


# --- Notes and the timeline ----------------------------------------------------------------


class ActivityRecord(Protocol):
    """A timeline row: a ``LeadActivity``, or a row of the Student 360 union (Phase 02-2)."""

    @property
    def id(self) -> uuid.UUID: ...

    @property
    def kind(self) -> str: ...

    @property
    def actor_membership_id(self) -> uuid.UUID | None: ...

    @property
    def details(self) -> dict[str, Any]: ...

    @property
    def body(self) -> str | None: ...

    @property
    def created_at(self) -> datetime: ...


@dataclass(frozen=True, slots=True)
class ActivityView:
    item: ActivityRecord
    actor_name: str | None
    details: dict[str, Any]


async def activity_views(
    db: AsyncSession, who: Caller, items: Sequence[ActivityRecord]
) -> list[ActivityView]:
    """Activity with names resolved server-side. Assignment details gain ``*_name`` keys;
    a campus outside the caller's scope is named generically, never disclosed."""
    members: set[uuid.UUID] = {i.actor_membership_id for i in items if i.actor_membership_id}
    campuses: set[uuid.UUID] = set()
    for item in items:
        for key in _ASSIGNMENT_KEYS:
            if item.details.get(key):
                members.add(uuid.UUID(item.details[key]))
        for key in _CAMPUS_KEYS:
            if item.details.get(key):
                campuses.add(uuid.UUID(item.details[key]))
    names = await repo.display_names(db, who.tenant_id, members)
    visible = {c for c in campuses if campus_visible(c, who.context)}
    campus_names = await repo.campus_names(db, who.tenant_id, visible)
    views: list[ActivityView] = []
    for item in items:
        details = dict(item.details)
        for key in _ASSIGNMENT_KEYS:
            if details.get(key):
                details[f"{key}_name"] = names.get(uuid.UUID(details[key]))
        for key in _CAMPUS_KEYS:
            if details.get(key):
                campus = uuid.UUID(details[key])
                details[f"{key}_name"] = campus_names.get(campus, "Another campus")
        actor = names.get(item.actor_membership_id) if item.actor_membership_id else None
        views.append(ActivityView(item, actor, details))
    return views


async def list_activity(
    db: AsyncSession, lead_id: uuid.UUID, page: PageParams
) -> tuple[list[ActivityView], int]:
    who = await caller(db, LEAD_READ)
    await authorized_lead(db, who, lead_id, LEAD_READ)
    items, total = await repo.activities_of(db, who.tenant_id, lead_id, page)
    return await activity_views(db, who, items), total


async def add_note(db: AsyncSession, lead_id: uuid.UUID, *, body: str) -> ActivityView:
    """Append an immutable note (plain text, 1-4000 characters)."""
    who = await caller(db, LEAD_UPDATE)
    lead = await authorized_lead(db, who, lead_id, LEAD_UPDATE)
    text = _text(body, "body", NOTE_MAX_LENGTH)
    if text is None:
        raise _invalid("body", "required", "Write a note.")
    activity_id = await _activity(db, who, lead.id, ActivityKind.NOTE, body=text)
    found = await db.get(LeadActivity, activity_id)
    if found is None:  # pragma: no cover - inserted in this transaction
        raise NotFoundError()
    return (await activity_views(db, who, [found]))[0]
