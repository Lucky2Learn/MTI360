"""Finance-lite services (Phase 02-5; ADR-0022).

Fee structures are institute-wide, like courses: an authorization resource
**without a campus** (D-B1). ``fee_structure.read`` (campus-scoped) admits
campus-restricted members; ``fee_structure.manage`` (tenant-scoped) needs
all-campus access. A structure is edited only while ``DRAFT``; activating
one archives the course's previous active structure in the same transaction
(the partial unique index makes a concurrent second activation a 409).

Every change checks the optimistic ``version`` and writes a ``domain`` audit
event in the request transaction (amounts, counts, statuses and field names
only; ADR-0013).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditTarget, write_audit_event
from app.core.authz import Permission, authorize
from app.core.errors import ConflictError, ErrorDetail, NotFoundError, ValidationFailedError
from app.core.pagination import PageParams, SortField
from app.modules.courses.domain import CourseStatus
from app.modules.finance import events
from app.modules.finance.domain import (
    CURRENCY,
    FEE_HEAD_MAX_LENGTH,
    FEE_STRUCTURE_TRANSITIONS,
    NAME_MAX_LENGTH,
    FeeItem,
    FeeStructureStatus,
    clean_label,
    items_problems,
)
from app.modules.finance.models import FeeStructure
from app.modules.finance.permissions import FEE_STRUCTURE_MANAGE, FEE_STRUCTURE_READ
from app.modules.finance.repository import (
    CourseRef,
    FeeStructureRepository,
    StructureFilters,
    StructureRow,
    course_ref,
)
from app.modules.leads.service import Caller, caller

STRUCTURE_STALE = "This fee structure was changed by someone else. Reload and try again."
ITEM_MESSAGES = {
    "line_count": "Add between 1 and 30 fee heads.",
    "duplicate_fee_head": "Use each fee head once.",
    "amount_out_of_range": "Enter amounts from ₹0 up to ₹1,00,00,00,000.",
    "total_out_of_range": "The total must be more than ₹0 and at most ₹1,00,00,00,000.",
}


@dataclass(frozen=True, slots=True)
class StructureResource:
    """A fee structure as an authorization resource: institute-wide, so no campus."""

    tenant_id: uuid.UUID
    campus_id: uuid.UUID | None = None


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def _invalid(*details: ErrorDetail) -> ValidationFailedError:
    return ValidationFailedError(details=list(details))


def invalid_transition(message: str) -> ValidationFailedError:
    return _invalid(_detail("status", "invalid_transition", message))


# --- Validation ----------------------------------------------------------------------------


def clean_items(
    raw: Sequence[FeeItem], field: str = "items"
) -> tuple[list[FeeItem], list[ErrorDetail]]:
    """Fee heads collapsed and bounded, then the list rules (``items_problems``)."""
    items: list[FeeItem] = []
    problems: list[ErrorDetail] = []
    for index, item in enumerate(raw):
        head = clean_label(item.fee_head, FEE_HEAD_MAX_LENGTH)
        if head is None:
            problems.append(
                _detail(
                    f"{field}.{index}.fee_head",
                    "invalid",
                    "Enter a fee head of up to 100 characters.",
                )
            )
            continue
        items.append(FeeItem(head, item.amount_minor))
    if not problems:
        problems.extend(_detail(field, code, ITEM_MESSAGES[code]) for code in items_problems(items))
    return items, problems


def _clean_name(raw: str) -> tuple[str | None, list[ErrorDetail]]:
    name = clean_label(raw, NAME_MAX_LENGTH)
    if name is None:
        return None, [_detail("name", "invalid", "Enter a name of up to 200 characters.")]
    return name, []


def stored_items(items: Sequence[FeeItem]) -> list[dict[str, object]]:
    return [{"fee_head": item.fee_head, "amount_minor": item.amount_minor} for item in items]


def structure_items(structure: FeeStructure) -> list[FeeItem]:
    return [FeeItem(str(item["fee_head"]), int(item["amount_minor"])) for item in structure.items]


# --- Fee structures ------------------------------------------------------------------------


async def _structure(
    db: AsyncSession, who: Caller, structure_id: uuid.UUID, permission: Permission, *, lock: bool
) -> FeeStructure:
    repository = FeeStructureRepository(db)
    found = await (repository.locked(structure_id) if lock else repository.find(structure_id))
    if found is None:
        raise NotFoundError()
    authorize(who.context, permission, StructureResource(found.tenant_id))
    return found


async def _row(db: AsyncSession, who: Caller, structure: FeeStructure) -> StructureRow:
    found = await course_ref(db, who.tenant_id, structure.course_id)
    if found is None:  # pragma: no cover - the composite foreign key guarantees the course
        raise NotFoundError()
    return StructureRow(structure, found[0])


async def list_structures(
    db: AsyncSession, filters: StructureFilters, page: PageParams, sort: Sequence[SortField]
) -> tuple[list[StructureRow], int]:
    await caller(db, FEE_STRUCTURE_READ)
    return await FeeStructureRepository(db).search(filters, page, sort)


async def get_structure(db: AsyncSession, structure_id: uuid.UUID) -> StructureRow:
    who = await caller(db, FEE_STRUCTURE_READ)
    return await _row(
        db, who, await _structure(db, who, structure_id, FEE_STRUCTURE_READ, lock=False)
    )


async def create_structure(
    db: AsyncSession, *, course_id: uuid.UUID, name: str, items: Sequence[FeeItem]
) -> StructureRow:
    """A new ``DRAFT`` fee structure for a course of the institute (not archived)."""
    who = await caller(db, FEE_STRUCTURE_MANAGE)
    clean_name, problems = _clean_name(name)
    cleaned, item_problems = clean_items(items)
    problems.extend(item_problems)
    found = await course_ref(db, who.tenant_id, course_id)
    if found is None or found[1] == CourseStatus.ARCHIVED.value:
        problems.insert(
            0, _detail("course_id", "course_not_available", "Choose a draft or active course.")
        )
    if problems or clean_name is None or found is None:
        raise _invalid(*problems)
    structure = FeeStructure(
        tenant_id=who.tenant_id,
        course_id=course_id,
        name=clean_name,
        status=FeeStructureStatus.DRAFT.value,
        items=stored_items(cleaned),
        total_minor=sum(item.amount_minor for item in cleaned),
        currency=CURRENCY,
        created_by_membership_id=who.membership_id,
    )
    await FeeStructureRepository(db).add(structure)
    await db.refresh(structure)
    await write_audit_event(
        db,
        events.FEE_STRUCTURE_CREATED,
        target=AuditTarget("fee_structure", structure.id),
        metadata={
            "line_count": len(cleaned),
            "total_minor": structure.total_minor,
            "currency": CURRENCY,
        },
    )
    return StructureRow(structure, found[0])


async def update_structure(
    db: AsyncSession,
    structure_id: uuid.UUID,
    *,
    name: str | None,
    items: Sequence[FeeItem] | None,
    version: int,
) -> StructureRow:
    """Edit a ``DRAFT`` structure's name or items (optimistic ``version``)."""
    who = await caller(db, FEE_STRUCTURE_MANAGE)
    structure = await _structure(db, who, structure_id, FEE_STRUCTURE_MANAGE, lock=True)
    if structure.version != version:
        raise ConflictError(STRUCTURE_STALE)
    if structure.status != FeeStructureStatus.DRAFT.value:
        raise _invalid(
            _detail(
                "status",
                "not_editable",
                "Only a draft fee structure can be edited. Create a new one instead.",
            )
        )
    problems: list[ErrorDetail] = []
    changes: dict[str, object] = {}
    if name is not None:
        clean_name, name_problems = _clean_name(name)
        problems.extend(name_problems)
        changes["name"] = clean_name
    if items is not None:
        cleaned, item_problems = clean_items(items)
        problems.extend(item_problems)
        changes["items"] = stored_items(cleaned)
        changes["total_minor"] = sum(item.amount_minor for item in cleaned)
    if problems:
        raise _invalid(*problems)
    changed = sorted(
        field for field, value in changes.items() if getattr(structure, field) != value
    )
    if not changed:
        return await _row(db, who, structure)
    for field in changed:
        setattr(structure, field, changes[field])
    await db.flush()
    await db.refresh(structure)
    await write_audit_event(
        db,
        events.FEE_STRUCTURE_UPDATED,
        target=AuditTarget("fee_structure", structure.id),
        metadata={"changed_fields": [f for f in changed if f != "total_minor"]},
    )
    return await _row(db, who, structure)


async def change_structure_status(
    db: AsyncSession, structure_id: uuid.UUID, *, status: FeeStructureStatus, version: int
) -> StructureRow:
    """Activate (archiving the course's previous active structure) or archive."""
    who = await caller(db, FEE_STRUCTURE_MANAGE)
    structure = await _structure(db, who, structure_id, FEE_STRUCTURE_MANAGE, lock=True)
    if structure.version != version:
        raise ConflictError(STRUCTURE_STALE)
    current = FeeStructureStatus(structure.status)
    if not FEE_STRUCTURE_TRANSITIONS.allows(current, status):
        raise invalid_transition("This fee structure cannot move to that status.")
    repository = FeeStructureRepository(db)
    previous: FeeStructure | None = None
    if status is FeeStructureStatus.ACTIVE:
        previous = await repository.active_for(structure.course_id, lock=True)
        if previous is not None:
            previous.status = FeeStructureStatus.ARCHIVED.value
            previous.archived_at = func.now()
            await db.flush()
        structure.activated_at = func.now()
    else:
        structure.archived_at = func.now()
    structure.status = status.value
    try:
        await db.flush()
    except IntegrityError:  # another structure of the course was activated concurrently
        raise ConflictError(STRUCTURE_STALE) from None
    await db.refresh(structure)
    if previous is not None:
        await write_audit_event(
            db,
            events.FEE_STRUCTURE_ARCHIVED,
            target=AuditTarget("fee_structure", previous.id),
            metadata={"from": FeeStructureStatus.ACTIVE.value, "replaced_by_activation": True},
        )
    await write_audit_event(
        db,
        events.FEE_STRUCTURE_ACTIVATED
        if status is FeeStructureStatus.ACTIVE
        else events.FEE_STRUCTURE_ARCHIVED,
        target=AuditTarget("fee_structure", structure.id),
        metadata={"from": current.value, "archived_previous": previous is not None}
        if status is FeeStructureStatus.ACTIVE
        else {"from": current.value, "replaced_by_activation": False},
    )
    return await _row(db, who, structure)


__all__ = [
    "CourseRef",
    "StructureFilters",
    "StructureRow",
    "change_structure_status",
    "create_structure",
    "get_structure",
    "list_structures",
    "update_structure",
]
