"""Admission and student audit events (Phase 02-2; ADR-0013 category ``domain``).

Metadata: whether the student was created or linked. Never a name, contact
detail or number that identifies the person.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

ADMISSION_APPROVED = AuditEventType("admission.approved", _D)
STUDENT_CREATED = AuditEventType("student.created", _D)
