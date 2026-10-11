"""Finance-lite audit events (Phase 02-5; ADR-0013 category ``domain``; ADR-0022 §11).

Metadata: amounts in paise, the currency, methods, statuses, field names,
counts and whether a reason was given. Never a name, a payment reference
(cheque, demand draft or UTR number) or reason text.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

FEE_STRUCTURE_CREATED = AuditEventType("fee_structure.created", _D)
FEE_STRUCTURE_UPDATED = AuditEventType("fee_structure.updated", _D)
FEE_STRUCTURE_ACTIVATED = AuditEventType("fee_structure.activated", _D)
FEE_STRUCTURE_ARCHIVED = AuditEventType("fee_structure.archived", _D)
INVOICE_ISSUED = AuditEventType("invoice.issued", _D)
INVOICE_CANCELLED = AuditEventType("invoice.cancelled", _D)
PAYMENT_RECORDED = AuditEventType("payment.recorded", _D)
PAYMENT_CONFIRMED = AuditEventType("payment.confirmed", _D)
PAYMENT_FAILED = AuditEventType("payment.failed", _D)
PAYMENT_REVERSED = AuditEventType("payment.reversed", _D)
