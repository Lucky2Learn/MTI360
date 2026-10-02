"""Platform authentication, MFA and session routes (T01-06). Mounted by ``app.api.platform``.

* ``anonymous_routes`` (``/api/v1/platform/auth/*``) — sign-in, sign-out and
  password reset; the realm guard requires a same-origin request.
* ``mfa_routes`` (``/api/v1/platform/auth/mfa/*``) — ``Access.MFA_PENDING``:
  enrolment, verification and recovery codes for a session that passed the
  password step only.
* ``session_routes`` (``/api/v1/platform/session*``) — ``Access.SESSION``: a
  full (MFA-verified) session; step-up and recovery-code regeneration.

Unsafe session routes need the CSRF token (the guard). The session cookie is
``__Host-mti360_psid`` (HttpOnly, Secure, SameSite=Lax, Path=/; ADR-0010 §4).
Responses carrying a secret or recovery codes are ``Cache-Control: no-store``.
"""

from typing import Annotated, Final

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.core.context import current_context
from app.core.net import client_ip
from app.core.schemas import Envelope
from app.modules.identity.service import send_email_safely
from app.modules.platform_identity.schemas import (
    MfaCodeRequest,
    MfaEnrolmentConfirmedOut,
    MfaEnrolmentOut,
    PlatformLoginRequest,
    PlatformMfaOut,
    PlatformPasswordResetConfirmRequest,
    PlatformPasswordResetRequest,
    PlatformSessionOut,
    PlatformUserOut,
    RecoveryCodeRequest,
    RecoveryCodesOut,
)
from app.modules.platform_identity.service import (
    IssuedPlatformSession,
    PlatformIdentityService,
    PlatformRequestInfo,
    PlatformSessionView,
    ResolvedPlatformSession,
)

PLATFORM_SESSION_COOKIE: Final = "__Host-mti360_psid"


def platform_service(request: Request) -> PlatformIdentityService:
    service: PlatformIdentityService = request.app.state.platform_identity
    return service


def request_info(request: Request) -> PlatformRequestInfo:
    return PlatformRequestInfo(
        request_id=current_context().request_id,
        ip=client_ip(request, request.app.state.settings.trusted_proxy_hops),
        user_agent=request.headers.get("user-agent"),
    )


def resolved_session(request: Request) -> ResolvedPlatformSession:
    resolved: ResolvedPlatformSession = request.state.platform_session
    return resolved


Service = Annotated[PlatformIdentityService, Depends(platform_service)]
Info = Annotated[PlatformRequestInfo, Depends(request_info)]
Resolved = Annotated[ResolvedPlatformSession, Depends(resolved_session)]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def set_platform_cookie(response: Response, token: str, service: PlatformIdentityService) -> None:
    response.set_cookie(
        PLATFORM_SESSION_COOKIE,
        token,
        max_age=int(service.config.absolute_timeout.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_platform_cookie(response: Response) -> None:
    response.delete_cookie(
        PLATFORM_SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )


def session_out(view: PlatformSessionView) -> PlatformSessionOut:
    user = (
        PlatformUserOut(display_name=view.display_name, email=view.email)
        if view.display_name is not None and view.email is not None
        else None
    )
    return PlatformSessionOut(
        status=view.status,
        user=user,
        permissions=list(view.permissions),
        roles=list(view.roles),
        mfa=PlatformMfaOut(
            enrolled=view.mfa_enrolled,
            verified_at=view.mfa_verified_at,
            step_up_expires_at=view.step_up_expires_at,
            recovery_codes_remaining=view.recovery_codes_remaining,
        ),
        csrf_token=view.csrf_token,
    )


def _issued(
    response: Response, issued: IssuedPlatformSession, service: PlatformIdentityService
) -> PlatformSessionOut:
    set_platform_cookie(response, issued.token, service)
    return session_out(issued.view)


anonymous_routes = APIRouter(prefix="/auth", tags=["platform-authentication"])
mfa_routes = APIRouter(prefix="/auth/mfa", tags=["platform-authentication"])
session_routes = APIRouter(prefix="/session", tags=["platform-session"])


@anonymous_routes.post("/login")
async def login(
    body: PlatformLoginRequest, request: Request, response: Response, service: Service, info: Info
) -> Envelope[PlatformSessionOut]:
    """Check email and password; opens an MFA-pending session. Failures: one generic 401."""
    issued = await service.login(
        body.email, body.password, info, request.cookies.get(PLATFORM_SESSION_COOKIE)
    )
    return Envelope(data=_issued(response, issued, service))


@anonymous_routes.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: Service, info: Info) -> None:
    """End the current platform session, if any, and clear the cookie (idempotent)."""
    await service.logout(request.cookies.get(PLATFORM_SESSION_COOKIE), info)
    clear_platform_cookie(response)


@anonymous_routes.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: PlatformPasswordResetRequest, background: BackgroundTasks, service: Service, info: Info
) -> None:
    """Always 202. The email (if any) is sent after the response."""
    message = await service.request_password_reset(body.email, info)
    if message is not None:
        background.add_task(send_email_safely, service.email_sender, message, info.request_id)


@anonymous_routes.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PlatformPasswordResetConfirmRequest, service: Service, info: Info
) -> None:
    """Set a new password with a reset token; signs out everywhere; MFA stays required."""
    await service.confirm_password_reset(body.token, body.new_password, info)


@mfa_routes.post("/enrolment")
async def start_enrolment(
    response: Response, service: Service, info: Info, resolved: Resolved
) -> Envelope[MfaEnrolmentOut]:
    """A TOTP secret and ``otpauth://`` URI for manual setup (shown once)."""
    _no_store(response)
    enrolment = await service.start_enrolment(resolved, info)
    return Envelope(
        data=MfaEnrolmentOut(secret=enrolment.secret, otpauth_uri=enrolment.otpauth_uri)
    )


@mfa_routes.post("/enrolment/confirm")
async def confirm_enrolment(
    body: MfaCodeRequest, response: Response, service: Service, info: Info, resolved: Resolved
) -> Envelope[MfaEnrolmentConfirmedOut]:
    """Confirm with a first code: recovery codes (once) and a rotated, full session."""
    _no_store(response)
    issued, codes = await service.confirm_enrolment(resolved, body.code, info)
    return Envelope(
        data=MfaEnrolmentConfirmedOut(
            recovery_codes=codes, session=_issued(response, issued, service)
        )
    )


@mfa_routes.post("/verify")
async def verify_mfa(
    body: MfaCodeRequest, response: Response, service: Service, info: Info, resolved: Resolved
) -> Envelope[PlatformSessionOut]:
    """Complete sign-in with an authenticator code; the session is rotated."""
    issued = await service.verify_mfa(resolved, body.code, info)
    return Envelope(data=_issued(response, issued, service))


@mfa_routes.post("/recovery")
async def use_recovery_code(
    body: RecoveryCodeRequest,
    response: Response,
    service: Service,
    info: Info,
    resolved: Resolved,
) -> Envelope[PlatformSessionOut]:
    """Complete sign-in with a single-use recovery code; the session is rotated."""
    issued = await service.use_recovery_code(resolved, body.recovery_code, info)
    return Envelope(data=_issued(response, issued, service))


@session_routes.get("")
async def read_session(
    service: Service, info: Info, resolved: Resolved
) -> Envelope[PlatformSessionOut]:
    """The signed-in platform user, roles, permissions and MFA state."""
    return Envelope(data=session_out(await service.view(resolved, info)))


@session_routes.post("/step-up")
async def step_up(
    body: MfaCodeRequest, service: Service, info: Info, resolved: Resolved
) -> Envelope[PlatformSessionOut]:
    """Re-verify an authenticator code: step-up for 10 minutes (D6-5)."""
    return Envelope(data=session_out(await service.step_up(resolved, body.code, info)))


@session_routes.post("/mfa/recovery-codes")
async def regenerate_recovery_codes(
    response: Response, service: Service, info: Info, resolved: Resolved
) -> Envelope[RecoveryCodesOut]:
    """New recovery codes (shown once; the old ones stop working). Needs step-up."""
    _no_store(response)
    codes = await service.regenerate_recovery_codes(resolved, info)
    return Envelope(data=RecoveryCodesOut(recovery_codes=codes))
