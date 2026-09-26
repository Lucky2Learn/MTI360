# MTI 360

# DESIGN SYSTEM

**Product:** MTI 360
**Positioning:** The Complete Growth & Operations Platform for Maritime Training Institutes
**Tagline:** Acquire Students. Simplify Operations. Grow Your Institute.

**Version:** 1.0
**Status:** Design System Baseline
**Purpose:** Master visual, interaction, responsive, accessibility, and theme specification for MTI 360.

---

# 1. PURPOSE

This document defines the complete design system for MTI 360.

It is the single source of truth for:

* Visual identity
* Color
* Typography
* Spacing
* Radius
* Elevation
* Icons
* Components
* Layout
* Navigation
* Page templates
* Responsive behavior
* Light mode
* Dark mode
* System theme
* Accessibility
* Charts
* AI interfaces
* Maritime visualization
* States
* Interaction patterns

The design system must be used consistently across:

```text
MTI 360
│
├── Platform / SaaS Control Plane
├── Tenant Application
├── Student Portal
└── Public Website
```

The objective is to create **one coherent product system**, not a collection of independent screens.

---

# 2. DESIGN PHILOSOPHY

MTI 360 should feel:

* Premium
* Maritime
* Intelligent
* Modern
* Enterprise-grade
* Calm
* Trustworthy
* Operational
* Efficient
* Accessible

The design should communicate:

> **A serious international SaaS platform built specifically for maritime training organizations.**

It must not look like:

* Legacy ERP software
* Government portal software
* Generic CRM software
* Generic blue SaaS
* Template marketplace dashboard
* Consumer mobile app
* AI gimmick

---

# 3. CORE DESIGN PRINCIPLES

## 3.1 Clarity

Users should understand:

* Where they are
* What they are looking at
* What needs attention
* What they can do
* What happened
* What happens next

---

## 3.2 Consistency

The same concept must look and behave consistently throughout the platform.

Examples:

* Buttons
* Tables
* Status badges
* Forms
* Filters
* Tabs
* Drawers
* Dialogs
* Notifications
* AI actions
* Navigation

---

## 3.3 Progressive Disclosure

Do not overwhelm users with every available field or action.

Show:

```text
Primary information
      ↓
Secondary information
      ↓
Advanced information
      ↓
Audit / technical information
```

---

## 3.4 Action-Oriented Design

Every operational screen should help the user answer:

> What should I do next?

---

## 3.5 Context Awareness

The user must always understand the current:

* Platform
* Tenant
* Campus
* Role
* Record
* Workflow

---

## 3.6 Responsive by Default

Responsive design is not an enhancement.

It is a fundamental product requirement.

Every component and screen must work across:

* Mobile
* Tablet
* Desktop
* Large desktop

---

## 3.7 Theme by Default

Every component must support:

* Light
* Dark
* System

Dark mode must be intentionally designed.

It must never be implemented as simple color inversion.

---

# 4. PRODUCT EXPERIENCES

The design system supports four experiences.

## 4.1 Platform / SaaS Control Plane

Used by MTI 360 platform administrators.

Visual characteristics:

* High information density
* Operational
* Enterprise
* Data-oriented
* Security-aware

---

## 4.2 Tenant Application

Used by Maritime Training Institutes.

Visual characteristics:

* Operational
* Business-oriented
* Rich dashboards
* Workflow-driven
* Configurable

---

## 4.3 Student Portal

Used by students.

Visual characteristics:

* Mobile-first
* Simple
* Friendly
* Task-oriented
* Low cognitive load

---

## 4.4 Public Website

Used by prospective students and visitors.

Visual characteristics:

* Marketing-oriented
* Premium
* Spacious
* Trust-building
* Conversion-focused

---

# 5. BRAND VISUAL DIRECTION

MTI 360 should use a sophisticated maritime identity.

Subtle maritime references may include:

* Navigation paths
* Route lines
* Port/campus references
* Compass-inspired geometry
* Ocean-depth layering
* Maritime operational indicators

Avoid decorative overuse.

Do not use:

* Large ship illustrations everywhere
* Repeated anchors
* Excessive waves
* Cartoon nautical imagery
* Nautical clichés

---

# 6. COLOR SYSTEM

## 6.1 Core Palette

### Deep Ocean

```text
#06283D
#073B57
#0A4F6E
```

Primary navigation and brand surfaces.

---

### Midnight

```text
#04151F
#071E2B
#0B2A3A
```

Primary dark-mode backgrounds and deep surfaces.

---

### Sea Glass

```text
#168F91
#1CA7A5
#4CB9B4
#DDF4F2
```

Primary interaction and maritime accent family.

---

### Pearl

```text
#F8FAF9
#F1F5F4
#E5ECEA
```

Primary Light Mode surfaces.

---

### Ice

```text
#F5FAFC
#EAF4F7
#D9E9EE
```

Secondary backgrounds and subtle maritime surfaces.

---

### Brass

```text
#B88A44
#C69B5A
#F5EBDD
```

Premium accent.

Use sparingly.

---

# 7. SEMANTIC COLORS

## Success

```text
Primary: #21875A
Surface: #E5F4EC
```

## Warning

```text
Primary: #B7791F
Surface: #FFF4DD
```

## Error

```text
Primary: #C44545
Surface: #FDECEC
```

## Information

```text
Primary: #2774A6
Surface: #E7F2FA
```

Semantic colors must never be the only method used to communicate status.

Combine color with:

* Icon
* Text
* Badge
* Shape
* Status indicator

---

# 8. AI COLOR SYSTEM

AI uses a restrained violet/plum family.

```text
AI Primary
#7056A8

AI Surface
#F0ECF8
```

Dark-mode AI surfaces must be adjusted appropriately.

AI should not dominate the overall product visual identity.

AI is a capability, not a visual theme replacing MTI 360.

---

# 9. COLOR RATIO

Recommended visual balance:

```text
60% Neutral / Pearl / Ice
25% Ocean / Midnight
10% Sea Glass
5% Brass / AI / Semantic
```

This is a visual hierarchy guideline, not a rigid mathematical requirement.

---

# 10. SEMANTIC DESIGN TOKENS

Components must consume semantic tokens rather than directly referencing raw color values.

Example:

```text
--background-primary
--background-secondary

--surface-primary
--surface-secondary
--surface-elevated

--text-primary
--text-secondary
--text-muted
--text-inverse

--border-subtle
--border-default
--border-strong

--brand-primary
--brand-secondary

--accent-maritime
--accent-brass

--success
--warning
--error
--info

--ai-primary
--ai-surface
--ai-border
```

This enables consistent Light/Dark theming.

---

# 11. THEME SYSTEM

MTI 360 supports:

```text
Light
Dark
System
```

## 11.1 Light Mode

Primary enterprise mode.

Use:

* Pearl backgrounds
* Ice secondary surfaces
* Deep Ocean navigation
* Sea Glass interactions
* restrained Brass
* dark readable text
* subtle borders
* controlled shadows

Example hierarchy:

```text
Page Background
    ↓
Pearl / Ice

Surface
    ↓
White / Pearl

Primary Navigation
    ↓
Deep Ocean

Interactive Accent
    ↓
Sea Glass

Premium Accent
    ↓
Brass
```

---

# 12. DARK MODE

Dark mode must be a **designed experience**, not an inverted Light Mode.

Use:

```text
Page Background
    ↓
Midnight

Surface
    ↓
Deep Ocean / Ocean Surface

Primary Text
    ↓
Pearl / Ice

Secondary Text
    ↓
Muted Ice

Interactive Accent
    ↓
Sea Glass

Premium Accent
    ↓
Brass
```

Avoid:

* pure black backgrounds everywhere
* excessively bright text
* excessive neon
* high-glow effects
* excessive shadows

---

# 13. SYSTEM THEME

System mode follows the user's operating-system preference.

Behavior:

```text
System preference = Light
        ↓
Light Mode

System preference = Dark
        ↓
Dark Mode
```

The user can override System by explicitly selecting Light or Dark.

---

# 14. THEME PERSISTENCE

Theme preference must persist across sessions.

Preferred storage strategy:

```text
Authenticated User
        ↓
User Preference

Unauthenticated
        ↓
Local Preference
```

System preference should remain dynamic when `System` is selected.

---

# 15. THEME SWITCHING

Preferred options:

```text
☀ Light
🌙 Dark
◐ System
```

Theme switching should:

* be accessible
* not disrupt current workflow
* preserve navigation
* preserve entered form data
* update charts
* update tables
* update dialogs
* update navigation
* update AI components

Avoid unnecessary page reloads.

---

# 16. DARK MODE COMPONENT REQUIREMENT

Every component must be reviewed in:

```text
Light
Dark
```

and in:

```text
Default
Hover
Focus
Active
Disabled
Selected
Loading
Error
Success
```

A component is not production-ready if only its Light Mode appearance is defined.

---

# 17. TYPOGRAPHY

Preferred:

**Inter**

Alternative:

**Plus Jakarta Sans**

Typography must remain consistent across the product.

---

# 18. TYPOGRAPHY SCALE

## Display

```text
48px / 56px
Weight: 700
```

## Page Title

```text
32px / 40px
Weight: 700
```

## Section Heading

```text
24px / 32px
Weight: 650–700
```

## Card Heading

```text
18px / 24px
Weight: 600
```

## Body

```text
14–16px
Weight: 400–500
```

## Caption

```text
12–13px
Weight: 400–500
```

Use typography hierarchy rather than excessive color variation.

---

# 19. TYPOGRAPHY RESPONSIVENESS

Typography may adapt at smaller breakpoints.

Example:

```text
Desktop Page Title
32px

Tablet
28–30px

Mobile
24–28px
```

Do not reduce readability simply to preserve desktop dimensions.

---

# 20. SPACING SYSTEM

Use a 4px base grid.

```text
4
8
12
16
20
24
32
40
48
64
80
96
```

Common usage:

```text
4   micro spacing
8   compact
12  small
16  standard
24  card/panel
32  section
48  major section
64+ page-level separation
```

---

# 21. RESPONSIVE BREAKPOINTS

Primary breakpoints:

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

Also test intermediate widths.

Do not assume only four screen sizes exist.

---

# 22. RESPONSIVE DESIGN PRINCIPLE

Responsive design means adapting the interaction model.

It does not mean:

```text
Desktop layout
      ↓
Shrink everything
```

Instead:

```text
Desktop
    ↓
Reorganize
    ↓
Tablet
    ↓
Reorganize
    ↓
Mobile
```

---

# 23. DESKTOP LAYOUT

Desktop may support:

* Expanded sidebar
* Multi-column dashboards
* Dense tables
* Side-by-side forms
* Multi-panel workspaces
* Large charts

Sidebar:

```text
240–280px
```

Collapsed:

```text
68–76px
```

---

# 24. TABLET LAYOUT

Tablet may use:

* Collapsed sidebar
* Drawer navigation
* Reduced table columns
* Two-column forms where appropriate
* Stacked cards
* Responsive filters
* Touch-friendly controls

---

# 25. MOBILE LAYOUT

Mobile must be intentionally designed.

Use:

* drawer navigation
* bottom navigation where appropriate
* stacked cards
* full-width controls
* simplified tables
* full-screen dialogs where appropriate
* sticky primary actions
* compact filters

Minimum recommended touch target:

```text
44px × 44px
```

---

# 26. RESPONSIVE NAVIGATION

## Desktop

```text
Persistent Sidebar
```

## Tablet

```text
Collapsible Sidebar / Drawer
```

## Mobile

```text
Drawer
+
Optional Bottom Navigation
```

Navigation hierarchy must remain understandable.

---

# 27. RESPONSIVE TABLES

Do not blindly shrink tables.

Choose one:

### Pattern A — Reduced Columns

Show only primary information.

### Pattern B — Horizontal Scroll

Useful when comparison is important.

### Pattern C — Card Rows

Transform records into cards.

### Pattern D — Expandable Rows

Secondary information expands.

### Pattern E — Detail Drawer

Open record details without leaving context.

---

# 28. RESPONSIVE FORMS

Desktop:

```text
First Name       Last Name
Email            Mobile
Course           Batch
```

Mobile:

```text
First Name

Last Name

Email

Mobile

Course

Batch
```

Long forms should use:

* sections
* accordions
* wizard steps
* sticky actions

where appropriate.

---

# 29. RESPONSIVE DASHBOARDS

Desktop:

```text
KPI KPI KPI KPI

Chart        Chart

Queue        Alerts
```

Mobile:

```text
KPI

KPI

Chart

Alerts

Queue
```

Preserve hierarchy, not geometry.

---

# 30. RESPONSIVE COMMUNICATION WORKSPACE

Desktop:

```text
Conversation List
      |
Conversation
      |
Context
```

Mobile:

```text
Conversation List
       ↓
Conversation
       ↓
Context Drawer
```

---

# 31. RESPONSIVE AI WORKSPACE

Desktop:

```text
Conversation | Context | Execution
```

Mobile:

```text
Conversation
     ↓
AI Suggestion
     ↓
Execution / Details
```

Secondary information should be expandable.

---

# 32. RESPONSIVE STUDENT PORTAL

Student Portal is mobile-first.

Prioritize:

```text
Dashboard
Attendance
Training
Exams
Fees
Certificates
Placement
Notifications
Profile
```

Avoid administrative density.

---

# 33. RESPONSIVE PUBLIC WEBSITE

Public website must adapt:

* navigation
* hero
* course cards
* content sections
* forms
* CTA
* testimonials
* pricing
* footer

Mobile conversion paths must remain simple.

---

# 34. BORDER RADIUS

Use:

```text
4px
6px
8px
10px
12px
16px
20px
```

Use pill radius mainly for:

* status
* tags
* filters
* compact indicators

Avoid excessive rounded-card styling.

---

# 35. ELEVATION

Use restrained elevation.

Light mode:

```text
Border
+
Subtle shadow
```

Dark mode:

Prefer:

```text
Surface contrast
+
Subtle border
```

rather than heavy shadows.

Do not make every card appear floating.

---

# 36. ICONOGRAPHY

Icons should be:

* simple
* professional
* consistent
* recognizable
* accessible

Use one coherent icon family.

Avoid mixing multiple icon styles.

Maritime-inspired icons should be subtle and limited.

---

# 37. APPLICATION SHELL

Standard desktop shell:

```text
┌────────────────────────────────────────────────────────────┐
│ Logo | Context | Search | Notifications | AI | Theme | User│
├──────────────┬─────────────────────────────────────────────┤
│              │                                             │
│ Sidebar      │ Main Content                                │
│              │                                             │
│              │                                             │
└──────────────┴─────────────────────────────────────────────┘
```

---

# 38. TOP BAR

Top bar contains:

* MTI 360 logo
* Tenant/Platform context
* Search
* Notifications
* AI access
* Theme control
* User menu

Tenant context must remain visible.

---

# 39. SIDEBAR

Sidebar must support:

* expanded
* collapsed
* mobile drawer

Navigation sections should visually group:

```text
GROW
ADMISSIONS
ACADEMICS
FINANCE
COMPLIANCE
PLACEMENT
COMMUNICATION
AUTOMATION
AI
ANALYTICS
ADMINISTRATION
```

---

# 40. PAGE HEADER

Standard:

```text
Breadcrumb

Page Title
Description

Primary Action
Secondary Actions
```

Example:

```text
Admissions / Students

Students
Manage enrolled students and admission information.

[Add Student]
```

---

# 41. BUTTON SYSTEM

Variants:

```text
Primary
Secondary
Tertiary
Ghost
Destructive
Success
Icon
```

States:

```text
Default
Hover
Focus
Active
Disabled
Loading
```

Buttons must work in both themes.

---

# 42. FORM CONTROLS

Components:

* Input
* Select
* Combobox
* Date Picker
* Time Picker
* File Upload
* Checkbox
* Radio
* Switch
* Textarea
* Search

All controls require:

```text
Default
Focus
Filled
Disabled
Error
Success
```

---

# 43. CARDS

Cards are used for:

* KPIs
* summaries
* records
* actions
* insights
* alerts

Do not put every piece of content inside a card.

Use cards only when they improve grouping.

---

# 44. DATA TABLE

DataTable must support where appropriate:

* sorting
* filtering
* search
* pagination
* selection
* bulk actions
* column visibility
* export
* row actions
* responsive behavior

---

# 45. FILTER BAR

Standard structure:

```text
Search
Status
Date
Category
Advanced Filters
Clear
```

Mobile should convert filters into a drawer or sheet when necessary.

---

# 46. TABS

Use tabs for closely related information.

Do not use tabs for unrelated workflows.

Mobile tabs may become:

* horizontally scrollable
* dropdown
* segmented control

depending on context.

---

# 47. DRAWERS

Use drawers for:

* filters
* contextual details
* secondary information
* mobile navigation
* supporting workflows

Drawers must support responsive sizing.

---

# 48. MODALS / DIALOGS

Use for:

* confirmation
* short forms
* destructive actions
* focused interactions

Long workflows should not be forced into small dialogs.

On mobile, dialogs may become full-screen sheets.

---

# 49. NOTIFICATIONS

Support:

* success
* information
* warning
* error

Notifications must be:

* concise
* actionable
* accessible
* theme-aware

---

# 50. STATUS BADGES

Examples:

```text
ACTIVE
PENDING
DRAFT
PUBLISHED
ARCHIVED
APPROVED
REJECTED
OVERDUE
COMPLETED
FAILED
```

Status must use:

* text
* icon where useful
* color

Never color alone.

---

# 51. KPI COMPONENT

KPI card should support:

```text
Label
Value
Trend
Comparison
Context
```

Example:

```text
Active Students

1,284

↑ 8.4%

vs last month
```

---

# 52. CHART SYSTEM

Charts must support:

* Light
* Dark
* Responsive resizing
* Accessible labels
* Tooltips
* Legend
* Empty state
* Loading state

Do not use excessive colors.

Charts should use the MTI 360 palette.

---

# 53. ANALYTICS RESPONSIVENESS

Desktop analytics may use:

```text
Filters
KPI row
Large chart
Secondary charts
Data table
```

Mobile:

```text
Filters
KPI
Chart
Chart
Data
```

Charts must remain readable.

---

# 54. AI COMPONENT SYSTEM

AI components:

```text
AIAssistant
AISuggestion
AIAction
AIExecution
AISource
AIConfidence
AIApproval
```

AI components must use the restrained AI visual language.

---

# 55. AI INTERACTION MODEL

Clearly distinguish:

```text
Suggestion
Recommendation
Action
Execution
```

Consequential actions:

```text
AI Suggests
      ↓
Human Reviews
      ↓
Human Confirms
      ↓
Action Executes
      ↓
Audit Recorded
```

---

# 56. AI EXECUTION COMPONENT

Show where appropriate:

```text
Intent
Tool
Data Source
Decision
Confidence
Result
Latency
Status
Record Link
```

Do not expose:

* secrets
* raw provider payloads
* internal credentials
* raw prompts by default

---

# 57. PERMISSION UX

Permissions include:

```text
View
Create
Edit
Delete
Approve
Export
Manage
Configure
```

Unauthorized states should be understandable.

Example:

```text
You don't have permission to approve this application.
```

Avoid confusing disabled controls without explanation where explanation is useful.

---

# 58. LOADING STATES

Use skeletons for structured content.

Examples:

```text
Dashboard Skeleton
Table Skeleton
Card Skeleton
Profile Skeleton
Chart Skeleton
```

Avoid unnecessary spinners for entire pages.

---

# 59. EMPTY STATES

Every major list must define an empty state.

Structure:

```text
Illustration/Icon
Title
Explanation
Primary Action
```

Keep illustrations subtle and consistent with the maritime identity.

---

# 60. ERROR STATES

Error state must communicate:

```text
What happened?
What was saved?
What can I do?
Can I retry?
```

Support:

```text
Retry
Go Back
Contact Support
```

where applicable.

---

# 61. SUCCESS STATES

Examples:

```text
Application submitted successfully.
Payment recorded successfully.
Certificate generated successfully.
Campaign published successfully.
```

Use clear confirmation without excessive animation.

---

# 62. DESTRUCTIVE ACTIONS

Examples:

* Delete
* Cancel
* Suspend
* Archive
* Remove access

Require:

* clear warning
* explicit action
* appropriate confirmation
* meaningful explanation

---

# 63. ACCESSIBILITY

Target:

**WCAG 2.2 AA**

Requirements:

* semantic HTML
* keyboard navigation
* visible focus
* logical tab order
* accessible labels
* screen-reader support
* sufficient contrast
* reduced motion
* touch-friendly controls
* non-color status indicators

---

# 64. ACCESSIBILITY — LIGHT/DARK

Contrast must be independently validated in:

```text
Light
Dark
```

Do not assume a color that works in Light will work in Dark.

Especially validate:

* text
* placeholder text
* borders
* links
* badges
* buttons
* chart labels
* disabled controls
* focus indicators
* AI surfaces

---

# 65. REDUCED MOTION

Respect user preference for reduced motion.

Animations must never be necessary to understand the workflow.

Prefer:

* subtle transitions
* opacity
* controlled movement

Avoid:

* excessive bouncing
* large parallax
* distracting motion
* unnecessary animation

---

# 66. MARITIME VISUALIZATION

Appropriate visual patterns:

* routes
* ports
* campuses
* training paths
* operational timelines
* maritime regions

Keep visualization functional.

---

# 67. DESIGN DENSITY

MTI 360 is an enterprise product.

Support three conceptual density levels:

```text
Comfortable
Standard
Compact
```

Default:

**Standard**

Do not make every screen excessively dense.

---

# 68. PAGE TEMPLATES

The system supports:

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

Templates must inherit:

* theme system
* responsive system
* accessibility system
* component system

---

# 69. COMPONENT LIBRARY

## Core

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
```

## Inputs

```text
Button
IconButton
Input
Select
Combobox
DatePicker
TimePicker
FileUpload
Checkbox
Radio
Switch
Textarea
```

## Data

```text
Card
Badge
DataTable
FilterBar
Pagination
Tabs
Timeline
KPI
ChartCard
```

## Feedback

```text
Toast
Alert
Dialog
Modal
Drawer
Skeleton
EmptyState
ErrorState
```

## Security

```text
PermissionGate
AccessDenied
SupportSessionBanner
AuditTimeline
```

---

# 70. ENTERPRISE COMPONENTS

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

All must support Light/Dark/Responsive.

---

# 71. TENANT COMPONENTS

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

# 72. AI COMPONENTS

```text
AIAssistant
AISuggestion
AIAction
AIExecution
AISource
AIConfidence
AIApproval
```

---

# 73. COMPONENT DEVELOPMENT CONTRACT

Every reusable component must define:

```text
Name
Purpose
Variants
Props
States
Light Theme
Dark Theme
Responsive Behavior
Accessibility
Interaction
Validation
Error Behavior
```

---

# 74. RESPONSIVE COMPONENT CONTRACT

Every reusable component must define behavior for:

```text
Desktop
Tablet
Mobile
```

Example:

```text
DataTable
Desktop → Full table
Tablet → Reduced columns
Mobile → Scroll/Card/Expand

Modal
Desktop → Centered dialog
Mobile → Full/near-full screen sheet

Sidebar
Desktop → Persistent
Tablet → Collapsible
Mobile → Drawer
```

---

# 75. THEME COMPONENT CONTRACT

Every reusable component must define:

```text
Light
Dark
```

plus:

```text
Default
Hover
Focus
Active
Selected
Disabled
Loading
Error
Success
```

where applicable.

---

# 76. DESIGN TOKEN ARCHITECTURE

Recommended hierarchy:

```text
Primitive Tokens
      ↓
Semantic Tokens
      ↓
Component Tokens
      ↓
Page Template Tokens
      ↓
Screen
```

Do not bypass semantic tokens.

---

# 77. EXAMPLE TOKEN STRUCTURE

```text
Primitive

Ocean-900
Ocean-800
Ocean-700
SeaGlass-500
Pearl-50
Ice-100
Brass-500
```

Then semantic:

```text
background-primary
surface-primary
text-primary
border-default
brand-primary
accent-maritime
```

Then component:

```text
button-primary-background
button-primary-text
table-row-hover
card-border
```

---

# 78. DESIGN TOKEN RULE

If a visual value appears repeatedly, it should become a token.

Avoid:

```text
margin: 17px
color: #123456
border-radius: 13px
```

when an established token exists.

---

# 79. RESPONSIVE TOKEN RULE

Where appropriate define responsive tokens for:

* spacing
* typography
* layout
* sidebar width
* grid columns
* card size
* modal size
* table behavior

---

# 80. THEME TOKEN RULE

Never implement:

```text
if dark then manually change every component color
```

Prefer:

```text
Component
   ↓
Semantic Token
   ↓
Theme Mapping
```

---

# 81. GRID SYSTEM

Desktop:

```text
12-column grid
```

Tablet:

```text
8-column conceptual grid
```

Mobile:

```text
4-column conceptual grid
```

Use flexible CSS layout rather than rigid pixel positioning.

---

# 82. CONTENT WIDTH

Typical desktop content width:

```text
1200–1440px
```

depending on screen type.

Do not stretch text-heavy content across the entire viewport.

---

# 83. MOBILE CONTENT WIDTH

Use comfortable horizontal padding.

Typical:

```text
16px
```

Increase where necessary for specific components.

---

# 84. FORM ACTIONS

Desktop:

```text
[Cancel] [Save Draft] [Save]
```

Mobile may use:

```text
Sticky Bottom Action Bar
```

where appropriate.

---

# 85. FILTER RESPONSIVENESS

Desktop:

```text
Search | Status | Date | Course | More
```

Mobile:

```text
Search

[Filters]
```

Open filters in a drawer/sheet.

---

# 86. NOTIFICATION RESPONSIVENESS

Desktop:

```text
Notification Panel
```

Mobile:

```text
Full-width Drawer / Screen
```

---

# 87. SEARCH RESPONSIVENESS

Desktop:

```text
Global Search
```

Mobile:

```text
Dedicated Search Screen / Overlay
```

Search should remain easily accessible.

---

# 88. MOBILE ACTION PRIORITY

On mobile prioritize:

```text
Primary Action
      ↓
Most common action
      ↓
Secondary action
      ↓
Overflow actions
```

Do not expose every desktop action simultaneously.

---

# 89. DATA VISUALIZATION ACCESSIBILITY

Charts must provide meaningful alternative information.

Use:

* labels
* summaries
* tables where appropriate
* accessible tooltips
* textual trends

Never make a critical business decision dependent solely on color.

---

# 90. AUTHENTICATION DESIGN

Authentication screens must support:

* Login
* Forgot Password
* Reset Password
* MFA
* Access Denied
* Session Expired

All must support:

* responsive layouts
* Light/Dark/System
* keyboard navigation
* accessible forms

---

# 91. PLATFORM DESIGN LANGUAGE

Platform screens should have a slightly higher information density than tenant screens.

Use:

* stronger operational indicators
* tenant health
* system health
* billing
* usage
* security
* audit

Avoid making Platform Admin look identical to Tenant Admin.

---

# 92. TENANT DESIGN LANGUAGE

Tenant application should emphasize:

* business workflows
* students
* admissions
* training
* finance
* compliance
* placement

---

# 93. STUDENT DESIGN LANGUAGE

Student Portal should emphasize:

* simplicity
* progress
* upcoming events
* attendance
* fees
* certificates
* placement

---

# 94. PUBLIC WEBSITE DESIGN LANGUAGE

Public website should emphasize:

* trust
* outcomes
* course discovery
* conversion
* visual storytelling

---

# 95. DESIGN REUSE RULE

Before creating a new component:

```text
1. Search existing components.
2. Search existing templates.
3. Reuse if possible.
4. Extend if appropriate.
5. Create new only when genuinely necessary.
```

Do not create duplicate components.

---

# 96. SCREEN DESIGN RULE

Every screen must be based on an existing template unless there is a documented reason for a new template.

The approximately 222 screens are not approximately 222 independent designs.

Target architecture:

```text
222+ Screens
      ↓
18 Templates
      ↓
30–50 Core Components
      ↓
Design Tokens
      ↓
Light / Dark / System
      ↓
Responsive System
```

---

# 97. SCREEN STATE STANDARD

Every major data-driven screen should consider:

```text
Loading
Empty
Populated
Error
Permission Restricted
Offline / Network Failure where applicable
Success
```

---

# 98. THEME QA MATRIX

Every foundation component should be reviewed against:

| Component    | Light | Dark | Mobile | Tablet | Desktop |
| ------------ | ----- | ---- | ------ | ------ | ------- |
| Button       | ✓     | ✓    | ✓      | ✓      | ✓       |
| Input        | ✓     | ✓    | ✓      | ✓      | ✓       |
| Select       | ✓     | ✓    | ✓      | ✓      | ✓       |
| Card         | ✓     | ✓    | ✓      | ✓      | ✓       |
| Table        | ✓     | ✓    | ✓      | ✓      | ✓       |
| Modal        | ✓     | ✓    | ✓      | ✓      | ✓       |
| Drawer       | ✓     | ✓    | ✓      | ✓      | ✓       |
| Chart        | ✓     | ✓    | ✓      | ✓      | ✓       |
| Sidebar      | ✓     | ✓    | ✓      | ✓      | ✓       |
| AI Component | ✓     | ✓    | ✓      | ✓      | ✓       |

No foundation component should be marked complete until this matrix is satisfied.

---

# 99. RESPONSIVE QA MATRIX

Each screen must be validated at minimum:

```text
390px
768px
1024px
1280px
1440px
```

Also validate important intermediate widths.

Check:

* overflow
* clipping
* text wrapping
* table behavior
* chart resizing
* navigation
* form layout
* dialog sizing
* button placement
* touch targets

---

# 100. ACCESSIBILITY QA MATRIX

Validate:

```text
Keyboard
Focus
Contrast
Labels
Screen Reader
Error Messages
Status Indicators
Reduced Motion
Touch Targets
```

in both Light and Dark modes.

---

# 101. DESIGN REVIEW GATE

Before expanding from foundation screens to the complete screen inventory:

```text
✓ Visual identity approved
✓ Color system approved
✓ Typography approved
✓ Spacing approved
✓ Components approved
✓ Light Mode approved
✓ Dark Mode approved
✓ System theme approved
✓ Responsive behavior approved
✓ Accessibility baseline approved
✓ Platform shell approved
✓ Tenant shell approved
✓ Student Portal foundation approved
✓ Public Website foundation approved
```

---

# 102. DESIGN QUALITY STANDARD

The final product should feel comparable to a mature enterprise SaaS platform while retaining a distinctive maritime identity.

Quality dimensions:

```text
Visual Quality
UX Quality
Responsive Quality
Theme Quality
Accessibility
Consistency
Performance Awareness
Security Awareness
AI Trust
Enterprise Readiness
```

---

# 103. WHAT TO AVOID

Never introduce:

* Generic blue SaaS styling
* Excessive gradients
* Neon colors
* Excessive glassmorphism
* Excessive shadows
* Over-rounded cards
* Random colors
* Random typography
* Random spacing
* Inconsistent iconography
* Desktop-only designs
* Dark-mode inversion
* Mobile layouts that merely shrink desktop
* Excessive nautical decoration
* AI visual gimmicks
* Unnecessary animations

---

# 104. DESIGN SYSTEM GOVERNANCE

Changes to the design system should be deliberate.

Before adding a new:

* color
* font
* spacing value
* radius
* component
* template
* interaction pattern

check whether an existing token or component can satisfy the requirement.

---

# 105. DESIGN SYSTEM CHANGE PRINCIPLE

Prefer:

```text
Reuse
   ↓
Extend
   ↓
Generalize
   ↓
Create New
```

not:

```text
Create New
   ↓
Create Another
   ↓
Create Another
```

---

# 106. FINAL DESIGN SYSTEM ARCHITECTURE

The MTI 360 design architecture is:

```text
BRAND
  ↓
DESIGN TOKENS
  ↓
SEMANTIC TOKENS
  ↓
LIGHT / DARK / SYSTEM
  ↓
RESPONSIVE RULES
  ↓
COMPONENT LIBRARY
  ↓
PAGE TEMPLATES
  ↓
PRODUCT SCREENS
  ↓
USER WORKFLOWS
```

---

# 107. FINAL PRINCIPLE

MTI 360 must be designed as:

> **One premium maritime product system that works beautifully across every device, every supported theme, and every major user experience.**

The three foundational principles are:

```text
CONSISTENT
RESPONSIVE
THEME-AWARE
```

Therefore:

**Every screen must be responsive.**

**Every reusable component must support Light and Dark modes.**

**System theme must be supported.**

**Accessibility must be considered in both themes.**

**The maritime visual identity must remain consistent across all experiences.**

**No screen should be designed as an isolated artifact.**

---

# END OF DESIGN SYSTEM
