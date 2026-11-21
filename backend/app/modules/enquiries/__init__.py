"""Public enquiry (Phase 02-4, ADR-0024): the hosted enquiry page's API.

An anonymous visitor at ``https://<slug>.<site domain>/enquiry`` creates a
``NEW`` website lead in the institute resolved from that verified hostname,
with versioned consent evidence, and an acknowledgement email queued in the
transactional outbox (``app.core.outbox``; delivered by ``python -m app.worker``).
"""
