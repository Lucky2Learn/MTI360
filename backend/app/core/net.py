"""Client network address behind a known number of trusted proxies (T01-04, D08).

``X-Forwarded-For`` is a list that every proxy appends to; only the entries
added by proxies we operate can be trusted. With ``TRUSTED_PROXY_HOPS = n``
the client address is the n-th entry from the right of
``X-Forwarded-For + [socket peer]``. With the default ``0`` the header is
ignored entirely, so a forged header cannot change the address used for rate
limits and session records.
"""

import ipaddress

from starlette.requests import HTTPConnection

UNKNOWN_CLIENT = "unknown"
FORWARDED_FOR = "x-forwarded-for"


def _valid_ip(value: str) -> str | None:
    candidate = value.strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(connection: HTTPConnection, trusted_proxy_hops: int) -> str:
    """The client IP address, trusting exactly ``trusted_proxy_hops`` proxies."""
    peer = connection.client.host if connection.client else UNKNOWN_CLIENT
    if trusted_proxy_hops <= 0:
        return _valid_ip(peer) or UNKNOWN_CLIENT
    forwarded = [
        entry
        for header in connection.headers.getlist(FORWARDED_FOR)
        for entry in header.split(",")
        if entry.strip()
    ]
    chain = [*forwarded, peer]
    index = max(0, len(chain) - 1 - trusted_proxy_hops)
    return _valid_ip(chain[index]) or UNKNOWN_CLIENT
