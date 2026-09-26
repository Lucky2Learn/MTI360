# CLAUDE.md

# MTI 360 — Engineering Constitution

**Product:** MTI 360
**Positioning:** The Complete Growth & Operations Platform for Maritime Training Institutes
**Tagline:** Acquire Students. Simplify Operations. Grow Your Institute.

---

# 1. PURPOSE

This document is the primary engineering constitution for **MTI 360**.

Claude Code MUST follow this document when:

* designing implementation approaches
* creating or modifying code
* creating database models
* creating APIs
* implementing authentication
* implementing authorization
* implementing tenant isolation
* implementing UI
* implementing responsive layouts
* implementing Light/Dark/System themes
* implementing AI functionality
* creating integrations
* writing tests
* refactoring
* fixing defects
* reviewing implementation
* preparing production-ready code

This document defines **engineering rules and implementation discipline**.

It does not replace the product specification.

---

# 2. SOURCE OF TRUTH

Before implementing any substantial feature, Claude Code MUST understand the following documents.

Recommended reading order:

1. `PRD.md`
2. `APP-FLOW.md`
3. `ARCHITECTURE.md`
4. `PLATFORM-ADMIN.md`
5. `DESIGN-SYSTEM.md`
6. `UI-SCREENS.md`
7. `TASKS.md`
8. `DEVELOPMENT-STATUS.md`

For UI implementation, the relevant hierarchy is:

```text
PRD
 ↓
APP-FLOW
 ↓
ARCHITECTURE
 ↓
DESIGN-SYSTEM
 ↓
UI-SCREENS
 ↓
Implementation
```

For engineering execution:

```text
CLAUDE.md
 ↓
TASKS.md
 ↓
Existing Repository
 ↓
Implementation
 ↓
Tests
 ↓
DEVELOPMENT-STATUS.md
```

If documents conflict:

1. Security requirements take highest priority.
2. Architecture constraints take priority over implementation convenience.
3. Product requirements take priority over assumptions.
4. Design-system rules take priority over arbitrary UI choices.
5. Existing production behavior must be preserved unless the task explicitly changes it.

Never invent requirements simply to make implementation easier.

---

# 3. PRODUCT UNDERSTANDING

MTI 360 is a multi-tenant SaaS platform for Maritime Training Institutes.

The platform supports the complete institute lifecycle:

```text
Acquire
   ↓
Convert
   ↓
Admit
   ↓
Train
   ↓
Collect
   ↓
Communicate
   ↓
Comply
   ↓
Place
   ↓
Grow
```

Major business capabilities include:

* Marketing
* Campaigns
* Website
* Lead Management
* Content & Social
* Counselling
* Applications
* Documents
* Students
* Courses
* Batches
* Timetable
* Attendance
* Faculty
* Training
* Examinations
* Certificates
* Finance
* Compliance
* Placement
* Alumni
* WhatsApp
* Email
* SMS
* Voice
* Templates
* Workflows
* AI Agents
* AI Executions
* Analytics
* Tenant Administration
* Student Portal
* Public Website

---

# 4. FOUR PRODUCT EXPERIENCES

MTI 360 consists of four distinct experiences.

## 4.1 Platform / SaaS Control Plane

Used by MTI 360 platform administrators.

Responsibilities include:

* Tenant management
* Subscription management
* Plans
* Billing
* Usage
* Platform integrations
* AI providers
* AI governance
* Support
* Security
* Audit
* Platform analytics
* Provisioning
* System health
* Feature flags
* Platform administration

Platform users MUST NOT automatically behave as tenant users.

---

## 4.2 Tenant Application

Used by Maritime Training Institutes.

Tenant users manage:

* Students
* Leads
* Admissions
* Academics
* Finance
* Compliance
* Placement
* Communication
* Automation
* AI
* Analytics
* Institute administration

---

## 4.3 Student Portal

Used by students.

The Student Portal is:

* separate from the tenant administration experience
* mobile-first
* simplified
* task-oriented
* responsive
* accessible

---

## 4.4 Public Website

Used by prospective students and public visitors.

The Public Website is:

* public
* responsive
* SEO-aware
* mobile-first
* conversion-oriented
* visually connected to the tenant's branding where applicable

---

# 5. MULTI-TENANT ARCHITECTURE

The core hierarchy is:

```text
MTI 360 Platform
       │
       ├── Tenant A
       │      ├── Campus
       │      ├── Users
       │      ├── Students
       │      └── Operations
       │
       ├── Tenant B
       │      ├── Campus
       │      ├── Users
       │      ├── Students
       │      └── Operations
       │
       └── Tenant C
              ├── Campus
              ├── Users
              ├── Students
              └── Operations
```

Tenant isolation is a fundamental security boundary.

## NEVER:

* trust a tenant ID supplied by the browser
* trust a tenant ID from arbitrary request payloads
* implement tenant isolation only in React/Next.js
* rely on hidden UI elements for authorization
* allow an authenticated user to query another tenant
* hardcode tenant IDs
* use global mutable tenant state without authorization
* bypass tenant filtering for convenience

Tenant context MUST be derived and validated server-side.

---

# 6. TENANT CONTEXT

Tenant context may be established from trusted sources such as:

* authenticated session
* validated access token
* server-side channel configuration
* trusted domain mapping
* authorized platform support session

The server MUST validate that the authenticated principal has access to the resolved tenant.

Never accept:

```text
tenant_id = request.body.tenant_id
```

as sufficient authorization.

Tenant identity is a security decision, not a UI parameter.

---

# 7. PLATFORM ADMIN VS TENANT ADMIN

These are different security domains.

## Platform Admin

Can potentially manage:

```text
All tenants
Plans
Subscriptions
Billing
Usage
Providers
Platform integrations
Platform AI
Support
Security
Audit
System health
```

## Tenant Admin

Can manage only:

```text
Own institute
Own campuses
Own users
Own students
Own operations
Own configuration
```

A tenant administrator MUST NOT gain platform-level access.

A platform administrator MUST use explicit platform capabilities to access tenant information.

---

# 8. CONTROLLED SUPPORT ACCESS

Platform support access to a tenant must be explicit.

A support session MUST:

* identify the target tenant
* identify the support user
* display a visible support-session indicator
* have an explicit purpose
* respect permissions
* be auditable
* have limited duration where appropriate
* provide a clear exit mechanism

Example:

```text
SUPPORT SESSION
ABC Maritime Training Institute
Read Only
Started 10:42 AM
[Exit Session]
```

Never silently impersonate a tenant administrator.

All sensitive support actions MUST be logged.

---

# 9. AUTHENTICATION

Authentication must be implemented centrally and consistently.

Support:

* secure login
* password reset
* MFA where required
* session management
* logout
* session expiration
* access denied
* appropriate rate limiting
* secure credential handling

Never:

* store passwords in plaintext
* expose secrets in frontend code
* bypass authentication for convenience
* create hidden development authentication paths in production
* log passwords, tokens or secrets

---

# 10. AUTHORIZATION

Authorization must be enforced server-side.

Use appropriate mechanisms such as:

* roles
* permissions
* resource ownership
* tenant scope
* campus scope
* feature entitlements
* subscription entitlements

UI permission hiding is useful for UX but is NOT security.

For example:

```text
PermissionGate
```

may hide a button.

The backend must still reject an unauthorized request.

---

# 11. ROLE-BASED ACCESS CONTROL

The platform and tenant roles are separate.

Platform examples:

* Super Admin
* Platform Operations Admin
* Customer Success Admin
* Billing Admin
* Support Admin
* Security/Audit Admin
* AI/Platform Admin

Tenant roles may include:

* Tenant Admin
* Admissions Manager
* Counsellor
* Faculty
* Finance User
* Compliance User
* Placement User
* Communication User
* AI Manager
* Analyst

Do not assume that a role has permission simply because a screen exists.

Permissions must be explicit.

---

# 12. SUBSCRIPTION & FEATURE ENTITLEMENTS

Tenant access may depend on:

* subscription
* plan
* feature entitlement
* usage limits
* account status

Tenant lifecycle:

```text
PROSPECT
   ↓
TRIAL
   ↓
PROVISIONING
   ↓
ACTIVE
   ↓
PAST_DUE
   ↓
SUSPENDED
   ↓
CANCELLED
   ↓
DEACTIVATED
```

Where appropriate:

```text
SUSPENDED → ACTIVE
```

Feature access MUST be validated server-side.

---

# 13. RESPONSIVE DESIGN — MANDATORY

**Responsive design is a mandatory product requirement.**

Every screen and component MUST work across:

```text
Mobile       390–767
Tablet       768–1023
Desktop      1024–1439
Large        1440+
```

Responsive design means adaptation, not simple scaling.

Claude Code MUST consider:

* navigation
* page layout
* cards
* tables
* filters
* forms
* charts
* dashboards
* dialogs
* drawers
* action bars
* toolbars
* tabs
* timelines
* Kanban
* calendars
* communication workspaces

---

# 14. RESPONSIVE IMPLEMENTATION RULES

## Desktop

Use:

* multi-column layouts
* persistent navigation
* wide tables
* dashboard grids
* side panels where useful

## Tablet

Adapt:

* navigation
* grid columns
* tables
* forms
* filters
* dashboards

## Mobile

Prefer:

* stacked layouts
* mobile navigation
* drawers
* cards
* horizontal scrolling only where appropriate
* collapsible sections
* sticky primary actions where useful
* touch-friendly controls

Never allow:

* accidental horizontal page overflow
* unreadable tables
* clipped buttons
* inaccessible dialogs
* tiny controls
* overlapping content

---

# 15. MOBILE-FIRST EXCEPTIONS

The following are explicitly mobile-first:

* Student Portal
* Public Website

The following are desktop-first but MUST adapt intentionally:

* Platform Control Plane
* Tenant Application

---

# 16. LIGHT / DARK / SYSTEM THEMES — MANDATORY

MTI 360 MUST support:

```text
Light
Dark
System
```

Theme preference must persist.

Every screen and component MUST support both Light and Dark modes.

Do not implement dark mode as:

```text
invert(colors)
```

or as an automatic inversion of Light mode.

Dark mode must be intentionally designed.

---

# 17. LIGHT THEME

Primary Light theme direction:

```text
Pearl
Ice
Deep Ocean
Sea Glass
Restrained Brass
```

Light mode should feel:

* premium
* clean
* calm
* maritime
* enterprise
* readable

---

# 18. DARK THEME

Dark mode must use the MTI 360 palette.

Primary surfaces:

```text
Midnight
Deep Ocean
Ocean
```

Accents:

```text
Sea Glass
Restrained Brass
```

Text:

```text
Pearl
Ice
```

Dark mode must include intentional treatment for:

* surfaces
* borders
* cards
* tables
* inputs
* buttons
* charts
* dialogs
* drawers
* notifications
* AI panels
* focus states
* disabled states
* semantic states

Do not simply replace white with black.

---

# 19. SYSTEM THEME

When the user selects:

```text
System
```

MTI 360 should follow the operating system preference.

The user must be able to explicitly select:

```text
Light
Dark
System
```

Theme selection belongs in an appropriate global appearance control, such as the user menu/settings.

---

# 20. DESIGN SYSTEM

Use `DESIGN-SYSTEM.md` as the source of truth for visual tokens.

Do not invent arbitrary colors.

Do not create one-off typography scales.

Do not introduce random spacing values.

Do not create unrelated border radii.

Use shared tokens.

---

# 21. MTI 360 VISUAL IDENTITY

The visual identity is:

```text
Deep Ocean
Sea Glass
Pearl
Ice
Restrained Brass
```

The interface should feel:

* premium
* maritime
* trustworthy
* intelligent
* modern
* calm
* enterprise-grade

Avoid:

* generic blue SaaS appearance
* excessive gradients
* neon colors
* excessive glassmorphism
* cartoon-like maritime graphics
* decorative waves everywhere
* legacy ERP visual language

Maritime references should remain subtle.

Examples:

* navigation lines
* compass-inspired micro-icons
* route visualization
* port references
* ocean-depth layering

---

# 22. COLOR RATIO

Target approximate visual balance:

```text
60%  Neutral / Pearl / Ice
25%  Ocean / Midnight
10%  Sea Glass
5%   Brass / AI / Semantic accents
```

Do not overuse accent colors.

---

# 23. TYPOGRAPHY

Preferred:

```text
Inter
```

Alternative:

```text
Plus Jakarta Sans
```

Typography must follow the design system.

Do not introduce arbitrary font sizes without reason.

---

# 24. UI ARCHITECTURE

MTI 360 contains approximately 222 business screens.

Do NOT build 222 isolated designs.

Use:

```text
~222 Screens
      ↓
18 Page Templates
      ↓
30–50 Shared Components
      ↓
Shared Design Tokens
      ↓
Light / Dark / System
      ↓
Responsive Layout System
```

Reuse is mandatory.

---

# 25. PAGE TEMPLATES

The platform defines these templates:

```text
T01 Dashboard
T02 Data List
T03 Detail
T04 Form
T05 Wizard
T06 Kanban
T07 Calendar
T08 Communication Workspace
T09 AI Workspace
T10 Analytics
T11 Workflow Builder
T12 Tenant 360
T13 Platform Operations
T14 Support Workspace
T15 Settings
T16 Authentication
T17 Student Portal
T18 Public Website
```

When implementing a screen:

1. Identify its template.
2. Reuse the template.
3. Reuse shared components.
4. Apply screen-specific configuration.
5. Avoid duplicating layout code.

---

# 26. COMPONENT-FIRST DEVELOPMENT

Build reusable components before duplicating UI.

Core components include:

```text
AppShell
Sidebar
TopBar
PageHeader
Breadcrumb
GlobalSearch
TenantContext
CampusSwitcher
NotificationCenter
UserMenu

Button
IconButton
Input
Select
Combobox
DatePicker
FileUpload
Tabs

Card
Badge
DataTable
FilterBar
Pagination
Drawer
Modal
Dialog
Toast
Alert

Timeline
KPI
ChartCard
EmptyState
ErrorState
Skeleton
PermissionGate
```

---

# 27. ENTERPRISE COMPONENTS

Use reusable enterprise components such as:

```text
TenantHealthCard
SubscriptionCard
UsageMeter
RevenueCard
PlatformHealthCard
IncidentCard
SupportSessionBanner
AuditTimeline
ProvisioningProgress
SystemStatus
```

---

# 28. TENANT COMPONENTS

Examples:

```text
AdmissionFunnel
StudentCard
CourseCard
BatchCard
TrainingProgress
AttendanceSummary
FeeSummary
ComplianceSummary
PlacementPipeline
```

---

# 29. AI COMPONENTS

Examples:

```text
AIAssistant
AISuggestion
AIAction
AIExecution
AISource
AIConfidence
AIApproval
```

AI components must be visually distinguishable but restrained.

Do not turn every screen into an AI interface.

---

# 30. SCREEN IMPLEMENTATION

Every screen should consider:

```text
Purpose
Persona
Experience
Navigation
Template
Primary action
Secondary actions
Information architecture
Permissions
Loading
Empty
Populated
Error
Success
Responsive behavior
Light theme
Dark theme
Accessibility
```

Refer to `UI-SCREENS.md`.

---

# 31. STANDARD SCREEN STRUCTURE

Where applicable:

```text
App Shell
    ↓
Page Header
    ↓
Breadcrumb / Context
    ↓
Primary Actions
    ↓
Filters / Tabs
    ↓
Main Content
    ↓
Secondary Information
    ↓
Pagination / Footer
```

Do not force this structure where another template is more appropriate.

---

# 32. DASHBOARDS

Dashboards must be useful, not decorative.

Prioritize:

* KPIs
* trends
* actionable alerts
* exceptions
* operational queues
* recent activity
* drill-downs

Avoid:

* excessive charts
* meaningless metrics
* decorative visualizations
* overcrowded cards

Dashboards must adapt responsively.

---

# 33. DATA TABLES

Tables must support appropriate combinations of:

* sorting
* filtering
* pagination
* search
* row actions
* column visibility
* responsive behavior
* empty states
* loading states

On mobile, large tables should use appropriate strategies such as:

* horizontal scrolling
* condensed columns
* card/list transformation
* row expansion

Do not squeeze every desktop column into a mobile viewport.

---

# 34. FORMS

Forms must provide:

* clear labels
* validation
* required indicators
* helpful errors
* appropriate grouping
* responsive layout
* keyboard accessibility
* loading state
* submission state

Never rely only on color to communicate validation.

---

# 35. LOADING STATES

Use:

* skeletons
* progress indicators
* disabled action states

Avoid unnecessary blocking spinners.

Loading states must preserve layout stability where possible.

---

# 36. EMPTY STATES

Every meaningful list/workspace should have an intentional empty state.

An empty state should explain:

```text
What is empty?
Why is it empty?
What can the user do next?
```

Where appropriate provide a primary action.

---

# 37. ERROR STATES

Errors must be:

* understandable
* actionable
* non-technical where possible
* appropriately logged
* secure

Do not expose:

* stack traces
* SQL
* secrets
* internal infrastructure details
* provider credentials

to end users.

---

# 38. ACCESSIBILITY

MTI 360 targets:

**WCAG 2.2 AA**

Implement:

* keyboard navigation
* visible focus states
* semantic HTML
* sufficient contrast
* accessible labels
* accessible form errors
* screen-reader support
* non-color status indicators
* reduced-motion support
* touch targets around 44px where appropriate

Accessibility must work in both Light and Dark themes.

---

# 39. DATABASE RULES

Database access must follow architecture boundaries.

Do not:

* duplicate schema logic
* bypass repositories/services without architectural justification
* embed business logic inside UI
* execute arbitrary SQL from frontend code
* expose database credentials
* create cross-tenant queries without explicit authorization

All tenant-scoped queries must enforce tenant boundaries.

---

# 40. API RULES

APIs must:

* validate inputs
* authenticate requests
* authorize requests
* enforce tenant boundaries
* validate resource ownership
* return consistent errors
* avoid leaking internal information
* support appropriate pagination/filtering
* avoid unnecessary payloads

Never trust frontend-provided authorization decisions.

---

# 41. BUSINESS LOGIC

Business logic belongs in appropriate backend/domain/service layers.

Do not duplicate the same business rule in:

```text
Frontend
API controller
Service
Database trigger
AI agent
```

unless the duplication is deliberate and documented.

Prefer one authoritative implementation.

---

# 42. AI ARCHITECTURE

MTI 360 is AI-enabled but AI must remain governed.

AI may:

* understand requests
* summarize information
* classify
* recommend
* draft
* retrieve knowledge
* execute approved tools
* assist users

AI must not automatically receive unrestricted system access.

---

# 43. AI TOOL GOVERNANCE

AI tools must be:

* explicitly registered
* permission-aware
* tenant-aware
* auditable
* validated
* appropriately scoped

Never allow an AI agent direct unrestricted database access.

Preferred architecture:

```text
AI Agent
   ↓
Tool
   ↓
Authorized Service
   ↓
Repository / Domain
   ↓
Database
```

Not:

```text
AI Agent
   ↓
Raw Database
```

---

# 44. AI ACTIONS

Distinguish between:

```text
Suggestion
```

and:

```text
Action
```

Low-risk actions may be automated where explicitly permitted.

Sensitive actions should require confirmation.

Examples:

* sending external communication
* changing financial information
* approving admissions
* modifying compliance records
* deleting data
* changing permissions

should have appropriate controls.

---

# 45. AI EXECUTION TRACE

Important AI operations should support traceability.

Where applicable capture:

```text
Intent
Tool
Data Source
Decision
Confidence
Result
Latency
Status
Case / Entity Link
```

Do not expose raw prompts, provider payloads or secrets by default.

---

# 46. AI PROVIDER ABSTRACTION

Do not hardcode the application to one AI provider.

Use an abstraction where appropriate:

```text
AI Provider
    ↓
Model
    ↓
AI Service
    ↓
Application
```

Support configurable providers/models where required.

Development should support a fake/mock provider for deterministic testing.

---

# 47. SQL / DATA AGENT

The SQL/Data Agent should be read-only by default.

It must:

* validate user permissions
* validate tenant scope
* restrict accessible data
* prevent destructive SQL
* apply query limits
* log executions
* provide understandable results

Never allow arbitrary write SQL from a general-purpose AI data agent.

---

# 48. COMMUNICATION CHANNELS

Communication capabilities include:

```text
WhatsApp
Email
SMS
Voice
```

Communication must support:

* tenant configuration
* provider abstraction
* templates
* audit
* delivery status
* appropriate consent
* rate limits
* failure handling

Provider credentials must never be exposed to frontend code.

---

# 49. SECRETS MANAGEMENT

Never commit:

* API keys
* passwords
* database credentials
* access tokens
* provider secrets
* encryption keys
* private certificates

Use environment configuration and secure secret management.

Never print secrets in logs.

---

# 50. FILE UPLOADS

File uploads must be treated as untrusted input.

Validate:

* file type
* extension
* MIME type
* size
* filename
* content where appropriate

Protect against:

* malicious files
* path traversal
* oversized uploads
* dangerous document content
* executable content

Uploaded files must respect tenant boundaries.

---

# 51. AUDITABILITY

Sensitive operations should produce audit records.

Examples:

* authentication
* authorization changes
* support sessions
* tenant changes
* subscription changes
* financial changes
* compliance changes
* AI actions
* data access
* administrative changes

Audit records should capture appropriate:

```text
Actor
Tenant
Action
Resource
Timestamp
Result
Relevant Context
```

Do not log sensitive payloads unnecessarily.

---

# 52. PERFORMANCE

Prefer:

* server-side pagination
* efficient queries
* indexes
* caching where justified
* asynchronous processing
* background jobs
* lazy loading where appropriate
* optimized assets

Do not optimize prematurely.

Measure before introducing complexity.

---

# 53. BACKGROUND JOBS

Long-running work should not unnecessarily block HTTP requests.

Potential background work includes:

* document ingestion
* indexing
* communication delivery
* bulk imports
* report generation
* AI processing
* notifications
* analytics aggregation

Jobs must support:

* retry
* failure handling
* observability
* idempotency where required

---

# 54. TESTING

Do not consider implementation complete without appropriate tests.

Testing layers may include:

```text
Unit Tests
Integration Tests
API Tests
Authorization Tests
Tenant Isolation Tests
UI Tests
End-to-End Tests
```

Security-critical functionality requires explicit tests.

---

# 55. MULTI-TENANT SECURITY TESTING

Always test:

```text
Tenant A cannot access Tenant B.
```

Test:

* list endpoints
* detail endpoints
* search
* exports
* uploads
* downloads
* reports
* AI tools
* background jobs
* communication
* analytics
* support access

Tenant isolation must be tested at the API/service/data layers.

---

# 56. UI TESTING

Important UI tests should verify:

* rendering
* interactions
* validation
* permissions
* loading states
* empty states
* errors
* responsive behavior
* Light theme
* Dark theme

At least foundation components should be explicitly checked in:

```text
Mobile
Tablet
Desktop
Light
Dark
```

---

# 57. RESPONSIVE + THEME VALIDATION GATE

Before considering a UI feature complete, verify:

### Responsive

```text
☐ Mobile
☐ Tablet
☐ Desktop
☐ Large Desktop
```

### Theme

```text
☐ Light
☐ Dark
☐ System
```

### State

```text
☐ Loading
☐ Empty
☐ Populated
☐ Error
☐ Permission Restricted
☐ Success where applicable
```

### Accessibility

```text
☐ Keyboard
☐ Focus
☐ Labels
☐ Contrast
☐ Touch targets
```

---

# 58. DO NOT CREATE GENERIC UI

Never generate a generic SaaS dashboard merely because it is technically functional.

The UI must reflect:

* MTI 360 identity
* maritime context
* premium enterprise quality
* information hierarchy
* actual user workflows
* responsive behavior
* Light/Dark themes

Avoid generic:

```text
Blue sidebar
White cards
Random charts
Generic CRM tables
```

without adapting them to the MTI 360 design system.

---

# 59. DO NOT DUPLICATE SCREENS

If two screens share the same pattern:

```text
Use the same template.
```

If two screens share components:

```text
Reuse the components.
```

If they differ only by data:

```text
Reuse the same UI implementation.
```

Avoid copy-paste implementations.

---

# 60. NO HARD-CODED TENANT DATA

Never hardcode:

```text
ABC Maritime Training Institute
Mumbai
tenant_001
student_001
```

as actual application identity.

Use realistic seeded/demo data where required.

Production values must come from data/configuration.

---

# 61. REALISTIC SAMPLE DATA

When implementing UI prototypes or development fixtures, use realistic maritime examples.

Examples:

```text
Maritime Training Institute
Pre-Sea Training
Post-Sea Training
STCW
DNS
B.Sc. Nautical Science
Marine Engineering
Deck Cadet
Engine Cadet
Batch
Training Berth
Seafarer
Certificate
Placement
RPSL
Compliance
```

Avoid meaningless placeholder data such as:

```text
Lorem ipsum
John Doe
Test Company
123456
```

unless specifically needed for testing.

---

# 62. NAVIGATION

Navigation must respect:

* role
* permissions
* tenant
* campus
* subscription
* feature entitlements

Do not show navigation options that the user cannot meaningfully access unless there is a deliberate upgrade/discovery experience.

---

# 63. ROUTING

Routes must be:

* predictable
* consistent
* permission-aware
* tenant-safe
* accessible
* bookmarkable where appropriate

Avoid leaking sensitive identifiers unnecessarily.

---

# 64. STATE MANAGEMENT

Use the simplest state-management approach that satisfies the requirements.

Do not introduce a global state library merely because it is available.

Separate:

```text
Server State
UI State
Form State
Session State
Tenant Context
```

Do not duplicate server state unnecessarily.

---

# 65. FRONTEND SECURITY

Never place secrets in:

* browser JavaScript
* public environment variables
* HTML
* local storage unless appropriate and explicitly justified
* client-side configuration

Frontend code is considered public.

---

# 66. ERROR HANDLING

Errors should be:

* consistent
* observable
* safe
* user-friendly

Backend logs may contain diagnostic information.

Frontend responses must not expose internal implementation details.

---

# 67. LOGGING

Logs should support debugging and operations without exposing sensitive data.

Never log:

* passwords
* access tokens
* API keys
* secret credentials
* full sensitive documents
* unnecessary personal information

Use correlation/request IDs where appropriate.

---

# 68. OBSERVABILITY

Production systems should support:

* structured logs
* request tracing where appropriate
* job monitoring
* API monitoring
* health checks
* error monitoring
* performance metrics

The platform control plane should provide appropriate operational visibility.

---

# 69. DATABASE MIGRATIONS

Database changes must be:

* versioned
* repeatable
* reviewable
* backward-aware where necessary

Never manually modify production schema as a substitute for migration discipline.

---

# 70. API VERSIONING

Where API versioning is used, maintain clear compatibility boundaries.

Avoid breaking existing clients without an explicit migration strategy.

---

# 71. INTEGRATIONS

External integrations must use service boundaries.

Examples:

```text
WhatsApp Provider
Email Provider
SMS Provider
Voice Provider
Payment Provider
AI Provider
Identity Provider
Storage Provider
```

Do not scatter provider-specific code throughout the application.

Prefer:

```text
Application
   ↓
Integration Interface
   ↓
Provider Adapter
```

---

# 72. FEATURE FLAGS

Feature flags should be:

* centrally managed where appropriate
* auditable
* tenant-aware where necessary
* safe by default

Do not use random environment variables as an uncontrolled substitute for feature management.

---

# 73. CONFIGURATION

Separate:

```text
Code
Configuration
Secrets
Tenant Data
Platform Data
```

Do not hardcode environment-specific values.

---

# 74. DEPENDENCY DISCIPLINE

Before adding a dependency:

1. Check whether an existing dependency already provides the capability.
2. Check compatibility.
3. Consider security.
4. Consider maintenance.
5. Consider bundle/runtime impact.
6. Add only when justified.

Do not introduce unnecessary frameworks.

---

# 75. CODE QUALITY

Prefer code that is:

* readable
* explicit
* maintainable
* testable
* modular
* predictable

Avoid:

* clever abstractions
* unnecessary indirection
* premature generalization
* duplicated logic
* enormous components
* enormous service classes
* hidden side effects

---

# 76. REFACTORING RULE

Do not perform large unrelated refactors while implementing a feature.

Keep changes:

* focused
* reviewable
* testable
* reversible

If architectural refactoring is necessary, document why.

---

# 77. EXISTING CODE FIRST

Before creating a new implementation:

```text
Inspect existing repository.
```

Understand:

* architecture
* conventions
* naming
* components
* services
* APIs
* database patterns
* tests
* authentication
* authorization

Do not overwrite existing architecture blindly.

---

# 78. NO ASSUMPTIONS ABOUT EXISTING CODE

Never assume:

```text
This endpoint exists.
This component exists.
This table exists.
This service exists.
This permission exists.
```

Verify the repository first.

---

# 79. DEVELOPMENT WORKFLOW

For every meaningful task:

```text
1. Read relevant specifications
2. Inspect repository
3. Identify existing implementation
4. Identify dependencies
5. Plan implementation
6. Implement smallest correct change
7. Run tests
8. Run lint/type checks/build
9. Review security
10. Review tenant isolation
11. Review responsive behavior
12. Review Light/Dark themes
13. Review accessibility
14. Update documentation/status
```

---

# 80. VERTICAL SLICE DEVELOPMENT

Prefer complete vertical slices.

Example:

```text
Database
   ↓
Backend Service
   ↓
API
   ↓
Authorization
   ↓
UI
   ↓
Tests
```

Do not build hundreds of incomplete frontend screens before implementing working backend capabilities.

---

# 81. FOUNDATION-FIRST DEVELOPMENT

Recommended implementation sequence:

```text
PHASE 00 — Foundation
PHASE 01 — Authentication & Multi-Tenancy
PHASE 02 — Platform Control Plane
PHASE 03 — Tenant Foundation
PHASE 04 — Admissions
PHASE 05 — Academics
PHASE 06 — Finance
PHASE 07 — Compliance
PHASE 08 — Placement
PHASE 09 — Communication
PHASE 10 — Automation
PHASE 11 — AI
PHASE 12 — Analytics
PHASE 13 — Student Portal
PHASE 14 — Public Website
PHASE 15 — Billing & SaaS Operations
PHASE 16 — Security & Hardening
PHASE 17 — Production Readiness
```

Follow `TASKS.md`.

---

# 82. TASK DISCIPLINE

Each task should have:

```text
Task ID
Objective
Dependencies
Files / Modules
Database Changes
API Changes
UI Screens
Tests
Acceptance Criteria
Definition of Done
```

Do not mark a task complete merely because code compiles.

---

# 83. DEVELOPMENT STATUS

`DEVELOPMENT-STATUS.md` is the live implementation tracker.

Claude Code MUST update it when meaningful implementation work is completed.

It must distinguish:

```text
Specification Ready
Design Ready
Prototype
Implemented
Tested
Verified
Production Ready
```

Never claim implementation progress that has not actually occurred.

---

# 84. STATUS INTEGRITY

Never report:

```text
100% complete
```

unless the corresponding implementation and verification actually exist.

Do not confuse:

```text
Designed
```

with:

```text
Implemented
```

Do not confuse:

```text
Implemented
```

with:

```text
Production Ready
```

---

# 85. DEFINITION OF DONE

A feature is not complete until applicable items are satisfied:

```text
☐ Requirements understood
☐ Existing architecture inspected
☐ Backend implemented
☐ Database changes implemented
☐ API implemented
☐ Authorization implemented
☐ Tenant isolation verified
☐ UI implemented
☐ Responsive behavior verified
☐ Light theme verified
☐ Dark theme verified
☐ System theme verified
☐ Loading state implemented
☐ Empty state implemented
☐ Error state implemented
☐ Permission state implemented
☐ Accessibility reviewed
☐ Tests added
☐ Tests passing
☐ Build passing
☐ Documentation updated
☐ DEVELOPMENT-STATUS.md updated
```

Only applicable items need to be checked for a particular task.

---

# 86. PRODUCTION READINESS

Before production release, verify:

### Security

```text
Authentication
Authorization
Tenant isolation
Secrets
Audit
Rate limits
Input validation
File security
```

### Reliability

```text
Error handling
Retries
Background jobs
Idempotency
Monitoring
Backups
Recovery
```

### Performance

```text
Database indexes
Query performance
API latency
Frontend performance
Asset optimization
```

### UI

```text
Responsive
Light
Dark
System
Accessibility
Loading
Empty
Error
```

### Operations

```text
Health checks
Logs
Metrics
Alerts
Audit
Support procedures
```

---

# 87. WHAT CLAUDE CODE MUST NEVER DO

Never:

* bypass authentication
* bypass authorization
* bypass tenant isolation
* trust client tenant IDs
* expose secrets
* give AI unrestricted database access
* create destructive AI actions without governance
* hardcode tenant data
* introduce arbitrary colors
* ignore Dark mode
* ignore responsive behavior
* build desktop-only UI
* duplicate components unnecessarily
* create 222 isolated screen implementations
* silently alter unrelated functionality
* delete existing functionality without instruction
* claim tests passed when they were not run
* claim implementation is complete when it is not
* fabricate missing APIs or database tables
* expose internal errors to users
* store sensitive credentials in frontend code

---

# 88. WHEN REQUIREMENTS ARE AMBIGUOUS

Do not invent major product behavior.

Use this hierarchy:

```text
Existing documented requirement
        ↓
Existing architecture
        ↓
Existing implementation convention
        ↓
Safe minimal assumption
```

If ambiguity affects:

* security
* data integrity
* tenant isolation
* financial behavior
* compliance
* external communication
* destructive operations

stop and request clarification rather than making a risky assumption.

---

# 89. UI FOUNDATION APPROVAL

Before expanding the UI to the complete screen inventory, establish and validate the foundation:

### Platform

```text
PLAT-03 Platform Dashboard
PLAT-04 Tenant List
PLAT-05 Tenant 360
PLAT-06 Create Tenant
PLAT-13 Billing & Invoices
PLAT-25 System Health
```

### Tenant

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

### Student

```text
STU-02 Student Dashboard
STU-03 My Course
STU-07 Fees
STU-08 Certificates
```

### Public

```text
PUB-01 Home
PUB-02 Features
PUB-05 Request Demo
```

These foundation screens should establish:

* shell
* navigation
* typography
* tokens
* components
* responsive behavior
* Light theme
* Dark theme
* accessibility
* states

before the entire UI inventory is implemented.

---

# 90. DESIGN-TO-CODE CONSISTENCY

Claude Code must treat the approved Claude Design output as a design reference.

Implementation must preserve:

* layout hierarchy
* component reuse
* spacing
* typography
* color tokens
* responsive behavior
* Light/Dark behavior
* interactions
* information hierarchy

Do not replace a premium design with a generic implementation merely because it is faster.

---

# 91. DESIGN SYSTEM EXTENSION

If a new UI pattern is required:

1. Check whether an existing component can support it.
2. If not, extend an existing component.
3. If genuinely new, create a reusable component.
4. Add it to the design system/component inventory.
5. Use it consistently thereafter.

Do not create one-off components without reason.

---

# 92. DOCUMENTATION DISCIPLINE

If implementation introduces a meaningful architectural decision, update the relevant documentation.

Potential documents:

```text
ARCHITECTURE.md
DESIGN-SYSTEM.md
UI-SCREENS.md
CLAUDE.md
TASKS.md
DEVELOPMENT-STATUS.md
```

Do not allow implementation to silently diverge from the documented architecture.

---

# 93. CHANGE SAFETY

Before modifying an existing feature:

```text
Understand current behavior
Identify consumers
Identify APIs
Identify database dependencies
Identify tests
Implement change
Run regression tests
```

Preserve backward compatibility where required.

---

# 94. SECURITY-FIRST RULE

Whenever convenience conflicts with security:

```text
Security wins.
```

Whenever speed conflicts with tenant isolation:

```text
Tenant isolation wins.
```

Whenever AI convenience conflicts with controlled execution:

```text
Controlled execution wins.
```

---

# 95. PRODUCT QUALITY PRINCIPLE

MTI 360 should feel like a mature enterprise SaaS platform, not a collection of generated screens.

Every implementation should aim for:

```text
Consistency
Clarity
Security
Accessibility
Responsiveness
Maintainability
Observability
Performance
Extensibility
Production Readiness
```

---

# 96. MASTER IMPLEMENTATION PRINCIPLE

Always think in this order:

```text
PRODUCT
   ↓
USER
   ↓
WORKFLOW
   ↓
SECURITY
   ↓
DATA
   ↓
API
   ↓
BUSINESS LOGIC
   ↓
UI
   ↓
RESPONSIVE BEHAVIOR
   ↓
LIGHT / DARK THEME
   ↓
ACCESSIBILITY
   ↓
TESTING
   ↓
OBSERVABILITY
   ↓
PRODUCTION READINESS
```

Do not start with UI code simply because it is visible.

---

# 97. FINAL CLAUDE CODE RULE

Before implementing any significant feature, Claude Code should be able to answer:

```text
What problem does this solve?

Who uses it?

Which experience does it belong to?

Which tenant does it belong to?

What permissions are required?

What data does it access?

What APIs are involved?

What business rules apply?

What existing components can be reused?

Which page template applies?

How does it behave on mobile?

How does it behave on tablet?

How does it behave on desktop?

How does it behave in Light mode?

How does it behave in Dark mode?

What happens while loading?

What happens when empty?

What happens on error?

What happens when permission is denied?

How is the operation tested?

How is tenant isolation verified?

How is the operation audited?

How is the feature monitored in production?
```

If these questions cannot be answered, implementation is not ready.

---

# 98. MASTER PRINCIPLE

MTI 360 is:

```text
ONE PRODUCT
FOUR EXPERIENCES
TRUE MULTI-TENANCY
ONE DESIGN LANGUAGE
THREE THEME MODES
RESPONSIVE BY DEFAULT
ACCESSIBLE BY DESIGN
REUSABLE COMPONENTS
REUSABLE PAGE TEMPLATES
GOVERNED AI
SECURE DATA ACCESS
AUDITABLE OPERATIONS
PRODUCTION-GRADE ENGINEERING
```

The goal is not to generate the maximum amount of code.

The goal is to build a **secure, maintainable, scalable and premium SaaS platform**.

---

# 99. CLAUDE CODE EXECUTION COMMAND

For every feature request, follow:

```text
READ
 ↓
UNDERSTAND
 ↓
INSPECT
 ↓
PLAN
 ↓
IMPLEMENT
 ↓
TEST
 ↓
SECURITY REVIEW
 ↓
RESPONSIVE REVIEW
 ↓
LIGHT/DARK REVIEW
 ↓
ACCESSIBILITY REVIEW
 ↓
REGRESSION REVIEW
 ↓
DOCUMENT
 ↓
UPDATE DEVELOPMENT STATUS
```

Never skip security, tenant isolation, responsive design, theme validation or testing merely because the feature appears simple.

---

# 100. FINAL INSTRUCTION TO CLAUDE CODE

You are not merely generating code for MTI 360.

You are contributing to a production SaaS platform.

Therefore:

**Understand the architecture before coding.**

**Respect the multi-tenant security boundary.**

**Reuse the design system and component architecture.**

**Build responsive interfaces.**

**Support Light, Dark and System themes.**

**Treat AI as governed infrastructure, not unrestricted automation.**

**Test security-sensitive behavior explicitly.**

**Preserve existing functionality unless the task requires a change.**

**Do not fabricate implementation status.**

**Do not optimize for speed at the expense of maintainability or security.**

**Build the smallest correct production-ready solution.**
