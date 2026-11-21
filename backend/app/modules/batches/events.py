"""Batch audit events (Phase 02-6; ADR-0013 category ``domain``).

Metadata: codes, statuses, field names, booleans and amounts in paise. Never
a student's name or contact detail; never the free-text reasons.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

BATCH_CREATED = AuditEventType("batch.created", _D)
BATCH_UPDATED = AuditEventType("batch.updated", _D)
BATCH_STATUS_CHANGED = AuditEventType("batch.status_changed", _D)
STUDENT_ALLOCATED = AuditEventType("batch.student_allocated", _D)
PAYMENT_OVERRIDDEN = AuditEventType("batch.payment_overridden", _D)
STUDENT_TRANSFERRED = AuditEventType("batch.student_transferred", _D)
STUDENT_WITHDRAWN = AuditEventType("batch.student_withdrawn", _D)
