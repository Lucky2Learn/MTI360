"""RBAC audit events (T01-05; ADR-0013).

Role and assignment changes are administrative events written in the
request transaction (``write_audit_event``): they exist only if the change
committed. A refused attempt to change a system role (D-B2) is a security
event, recorded even though the request fails. Metadata holds role names,
permission codes and counts — never credentials or tokens. Ordinary
permission checks are not audited; refusals are (``authz.denied``).
"""

from app.core.audit import AuditCategory, AuditEventType

_A = AuditCategory.ADMIN
_S = AuditCategory.SECURITY

ROLE_CREATED = AuditEventType("role.created", _A)
ROLE_UPDATED = AuditEventType("role.updated", _A)
ROLE_PERMISSIONS_CHANGED = AuditEventType("role.permissions_changed", _A)
ROLE_DELETED = AuditEventType("role.deleted", _A)
ROLE_ASSIGNED = AuditEventType("membership.role_assigned", _A)
ROLE_REMOVED = AuditEventType("membership.role_removed", _A)
SYSTEM_ROLE_CHANGE_REJECTED = AuditEventType("role.system_change_rejected", _S)
# T01-08, D8-4: a member administration action on one's own membership was refused.
SELF_ACTION_REFUSED = AuditEventType("member.self_action_refused", _S)
