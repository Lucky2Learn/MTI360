"""Application document permissions (Phase 02-2; ADR-0021 §11). Tenant realm, campus-scoped.

A document belongs to an application, and is authorized through the
application's campus (404 outside it). A separate verifier is a custom role.
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "documents"
_C = PermissionScope.CAMPUS

DOCUMENT_READ = permission(
    "document.read", Realm.TENANT, _C, "View and download application documents", module=_M
)
DOCUMENT_UPLOAD = permission(
    "document.upload", Realm.TENANT, _C, "Upload application documents", module=_M
)
DOCUMENT_VERIFY = permission(
    "document.verify", Realm.TENANT, _C, "Verify or reject application documents", module=_M
)
