"""Authentication security events (T01-04; ADR-0013 category ``security``).

Recorded with ``record_security_event`` and committed after the request
transaction, so they survive rejected requests. Login, reset and invitation
events are recorded in the request's anonymous context (decision D13): the
user, when known, is the event *target*. Metadata never contains passwords,
hashes, tokens, cookies or email addresses.
"""

from app.core.audit import AuditCategory, AuditEventType

_S = AuditCategory.SECURITY

LOGIN_SUCCESS = AuditEventType("auth.login.success", _S)
LOGIN_FAILED = AuditEventType("auth.login.failed", _S)
ACCOUNT_LOCKED = AuditEventType("auth.account.locked", _S)
LOGOUT = AuditEventType("auth.logout", _S)
SESSION_CREATED = AuditEventType("auth.session.created", _S)
SESSION_ROTATED = AuditEventType("auth.session.rotated", _S)
SESSION_REVOKED = AuditEventType("auth.session.revoked", _S)
TENANT_SWITCHED = AuditEventType("auth.tenant.switched", _S)
CAMPUS_SWITCHED = AuditEventType("auth.campus.switched", _S)
PASSWORD_RESET_REQUESTED = AuditEventType("auth.password_reset.requested", _S)
PASSWORD_RESET_COMPLETED = AuditEventType("auth.password_reset.completed", _S)
INVITATION_ACCEPTED = AuditEventType("auth.invitation.accepted", _S)
RATE_LIMITED = AuditEventType("auth.rate_limited", _S)
CSRF_REJECTED = AuditEventType("auth.csrf.rejected", _S)
# Optional tenant MFA (T01-06).
MFA_CHALLENGED = AuditEventType("auth.mfa.challenged", _S)
MFA_VERIFIED = AuditEventType("auth.mfa.verified", _S)
MFA_FAILED = AuditEventType("auth.mfa.failed", _S)
MFA_RECOVERY_CODE_USED = AuditEventType("auth.mfa.recovery_code.used", _S)
MFA_ENROLMENT_STARTED = AuditEventType("auth.mfa.enrolment.started", _S)
MFA_ENROLLED = AuditEventType("auth.mfa.enrolment.confirmed", _S)
MFA_REMOVED = AuditEventType("auth.mfa.removed", _S)
