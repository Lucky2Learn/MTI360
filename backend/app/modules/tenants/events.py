"""Tenant administration audit events (T01-07; ADR-0013 category ``admin``).

Written in the transaction of the change they describe (D22). Provisioning
events are written inside the provisioning transaction and carry the new
tenant as ``tenant_id`` (D7-1); events about an existing tenant carry it as
the target. Metadata holds reasons and counts, never emails or tokens.
"""

from app.core.audit import AuditCategory, AuditEventType

_A = AuditCategory.ADMIN

TENANT_CREATED = AuditEventType("platform.tenant.created", _A)
OWNER_INVITED = AuditEventType("platform.tenant.owner_invited", _A)
OWNER_INVITATION_RESENT = AuditEventType("platform.tenant.owner_invitation.resent", _A)
TENANT_SUSPENDED = AuditEventType("platform.tenant.suspended", _A)
TENANT_REACTIVATED = AuditEventType("platform.tenant.reactivated", _A)
