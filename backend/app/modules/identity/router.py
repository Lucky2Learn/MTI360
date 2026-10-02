"""Authentication and session routes (T01-04). Mounted on tenant-realm routers by ``app.api``.

* ``anonymous_routes`` (``/api/v1/auth/*``) — sign-in, sign-out, password
  reset, invitation preview and acceptance. The realm guard requires a
  same-origin request for these unsafe anonymous routes (D14).
* ``session_routes`` (``/api/v1/session*``) — ``Access.SESSION``: a valid
  session, institute optional (D12, D04 §2.2). The guard checks the CSRF
  token on unsafe methods.

Handlers are thin: the service owns every rule. The session cookie is
``__Host-mti360_tsid`` (HttpOnly, Secure, SameSite=Lax, Path=/, no Domain;
ADR-0010 §4). Request bodies are never logged.
"""

from typing import Annotated, Final

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.core.context import current_context
from app.core.db.session import DbSession
from app.core.net import client_ip
from app.core.schemas import Envelope
from app.modules.identity.schemas import (
    CampusOut,
    CampusSelectionRequest,
    InstituteOut,
    InvitationAcceptRequest,
    InvitationPreviewOut,
    InvitationTokenRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SessionOut,
    TenantSelectionRequest,
    UserOut,
)
from app.modules.identity.service import (
    IdentityService,
    IssuedSession,
    RequestInfo,
    ResolvedSession,
    SessionView,
    send_email_safely,
)

SESSION_COOKIE: Final = "__Host-mti360_tsid"


def identity_service(request: Request) -> IdentityService:
    service: IdentityService = request.app.state.identity
    return service


def request_info(request: Request) -> RequestInfo:
    return RequestInfo(
        request_id=current_context().request_id,
        ip=client_ip(request, request.app.state.settings.trusted_proxy_hops),
        user_agent=request.headers.get("user-agent"),
    )


def resolved_session(request: Request) -> ResolvedSession:
    """The session the realm guard re-validated for this request."""
    resolved: ResolvedSession = request.state.auth_session
    return resolved


Service = Annotated[IdentityService, Depends(identity_service)]
Info = Annotated[RequestInfo, Depends(request_info)]
Resolved = Annotated[ResolvedSession, Depends(resolved_session)]


def set_session_cookie(response: Response, token: str, service: IdentityService) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(service.config.absolute_timeout.total_seconds()),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")


def session_out(view: SessionView) -> SessionOut:
    return SessionOut(
        status=view.status,
        user=UserOut(display_name=view.display_name, email=view.email),
        active_institute=(
            InstituteOut.model_validate(view.active_institute) if view.active_institute else None
        ),
        institutes=[InstituteOut.model_validate(item) for item in view.institutes],
        active_campus=CampusOut.model_validate(view.active_campus) if view.active_campus else None,
        campus_options=[CampusOut.model_validate(item) for item in view.campus_options],
        all_campuses_allowed=view.all_campuses_allowed,
        campus_selection_required=view.campus_selection_required,
        csrf_token=view.csrf_token,
    )


def _issued(
    response: Response, issued: IssuedSession, service: IdentityService
) -> Envelope[SessionOut]:
    set_session_cookie(response, issued.token, service)
    return Envelope(data=session_out(issued.view))


anonymous_routes = APIRouter(prefix="/auth", tags=["authentication"])
session_routes = APIRouter(prefix="/session", tags=["session"])


@anonymous_routes.post("/login")
async def login(
    body: LoginRequest, request: Request, response: Response, service: Service, info: Info
) -> Envelope[SessionOut]:
    """Sign in with email and password. Failures are one generic 401."""
    issued = await service.login(
        body.email, body.password, info, request.cookies.get(SESSION_COOKIE)
    )
    return _issued(response, issued, service)


@anonymous_routes.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: Service, info: Info) -> None:
    """End the current session, if any, and clear the cookie (idempotent)."""
    await service.logout(request.cookies.get(SESSION_COOKIE), info)
    clear_session_cookie(response)


@anonymous_routes.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    body: PasswordResetRequest, background: BackgroundTasks, service: Service, info: Info
) -> None:
    """Always 202. The email (if any) is sent after the response."""
    message = await service.request_password_reset(body.email, info)
    if message is not None:
        background.add_task(send_email_safely, service.email_sender, message, info.request_id)


@anonymous_routes.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    body: PasswordResetConfirmRequest, service: Service, info: Info
) -> None:
    """Set a new password with a reset token; signs the user out everywhere."""
    await service.confirm_password_reset(body.token, body.new_password, info)


@anonymous_routes.post("/invitations/preview")
async def preview_invitation(
    body: InvitationTokenRequest, service: Service, info: Info
) -> Envelope[InvitationPreviewOut]:
    """D19: institute name, masked email and account kind; generic 404 otherwise."""
    preview = await service.preview_invitation(body.token, info)
    return Envelope(data=InvitationPreviewOut.model_validate(preview))


@anonymous_routes.post("/invitations/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_invitation(body: InvitationAcceptRequest, service: Service, info: Info) -> None:
    """D19 §3.4: activates the membership; never signs in, never overwrites a password."""
    await service.accept_invitation(body.token, body.display_name, body.password, info)


@session_routes.get("")
async def read_session(db: DbSession, service: Service, resolved: Resolved) -> Envelope[SessionOut]:
    """The signed-in user, institute choices, active institute and campus state."""
    return Envelope(data=session_out(await service.view(db, resolved)))


@session_routes.put("/tenant")
async def select_tenant(
    body: TenantSelectionRequest,
    response: Response,
    service: Service,
    info: Info,
    resolved: Resolved,
) -> Envelope[SessionOut]:
    """Choose an institute; the session is rotated. Not eligible → 404."""
    issued = await service.switch_tenant(resolved, body.tenant_id, info)
    return _issued(response, issued, service)


@session_routes.put("/campus")
async def select_campus(
    body: CampusSelectionRequest, db: DbSession, service: Service, resolved: Resolved
) -> Envelope[SessionOut]:
    """Choose a campus (``null`` = all campuses where allowed). Outside the options → 404."""
    return Envelope(data=session_out(await service.switch_campus(db, resolved, body.campus_id)))
