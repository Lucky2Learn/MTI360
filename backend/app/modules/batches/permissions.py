"""Batch permissions (Phase 02-6). Tenant realm, campus-scoped.

A batch belongs to one campus, so every batch permission is checked against
that campus: a batch outside the caller's campuses is not found (404).
Overriding the payment gate needs ``batch.allocate`` and a recorded reason.
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "batches"
_C = PermissionScope.CAMPUS

BATCH_READ = permission(
    "batch.read", Realm.TENANT, _C, "View batches and their allocations", module=_M
)
BATCH_MANAGE = permission(
    "batch.manage",
    Realm.TENANT,
    _C,
    "Create and edit batches; open, close and cancel them",
    module=_M,
)
BATCH_ALLOCATE = permission(
    "batch.allocate",
    Realm.TENANT,
    _C,
    "Allocate admitted students to batches, transfer and withdraw them",
    module=_M,
)
