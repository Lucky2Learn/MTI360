# tests/

**Status:** Reserved. No tests exist yet.

## Purpose

**Cross-stack** test suites that exercise the running system (frontend + backend + database) end to end.

```text
tests/
├── e2e/            Playwright user journeys against the full local stack
└── accessibility/  axe checks at 390 / 768 / 1024 / 1440 px × Light / Dark,
                    plus keyboard and focus checks
```

## Ownership

Shared by frontend and backend engineering.

## What belongs here

- End-to-end journeys (e.g. lead → application → admission → student)
- End-to-end tenant-isolation checks: signed in as Tenant A, navigating directly to a Tenant B resource URL must show a not-found / denied state
- Accessibility and responsive checks across breakpoints and themes

## What does NOT belong here

- Backend unit / integration / API / tenancy tests — these live in `backend/tests/`
- Frontend unit / component tests — these are colocated in `frontend/src/`
- Real personal data. Fixtures use realistic maritime development data only

## Critical requirement

The automated suite must prove **Tenant A cannot access Tenant B**. The primary enforcement suite lives in `backend/tests/security/` (including a route-coverage test that fails when a tenant route lacks a cross-tenant test); this directory adds the end-to-end layer. See [tenancy.md](../docs/architecture/tenancy.md).

## Populated by

| Task | Adds |
|---|---|
| T00-05 | CI wiring |
| T00-09 / T00-10 | Responsive and accessibility harness |
| T01-12 | Cross-tenant security tests |
