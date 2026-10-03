"""Platform authentication and MFA security events (T01-06; ADR-0013 category ``security``).

Recorded with ``record_security_event`` and committed after the request, so
they survive rejected requests. Events before the platform user is known run
in the anonymous platform context with the user as *target*. Metadata never
contains passwords, TOTP secrets or codes, recovery codes, reset or session
tokens, or email addresses.
"""

from app.core.audit import AuditCategory, AuditEventType

_S = AuditCategory.SECURITY

LOGIN_SUCCESS = AuditEventType("platform.auth.login.success", _S)
LOGIN_FAILED = AuditEventType("platform.auth.login.failed", _S)
ACCOUNT_LOCKED = AuditEventType("platform.auth.account.locked", _S)
MFA_CHALLENGED = AuditEventType("platform.auth.mfa.challenged", _S)
LOGOUT = AuditEventType("platform.auth.logout", _S)
SESSION_ROTATED = AuditEventType("platform.auth.session.rotated", _S)
SESSION_REVOKED = AuditEventType("platform.auth.session.revoked", _S)
MFA_ENROLMENT_STARTED = AuditEventType("platform.mfa.enrolment.started", _S)
MFA_ENROLLED = AuditEventType("platform.mfa.enrolment.confirmed", _S)
MFA_VERIFIED = AuditEventType("platform.mfa.verified", _S)
MFA_FAILED = AuditEventType("platform.mfa.failed", _S)
RECOVERY_CODE_USED = AuditEventType("platform.mfa.recovery_code.used", _S)
RECOVERY_CODES_REGENERATED = AuditEventType("platform.mfa.recovery_codes.regenerated", _S)
MFA_RESET = AuditEventType("platform.mfa.reset", _S)
STEP_UP_SUCCEEDED = AuditEventType("platform.auth.step_up.success", _S)
STEP_UP_FAILED = AuditEventType("platform.auth.step_up.failed", _S)
PASSWORD_RESET_REQUESTED = AuditEventType("platform.auth.password_reset.requested", _S)
PASSWORD_RESET_COMPLETED = AuditEventType("platform.auth.password_reset.completed", _S)
RATE_LIMITED = AuditEventType("platform.auth.rate_limited", _S)

# --- Platform user administration (T01-07; D7-2 … D7-5) -------------------------------------
# Administrative changes are written in the transaction of the change (ADR-0013 §4, D22);
# invitation acceptance happens without a session and is a security event.
_A = AuditCategory.ADMIN

USER_CREATED = AuditEventType("platform.user.created", _A)
USER_UPDATED = AuditEventType("platform.user.updated", _A)
USER_SUSPENDED = AuditEventType("platform.user.suspended", _A)
USER_REACTIVATED = AuditEventType("platform.user.reactivated", _A)
INVITATION_SENT = AuditEventType("platform.user.invitation.sent", _A)
INVITATION_REVOKED = AuditEventType("platform.user.invitation.revoked", _A)
INVITATION_ACCEPTED = AuditEventType("platform.auth.invitation.accepted", _S)
SELF_ACTION_REFUSED = AuditEventType("platform.user.self_action_refused", _S)
