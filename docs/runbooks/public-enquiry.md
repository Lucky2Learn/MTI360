# Hosted enquiry page (Phase 02-4)

How to run, operate and check the institute enquiry page at `https://<slug>.<PUBLIC_SITE_DOMAIN>/enquiry`. The design is in [ADR-0024](../adr/0024-public-enquiry.md).

## 1. Run it locally

Browsers resolve `<anything>.localhost` to this machine, so a local institute address is `http://konkan.localhost:3100/enquiry`.

1. Infrastructure and schema: `pnpm infra:up`, then `pnpm db:migrate` (migration `0012`).
2. Use these settings in your shell or local env files. They are not in the committed defaults.
   - API (`backend/.env`): `PUBLIC_SITE_DOMAIN=localhost` and `TRUSTED_PROXY_HOPS=1`. The API then trusts the Next.js server's `X-Forwarded-Host`; with `0` it uses its own `Host` (`127.0.0.1:8100`) and every enquiry request is 404.
   - Frontend (`frontend/.env.local`): `PUBLIC_SITE_DOMAIN=localhost`.
3. Give an institute an address. Either way, the database must not hold that address already.
   - A seeded institute gets one automatically when seeded with `PUBLIC_SITE_DOMAIN=localhost`: `konkan.localhost`, `coromandel.localhost`, or `konkan-demo2.localhost` for a tagged copy (see [demo.md](demo.md)).
   - Any institute: `uv run --directory backend python -m app.cli issue-site --tenant <tenant UUID> --slug konkan`.
4. Start `pnpm dev`, and `pnpm worker` in a second terminal for the acknowledgement emails. Emails arrive in Mailpit at http://127.0.0.1:18025.

## 2. Operate it

| Setting | Default | Meaning |
|---|---|---|
| `PUBLIC_SITE_DOMAIN` | `mti360.in` | `<slug>.<domain>` addresses (backend and frontend) |
| `TRUSTED_PROXY_HOPS` | `0` | Must be `1` when the API sits behind the Next.js server |
| `ENQUIRY_IP_LIMIT` / `_WINDOW_SECONDS` | 5 / 600 | Enquiries per client IP |
| `ENQUIRY_TENANT_LIMIT` / `_WINDOW_SECONDS` | 200 / 3600 | Enquiries per institute |
| `ENQUIRY_DUPLICATE_WINDOW_SECONDS` | 600 | The same contact and course again is acknowledged, not stored |
| `ENQUIRY_RETENTION_MONTHS` | 12 | Stated in the consent text; **no deletion job yet** |
| `OUTBOX_MAX_ATTEMPTS` / `OUTBOX_STALE_SECONDS` / `OUTBOX_POLL_SECONDS` | 6 / 300 / 5 | Worker retries, crash reclaim, idle poll |

- **Worker:** `python -m app.worker` runs until stopped, and any number of copies can run side by side. Use `--once` for a single pass.
- **Failed messages** (`outbox_messages.status = 'FAILED'`, `last_error` = exception class): the lead is unaffected. Re-queue one deliberately with `UPDATE outbox_messages SET status='PENDING', failed_at=NULL, attempts=0, available_at=now() WHERE id = …`. Run it as the database owner, after fixing the cause.
- **Turn an address off:** set `tenant_domains.status = 'INACTIVE'` for that hostname. The page and API answer 404 from then on, and the hostname stays with its institute.

## 3. Browser checklist (manual; not yet performed)

Run each check at **390, 768, 1024 and 1440 px**, in **Light and Dark** (footer appearance control), and once with **System**. Use a seeded institute address on a local or disposable database. Results of the first run are below the table.

| # | Check | Pass when |
|---|---|---|
| E1 | Open `http://konkan.localhost:3100/enquiry` | The institute name shows in the header and introduction, with "Ask about a course" as the heading; there is no horizontal scroll at any width |
| E2 | Open `http://unknown.localhost:3100/enquiry`, `http://localhost:3100/enquiry` and `http://konkan.localhost:3100/sites/konkan.localhost/enquiry` | Status 404 each. The first two show the neutral public 404 (no institute named, no link); the third (on Konkan's address) shows the branded 404 with Konkan's name and an "Ask about a course" link |
| E3 | Submit an empty form | Name, contact and consent errors show next to their fields; focus moves to Full name; errors are readable in both themes and not shown by colour alone |
| E4 | Fill name and phone only, without consent | The consent error shows; nothing is sent (DevTools network tab) |
| E5 | Open the Course list | Only the institute's active courses, plus "Not sure yet"; usable by touch at 390 |
| E6 | Send a complete enquiry with an email and a message | The confirmation shows and takes focus. As the institute's admissions manager, the lead appears as NEW, Website, with no creator, and the message is in its timeline |
| E7 | Run `pnpm worker`, then check Mailpit | One acknowledgement to the entered email, naming the institute and course, with no link |
| E8 | Send the same enquiry again within 10 minutes | The same confirmation shows; still one lead |
| E9 | Send 6 enquiries from one browser within 10 minutes | The 6th shows "Too many enquiries" with a waiting time; the entries are kept |
| E10 | Stop the worker or Mailpit, send an enquiry, then restart them | The lead exists at once; the email arrives after the retry |
| E11 | Sign in as the other institute | The enquiry is not visible to it |
| E12 | Keyboard only through E3 and E6 | Every control is reachable in order; the spam trap is never focused; focus is always visible |
| E13 | A screen reader (NVDA or VoiceOver) on the form | Labels, the required marker, errors and the confirmation are announced; the spam trap is not |

Record the date, the browser and any failure (with its width, theme and a screenshot) in DEVELOPMENT-STATUS.md §9A (02-4).

### Results (2026-11-01)

Run in **headless Chromium 1243**, driven by Playwright from outside the repository, against a local stack:
- frontend `:3200` (`next dev`) → API `:8200` → the **disposable `mti360_seed_verification` database**, migrated to `0013`, with `konkan.localhost` and `coromandel.localhost` issued by `issue-site`;
- `PUBLIC_SITE_DOMAIN=localhost` on both sides, `TRUSTED_PROXY_HOPS=1`, Redis db 2, Mailpit.

The development database, the TEST tenant and the running containers were not touched. The screenshots are kept outside the repository.

| # | Result | Evidence |
|---|---|---|
| E1 | Pass | 390 / 768 / 1024 / 1440 × Light and Dark: status 200, `data-theme` as chosen, 0 px horizontal overflow, institute name in header and title. System follows the OS (light and dark) |
| E2 | Pass (after the fix below) | `unknown.localhost`, bare `localhost` and direct `/sites/…`: status 404 with the not-found page |
| E3 | Pass | Light and Dark at 390: three field errors with icon and text, `aria-invalid`, focus on Full name, no request sent |
| E4 | Pass | Consent error; no request sent |
| E5 | Pass | Diploma in Nautical Science, GP Rating, STCW Basic Safety Training, Not sure yet; options 44 px tall at 390 |
| E6 | Pass | Confirmation shown and focused; one lead in Konkan only (WEBSITE, NEW, no creator, consent `enquiry-2026-10`, one note); the Konkan admissions manager's lead detail shows it as a website enquiry with the message in the timeline |
| E7 | Pass | One Mailpit email, "We received your enquiry - Konkan Maritime Training Institute", naming GP Rating, no link |
| E8 | Pass | Repeat confirmed; still one lead |
| E9 | Pass | Five accepted, the sixth shows "Too many enquiries — Please wait 10 minutes and try again."; entries kept |
| E10 | Pass | Worker stopped: lead stored at once, outbox `PENDING`; worker restarted with `pnpm worker`: `SENT`, email delivered |
| E11 | Pass | The Coromandel owner sees neither the lead detail nor the lead in the list |
| E12 | Pass | Tab order Full name → Email → Phone → Course → Message → consent → Send; visible focus on each; the spam trap never focused; submitted with Space and Enter |
| E13 | **Not performed** | Needs a real screen reader (NVDA or VoiceOver); not available to automation |

**Branded public 404 (added after the run, 2026-11-01):** the observation below about Next.js's unbranded 404 is resolved. Headless Chromium against the same local stack:
- On an institute address, every non-page path returns **404 with the branded page**: the institute's name, "Page not found" and an "Ask about a course" link to `/enquiry`. Checked: `/no-such-page`, `/`, `/app/admissions/leads`, `/platform` and `/sites/…` on Konkan; `/login` on Coromandel.
- **Neutral 404** for `unknown.localhost` (`/enquiry`, `/anything`) and the bare `localhost/enquiry`: no institute named, no link, no navigation.
- No staff or platform navigation anywhere; the link opens the enquiry page.
- 390 Dark and 1440 Light for both variants: theme applied, 0 px overflow.
- `/app` and `/platform` on the application host still go to their session-ended pages.
- 16/16 checks passed.
- Not checked in the browser: an *inactive* address, because changing a database row was out of scope. The API's 404 for it is covered by `test_inactive_addresses_and_closed_institutes_are_not_found`, and the neutral page by the frontend tests.
- **Dev-only console warning:** React reports the root layout's theme pre-paint `<script>` ("Encountered a script tag…") when a `notFound()` boundary renders in `next dev`. The theme is still applied correctly. Whether `/app` RESOURCE-02 pages and the production build show it was not checked.

**Defect found and fixed:** a refusal by the proxy (bare host, direct `/sites/*`) returned an empty 404, and Chromium showed its own error page. Refusals are now rewritten to a path with no route, so the not-found page renders with status 404 (`src/proxy.ts`, `SITE_NOT_FOUND`; proxy tests updated).

**Observations (open, outside the checklist):**
- ~~The not-found page on an institute host is Next.js's default (unbranded).~~ Resolved: branded public 404, see above.
- The Next.js dev-tools badge ("N") overlaps content at 390 px in development only.
- Not covered: Safari, Firefox, real mobile devices, the production build (`next build`).

