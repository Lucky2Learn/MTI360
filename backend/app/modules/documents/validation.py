"""The upload validation pipeline (Phase 02-2; ADR-0021 §8, ARCHITECTURE §49, PRD §66).

Uploaded files are untrusted. Before anything is stored:

1. size — 1 byte to :data:`MAX_FILE_BYTES` (the request body itself is capped
   while it is read, see ``router.read_upload``);
2. file name — sanitised for display only (never a storage key or path);
3. type — the extension, the declared MIME type and the leading bytes
   (magic number) must all agree, and be PDF, JPEG or PNG;
4. PDF content — refused when encrypted or carrying active content, also
   inside compressed object streams and with ``#xx``-escaped names.

Malware scanning is deferred (ADR-0021 §8, an explicit risk acceptance);
these checks are its compensating controls. Nothing here echoes file content.

The work is bounded for hostile input: one linear scan of the file, at most
:data:`OBJECT_STREAMS_MAX` object streams, each inflated to at most
:data:`OBJECT_STREAM_MAX_BYTES` and all of them together to at most
:data:`INFLATED_TOTAL_MAX_BYTES`. A PDF over any bound is refused as
unreadable. The pipeline is synchronous CPU work: async callers run it in a
worker thread (``service.check_upload``).
"""

import hashlib
import re
import unicodedata
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

MAX_FILE_BYTES: Final = 10 * 1024 * 1024
"""10 MiB per file (L5, INC-22)."""
MAX_REQUEST_BYTES: Final = MAX_FILE_BYTES + 64 * 1024
"""The whole multipart body: the file plus room for the form fields and boundaries."""
FILE_NAME_MAX_LENGTH: Final = 120
OBJECT_STREAM_MAX_BYTES: Final = 16 * 1024 * 1024
"""Decompressed size limit of one PDF object stream (refused beyond: a bomb or unreadable)."""
INFLATED_TOTAL_MAX_BYTES: Final = 32 * 1024 * 1024
"""Decompressed size limit of all object streams of one PDF together. Object streams hold
only object dictionaries (no page content or images), typically a few KiB to a few MiB per
file; without a total, many small bombs under the per-stream limit cost minutes of CPU."""
OBJECT_STREAMS_MAX: Final = 256
"""Object streams per PDF. Writers pack up to a few hundred objects into each, so even a
large 10 MiB document needs far fewer; the bound stops floods of tiny streams."""

PDF: Final = "application/pdf"
JPEG: Final = "image/jpeg"
PNG: Final = "image/png"
EXTENSIONS: Final = MappingProxyType({PDF: ("pdf",), JPEG: ("jpg", "jpeg"), PNG: ("png",)})
ALLOWED_TYPES: Final = frozenset(EXTENSIONS)
_MAGIC: Final = ((PDF, b"%PDF-"), (PNG, b"\x89PNG\r\n\x1a\n"), (JPEG, b"\xff\xd8\xff"))

ACTIVE_PDF_NAMES: Final = frozenset(
    {
        b"JavaScript",
        b"JS",
        b"Launch",
        b"EmbeddedFile",
        b"EmbeddedFiles",
        b"RichMedia",
        b"XFA",
        b"SubmitForm",
        b"ImportData",
        b"GoToE",
    }
)
"""PDF names that run code, open other files or carry attachments."""
_NAME = re.compile(rb"/([^\s()<>\[\]{}/%]*)")
_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
_STREAM = re.compile(rb"(?<!end)stream\r?\n")
_UNSAFE_NAME = re.compile(r"[^\w .()\-]")


class UploadProblem(StrEnum):
    EMPTY = "file_empty"
    TOO_LARGE = "file_too_large"
    NAME = "file_name_invalid"
    TYPE = "file_type_not_allowed"
    MISMATCH = "file_content_mismatch"
    PDF_ACTIVE = "pdf_active_content"
    PDF_ENCRYPTED = "pdf_encrypted"
    PDF_UNREADABLE = "pdf_unreadable"


MESSAGES: Final = MappingProxyType(
    {
        UploadProblem.EMPTY: "Choose a file to upload.",
        UploadProblem.TOO_LARGE: "Files can be at most 10 MB.",
        UploadProblem.NAME: "Give the file a name with a .pdf, .jpg, .jpeg or .png extension.",
        UploadProblem.TYPE: "Upload a PDF, JPEG or PNG file.",
        UploadProblem.MISMATCH: "The file's content does not match its type.",
        UploadProblem.PDF_ACTIVE: "PDFs with scripts, attachments or actions are not accepted.",
        UploadProblem.PDF_ENCRYPTED: "Password-protected PDFs are not accepted.",
        UploadProblem.PDF_UNREADABLE: "This PDF could not be checked. Save it again and retry.",
    }
)


class UploadRejectedError(ValueError):
    def __init__(self, problem: UploadProblem) -> None:
        super().__init__(problem.value)
        self.problem = problem


@dataclass(frozen=True, slots=True)
class ValidatedFile:
    file_name: str
    content_type: str
    size: int
    sha256: str


def sanitize_file_name(raw: str | None) -> str | None:
    """A display name: the last path component, printable, safe characters only, with an
    extension, at most :data:`FILE_NAME_MAX_LENGTH` characters; ``None`` when nothing is left."""
    if not raw:
        return None
    name = unicodedata.normalize("NFC", raw).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable())
    name = " ".join(_UNSAFE_NAME.sub("_", name).split()).strip(" .")
    stem, dot, extension = name.rpartition(".")
    stem = stem.rstrip(" .")
    if not dot or not stem or not extension:
        return None
    extension = extension.lower()
    room = FILE_NAME_MAX_LENGTH - len(extension) - 1
    if room < 1:
        return None
    return f"{stem[:room].rstrip(' .') or '_'}.{extension}"


def detect_type(data: bytes) -> str | None:
    """The allowed type the leading bytes belong to, if any."""
    return next((kind for kind, magic in _MAGIC if data.startswith(magic)), None)


def _names(data: bytes) -> set[bytes]:
    """Every PDF name token, with ``#xx`` escapes decoded (``/J#61vaScript`` is JavaScript)."""
    return {
        _ESCAPE.sub(lambda match: bytes([int(match.group(1), 16)]), raw)
        for raw in _NAME.findall(data)
    }


def _object_streams(data: bytes) -> Iterator[bytes]:
    """The raw bytes of every stream whose object dictionary names ``/ObjStm``, in order.

    Actions live in objects; compressed object streams are where they can
    hide. Page content and image streams cannot define actions and are not
    decompressed (no budget can be exhausted by large images).

    Linear in the file size: a stream's dictionary is looked for only after
    the previous ``stream`` keyword (headers never overlap), and the scan
    resumes after the ``endstream`` of each object stream."""
    position = 0
    while (match := _STREAM.search(data, position)) is not None:
        header_start = data.rfind(b"obj", position, match.start())
        header = data[header_start if header_start >= 0 else position : match.start()]
        position = match.end()
        if b"ObjStm" not in _names(header):
            continue
        end = data.find(b"endstream", position)
        if end < 0:
            yield data[position:]
            return
        yield data[position:end]
        position = end + len(b"endstream")


def _inflate(raw: bytes, limit: int) -> bytes:
    """Flate decompression of a complete stream to at most ``limit`` bytes;
    :class:`UploadRejectedError` when unreadable, truncated or bigger."""
    if limit <= 0:  # zlib reads a max_length of 0 as "unlimited"
        raise UploadRejectedError(UploadProblem.PDF_UNREADABLE)
    inflater = zlib.decompressobj()
    try:
        inflated = inflater.decompress(raw, limit)
    except zlib.error:
        raise UploadRejectedError(UploadProblem.PDF_UNREADABLE) from None
    if inflater.unconsumed_tail or not inflater.eof:
        raise UploadRejectedError(UploadProblem.PDF_UNREADABLE)
    return inflated


def pdf_problem(data: bytes) -> UploadProblem | None:
    """Why a PDF is refused (encrypted, active content, or unreadable within the bounds),
    or ``None``. Stops at the first object stream that exceeds a bound."""
    names = _names(data)
    if b"Encrypt" in names:
        return UploadProblem.PDF_ENCRYPTED
    budget = INFLATED_TOTAL_MAX_BYTES
    for count, stream in enumerate(_object_streams(data), start=1):
        if count > OBJECT_STREAMS_MAX:
            return UploadProblem.PDF_UNREADABLE
        try:
            inflated = _inflate(stream, min(OBJECT_STREAM_MAX_BYTES, budget))
        except UploadRejectedError as error:
            return error.problem
        budget -= len(inflated)
        names |= _names(inflated)
    if names & ACTIVE_PDF_NAMES:
        return UploadProblem.PDF_ACTIVE
    return None


def validate_upload(file_name: str | None, declared_type: str | None, data: bytes) -> ValidatedFile:
    """Run the pipeline; raise :class:`UploadRejectedError` with the first problem."""
    if not data:
        raise UploadRejectedError(UploadProblem.EMPTY)
    if len(data) > MAX_FILE_BYTES:
        raise UploadRejectedError(UploadProblem.TOO_LARGE)
    name = sanitize_file_name(file_name)
    if name is None:
        raise UploadRejectedError(UploadProblem.NAME)
    extension = name.rsplit(".", 1)[1]
    declared = (declared_type or "").split(";", 1)[0].strip().lower()
    if declared not in ALLOWED_TYPES or not any(extension in e for e in EXTENSIONS.values()):
        raise UploadRejectedError(UploadProblem.TYPE)
    detected = detect_type(data)
    if detected != declared or extension not in EXTENSIONS[declared]:
        raise UploadRejectedError(UploadProblem.MISMATCH)
    if detected == PDF:
        problem = pdf_problem(data)
        if problem is not None:
            raise UploadRejectedError(problem)
    return ValidatedFile(
        file_name=name,
        content_type=detected,
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
