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
