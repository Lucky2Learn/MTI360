"""Public enquiry routes, mounted on the public realm (``/api/v1/public``; ADR-0024).

* ``GET /enquiry-form`` — the institute's name, open courses and the consent
  text, for the hosted page at ``https://<slug>.<site domain>/enquiry``.
* ``POST /enquiries`` — submit an enquiry. ``202`` with the same body for
  every accepted outcome (stored, repeated within the window, or spam-trap).

Both resolve the institute from the request host only (``app.core.net``),
answer 404 for any host that is not an active, verified institute address, and
never read a tenant from the request. The submit body is read in chunks and
refused with 413 above :data:`MAX_BODY_BYTES`, before it is parsed.
"""

from fastapi import APIRouter, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.errors import PayloadTooLargeError
from app.core.net import client_ip, request_host
from app.core.schemas import Envelope
from app.modules.enquiries.domain import MAX_BODY_BYTES
from app.modules.enquiries.schemas import EnquiryFormOut, EnquiryReceived, EnquiryRequest
from app.modules.enquiries.service import PublicEnquiries

enquiry_routes = APIRouter(tags=["public-enquiries"])


def _service(request: Request) -> PublicEnquiries:
    service: PublicEnquiries = request.app.state.enquiries
    return service


def _hops(request: Request) -> int:
    hops: int = request.app.state.settings.trusted_proxy_hops
    return hops


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
        raise PayloadTooLargeError()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise PayloadTooLargeError()
    return bytes(body)


@enquiry_routes.get("/enquiry-form")
async def get_enquiry_form(request: Request) -> Envelope[EnquiryFormOut]:
    """The hosted enquiry page's content for the institute at the request host."""
    form = await _service(request).form(request_host(request, _hops(request)))
    return Envelope(data=form)


@enquiry_routes.post(
    "/enquiries",
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": EnquiryRequest.model_json_schema()}},
        }
    },
)
async def submit_enquiry(request: Request) -> Envelope[EnquiryReceived]:
    """Submit an enquiry to the institute at the request host."""
    service = _service(request)
    hops = _hops(request)
    host = request_host(request, hops)
    institute = await service.resolve(host)  # 404 before the body is read or validated
    raw = await _read_body(request)
    try:
        body = EnquiryRequest.model_validate_json(raw or b"{}")
    except ValidationError as error:
        # Located under "body", as FastAPI reports a parsed request body.
        errors = [
            {**problem, "loc": ("body", *problem["loc"])}
            for problem in error.errors(include_url=False, include_input=False)
        ]
        raise RequestValidationError(errors) from None
    await service.submit(
        institute,
        host=host,
        origin=request.headers.get("origin"),
        client_ip=client_ip(request, hops),
        request=body,
    )
    return Envelope(data=EnquiryReceived())
