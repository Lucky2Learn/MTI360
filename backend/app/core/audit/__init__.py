"""Audit foundation (T01-02; ADR-0013): the append-only ``audit_events`` table."""

from app.core.audit.events import AuditCategory
from app.core.audit.models import AuditEvent

__all__ = ["AuditCategory", "AuditEvent"]
