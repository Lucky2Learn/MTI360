"""Public enquiry audit events (Phase 02-4, ADR-0024).

An accepted enquiry is recorded as ``lead.created`` (``channel =
public_enquiry``) with the lead, like any other new lead. These are the
public-only signals. Neither carries personal data.
"""

from app.core.audit import AuditCategory, AuditEventType

ENQUIRY_DISCARDED = AuditEventType("enquiry.discarded", AuditCategory.SECURITY)
"""The hidden spam-trap field was filled in: answered as received, nothing stored."""
ENQUIRY_ORIGIN_REJECTED = AuditEventType("enquiry.origin_rejected", AuditCategory.SECURITY)
"""The browser said the form was posted from another site."""
