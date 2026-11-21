"""Institute site addresses: rules for ``tenant_domains`` (Phase 02-4, ADR-0024).

Pure rules: no I/O, no framework or database imports.

* An institute's public pages are served at a **platform-issued** hostname,
  ``<slug>.<public_site_domain>`` (``konkan.mti360.in``). The platform owns
  the domain, so such a hostname is verified by construction (master
  readiness §15); custom domains with DNS verification come later.
* Hostnames are stored normalized: lowercase, no port, no trailing dot.
  :func:`normalize_host` applies the same rules to a request ``Host`` and
  returns ``None`` for anything that is not a plain DNS name (IP literals,
  credentials, paths, invalid characters), so such a request matches nothing.
"""

import re
from enum import StrEnum
from typing import Final

HOSTNAME_MAX_LENGTH: Final = 253
SLUG_MIN_LENGTH: Final = 3
SLUG_MAX_LENGTH: Final = 40
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOSTNAME_PATTERN: Final = rf"^{_LABEL}(?:\.{_LABEL})+$"
"""Two or more DNS labels (also the database CHECK; POSIX-compatible)."""
_HOSTNAME = re.compile(HOSTNAME_PATTERN)
_SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_PORT = re.compile(r":[0-9]{1,5}")

RESERVED_SLUGS: Final = frozenset(
    {
        "admin", "api", "app", "assets", "auth", "cdn", "docs", "help", "login", "mail",
        "platform", "portal", "sites", "smtp", "static", "status", "student", "support",
        "www",
    }
)  # fmt: skip
"""Labels kept for the platform's own services; never issued to an institute."""


class DomainKind(StrEnum):
    PLATFORM_SUBDOMAIN = "PLATFORM_SUBDOMAIN"
    """``<slug>.<public_site_domain>``: issued by the platform, verified by construction."""


class DomainStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    """Kept (the hostname stays with its institute) but resolves to nothing."""


class InvalidSlugError(ValueError):
    """The slug cannot become a hostname label. The message is safe to show."""


def clean_slug(raw: str) -> str:
    """A lowercase hostname label of 3-40 characters that is not reserved."""
    slug = raw.strip().lower()
    if not SLUG_MIN_LENGTH <= len(slug) <= SLUG_MAX_LENGTH or not _SLUG.fullmatch(slug):
        raise InvalidSlugError(
            "Use 3-40 lowercase letters, digits or hyphens, starting and ending with a "
            "letter or digit."
        )
    if "--" in slug:
        raise InvalidSlugError("Do not use two hyphens in a row.")
    if slug in RESERVED_SLUGS:
        raise InvalidSlugError("This address is reserved.")
    return slug


def site_hostname(slug: str, site_domain: str) -> str:
    """The platform-issued hostname of ``slug`` (already cleaned)."""
    hostname = f"{slug}.{site_domain}"
    if len(hostname) > HOSTNAME_MAX_LENGTH or not _HOSTNAME.fullmatch(hostname):
        raise InvalidSlugError("This address is too long.")
    return hostname


def normalize_host(raw: str | None) -> str | None:
    """A request host as a stored hostname: lowercase, no port, no trailing dot.

    ``None`` when ``raw`` is missing or is not a plain DNS name of two or more
    labels (``127.0.0.1``, ``[::1]``, ``user@host``, ``host/path`` and other
    forms never match an institute).
    """
    if not raw:
        return None
    host = raw.strip().lower()
    match = _PORT.search(host)
    if match is not None and match.end() == len(host):
        host = host[: match.start()]
    host = host.removesuffix(".")
    if len(host) > HOSTNAME_MAX_LENGTH or not _HOSTNAME.fullmatch(host):
        return None
    if all(label.isdigit() for label in host.split(".")):
        return None  # a dotted-decimal IP address
    return host
