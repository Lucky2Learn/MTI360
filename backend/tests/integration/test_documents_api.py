"""Admission documents over HTTP (Phase 02-2; ADR-0021 §5, §8).

Storage is the in-memory fake (``admissions_support.use_memory_storage``).
Covered: the validation pipeline end to end (type, content agreement, PDF
active content, empty and oversized files, the streaming body cap with and
without ``Content-Length``), generated tenant-prefixed keys, download
authorization and headers, replacement instead of deletion, verification
permissions and rules, the campus-scoped queue, storage failures (nothing
written, 503) and cleanup when the database work fails, the upload rate
limit, and audit metadata without file names or contents.
"""

import uuid
import zlib
from collections.abc import AsyncIterator
from typing import Any

import pytest
from admissions_support import (
    APPLICATIONS,
    DOCUMENTS,
    PDF,
    PNG,
    active_course,
    admit,
    approved,
    decide,
    errors,
    new_application,
    ready,
    reload,
    review,
    submit,
    upload,
    use_memory_storage,
)
from conftest import DatabaseUnderTest
from courses_leads_support import admissions_team
from identity_support import Harness, auth_harness
from tenant_admin_support import data, send, sign_in

from app.core.ratelimit import Limit
from app.integrations.storage import InMemoryObjectStorage
from app.modules.documents import service as document_service
from app.modules.documents.validation import MAX_REQUEST_BYTES, OBJECT_STREAMS_MAX

pytestmark = [pytest.mark.anyio, pytest.mark.integration]

# More compressed object streams than the validation bound allows (a small file).
_OBJECT_STREAM = (
    b"5 0 obj\n<< /Type /ObjStm >>\nstream\n"
    + zlib.compress(b"6 0 << /Type /Page >>")
    + b"\nendstream\nendobj\n"
)
OBJECT_STREAM_FLOOD = b"%PDF-1.7\n" + _OBJECT_STREAM * (OBJECT_STREAMS_MAX + 1) + b"%%EOF\n"


@pytest.fixture
async def h(migrated_database: DatabaseUnderTest, redis_url: str) -> AsyncIterator[Harness]:
    async with auth_harness(migrated_database, redis_url) as harness:
        await admissions_team(harness)
        use_memory_storage(harness)
        yield harness


def _storage(h: Harness) -> InMemoryObjectStorage:
    storage: InMemoryObjectStorage = h.app.state.storage
    return storage


async def _draft(h: Harness, csrf: str, campus: uuid.UUID | None = None) -> dict[str, Any]:
    course = await active_course(h, csrf)
    return await new_application(h, csrf, course=course, campus=campus or h.world.campus_a1)  # type: ignore[no-any-return]


async def _rows(h: Harness, table: str) -> int:
    rows = await h.owner(f"SELECT count(*) FROM {table}")  # noqa: S608 - constant names
    return int(rows[0][0])


async def test_valid_uploads_are_stored_privately_and_downloaded_as_attachments(
    h: Harness,
) -> None:
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    response = await upload(h, csrf, application["id"], file_name="..\\Arjun Nair passport.PDF")
    document = data(response, 201)
    assert (document["status"], document["document_type"], document["current"]) == (
        "UPLOADED",
        "PASSPORT",
        True,
    )
    assert document["file_name"] == "Arjun Nair passport.pdf"
    assert set(document) >= {"size_bytes", "content_type", "version"}
    assert not {"object_key", "sha256", "url", "key"} & set(document)
    (key,) = _storage(h).objects
    assert key == f"tenants/{h.world.tenant_a}/files/{key.rsplit('/', 1)[1]}"
    stored = await h.owner(
        "SELECT object_key, size_bytes FROM stored_files WHERE object_key = :k", k=key
    )
    assert stored[0][1] == len(PDF)
    (event,) = [e for e in await h.audit(response) if e.event_type == "document.uploaded"]
    assert event.metadata == {
        "document_type": "PASSPORT",
        "content_type": "application/pdf",
        "size_bytes": len(PDF),
        "replacement": False,
    }
    assert "Arjun" not in repr(event.metadata)

    downloaded = await h.client.get(f"{DOCUMENTS}/{document['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    headers = downloaded.headers
    assert headers["content-type"] == "application/pdf"
    assert headers["content-disposition"].startswith(
        'attachment; filename="Arjun Nair passport.pdf"'
    )
    assert "filename*=UTF-8''Arjun%20Nair%20passport.pdf" in headers["content-disposition"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert headers["cache-control"] == "no-store"
    png = data(
        await upload(
            h,
            csrf,
            application["id"],
            document_type="PHOTO",
            content=PNG,
            file_name="photo.png",
            content_type="image/png",
        ),
        201,
    )
    assert png["content_type"] == "image/png"


@pytest.mark.parametrize(
    ("file_name", "content", "content_type", "code"),
    [
        ("cv.docx", b"PK\x03\x04", "application/msword", "file_type_not_allowed"),
        ("page.html", b"<html><script>", "text/html", "file_type_not_allowed"),
        ("passport.pdf", PNG, "application/pdf", "file_content_mismatch"),
        ("photo.png", PDF, "image/png", "file_content_mismatch"),
        ("payload.pdf", b"MZ\x90\x00", "application/pdf", "file_content_mismatch"),
        (
            "form.pdf",
            PDF.replace(b"/Type /Catalog", b"/OpenAction << /S /JavaScript /JS (x) >>"),
            "application/pdf",
            "pdf_active_content",
        ),
        ("empty.pdf", b"", "application/pdf", "file_empty"),
        ("flood.pdf", OBJECT_STREAM_FLOOD, "application/pdf", "pdf_unreadable"),
    ],
    ids=["docx", "html", "pdf-is-png", "png-is-pdf", "exe", "javascript", "empty", "streams"],
)
async def test_invalid_files_are_refused_before_anything_is_stored(
    h: Harness, file_name: str, content: bytes, content_type: str, code: str
) -> None:
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    files_before = await _rows(h, "stored_files")
    response = await upload(
        h, csrf, application["id"], file_name=file_name, content=content, content_type=content_type
    )
    assert errors(response) == {("file", code)}
    assert _storage(h).objects == {}
    assert await _rows(h, "stored_files") == files_before


async def test_the_body_is_capped_while_streaming(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    url = f"{APPLICATIONS}/{application['id']}/documents"
    too_big = b"%PDF-" + b"0" * MAX_REQUEST_BYTES
    declared = await upload(h, csrf, application["id"], content=too_big)
    assert declared.status_code == 413
    assert declared.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    async def chunks() -> AsyncIterator[bytes]:  # no Content-Length: chunked transfer
        yield b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\n\r\n'
        for _ in range(12):
            yield b"0" * (1024 * 1024)

    streamed = await h.client.post(
        url,
        content=chunks(),
        headers={"X-CSRF-Token": csrf, "Content-Type": "multipart/form-data; boundary=x"},
    )
    assert streamed.status_code == 413
    lying = await h.client.post(
        url,
        content=b"x",
        headers={
            "X-CSRF-Token": csrf,
            "Content-Type": "multipart/form-data; boundary=x",
            "Content-Length": "999999999999",
        },
    )
    assert lying.status_code in {400, 413}
    assert _storage(h).objects == {}


async def test_the_form_is_checked(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    url = f"{APPLICATIONS}/{application['id']}/documents"
    as_json = await send(h, "POST", url, csrf, {"document_type": "PASSPORT"})
    assert errors(as_json) == {("file", "multipart_required")}
    no_type = await h.client.post(
        url,
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers={"X-CSRF-Token": csrf},
    )
    assert errors(no_type) == {("document_type", "invalid")}
    wrong_type = await upload(h, csrf, application["id"], document_type="AADHAAR_SCAN")
    assert errors(wrong_type) == {("document_type", "invalid")}
    two_files = await h.client.post(
        url,
        data={"document_type": "PASSPORT"},
        files=[
            ("file", ("a.pdf", PDF, "application/pdf")),
            ("file", ("b.pdf", PDF, "application/pdf")),
        ],
        headers={"X-CSRF-Token": csrf},
    )
    assert errors(two_files) == {("file", "invalid_form")}
    no_file = await h.client.post(
        url,
        files={"document_type": (None, "PASSPORT")},
        headers={"X-CSRF-Token": csrf},
    )
    assert errors(no_file) == {("file", "file_empty")}
    no_csrf = await h.client.post(
        url, data={"document_type": "PASSPORT"}, files={"file": ("a.pdf", PDF, "application/pdf")}
    )
    assert no_csrf.status_code == 403
    assert _storage(h).objects == {}


async def test_replacement_keeps_history_and_verified_documents_stay(h: Harness) -> None:
    csrf = await sign_in(h, "maya")
    application = await ready(h, csrf, await _draft(h, csrf))
    first = data(await upload(h, csrf, application["id"]), 201)
    medical = data(
        await upload(h, csrf, application["id"], document_type="MEDICAL_CERTIFICATE"), 201
    )
    application = data(await submit(h, csrf, await reload(h, application)))
    items = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"]
    by_id = {item["id"]: item for item in items}
    assert {item["status"] for item in items} == {"UNDER_REVIEW"}
    rejected = data(await decide(h, csrf, by_id[first["id"]], reason="Passport has expired"))
    verified = data(await decide(h, csrf, by_id[medical["id"]]))
    # The type of a replacement is the replaced document's; verified documents stay.
    assert errors(
        await upload(h, csrf, application["id"], document_type="CDC", replaces=rejected["id"])
    ) == {("document_type", "type_mismatch")}
    assert errors(
        await upload(
            h, csrf, application["id"], document_type="MEDICAL_CERTIFICATE", replaces=verified["id"]
        )
    ) == {("replaces_document_id", "not_replaceable")}
    replacement = data(await upload(h, csrf, application["id"], replaces=rejected["id"]), 201)
    assert (replacement["status"], replacement["replaces_document_id"]) == (
        "UNDER_REVIEW",  # the application is submitted: straight into review
        rejected["id"],
    )
    assert errors(await upload(h, csrf, application["id"], replaces=rejected["id"])) == {
        ("replaces_document_id", "not_replaceable")
    }
    history = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"]
    old = next(item for item in history if item["id"] == rejected["id"])
    assert (old["current"], old["status"], old["rejection_reason"]) == (
        False,
        "REJECTED",
        "Passport has expired",
    )
    assert len(history) == 3
    # Replaced documents are not decided any more; stale versions conflict.
    assert errors(await decide(h, csrf, old)) == {("status", "invalid_transition")}
    stale = {**replacement, "version": replacement["version"] + 5}
    assert (await decide(h, csrf, stale)).status_code == 409
    assert errors(await decide(h, csrf, verified, reason="Changed my mind")) == {
        ("status", "invalid_transition")
    }
    reject_without_reason = await send(
        h,
        "POST",
        f"{DOCUMENTS}/{replacement['id']}/reject",
        csrf,
        {"reason": "", "version": replacement["version"]},
    )
    assert reject_without_reason.status_code == 422


async def test_counsellors_upload_but_do_not_verify(h: Harness) -> None:
    manager = await sign_in(h, "maya")
    application = await ready(h, manager, await _draft(h, manager))
    counsellor = await sign_in(h, "ravi")
    document = data(await upload(h, counsellor, application["id"]), 201)
    application = data(await submit(h, counsellor, await reload(h, application)))
    current = data(await h.client.get(f"{APPLICATIONS}/{application['id']}/documents"))["items"][0]
    assert (await decide(h, counsellor, current)).status_code == 403
    assert (await decide(h, counsellor, current, reason="x")).status_code == 403
    assert document["uploaded_by"] == "Ravi"


async def test_the_queue_lists_documents_under_review_in_my_campuses(h: Harness) -> None:
    w = h.world
    manager = await sign_in(h, "maya")
    a1 = await ready(h, manager, await _draft(h, manager, w.campus_a1))
    a2 = await ready(h, manager, await _draft(h, manager, w.campus_a2))
    for application in (a1, a2):
        data(await upload(h, manager, application["id"]), 201)
        data(await submit(h, manager, await reload(h, application)))
    draft = await _draft(h, manager, w.campus_a1)
    data(await upload(h, manager, draft["id"]), 201)  # still UPLOADED: not in the queue
    queue = data(await h.client.get(DOCUMENTS))
    mine = {item["application_id"] for item in queue}
    assert {a1["id"], a2["id"]} <= mine
    assert draft["id"] not in mine
    assert all(item["status"] == "UNDER_REVIEW" for item in queue)
    uploaded = data(await h.client.get(DOCUMENTS, params={"status": "UPLOADED"}))
    assert draft["id"] in {item["application_id"] for item in uploaded}
    await sign_in(h, "sita")  # campus A2 only
    seen = {item["application_id"] for item in data(await h.client.get(DOCUMENTS))}
    assert a2["id"] in seen
    assert a1["id"] not in seen
    a1_document = next(item for item in queue if item["application_id"] == a1["id"])
    assert (await h.client.get(f"{DOCUMENTS}/{a1_document['id']}/download")).status_code == 404


async def test_storage_failures_write_nothing_and_cleanup_follows_database_failures(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    storage = _storage(h)
    files_before = await _rows(h, "stored_files")
    storage.fail = True
    unavailable = await upload(h, csrf, application["id"])
    assert unavailable.status_code == 503
    assert await _rows(h, "stored_files") == files_before
    storage.fail = False

    async def broken(*_: Any, **__: Any) -> None:
        raise RuntimeError("database write failed")

    monkeypatch.setattr(document_service, "write_audit_event", broken)
    failed = await upload(h, csrf, application["id"])
    assert failed.status_code == 500
    assert storage.objects == {}  # the stored bytes were removed again
    assert await _rows(h, "stored_files") == files_before
    monkeypatch.undo()

    document = data(await upload(h, csrf, application["id"]), 201)
    storage.objects.clear()  # metadata without content
    missing = await h.client.get(f"{DOCUMENTS}/{document['id']}/download")
    assert missing.status_code == 503


async def test_uploads_are_rate_limited_per_member(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(document_service, "UPLOAD_LIMIT", Limit(attempts=2, window_seconds=60))
    csrf = await sign_in(h, "maya")
    application = await _draft(h, csrf)
    for _ in range(2):
        assert (await upload(h, csrf, application["id"])).status_code == 201
    limited = await upload(h, csrf, application["id"])
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


async def test_final_applications_take_no_documents(h: Harness) -> None:
    w = h.world
    csrf = await sign_in(h, "maya")
    course = await active_course(h, csrf)
    application = data(
        await admit(h, csrf, await approved(h, csrf, course=course, campus=w.campus_a1))
    )
    assert errors(await upload(h, csrf, application["id"])) == {("application", "documents_closed")}
    rejected = await ready(
        h, csrf, await new_application(h, csrf, course=course, campus=w.campus_a1)
    )
    rejected = data(await submit(h, csrf, rejected))
    rejected = data(await review(h, csrf, rejected, "REJECTED", "Incomplete"))
    assert errors(await upload(h, csrf, rejected["id"])) == {("application", "documents_closed")}
