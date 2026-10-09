"""Document audit events (Phase 02-2; ADR-0013 category ``domain``, ADR-0021 §12).

Metadata: the document type, content type, size and booleans. Never a file
name, file content, checksum or rejection reason.
"""

from app.core.audit import AuditCategory, AuditEventType

_D = AuditCategory.DOMAIN

DOCUMENT_UPLOADED = AuditEventType("document.uploaded", _D)
DOCUMENT_VERIFIED = AuditEventType("document.verified", _D)
DOCUMENT_REJECTED = AuditEventType("document.rejected", _D)
