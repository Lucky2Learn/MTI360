"""Finance-lite permissions (Phase 02-5; ADR-0022, readiness plan §6). Tenant realm.

* ``fee_structure.read`` is campus-scoped and reads the institute catalogue
  (fee structures have no campus, like courses); ``fee_structure.manage`` is
  tenant-wide, so it is effective only with all-campus access (D-B1).
* Invoices and payments are checked against the fee invoice's campus (the
  admission's). ``invoice.read`` covers payments and receipts.
* No finance permission requires step-up in the MVP (ADR-0022 §10).
"""

from app.core.authz import PermissionScope, permission
from app.core.context import Realm

_M = "finance"
_C = PermissionScope.CAMPUS

FEE_STRUCTURE_READ = permission(
    "fee_structure.read", Realm.TENANT, _C, "View fee structures", module=_M
)
FEE_STRUCTURE_MANAGE = permission(
    "fee_structure.manage",
    Realm.TENANT,
    PermissionScope.TENANT,
    "Create, edit, activate and archive fee structures",
    module=_M,
)
INVOICE_READ = permission(
    "invoice.read", Realm.TENANT, _C, "View fee invoices, payments and receipts", module=_M
)
INVOICE_ISSUE = permission("invoice.issue", Realm.TENANT, _C, "Issue fee invoices", module=_M)
INVOICE_CANCEL = permission("invoice.cancel", Realm.TENANT, _C, "Cancel fee invoices", module=_M)
PAYMENT_RECORD = permission(
    "payment.record",
    Realm.TENANT,
    _C,
    "Record payments and confirm or fail pending cheques and demand drafts",
    module=_M,
)
PAYMENT_REVERSE = permission(
    "payment.reverse", Realm.TENANT, _C, "Reverse confirmed payments", module=_M
)
