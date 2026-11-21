"""Public enquiry rules (Phase 02-4, ADR-0024). Pure: no I/O, no framework imports.

* **Consent is mandatory and versioned.** The page shows the text of
  :data:`CONSENT_VERSION`; a submission must accept it and name that version
  (a stale page is refused). The lead stores the version and the time; the
  retention period in force is recorded with it, so the exact wording can be
  rebuilt with :func:`consent_text`.
* **Minimal personal data:** a name, an email or a mobile number (at least
  one), optionally a course and a short message. No date of birth, address,
  documents or free-form profile.
* The wording is a draft for review, not legal advice or approval
  (docs/legal/enquiry-privacy-notice.md).
"""

from typing import Final

CONSENT_VERSION: Final = "enquiry-2026-10"
"""Change it whenever :func:`consent_text` or :func:`privacy_notice` changes."""

MESSAGE_MAX_LENGTH: Final = 1000
HONEYPOT_FIELD: Final = "website"
"""Hidden from people (off-screen, not focusable); bots tend to fill it in."""

ACKNOWLEDGEMENT_KIND: Final = "enquiry.acknowledgement"
"""Outbox kind of the acknowledgement email; its payload is ``{"lead_id": …}``."""

MAX_BODY_BYTES: Final = 16 * 1024
"""A complete enquiry is far smaller; anything larger is refused (413) unread."""


def consent_text(institute: str, retention_months: int) -> str:
    """The consent statement next to the mandatory checkbox (version :data:`CONSENT_VERSION`)."""
    return (
        f"I agree that {institute} may use the details in this form to answer my enquiry "
        "and to contact me about its courses by email, phone or message. My details are "
        f"kept for up to {retention_months} months and are not shared with other institutes."
    )


def privacy_notice(institute: str, retention_months: int) -> str:
    """The short notice shown above the submit button (version :data:`CONSENT_VERSION`)."""
    return (
        f"{institute} receives your enquiry through MTI 360, which hosts this page for the "
        "institute. We collect only your name, contact details, the course you are interested "
        "in and your message, and use them only to respond to you. We keep them for up to "
        f"{retention_months} months. To see, correct or delete your details, contact "
        f"{institute}."
    )
