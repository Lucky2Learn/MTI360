# MTI 360

# UI-SCREENS.md

**Product:** MTI 360
**Positioning:** The Complete Growth & Operations Platform for Maritime Training Institutes
**Tagline:** Acquire Students. Simplify Operations. Grow Your Institute.

**Version:** 1.1
**Status:** UI Screen Inventory & Screen Behavior Specification

---

# 1. PURPOSE

This document defines the complete MTI 360 screen inventory and the functional UI expectations for each screen.

It defines:

* Screen identity
* Screen purpose
* Persona
* Product experience
* Navigation location
* Page template
* Primary actions
* Important information
* Responsive behavior
* Theme requirements
* Major UI states
* Permission considerations
* Related workflows

It does **not** replace:

* `PRD.md` — product requirements
* `APP-FLOW.md` — application flows
* `ARCHITECTURE.md` — technical architecture
* `PLATFORM-ADMIN.md` — platform control plane specification
* `DESIGN-SYSTEM.md` — visual design system
* `CLAUDE.md` — implementation rules
* `TASKS.md` — development roadmap

---

# 2. UI DESIGN SOURCE OF TRUTH

The UI design hierarchy is:

```text
PRD.md
   ↓
APP-FLOW.md
   ↓
ARCHITECTURE.md
   ↓
PLATFORM-ADMIN.md
   ↓
DESIGN-SYSTEM.md
   ↓
UI-SCREENS.md
```

`DESIGN-SYSTEM.md` defines **how the product looks and behaves visually**.

`UI-SCREENS.md` defines **what screens exist and what each screen must accomplish**.

---

# 3. FOUR PRODUCT EXPERIENCES

MTI 360 consists of:

```text
MTI 360
│
├── 1. PLATFORM / SAAS CONTROL PLANE
│
├── 2. TENANT APPLICATION
│
├── 3. STUDENT PORTAL
│
└── 4. PUBLIC WEBSITE
```

---

# 4. SCREEN DESIGN CONTRACT

Every screen must support the following where applicable:

```text
Theme
├── Light
├── Dark
└── System

Responsive
├── Mobile
├── Tablet
├── Desktop
└── Large Desktop

States
├── Loading
├── Empty
├── Populated
├── Error
├── Permission Restricted
└── Success where applicable
```

A screen is not considered design-complete if it only defines its desktop Light Mode appearance.

---

# 5. RESPONSIVE BREAKPOINTS

Reference breakpoints from `DESIGN-SYSTEM.md`:

```text
Mobile
390–767px

Tablet
768–1023px

Desktop
1024–1439px

Large Desktop
1440px+
```

Important intermediate widths should also be tested.

---

# 6. THEME REQUIREMENT

All screens must support:

```text
Light
Dark
System
```

Dark Mode must be intentionally designed using the MTI 360 Midnight/Ocean palette.

It must not be implemented as a simple inversion of Light Mode.

---

# 7. RESPONSIVE REQUIREMENT

Responsive behavior must be explicitly considered for every screen.

Do not simply scale desktop layouts.

The design must determine:

* what stacks
* what collapses
* what scrolls
* what becomes a drawer
* what becomes a modal
* what becomes a card
* what moves to an overflow menu
* what remains sticky
* what becomes a mobile-first action

---

# 8. PAGE TEMPLATE SYSTEM

The following templates are reusable across the product.

| ID  | Template                | Primary Use                      |
| --- | ----------------------- | -------------------------------- |
| T01 | Dashboard               | KPI, charts, operational summary |
| T02 | Data List               | Tables, filters, search          |
| T03 | Detail                  | Record information               |
| T04 | Form                    | Create/edit                      |
| T05 | Wizard                  | Multi-step workflow              |
| T06 | Kanban                  | Pipeline/workflow                |
| T07 | Calendar                | Scheduling                       |
| T08 | Communication Workspace | Conversations                    |
| T09 | AI Workspace            | AI interaction                   |
| T10 | Analytics               | Reporting                        |
| T11 | Workflow Builder        | Automation                       |
| T12 | Tenant 360              | Tenant overview                  |
| T13 | Platform Operations     | Platform administration          |
| T14 | Support Workspace       | Support operations               |
| T15 | Settings                | Configuration                    |
| T16 | Authentication          | Login/security                   |
| T17 | Student Portal          | Student experience               |
| T18 | Public Website          | Public marketing                 |

---

# 9. RESPONSIVE TEMPLATE RULE

Templates themselves must be responsive.

Example:

```text
T02 Data List

Desktop
→ DataTable

Tablet
→ Reduced columns

Mobile
→ Card / horizontal scroll / expandable row
```

Similarly:

```text
T08 Communication Workspace

Desktop
→ 3-panel workspace

Tablet
→ 2-panel workspace

Mobile
→ sequential navigation
```

---

# 10. COMMON SCREEN STATES

## Loading

Use skeletons appropriate to the content.

## Empty

Explain:

* what is empty
* why
* what the user can do

## Error

Explain:

* what failed
* whether data was saved
* retry option
* next action

## Permission Restricted

Clearly explain insufficient access where appropriate.

## Success

Provide confirmation after important actions.

---

# 11. SCREEN PRIORITY

Each screen is classified:

```text
P0
Critical / foundation / core workflow

P1
Important operational capability

P2
Secondary / advanced capability
```

Priority does not mean visual quality differs.

All screens must follow the same design system.

---

# 12. PLATFORM / SAAS CONTROL PLANE

The Platform Control Plane is used by MTI 360 platform administrators.

Primary context:

```text
MTI 360 Platform
All Tenants
```

---

## PLAT-01 — Platform Login

**Template:** T16 Authentication
**Priority:** P0

Detailed UI/UX specification (T01-09B): [docs/ui/T01-09B-PLATFORM-IDENTITY-MFA-UI.md](docs/ui/T01-09B-PLATFORM-IDENTITY-MFA-UI.md). Route `/platform/login`.

### Purpose

Authenticate MTI 360 platform administrators.

### Primary Elements

* Email
* Password
* Sign in
* Forgot password

"Remember device" is removed: trusted and remembered devices are deferred by T01-06 D6-4.

### States

* Loading
* Invalid credentials (one generic message; a locked or suspended account is not distinguished, T01-04 S8)
* MFA required (PLAT-02) or MFA set-up required (PAUTH-04), as in-memory steps of `/platform/login`

### Responsive

Mobile:

* Single-column
* Full-width form

Desktop:

* Split authentication layout may be used

### Theme

* Light
* Dark
* System

---

## PLAT-02 — Platform MFA

**Template:** T16 Authentication
**Priority:** P0

A step of `/platform/login`, not a route (T01-09B D9B-2).

### Purpose

Secure platform administrator access.

### Elements

* Authenticator (TOTP) code
* Verification
* Recovery-code option

"Resend" and "Trusted device" are removed: OTP resend and trusted devices are deferred by T01-06 D6-4 (TOTP and recovery codes only).

### Responsive

Mobile-first verification experience.

---

## PLAT-03 — Platform Dashboard

**Template:** T01 Dashboard
**Priority:** P0

### Purpose

Provide platform-wide operational overview.

### KPIs

* Total Tenants
* Active Tenants
* Trial Tenants
* New Tenants
* MRR
* ARR
* Active Users
* Students
* Leads
* AI Executions
* Communication Volume
* Storage
* Failed Jobs
* Open Support Tickets
* Expiring Subscriptions
* Suspended Tenants

### Charts

* Tenant Growth
* Subscription Distribution
* MRR Trend
* Retention
* Usage by Tenant
* AI Usage / Cost
* Communication Volume
* Platform Health

### Quick Actions

* Create Tenant
* Invite Tenant Admin
* Manage Subscription
* Open Support Ticket
* Platform Health
* Announce to Tenants
* Controlled Support Session

### AI Assistant

Example questions:

* What needs attention across MTI 360 today?
* Which tenants approach usage limits?
* Show failed payments.
* Which subscriptions expire soon?
* Show AI cost anomalies.

### Responsive

Desktop:

* Multi-column KPI and chart layout

Tablet:

* Reduced columns

Mobile:

* Stacked KPIs
* Stacked charts
* Priority alerts first

### Theme

Charts and KPI states must work in Light/Dark.

---

## PLAT-04 — Tenant List

**Template:** T02 Data List
**Priority:** P0

### Purpose

Manage and search all MTI tenants.

### Columns

* Tenant
* Status
* Plan
* Users
* Students
* Usage
* Subscription
* Health
* Created
* Actions

### Filters

* Status
* Plan
* Subscription
* Usage
* Health
* Date

### Responsive

Mobile:

* Tenant cards or prioritized table
* Secondary information expandable

---

## PLAT-05 — Tenant 360

**Template:** T12 Tenant 360
**Priority:** P0

### Purpose

Provide comprehensive tenant overview.

### Sections

* Institute
* Subscription
* Usage
* Users
* Health
* Billing
* Integrations
* AI
* Support
* Audit

### Actions

* Manage Tenant
* Manage Subscription
* Support Session
* Suspend
* Activate

Sensitive actions require confirmation.

---

## PLAT-06 — Create Tenant

**Template:** T05 Wizard
**Priority:** P0

### Steps

1. Institute
2. Subscription
3. Primary Admin
4. Campus
5. Courses
6. Branding
7. Communication
8. AI
9. Billing
10. Review
11. Activate

### Requirements

* Save Draft
* Validation
* Back
* Next
* Review
* Activate

### Mobile

Each step becomes a full-width mobile form.

---

## PLAT-07 — Tenant Onboarding

**Template:** T05 Wizard
**Priority:** P0

### Purpose

Guide newly created tenants through setup.

### Areas

* Institute
* Campus
* Users
* Courses
* Branding
* Communication
* AI
* Billing
* Verification

---

## PLAT-08 — Tenant Status

**Template:** T03 Detail
**Priority:** P1

### Statuses

```text
PROSPECT
TRIAL
PROVISIONING
ACTIVE
PAST_DUE
SUSPENDED
CANCELLED
DEACTIVATED
```

Show lifecycle history.

---

## PLAT-09 — Tenant Usage & Health

**Template:** T13 Platform Operations
**Priority:** P1

### Metrics

* Users
* Students
* Storage
* API
* Communication
* AI
* Background jobs

Use UsageMeter components.

---

## PLAT-10 — Tenant Users / Support Access

**Template:** T02 Data List
**Priority:** P1

Manage:

* Tenant users
* Roles
* Support access
* Access history

---

## PLAT-11 — Plans & Pricing

**Template:** T02 Data List
**Priority:** P1

Manage SaaS plans.

---

## PLAT-12 — Subscriptions

**Template:** T02 Data List
**Priority:** P1

Manage tenant subscriptions.

---

## PLAT-13 — Billing & Invoices

**Template:** T02 Data List
**Priority:** P0

Show:

* Tenant
* Invoice
* Amount
* Status
* Due Date
* Payment
* Actions

---

## PLAT-14 — Payment Transactions

**Template:** T02 Data List
**Priority:** P1

Show payment transaction history.

---

## PLAT-15 — Coupons / Discounts / Trials

**Template:** T02 Data List
**Priority:** P1

Manage promotional offers.

---

## PLAT-16 — Feature Entitlements

**Template:** T03 Detail
**Priority:** P1

Configure feature access by plan/tenant.

---

## PLAT-17 — Usage Metering

**Template:** T10 Analytics
**Priority:** P1

Show platform and tenant usage.

---

## PLAT-18 — Communication Providers

**Template:** T15 Settings
**Priority:** P1

Manage:

* WhatsApp providers
* Email providers
* SMS providers
* Voice providers

---

## PLAT-19 — AI Providers / Models

**Template:** T15 Settings
**Priority:** P1

Manage:

* Providers
* Models
* Availability
* Routing
* Limits

---

## PLAT-20 — AI Cost & Usage

**Template:** T10 Analytics
**Priority:** P1

Show:

* Token usage
* Executions
* Cost
* Tenant usage
* Model usage

---

## PLAT-21 — Global AI Guardrails

**Template:** T15 Settings
**Priority:** P0

Manage:

* Allowed tools
* Approval requirements
* Data access
* Execution limits
* Safety rules

---

## PLAT-22 — Global Integrations

**Template:** T15 Settings
**Priority:** P1

Manage platform integrations.

---

## PLAT-23 — Tenant Provisioning

**Template:** T13 Platform Operations
**Priority:** P0

Show provisioning pipeline:

```text
Requested
→ Database
→ Storage
→ Configuration
→ Admin
→ Integrations
→ Ready
```

---

## PLAT-24 — Background Jobs

**Template:** T13 Platform Operations
**Priority:** P1

Show:

* Queued
* Running
* Completed
* Failed
* Retried

---

## PLAT-25 — System Health

**Template:** T13 Platform Operations
**Priority:** P0

Show:

* API
* Database
* Cache
* Queue
* Storage
* AI
* Communication
* External integrations

---

## PLAT-26 — API / Webhook Monitoring

**Template:** T13 Platform Operations
**Priority:** P1

Show:

* Requests
* Errors
* Latency
* Webhook delivery
* Retry

---

## PLAT-27 — Incident Dashboard

**Template:** T13 Platform Operations
**Priority:** P1

Show:

* Active incidents
* Severity
* Impact
* Status
* Timeline

---

## PLAT-28 — Support Tickets

**Template:** T02 Data List
**Priority:** P1

---

## PLAT-29 — Support Ticket Detail

**Template:** T03 Detail
**Priority:** P1

---

## PLAT-30 — Controlled Support Session

**Template:** T14 Support Workspace
**Priority:** P0

Must display persistent support-session context.

### Requirements

* Tenant
* Access mode
* Reason
* Start time
* Exit
* Audit visibility

---

## PLAT-31 — Platform Notifications

**Template:** T02 Data List
**Priority:** P1

---

## PLAT-32 — Platform Templates

**Template:** T02 Data List
**Priority:** P1

---

## PLAT-33 — Feature Flags

**Template:** T15 Settings
**Priority:** P1

---

## PLAT-34 — Global Settings

**Template:** T15 Settings
**Priority:** P1

---

## PLAT-35 — Security Dashboard

**Template:** T10 Analytics
**Priority:** P0

Show:

* Login activity
* Suspicious activity
* Failed authentication
* Privileged access
* Security events

---

## PLAT-36 — Platform Audit Logs

**Template:** T02 Data List
**Priority:** P0

Filters:

* User
* Tenant
* Action
* Date
* Resource
* Result

---

## PLAT-37 — Login / Session Audit

**Template:** T02 Data List
**Priority:** P1

---

## PLAT-38 — Data Access Audit

**Template:** T02 Data List
**Priority:** P0

Show sensitive data access.

---

## PLAT-39 — Data Retention

**Template:** T15 Settings
**Priority:** P1

Manage retention policies.

---

## PLAT-40 — Backup / Restore Status

**Template:** T13 Platform Operations
**Priority:** P1

Show:

* Backup status
* Last successful backup
* Failures
* Restore readiness

---

## PLAT-41 — Platform Analytics

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-42 — Tenant Growth

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-43 — Revenue Analytics

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-44 — Retention / Churn

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-45 — Subscription Analytics

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-46 — Platform AI Analytics

**Template:** T10 Analytics
**Priority:** P1

---

## PLAT-47 — API Keys / Service Credentials

**Template:** T15 Settings
**Priority:** P0

Sensitive credentials must never be displayed in plaintext after creation.

---

## PLAT-48 — Domain / Branding

**Template:** T15 Settings
**Priority:** P1

Manage tenant domains and branding.

---

## PLAT-49 — Tenant Provisioning Templates

**Template:** T02 Data List
**Priority:** P1

---

## PLAT-50 — Platform Admin Users

**Template:** T02 Data List
**Priority:** P0

---

## PLAT-51 — Platform Roles & Permissions

**Template:** T15 Settings
**Priority:** P0

---

## PLAT-52 — Platform Admin Profile

**Template:** T03 Detail
**Priority:** P1

Partially built in T01-09B (D9B-8): "Sign-in security" at `/platform/profile` — name, email and roles (read-only), two-step verification status, recovery codes remaining and "Generate new recovery codes" (step-up). The rest of the profile belongs to T02-23.

---

## PLAT-53 — Platform Settings

**Template:** T15 Settings
**Priority:** P1

---

# 13. TENANT APPLICATION

Tenant context example:

```text
MTI 360
ABC Maritime Training Institute
Mumbai Campus
```

Tenant users must never see another tenant's data.

---

# 12A. PLATFORM AUTHENTICATION (T01-09B)

Detailed UI/UX specification: [docs/ui/T01-09B-PLATFORM-IDENTITY-MFA-UI.md](docs/ui/T01-09B-PLATFORM-IDENTITY-MFA-UI.md). The new platform authentication screens form the **PAUTH** family, because PLAT-03 … PLAT-13 already name Platform Dashboard … Billing & Invoices (D9B-1). All use T16 with the context label "Platform administration", except PAUTH-07.

## PAUTH-01 — Platform Forgot Password

**Template:** T16
**Priority:** P0

`/platform/forgot-password`. One confirmation for every email.

## PAUTH-02 — Platform Reset Password

**Template:** T16
**Priority:** P0

`/platform/reset-password#token=…` (fragment token). A reset never bypasses MFA.

## PAUTH-03 — Platform Accept Invitation

**Template:** T16
**Priority:** P0

`/platform/accept-invitation#token=…`. Masked email preview; password only; no automatic sign-in.

## PAUTH-04 — Set Up Two-Step Verification

**Template:** T16
**Priority:** P0

Step of `/platform/login` after `mfa_enrolment_required` (first sign-in, or after an MFA reset). Starts only on an explicit press; manual setup key, `otpauth://` link, no QR code.

## PAUTH-05 — Recovery Codes

**Template:** component (T16 card or Dialog)
**Priority:** P0

The ten codes, shown once, with a required acknowledgement. After enrolment and after regeneration on PLAT-52.

## PAUTH-06 — Platform Session Ended

**Template:** T16
**Priority:** P0

`/platform/session-ended?reason=signed-out|ended`.

## PAUTH-07 — Step-Up Verification

**Template:** Dialog in the platform shell
**Priority:** P0

Opened by `403 STEP_UP_REQUIRED`; TOTP only; the original request is resent once after success.

---

# 14. TENANT AUTHENTICATION

Detailed UI/UX specification for AUTH-01 … AUTH-03 and AUTH-05 … AUTH-08 (T01-04 design, implemented in T01-09): [docs/ui/T01-04-IDENTITY-AUTHENTICATION-UI.md](docs/ui/T01-04-IDENTITY-AUTHENTICATION-UI.md).

## AUTH-01 — Tenant Login

**Template:** T16
**Priority:** P0

---

## AUTH-02 — Forgot Password

**Template:** T16
**Priority:** P0

---

## AUTH-03 — Reset Password

**Template:** T16
**Priority:** P0

---

## AUTH-04 — MFA

**Template:** T16
**Priority:** P0

Designed with platform identity and MFA (T01-06), not in the T01-04 specification. The tenant sign-in MFA step (verify and recovery code) is built in T01-09A and shares its implementation with PLAT-02 (T01-09B). Tenant MFA set-up and removal are built in **T01-09C** (completing D9B-9) on the personal **Sign-in security** page `/app/account/security`, reached from the account menu (D9C-1). Specification: [docs/ui/T01-09C-TENANT-MFA-UI.md](docs/ui/T01-09C-TENANT-MFA-UI.md).

---

## AUTH-05 — Session / Access Denied

**Template:** T16
**Priority:** P0

Support:

* expired session
* unauthorized access
* insufficient permissions

The session states (expired, ended, signed out) are specified for T01-04. Insufficient permissions is AUTHZ-01 (T01-05).

---

## AUTH-06 — Accept Invitation

**Template:** T16
**Priority:** P0

Invitation acceptance after a server preview (institute name, masked email, new or existing account). A new account sets a name and password; an existing account never sets a password. No automatic sign-in. Added by the T01-04 UI specification (decision D19).

---

## AUTH-07 — Choose Institute

**Template:** T16
**Priority:** P0

Institute selection after sign-in when the person has access to more than one institute. Added by the T01-04 UI specification.

---

## AUTH-08 — Choose Campus

**Template:** T16
**Priority:** P0

Mandatory only for a restricted (selected-campus) membership with two or more permitted campuses. All-campus access starts at "All campuses", and a single permitted campus is selected automatically. The options come only from the server. Added by the T01-04 UI specification (decision D04).

---

# 14A. TENANT AUTHORIZATION (T01-05)

Detailed UI/UX specification: [docs/ui/T01-05-AUTHORIZATION-RBAC-UI.md](docs/ui/T01-05-AUTHORIZATION-RBAC-UI.md). Role and permission administration (ADMIN-07) is not part of it (T01-08, Phase 03).

## AUTHZ-01 — Access Denied

**Template:** state inside the tenant shell (ErrorState, permission presentation)
**Priority:** P0

A signed-in member opens a page their permissions don't include. Rendered at the requested URL; never names a permission, role, institute or campus.

---

## RESOURCE-02 — Not Found (in the shell)

**Template:** state inside the tenant shell (EmptyState)
**Priority:** P0

One answer for missing, cross-tenant and out-of-scope-campus resources and for unknown or unreleased pages.

---

## Authorization states and modifications (T01-05)

* RESOURCE-01 — Action denied (inline Alert in forms, toast otherwise; state only)
* NAV-01 / NAV-02 — Permission-aware navigation, desktop and mobile (modification of the shell navigation)
* SESSION-01 — Roles line in the account menu (modification of UserMenu)
* CAMPUS-01 — Active campus is a view filter, not an access boundary (behaviour rules)
* DASH-01 — Dashboard sections hidden without permission; empty-dashboard state (convention)

---

# 15. TENANT DASHBOARDS

## DASH-01 — Executive Dashboard

**Template:** T01
**Priority:** P0

### KPIs

* Leads
* Applications
* Admissions
* Students
* Revenue
* Outstanding
* Attendance
* Placement
* Compliance

### Sections

* Admission Funnel
* Revenue Trend
* Attendance
* Compliance
* Placement
* Alerts
* Tasks

### Responsive

Mobile prioritizes:

1. Alerts
2. KPIs
3. Admission funnel
4. Tasks
5. Trends

---

## DASH-02 — Admissions Dashboard

**Template:** T01
**Priority:** P0

Show:

* Leads
* Counselling
* Applications
* Documents
* Admissions
* Conversion

---

## DASH-03 — Academic Dashboard

**Template:** T01
**Priority:** P0

Show:

* Active batches
* Attendance
* Training
* Exams
* Faculty
* Certificates

---

## DASH-04 — Finance Dashboard

**Template:** T01
**Priority:** P0

Show:

* Revenue
* Collections
* Outstanding
* Due
* Refunds
* Payment trend

---

## DASH-05 — Operations Dashboard

**Template:** T01
**Priority:** P1

Show:

* Tasks
* Training
* Compliance
* Communication
* Issues
* Alerts

---

# 16. GROW

## GROW-01 — Marketing Dashboard

**Template:** T01
**Priority:** P1

---

## GROW-02 — Campaigns

**Template:** T02
**Priority:** P1

---

## GROW-03 — Campaign Detail

**Template:** T03
**Priority:** P1

---

## GROW-04 — Website Dashboard

**Template:** T01
**Priority:** P1

---

## GROW-05 — Website Pages

**Template:** T02
**Priority:** P1

---

## GROW-06 — Website Page Editor

**Template:** T04
**Priority:** P1

Responsive preview required.

---

## GROW-07 — Lead Sources

**Template:** T02
**Priority:** P1

---

## GROW-08 — Lead List

**Template:** T02
**Priority:** P0

---

## GROW-09 — Lead Detail

**Template:** T03
**Priority:** P0

---

## GROW-10 — Lead Import

**Template:** T05
**Priority:** P1

---

## GROW-11 — Content & Social

**Template:** T02
**Priority:** P1

---

## GROW-12 — Social Content Calendar

**Template:** T07
**Priority:** P1

Mobile calendar must support alternative list/day views.

---

# 17. ADMISSIONS

## ADM-01 — Admissions Dashboard

**Template:** T01
**Priority:** P0

---

## ADM-02 — Lead Pipeline

**Template:** T06
**Priority:** P0

Pipeline:

```text
New
→ Contacted
→ Counselling
→ Application
→ Review
→ Approved
→ Enrolled
→ Lost
```

Mobile may use horizontal stage scrolling or list representation.

---

## ADM-03 — Counselling Queue

**Template:** T02
**Priority:** P0

---

## ADM-04 — Counselling Detail

**Template:** T03
**Priority:** P0

Show:

* Lead
* Counsellor
* History
* Notes
* Follow-ups
* AI suggestions

---

## ADM-05 — Applications

**Template:** T02
**Priority:** P0

---

## ADM-06 — Application Detail

**Template:** T03
**Priority:** P0

---

## ADM-07 — New Application

**Template:** T05
**Priority:** P0

---

## ADM-08 — Application Review

**Template:** T03
**Priority:** P0

---

## ADM-09 — Document Verification

**Template:** T03
**Priority:** P0

Show:

* Document
* Status
* Verification
* Reviewer
* Comments

---

## ADM-10 — Admission Approval

**Template:** T03
**Priority:** P0

Approval must require appropriate permission.

---

## ADM-11 — Students

**Template:** T02
**Priority:** P0

---

## ADM-12 — Student Profile

**Template:** T03
**Priority:** P0

Sections:

* Personal
* Admission
* Course
* Batch
* Attendance
* Fees
* Training
* Exams
* Certificates
* Placement
* Documents
* Communication
* Activity

Mobile should use tabs/sections rather than a dense desktop layout.

---

## ADM-13 — Student Admission

**Template:** T03
**Priority:** P0

---

## ADM-14 — Student Documents

**Template:** T02
**Priority:** P0

---

## ADM-15 — Student Communication

**Template:** T08
**Priority:** P1

---

# 18. ACADEMICS

## ACA-01 — Courses

**Template:** T02
**Priority:** P0

---

## ACA-02 — Course Detail

**Template:** T03
**Priority:** P0

---

## ACA-03 — Create Course

**Template:** T04
**Priority:** P0

---

## ACA-04 — Course Curriculum

**Template:** T03
**Priority:** P1

---

## ACA-05 — Batches

**Template:** T02
**Priority:** P0

---

## ACA-06 — Batch Detail

**Template:** T03
**Priority:** P0

---

## ACA-07 — Create Batch

**Template:** T04
**Priority:** P0

---

## ACA-08 — Timetable

**Template:** T07
**Priority:** P0

Mobile should provide:

* Day view
* List view

---

## ACA-09 — Timetable Editor

**Template:** T07
**Priority:** P0

Desktop can support richer scheduling interactions.

Mobile should use a simplified editor.

---

## ACA-10 — Attendance

**Template:** T02
**Priority:** P0

---

## ACA-11 — Attendance Detail

**Template:** T03
**Priority:** P1

---

## ACA-12 — Faculty

**Template:** T02
**Priority:** P0

---

## ACA-13 — Faculty Profile

**Template:** T03
**Priority:** P1

---

## ACA-14 — Faculty Allocation

**Template:** T04
**Priority:** P1

---

## ACA-15 — Training Dashboard

**Template:** T01
**Priority:** P0

---

## ACA-16 — Training Plan

**Template:** T03
**Priority:** P0

---

## ACA-17 — Training Session

**Template:** T07
**Priority:** P0

---

## ACA-18 — Training Session Detail

**Template:** T03
**Priority:** P0

---

## ACA-19 — Training Progress

**Template:** T03
**Priority:** P0

Progress must be understandable without relying only on color.

---

## ACA-20 — Examinations

**Template:** T02
**Priority:** P0

---

## ACA-21 — Examination Detail

**Template:** T03
**Priority:** P0

---

## ACA-22 — Examination Schedule

**Template:** T07
**Priority:** P0

---

## ACA-23 — Results

**Template:** T02
**Priority:** P0

---

## ACA-24 — Certificates

**Template:** T02
**Priority:** P0

---

## ACA-25 — Certificate Detail

**Template:** T03
**Priority:** P1

---

## ACA-26 — Certificate Generation

**Template:** T04
**Priority:** P1

---

## ACA-27 — Academic Reports

**Template:** T10
**Priority:** P1

---

# 19. FINANCE

## FIN-01 — Finance Dashboard

**Template:** T01
**Priority:** P0

---

## FIN-02 — Fee Structure

**Template:** T02
**Priority:** P0

---

## FIN-03 — Fee Structure Detail

**Template:** T03
**Priority:** P0

---

## FIN-04 — Invoices

**Template:** T02
**Priority:** P0

---

## FIN-05 — Invoice Detail

**Template:** T03
**Priority:** P0

---

## FIN-06 — Payments

**Template:** T02
**Priority:** P0

---

## FIN-07 — Payment Detail

**Template:** T03
**Priority:** P1

---

## FIN-08 — Outstanding

**Template:** T02
**Priority:** P0

---

## FIN-09 — Refunds

**Template:** T02
**Priority:** P1

---

## FIN-10 — Finance Reports

**Template:** T10
**Priority:** P1

---

# 20. COMPLIANCE

## COM-01 — Compliance Dashboard

**Template:** T01
**Priority:** P0

---

## COM-02 — Requirements

**Template:** T02
**Priority:** P0

---

## COM-03 — Requirement Detail

**Template:** T03
**Priority:** P0

---

## COM-04 — Compliance Documents

**Template:** T02
**Priority:** P0

---

## COM-05 — Inspections

**Template:** T02
**Priority:** P1

---

## COM-06 — Inspection Detail

**Template:** T03
**Priority:** P1

---

## COM-07 — Corrective Actions

**Template:** T02
**Priority:** P1

---

## COM-08 — Compliance Audit

**Template:** T10
**Priority:** P1

---

# 21. PLACEMENT

## PLC-01 — Placement Dashboard

**Template:** T01
**Priority:** P1

---

## PLC-02 — Eligible Students

**Template:** T02
**Priority:** P1

---

## PLC-03 — Companies

**Template:** T02
**Priority:** P1

---

## PLC-04 — Company Detail

**Template:** T03
**Priority:** P1

---

## PLC-05 — Opportunities

**Template:** T02
**Priority:** P1

---

## PLC-06 — Opportunity Detail

**Template:** T03
**Priority:** P1

---

## PLC-07 — Placement Tracking

**Template:** T06
**Priority:** P1

---

## PLC-08 — Alumni

**Template:** T02
**Priority:** P2

---

# 22. COMMUNICATION

## COMMS-01 — WhatsApp Workspace

**Template:** T08
**Priority:** P0

Desktop:

```text
Conversation List | Conversation | Context
```

Mobile:

```text
List → Conversation → Context Drawer
```

---

## COMMS-02 — Email Workspace

**Template:** T08
**Priority:** P1

---

## COMMS-03 — SMS

**Template:** T02
**Priority:** P1

---

## COMMS-04 — Voice

**Template:** T08
**Priority:** P1

---

## COMMS-05 — Conversation Detail

**Template:** T03
**Priority:** P0

---

## COMMS-06 — Contacts

**Template:** T02
**Priority:** P1

---

## COMMS-07 — Templates

**Template:** T02
**Priority:** P1

---

## COMMS-08 — Template Editor

**Template:** T04
**Priority:** P1

---

## COMMS-09 — Broadcasts

**Template:** T02
**Priority:** P1

---

## COMMS-10 — Broadcast Detail

**Template:** T03
**Priority:** P1

---

## COMMS-11 — Communication Analytics

**Template:** T10
**Priority:** P1

---

# 23. AUTOMATION

## AUTO-01 — Workflow List

**Template:** T02
**Priority:** P1

---

## AUTO-02 — Workflow Builder

**Template:** T11
**Priority:** P1

Desktop-first visual builder with responsive fallback.

---

## AUTO-03 — AI Agents

**Template:** T02
**Priority:** P1

---

## AUTO-04 — Agent Detail

**Template:** T03
**Priority:** P1

---

## AUTO-05 — Executions

**Template:** T02
**Priority:** P0

---

## AUTO-06 — Execution Detail

**Template:** T03
**Priority:** P0

Show:

* Trigger
* Agent
* Tools
* Data
* Decision
* Result
* Latency
* Status

---

# 24. AI

## AI-01 — AI Assistant

**Template:** T09
**Priority:** P0

Desktop:

```text
Conversation | Context
```

Mobile:

```text
Conversation
↓
Context Drawer
```

---

## AI-02 — AI Resolution

**Template:** T09
**Priority:** P1

---

## AI-03 — AI Knowledge

**Template:** T02
**Priority:** P1

---

## AI-04 — Knowledge Detail

**Template:** T03
**Priority:** P1

---

## AI-05 — AI Analytics

**Template:** T10
**Priority:** P1

---

## AI-06 — SQL / Data Agent

**Template:** T09
**Priority:** P1

Must clearly display:

* tenant scope
* data scope
* read-only status
* query/result
* permission

---

## AI-07 — AI Execution

**Template:** T03
**Priority:** P0

---

## AI-08 — AI Configuration

**Template:** T15
**Priority:** P0

---

## AI-09 — AI Guardrails

**Template:** T15
**Priority:** P0

---

# 25. ANALYTICS

## ANA-01 — Executive Analytics

**Template:** T10
**Priority:** P1

---

## ANA-02 — Admissions Analytics

**Template:** T10
**Priority:** P1

---

## ANA-03 — Finance Analytics

**Template:** T10
**Priority:** P1

---

## ANA-04 — Academic Analytics

**Template:** T10
**Priority:** P1

---

## ANA-05 — Marketing Analytics

**Template:** T10
**Priority:** P1

---

## ANA-06 — AI Analytics

**Template:** T10
**Priority:** P1

---

# 26. TENANT ADMINISTRATION

## ADMIN-01 — Institute Profile

**Template:** T03 / T04
**Priority:** P0

---

## ADMIN-02 — Institute Branding

**Template:** T15
**Priority:** P1

---

## ADMIN-03 — Campuses

**Template:** T02
**Priority:** P0

---

## ADMIN-04 — Campus Detail

**Template:** T03
**Priority:** P0

---

## ADMIN-05 — Users

**Template:** T02
**Priority:** P0

---

## ADMIN-06 — User Detail

**Template:** T03
**Priority:** P0

---

## ADMIN-07 — Roles & Permissions

**Template:** T15
**Priority:** P0

---

## ADMIN-08 — Integrations

**Template:** T15
**Priority:** P1

---

## ADMIN-09 — AI Configuration

**Template:** T15
**Priority:** P0

---

## ADMIN-10 — Notifications

**Template:** T15
**Priority:** P1

---

## ADMIN-11 — Billing

**Template:** T15
**Priority:** P1

---

## ADMIN-12 — Audit Logs

**Template:** T02
**Priority:** P0

---

## ADMIN-13 — Settings

**Template:** T15
**Priority:** P0

### Includes

* Appearance
* Theme
* Light
* Dark
* System
* Notification preferences
* Localization
* Security preferences

---

## ADMIN-14 — Security

**Template:** T15
**Priority:** P0

---

# 27. STUDENT PORTAL

Student Portal is a separate experience.

Primary design principle:

> Mobile-first, simple, progress-oriented.

---

## STU-01 — Student Login

**Template:** T16
**Priority:** P0

---

## STU-02 — Student Dashboard

**Template:** T17
**Priority:** P0

Show:

* Course
* Attendance
* Training progress
* Upcoming classes
* Exams
* Fees
* Certificates
* Placement

Mobile-first.

---

## STU-03 — My Course

**Template:** T17
**Priority:** P0

---

## STU-04 — Attendance

**Template:** T17
**Priority:** P0

---

## STU-05 — Training

**Template:** T17
**Priority:** P0

---

## STU-06 — Examinations

**Template:** T17
**Priority:** P0

---

## STU-07 — Fees

**Template:** T17
**Priority:** P0

---

## STU-08 — Certificates

**Template:** T17
**Priority:** P0

---

## STU-09 — Placement

**Template:** T17
**Priority:** P1

---

## STU-10 — Profile

**Template:** T17
**Priority:** P1

---

# 28. PUBLIC WEBSITE

Public website is a marketing/conversion experience.

---

## PUB-01 — Home

**Template:** T18
**Priority:** P0

Sections:

* Hero
* Value proposition
* Courses
* Institute credibility
* Outcomes
* Features
* CTA

---

## PUB-02 — Features

**Template:** T18
**Priority:** P1

---

## PUB-03 — Solutions

**Template:** T18
**Priority:** P1

---

## PUB-04 — Pricing

**Template:** T18
**Priority:** P1

---

## PUB-05 — Request Demo

**Template:** T18
**Priority:** P0

---

## PUB-06 — Contact

**Template:** T18
**Priority:** P1

---

# 29. SCREEN INVENTORY SUMMARY

## Platform

```text
53 screens
```

## Tenant Application

```text
~153 screens
```

## Student Portal

```text
10 screens
```

## Public Website

```text
6 screens
```

## Total

```text
~222 screens
```

The count is a planning metric.

It does **not** mean 222 completely independent UI implementations.

---

# 30. SCREEN IMPLEMENTATION MODEL

The target architecture is:

```text
~222 Screens
      ↓
18 Page Templates
      ↓
30–50 Core Components
      ↓
Shared Design Tokens
      ↓
Light / Dark / System
      ↓
Responsive Rules
      ↓
Accessible UI
```

---

# 31. FOUNDATION SCREENS

Before generating all screens, establish the following foundation screens.

## Platform

```text
PLAT-03 Platform Dashboard
PLAT-04 Tenant List
PLAT-05 Tenant 360
PLAT-06 Create Tenant
PLAT-13 Billing & Invoices
PLAT-25 System Health
```

## Tenant

```text
DASH-01 Executive Dashboard
ADM-01 Admissions Dashboard
ADM-02 Lead Pipeline
ADM-12 Student Profile
ACA-02 Course Detail
ACA-06 Batch Detail
FIN-01 Finance Dashboard
COMMS-01 WhatsApp Workspace
AI-01 AI Assistant
ADMIN-01 Institute Profile
```

## Student

```text
STU-02 Student Dashboard
STU-03 My Course
STU-07 Fees
STU-08 Certificates
```

## Public

```text
PUB-01 Home
PUB-02 Features
PUB-05 Request Demo
```

---

# 32. FOUNDATION VALIDATION MATRIX

Foundation screens must be reviewed in:

| Experience | Light | Dark | Mobile | Tablet | Desktop |
| ---------- | ----: | ---: | -----: | -----: | ------: |
| Platform   |     ✓ |    ✓ |      ✓ |      ✓ |       ✓ |
| Tenant     |     ✓ |    ✓ |      ✓ |      ✓ |       ✓ |
| Student    |     ✓ |    ✓ |      ✓ |      ✓ |       ✓ |
| Public     |     ✓ |    ✓ |      ✓ |      ✓ |       ✓ |

---

# 33. SCREEN DESIGN DEFINITION OF DONE

A screen is complete only when:

### Product

* Correct purpose
* Correct persona
* Correct workflow
* Correct navigation

### Design

* Correct template
* Correct components
* Correct design tokens
* Correct maritime identity

### Theme

* Light
* Dark
* System compatibility

### Responsive

* Mobile
* Tablet
* Desktop
* Large Desktop

### States

* Loading
* Empty
* Populated
* Error
* Permission
* Success where applicable

### Accessibility

* Keyboard
* Focus
* Contrast
* Labels
* Screen reader
* Touch targets

### Security

* Tenant context
* Permission behavior
* Sensitive action confirmation

### AI

Where applicable:

* Suggestion vs action
* Human confirmation
* Execution visibility
* Source/context
* Confidence where appropriate

---

# 34. RESPONSIVE SCREEN CHECKLIST

For every screen verify:

```text
□ No horizontal overflow unless intentionally designed
□ No clipped text
□ No inaccessible controls
□ Navigation adapts
□ Forms adapt
□ Tables adapt
□ Charts adapt
□ Dialogs adapt
□ Drawers adapt
□ Actions remain discoverable
□ Primary action remains obvious
□ Touch targets are appropriate
□ Mobile information hierarchy is intentional
```

---

# 35. THEME SCREEN CHECKLIST

For every screen verify:

```text
□ Light Mode
□ Dark Mode
□ System preference
□ Text contrast
□ Border contrast
□ Button states
□ Input states
□ Table states
□ Chart readability
□ Status badges
□ Dialogs
□ Drawers
□ AI components
□ Focus indicators
□ Disabled states
```

---

# 36. CROSS-SCREEN CONSISTENCY

The following must remain consistent:

* Sidebar
* Top bar
* Page headers
* Breadcrumbs
* Buttons
* Forms
* Tables
* Filters
* Cards
* Tabs
* Drawers
* Dialogs
* Notifications
* Status badges
* Charts
* AI components
* Loading states
* Empty states
* Error states
* Theme switching
* Responsive behavior

---

# 37. MOBILE-FIRST EXCEPTIONS

Not every experience should use identical mobile behavior.

### Student Portal

Mobile-first.

### Public Website

Mobile-first responsive.

### Tenant Application

Desktop-first enterprise workflow with intentional mobile adaptation.

### Platform Control Plane

Desktop-first operational interface with responsive support for essential workflows.

---

# 38. DESIGN PRINCIPLE FOR MOBILE

Do not ask:

> How do we fit the desktop screen onto mobile?

Ask:

> What is the most useful mobile experience for this workflow?

---

# 39. DESIGN PRINCIPLE FOR DARK MODE

Do not ask:

> How do we make the Light Mode dark?

Ask:

> What is the best dark enterprise experience using the MTI 360 maritime palette?

---

# 40. DESIGN PRINCIPLE FOR REUSE

Do not ask:

> How can this screen look different?

Ask:

> Which existing template and components best express this workflow?

---

# 41. DESIGN PRINCIPLE FOR AI

Do not ask:

> Where can we add AI?

Ask:

> Where can AI meaningfully reduce effort while preserving user control and trust?

---

# 42. FINAL UI ARCHITECTURE

```text
MTI 360
│
├── Platform Control Plane
│      └── 53 screens
│
├── Tenant Application
│      └── ~153 screens
│
├── Student Portal
│      └── 10 screens
│
└── Public Website
       └── 6 screens

Shared Foundation
│
├── Design Tokens
├── Light Theme
├── Dark Theme
├── System Theme
├── Responsive System
├── Accessibility System
├── Component Library
└── Page Templates
```

---

# 43. FINAL UI PRINCIPLE

MTI 360 is not:

```text
222 isolated screens
```

It is:

```text
One Product
    ↓
Four Experiences
    ↓
One Design Language
    ↓
Three Theme Modes
    ↓
Responsive Layout System
    ↓
Reusable Components
    ↓
Reusable Page Templates
    ↓
~222 Business Screens
```

Every screen must feel like it belongs to the same product.

Every screen must work across supported devices.

Every screen must support the MTI 360 theme system.

Every screen must preserve accessibility.

Every screen must preserve tenant/security context.

Every screen must support realistic operational workflows.

---

# END OF UI-SCREENS.md
