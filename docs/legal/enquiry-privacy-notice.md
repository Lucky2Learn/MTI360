# Enquiry consent and privacy notice — DRAFT FOR REVIEW

> **Status: draft for legal and product review. Not legal advice and not approved.** The wording below is what the hosted enquiry page shows today (Phase 02-4, [ADR-0024](../adr/0024-public-enquiry.md)). It must be reviewed against the Digital Personal Data Protection Act, 2023 and each institute's own policies before production use.

- **Consent version:** `enquiry-2026-10` (`backend/app/modules/enquiries/domain.py`, `CONSENT_VERSION`). Any change to the wording below needs a new version; the page then refuses submissions made with the old one (the visitor is asked to reload).
- **Retention:** `ENQUIRY_RETENTION_MONTHS` (default **12**), inserted where `{months}` appears. Changing it changes the text shown, so it should go with a new consent version.

## Consent (mandatory checkbox)

> I agree that **{institute}** may use the details in this form to answer my enquiry and to contact me about its courses by email, phone or message. My details are kept for up to **{months}** months and are not shared with other institutes.

## Privacy notice (shown above the submit button)

> **{institute}** receives your enquiry through MTI 360, which hosts this page for the institute. We collect only your name, contact details, the course you are interested in and your message, and use them only to respond to you. We keep them for up to **{months}** months. To see, correct or delete your details, contact **{institute}**.

## What is collected and recorded

| Data | Why | Where |
|---|---|---|
| Name; email and/or phone | To respond (at least one contact) | `leads` |
| Course (optional) | To route the enquiry | `leads.interested_course_id` |
| Message (optional, ≤ 1,000 characters) | The enquiry itself | the lead's first note |
| Consent version and time | Evidence of consent | `leads.consent_version`, `leads.consented_at`; retention months in the `CREATED` activity |

Not collected: date of birth, address, documents, IP address (used transiently for rate limiting only, as a hash in Redis), tracking identifiers.

## Open questions for the reviewers

1. Is "contact me about its courses" within the purpose of answering the enquiry, or a separate consent (marketing)?
2. Does each institute act as data fiduciary with MTI 360 as processor, and does the notice need the institute's contact details and a grievance officer?
3. Is 12 months appropriate; what happens at expiry (deletion or anonymisation)? No deletion job exists yet.
4. Language versions (English only today).
