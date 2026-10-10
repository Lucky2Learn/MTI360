"""The upload check of the document service (Phase 02-2; ADR-0021 §8).

``check_upload`` runs the synchronous validation pipeline in a worker thread,
so a slow file never blocks the event loop, and maps a refusal to the 422
contract (``file`` + the problem code) without echoing the file.
"""

import threading
import zlib

import pytest

from app.core.errors import ErrorDetail, ValidationFailedError
from app.modules.documents import service
from app.modules.documents.validation import (
    MESSAGES,
    OBJECT_STREAMS_MAX,
    UploadProblem,
    validate_upload,
)

pytestmark = pytest.mark.anyio

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def _flood() -> bytes:
    compressed = zlib.compress(b"6 0 << /Type /Page >>")
    stream = b"5 0 obj\n<< /Type /ObjStm >>\nstream\n" + compressed + b"\nendstream\nendobj\n"
    return b"%PDF-1.7\n" + stream * (OBJECT_STREAMS_MAX + 1) + b"%%EOF\n"


async def test_validation_runs_in_a_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    loop_thread = threading.get_ident()
    seen: list[int] = []

    def recording(file_name: str | None, declared_type: str | None, data: bytes) -> object:
        seen.append(threading.get_ident())
        return validate_upload(file_name, declared_type, data)

    monkeypatch.setattr(service, "validate_upload", recording)
    checked = await service.check_upload(service.Upload("passport.pdf", "application/pdf", PDF))
    assert checked.content_type == "application/pdf"
    assert checked.size == len(PDF)
    assert len(seen) == 1
    assert seen[0] != loop_thread


async def test_a_pdf_over_the_bounds_is_refused_as_unreadable() -> None:
    with pytest.raises(ValidationFailedError) as raised:
        await service.check_upload(service.Upload("flood.pdf", "application/pdf", _flood()))
    assert raised.value.details == (
        ErrorDetail(
            field="file",
            code=UploadProblem.PDF_UNREADABLE.value,
            message=MESSAGES[UploadProblem.PDF_UNREADABLE],
        ),
    )


async def test_other_refusals_keep_their_codes() -> None:
    active = PDF.replace(b"/Type /Catalog", b"/OpenAction << /S /JavaScript /JS (x) >>")
    with pytest.raises(ValidationFailedError) as raised:
        await service.check_upload(service.Upload("form.pdf", "application/pdf", active))
    assert [(d.field, d.code) for d in raised.value.details] == [("file", "pdf_active_content")]
