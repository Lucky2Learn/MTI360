"""Request middleware: correlation ID, API response headers, request log (T01-01).

Pure ASGI (not ``BaseHTTPMiddleware``) so that the request ID context variable
is shared with the endpoint and with exception handlers.

* A new UUIDv7 request ID is generated for every request and returned in
  ``X-Request-ID``. An inbound ``X-Request-ID`` is ignored: it is not trusted
  until a trusted proxy is configured.
* API responses (``/api/*``) carry ``Cache-Control: no-store`` and
  ``X-Content-Type-Options: nosniff``.
* One ``request.completed`` log line per request with method, path (never the
  query string), status and duration. ``/health`` probes are not logged.
"""

import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import bind_request_id, reset_request_id
from app.core.errors import REQUEST_ID_HEADER
from app.core.ids import new_id

logger = logging.getLogger("app.request")

_UNLOGGED_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = new_id()
        scope.setdefault("state", {})["request_id"] = request_id
        path: str = scope["path"]
        is_api = path.startswith("/api/")
        status = 500
        started = time.perf_counter()

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = str(request_id)
                if is_api:
                    headers["Cache-Control"] = "no-store"
                    headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        token = bind_request_id(request_id)
        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            if path not in _UNLOGGED_PATHS:
                logger.info(
                    "request.completed",
                    extra={
                        "method": scope["method"],
                        "path": path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )
            reset_request_id(token)
