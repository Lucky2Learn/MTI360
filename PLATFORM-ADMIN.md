# MTI 360 — PLATFORM ADMINISTRATION

## SaaS Control Plane Specification

**Product:** MTI 360
**Module:** Platform Administration / SaaS Control Plane
**Document:** `PLATFORM-ADMIN.md`
**Version:** 1.0
**Status:** Product Architecture Baseline

---

# 1. PURPOSE

MTI 360 is a multi-tenant SaaS platform used by multiple Maritime Training Institutes (MTIs).

The **Platform Administration module** is the control plane used by the organization operating MTI 360.

It manages the SaaS platform itself rather than the day-to-day operations of an individual MTI.

The Platform Administration layer is responsible for:

* Tenant lifecycle
* Tenant provisioning
* Subscription management
* Plans and pricing
* Billing
* Usage metering
* Platform-wide integrations
* AI provider/model management
* Platform AI governance
* Platform operations
* System health
* Customer support
* Controlled support access
* Security
* Audit
* Compliance
* Platform analytics
* Feature flags
* Platform configuration
* Platform administrator management

---

# 2. FUNDAMENTAL PRINCIPLE

## Platform Admin ≠ Tenant Admin

These are two completely different administrative boundaries.

### Platform Admin

Manages the MTI 360 SaaS platform and all subscribing tenants.

### Tenant Admin

Manages only one subscribing Maritime Training Institute.

For example:

```text
MTI 360 Platform
│
├── Tenant: Oceanic Maritime Institute
│
├── Tenant: BlueWave Maritime Academy
│
├── Tenant: National Maritime Training Centre
│
└── Tenant: Seafarers Training Institute
```

A Platform Administrator may have visibility across tenants according to role and permissions.

A Tenant Administrator can only access:

```text
Their Tenant
    ↓
Their Campuses
    ↓
Their Users
    ↓
Their Students
    ↓
Their Business Data
```

---

# 3. PLATFORM ADMIN BOUNDARY

Platform-level resources include:

```text
Platform
├── Tenants
├── Plans
├── Subscriptions
├── Billing
├── Usage
├── Platform Users
├── Platform Roles
├── Platform Integrations
├── AI Providers
├── AI Models
├── AI Policies
├── Feature Flags
├── System Health
├── Jobs
├── Queues
├── Incidents
├── Support
├── Security
├── Audit
├── Compliance
├── Backup
└── Platform Analytics
```

Tenant business resources are NOT platform-owned operational data.

Examples:

```text
Students
Admissions
Applications
Attendance
Faculty
Courses
Fees
Training
Placement
```

remain tenant-scoped.

Platform administrators may access tenant data only through explicitly authorized support or operational workflows.

---

# 4. MULTI-TENANT MODEL

Each subscribing MTI is represented as a tenant.

Example:

```text
Platform
│
├── Tenant A
│   ├── Campus A1
│   ├── Campus A2
│   ├── Users
│   ├── Students
│   ├── Courses
│   └── Operations
│
├── Tenant B
│   ├── Campus B1
│   ├── Users
│   ├── Students
│   └── Operations
│
└── Tenant C
    └── ...
```

Every tenant must have a unique internal identifier.

Example:

```text
tenant_id
```

Tenant data must be isolated at the backend/database authorization layer.

Frontend filtering alone is never considered tenant isolation.

---

# 5. TENANT LIFECYCLE

A tenant progresses through a defined lifecycle.

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

Possible reactivation:

```text
SUSPENDED
    ↓
ACTIVE
```

Cancellation and deactivation must be treated as separate states.

Cancellation refers to subscription/business status.

Deactivation refers to platform access status.

---

# 6. TENANT STATUS DEFINITIONS

## PROSPECT

Tenant is not yet provisioned.

## TRIAL

Tenant has trial access.

## PROVISIONING

Platform is creating/configuring tenant resources.

## ACTIVE

Tenant is fully operational.

## PAST_DUE

Subscription payment requires attention.

## SUSPENDED

Access is temporarily blocked.

## CANCELLED

Subscription has ended or been cancelled.

## DEACTIVATED

Tenant is no longer operationally active on the platform.

---

# 7. PLATFORM ADMIN ROLES

Platform access uses separate platform-level RBAC.

Recommended roles:

```text
Super Admin
Platform Operations Admin
Customer Success Admin
Billing Admin
Support Admin
Security / Audit Admin
AI / Platform Admin
```

These are platform roles and are completely separate from tenant roles.

---

# 8. SUPER ADMIN

Full platform administration.

Permissions may include:

* Tenant management
* Plans
* Subscriptions
* Billing
* Usage
* Platform users
* Platform roles
* Integrations
* AI configuration
* Security
* Audit
* Support
* Feature flags
* System configuration
* Platform analytics

Sensitive actions should require elevated confirmation and audit.

---

# 9. PLATFORM OPERATIONS ADMIN

Responsible for platform health.

Permissions:

* Tenant provisioning
* Background jobs
* Queues
* System health
* API monitoring
* Webhook monitoring
* Incidents
* Service health
* Operational logs

---

# 10. CUSTOMER SUCCESS ADMIN

Responsible for tenant relationship and onboarding.

Permissions:

* View tenants
* Tenant onboarding
* Tenant health
* Tenant usage
* Support
* Tenant configuration assistance
* Controlled support sessions according to policy

---

# 11. BILLING ADMIN

Responsible for:

* Plans
* Pricing
* Subscriptions
* Invoices
* Payments
* Discounts
* Trials
* Billing status
* Revenue analytics

---

# 12. SUPPORT ADMIN

Responsible for:

* Support tickets
* Tenant issues
* Support sessions
* Issue tracking
* Tenant communication

---

# 13. SECURITY / AUDIT ADMIN

Responsible for:

* Security events
* Login audit
* Session audit
* Data access audit
* Security policies
* Audit logs
* Retention policies
* Compliance controls

---

# 14. AI / PLATFORM ADMIN

Responsible for:

* AI providers
* AI models
* AI routing
* AI cost
* AI usage
* AI policies
* AI guardrails
* AI feature availability
* AI platform monitoring

---

# 15. PLATFORM AUTHENTICATION

Platform administrators use a separate authentication experience.

Recommended route:

```text
/platform/login
```

Authentication supports:

* Email/password
* MFA
* SSO where configured
* Password recovery
* Session management

Platform administrators should not authenticate through the normal tenant login flow unless explicitly supported by the identity architecture.

---

# 16. PLATFORM MFA

MFA should be mandatory for privileged platform roles.

Support:

* Authenticator application
* OTP
* Recovery codes
* Trusted device
* Session expiry

High-risk operations may require step-up authentication.

Examples:

```text
Delete tenant
Restore data
Change subscription
Rotate credentials
Change AI provider
Change security policy
```

---

# 17. PLATFORM DASHBOARD

Route:

```text
/platform/dashboard
```

Purpose:

Provide a single operational and business overview of MTI 360 as a SaaS platform.

---

# 18. PLATFORM DASHBOARD KPIs

Primary KPIs:

```text
Total Tenants
Active Tenants
Trial Tenants
New Tenants This Month
MRR
ARR
Active Users
Students Across Platform
Leads Across Platform
AI Executions
Communication Volume
Storage Usage
Failed Jobs
Open Support Tickets
Expiring Subscriptions
Suspended Tenants
```

KPIs must respect the current platform user's permissions.

---

# 19. PLATFORM DASHBOARD CHARTS

Recommended charts:

### Tenant Growth

```text
New tenants
Active tenants
Cancelled tenants
```

### Subscription Distribution

```text
Starter
Professional
Business
Enterprise
```

### MRR Trend

Monthly recurring revenue.

### Retention / Churn

Show historical measurements.

### Platform Usage

Usage across tenants.

### AI Usage

Requests, executions and cost.

### Communication Volume

```text
WhatsApp
Email
SMS
Voice
```

### Platform Health

```text
API
Database
Workers
Queues
Storage
External providers
```

---

# 20. PLATFORM DASHBOARD TABLES

### Recent Tenants

Fields:

```text
Tenant
Plan
Status
Created
Users
Students
Usage
MRR
```

### Failed Jobs

```text
Job
Tenant
Type
Started
Duration
Status
Retry
```

### Support Issues

```text
Ticket
Tenant
Priority
Assigned
Status
Updated
```

### Security Events

```text
Event
Actor
Tenant
Timestamp
Risk
Status
```

---

# 21. PLATFORM QUICK ACTIONS

Provide:

```text
Create Tenant
Invite Tenant Admin
Manage Subscription
View Tenant
Open Support Ticket
View Platform Health
Create Announcement
View Security Events
```

Actions must be permission-controlled.

---

# 22. TENANT MANAGEMENT

Route:

```text
/platform/tenants
```

---

# 23. TENANT LIST

The tenant list provides the platform-wide tenant directory.

Filters:

```text
Status
Plan
Subscription
Location
Created Date
Usage
Health
```

Search:

```text
Institute Name
Tenant ID
Domain
Admin Email
```

Columns:

```text
Tenant
Status
Plan
Subscription
Users
Students
Usage
Health
Created
Actions
```

---

# 24. TENANT 360

Route:

```text
/platform/tenants/:tenantId
```

The Tenant 360 page provides a consolidated view of a tenant.

Tabs:

```text
Overview
Subscription
Usage
Users
Campuses
Integrations
AI
Communication
Billing
Support
Health
Audit
```

---

# 25. TENANT 360 OVERVIEW

Show:

```text
Tenant Name
Tenant ID
Status
Plan
Subscription
Primary Admin
Created Date
Last Activity
Health
```

Operational indicators:

```text
Users
Students
Leads
Applications
AI Usage
Communication
Storage
API Usage
```

---

# 26. CREATE TENANT

Route:

```text
/platform/tenants/new
```

Use a wizard.

Steps:

```text
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
```

---

# 27. TENANT INSTITUTE INFORMATION

Fields may include:

```text
Institute Name
Legal Name
Registration Information
Address
City
State
Country
Contact Number
Email
Website
Domain
Timezone
Currency
```

Do not invent regulatory fields unless defined in the product requirements.

---

# 28. TENANT SUBSCRIPTION SETUP

Select:

```text
Plan
Billing Cycle
Trial
Start Date
Renewal Date
Add-ons
Usage Limits
```

---

# 29. TENANT PRIMARY ADMIN

Fields:

```text
Name
Email
Mobile
Role
MFA Required
Invitation Status
```

The primary tenant administrator is different from a Platform Administrator.

---

# 30. TENANT CAMPUS SETUP

Allow creation of one or more campuses.

Fields:

```text
Campus Name
Code
Address
Contact
Timezone
Status
```

---

# 31. TENANT COURSE SETUP

Allow initial course configuration.

Examples:

```text
STCW Basic Safety Training
Pre-Sea Deck Cadet
Pre-Sea GP Rating
Post-Sea Advanced Fire Fighting
Personal Survival Techniques
Medical First Aid
```

Actual master data should be configurable.

---

# 32. TENANT BRANDING

Allow configuration of:

```text
Logo
Favicon
Primary Brand Color
Secondary Color
Email Branding
Portal Branding
Domain
```

Platform design system remains consistent.

Tenant branding should not allow unsafe or inaccessible configurations.

---

# 33. TENANT COMMUNICATION SETUP

Configure:

```text
WhatsApp
Email
SMS
Voice
```

Show:

```text
Provider
Status
Verification
Usage
```

Credentials must be masked.

---

# 34. TENANT AI SETUP

Configure tenant-level AI features.

Examples:

```text
AI Assistant
AI Agents
Knowledge/RAG
SQL/Data Agent
Automation
```

Platform-wide AI policies always take precedence over tenant-level settings.

---

# 35. TENANT ACTIVATION

Before activation, show a validation checklist:

```text
✓ Tenant profile
✓ Subscription
✓ Primary admin
✓ Campus
✓ Required configuration
✓ Communication
✓ Billing
✓ AI
```

Only permitted platform roles can activate a tenant.

---

# 36. TENANT SUSPENSION

Suspending a tenant requires:

```text
Reason
Effective Time
Expected Duration
Notification
```

Confirmation:

```text
Suspend Tenant?
```

Explain impact.

The operation must create an audit record.

---

# 37. TENANT REACTIVATION

Require:

```text
Reason
Operator
Timestamp
```

Audit the action.

---

# 38. TENANT DEACTIVATION

Deactivation is a high-risk action.

Require:

* Explicit confirmation
* Reason
* Authorized role
* Optional step-up authentication
* Audit entry

Data should not be physically deleted merely because a tenant is deactivated unless a separate approved data deletion process is executed.

---

# 39. PLANS & PRICING

Route:

```text
/platform/plans
```

Manage:

```text
Plan Name
Description
Billing Cycle
Base Price
Features
Limits
Add-ons
Trial
Status
```

Do not hard-code commercial pricing in the frontend unless defined elsewhere.

---

# 40. FEATURE ENTITLEMENTS

Each plan may define feature entitlements.

Example:

```text
Feature
Starter
Professional
Business
Enterprise
```

Possible features:

```text
Admissions
Marketing
Automation
AI
WhatsApp
Voice
Analytics
Advanced Reports
API
Multiple Campuses
Custom Domain
```

---

# 41. TENANT-SPECIFIC OVERRIDES

Platform administrators may grant controlled overrides.

Example:

```text
Feature:
AI Agent

Plan Limit:
1000 executions/month

Tenant Override:
2500 executions/month
```

Overrides require:

```text
Reason
Operator
Start Date
End Date
```

Audit all changes.

---

# 42. SUBSCRIPTION MANAGEMENT

Route:

```text
/platform/subscriptions
```

Fields:

```text
Tenant
Plan
Status
Start Date
Renewal Date
Billing Cycle
Amount
Payment Status
```

Actions:

```text
Change Plan
Renew
Pause
Cancel
Resume
```

All commercial actions require appropriate authorization.

---

# 43. BILLING

Route:

```text
/platform/billing
```

Sections:

```text
Overview
Invoices
Payments
Refunds
Failed Payments
Revenue
```

---

# 44. PAYMENT TRANSACTIONS

Display:

```text
Transaction ID
Tenant
Invoice
Amount
Currency
Provider
Status
Date
```

Statuses:

```text
Success
Pending
Failed
Refunded
Partially Refunded
```

---

# 45. COUPONS AND DISCOUNTS

Support:

```text
Coupon Code
Discount Type
Discount Value
Eligibility
Start Date
Expiry
Usage Limit
Tenant Limit
```

---

# 46. TRIAL MANAGEMENT

Support:

```text
Trial Duration
Trial Plan
Trial Features
Usage Limits
Conversion Rules
Expiry Notifications
```

---

# 47. USAGE METERING

Platform must measure resource consumption.

Possible dimensions:

```text
AI Requests
AI Tokens
AI Cost
WhatsApp Messages
Email Messages
SMS Messages
Voice Minutes
API Requests
Storage
Users
Students
Documents
Background Jobs
```

Usage is:

```text
Tenant Scoped
Time Scoped
Feature Scoped
```

---

# 48. USAGE LIMITS

When a tenant approaches limits:

```text
80% → Warning
90% → Critical Warning
100% → Limit Reached
```

Actual enforcement depends on the subscription configuration.

Provide notifications and platform visibility.

---

# 49. COMMUNICATION PROVIDERS

Platform administrators can manage supported communication providers.

Provider categories:

```text
WhatsApp
Email
SMS
Voice
```

Display:

```text
Provider
Environment
Status
Health
Usage
Cost
Last Check
```

Credentials must never be displayed in plaintext.

---

# 50. AI PROVIDERS

Platform AI configuration includes:

```text
Provider
Model
Capability
Status
Cost
Rate Limit
Availability
```

Use a provider abstraction rather than hard-coding one AI provider throughout the application.

---

# 51. AI MODEL ROUTING

Platform may define model routing policies.

Examples:

```text
Simple classification → economical model
Complex reasoning → advanced model
Embeddings → embedding model
Speech → speech provider
```

Actual routing must be defined by backend policy.

---

# 52. AI COST MANAGEMENT

Track:

```text
Requests
Input Tokens
Output Tokens
Total Tokens
Cost
Tenant
Feature
Model
Time
```

Analytics:

```text
Cost by Tenant
Cost by Feature
Cost by Model
Cost Trend
Cost Anomalies
```

---

# 53. GLOBAL AI GUARDRAILS

Platform-level AI policies may define:

```text
Allowed Models
Maximum Usage
Sensitive Actions
Human Approval
Tool Access
Data Access
Confidence Threshold
Retention
Logging
```

Tenant settings cannot override platform security policies.

---

# 54. AI EXECUTION MONITORING

Track:

```text
Execution ID
Tenant
User
Feature
Model
Decision
Confidence
Latency
Status
Cost
```

Avoid storing/displaying raw prompts or provider payloads unnecessarily.

---

# 55. GLOBAL INTEGRATIONS

Platform integrations may include:

```text
Payment
AI
Email
SMS
WhatsApp
Voice
Storage
Identity
Monitoring
Webhooks
```

Every integration should expose:

```text
Status
Health
Configuration
Last Test
Last Failure
```

---

# 56. TENANT PROVISIONING ENGINE

Tenant creation may trigger provisioning jobs.

Example:

```text
Create Tenant
      ↓
Create Tenant Record
      ↓
Create Default Roles
      ↓
Create Default Settings
      ↓
Create Initial Admin
      ↓
Create Campus
      ↓
Configure Plan
      ↓
Configure Features
      ↓
Configure Integrations
      ↓
Provision Complete
```

Provisioning must be idempotent.

Failed steps must be retryable.

---

# 57. BACKGROUND JOBS

Monitor:

```text
Job ID
Type
Tenant
Queue
Status
Started
Completed
Duration
Attempts
Error
```

Statuses:

```text
Queued
Running
Completed
Failed
Retrying
Cancelled
```

---

# 58. QUEUE HEALTH

Show:

```text
Queue
Pending
Running
Failed
Latency
Throughput
```

Critical queue degradation should generate platform alerts.

---

# 59. SYSTEM HEALTH

Platform health dashboard should monitor:

```text
Frontend
API
Database
Cache
Workers
Queue
Storage
AI Providers
Communication Providers
Payment Providers
```

Status:

```text
Healthy
Degraded
Critical
Unknown
```

---

# 60. API MONITORING

Track:

```text
Endpoint
Requests
Latency
Error Rate
Status Codes
Tenant
Time Period
```

Avoid exposing sensitive request payloads.

---

# 61. WEBHOOK MONITORING

Track:

```text
Webhook
Provider
Tenant
Event
Status
Attempts
Last Attempt
Response
```

Provide retry only where technically safe.

---

# 62. INCIDENT MANAGEMENT

Incident dashboard:

```text
Incident
Service
Severity
Started
Duration
Status
Owner
Affected Tenants
```

Statuses:

```text
Investigating
Identified
Monitoring
Resolved
Closed
```

---

# 63. SUPPORT TICKETS

Route:

```text
/platform/support
```

Fields:

```text
Ticket
Tenant
Requester
Category
Priority
Status
Assigned
Created
Updated
```

Categories:

```text
Billing
Technical
Account
Integration
AI
Communication
Performance
Security
Other
```

---

# 64. SUPPORT TICKET DETAIL

Include:

```text
Conversation
Tenant Context
Issue
Attachments
Activity
Internal Notes
Status
Assignment
Related Incident
```

Never expose internal notes to tenants.

---

# 65. CONTROLLED SUPPORT SESSION

Platform support users may enter a tenant context only through an explicit controlled mechanism.

Flow:

```text
Platform Admin
      ↓
Select Tenant
      ↓
Start Support Session
      ↓
Select Reason
      ↓
Select Access Mode
      ↓
Confirm
      ↓
Tenant Application
```

Modes:

```text
Read Only
Limited Support Write
```

Only approved roles may use write access.

---

# 66. SUPPORT SESSION BANNER

While active:

```text
SUPPORT SESSION

Tenant:
ABC Maritime Training Institute

Mode:
Read Only

Operator:
Platform Support Admin

Reason:
Investigating configuration issue

Started:
10:42 AM

[Exit Session]
```

The banner must remain visible.

---

# 67. SUPPORT SESSION AUDIT

Log:

```text
Session ID
Operator
Tenant
Start Time
End Time
Reason
Access Mode
Actions Performed
```

Every write action must be traceable.

---

# 68. PLATFORM NOTIFICATIONS

Platform administrators may send announcements.

Audience:

```text
All Tenants
Selected Plans
Selected Tenants
```

Channels:

```text
In-App
Email
SMS
WhatsApp
```

Only configured channels should be available.

---

# 69. PLATFORM MESSAGE TEMPLATES

Manage:

```text
Email Templates
SMS Templates
WhatsApp Templates
System Notifications
```

Examples:

```text
Trial Expiring
Payment Failed
Subscription Renewed
Maintenance Notice
Service Incident
Usage Limit
```

---

# 70. FEATURE FLAGS

Platform feature flags control controlled rollout.

Example:

```text
Feature
Environment
Enabled
Percentage
Tenant Allowlist
Start
End
```

Support:

```text
Global
Tenant-specific
Role-specific
```

Feature flags must not replace authorization.

---

# 71. DOMAIN MANAGEMENT

Platform may manage:

```text
MTI 360 SaaS Domain
Tenant Custom Domains
DNS Verification
SSL Status
Branding
```

Domain ownership verification must be required before activation.

---

# 72. TENANT PROVISIONING TEMPLATES

Templates can define defaults:

```text
Default Roles
Default Permissions
Default Courses
Default Communication Templates
Default Notifications
Default Workflows
Default AI Features
Default Settings
```

Provisioning templates must be versioned.

---

# 73. SECURITY DASHBOARD

Monitor:

```text
Failed Logins
Suspicious Sessions
MFA Status
Privileged Actions
Support Sessions
Credential Changes
Security Events
```

---

# 74. PLATFORM AUDIT LOG

Every privileged action should be auditable.

Example:

```text
Timestamp
Actor
Role
Action
Resource
Tenant
Result
IP / Session Reference
Reason
```

Do not log secrets.

---

# 75. LOGIN / SESSION AUDIT

Track:

```text
User
Role
Login Time
Logout Time
MFA
Device
Session
Result
```

---

# 76. DATA ACCESS AUDIT

Sensitive tenant data access should be traceable.

Example:

```text
Platform User
Tenant
Resource
Action
Timestamp
Reason
Result
```

This is particularly important for support sessions.

---

# 77. DATA RETENTION

Platform administrators may configure retention policies where supported.

Potential categories:

```text
Audit Logs
Application Logs
Support Records
AI Execution Metadata
Communication Logs
Deleted Tenant Data
```

Actual retention periods must be defined by product/legal requirements rather than hard-coded by UI.

---

# 78. BACKUP STATUS

Display:

```text
Last Backup
Backup Status
Backup Size
Next Scheduled Backup
Retention
Last Restore Test
```

Restore operations require high privilege.

---

# 79. PLATFORM ANALYTICS

Platform analytics are different from tenant analytics.

Tenant analytics:

> How is my institute performing?

Platform analytics:

> How is the MTI 360 SaaS business and infrastructure performing?

---

# 80. TENANT GROWTH ANALYTICS

Metrics:

```text
New Tenants
Active Tenants
Trial Conversion
Cancelled Tenants
Tenant Growth
```

---

# 81. REVENUE ANALYTICS

Metrics:

```text
MRR
ARR
Revenue
Average Revenue Per Tenant
Plan Distribution
Revenue by Plan
```

Historical measurements should be preserved.

---

# 82. RETENTION ANALYTICS

Metrics:

```text
Active Tenants
Cancelled Tenants
Retention
Churn
Trial Conversion
Expansion
Contraction
```

---

# 83. PLATFORM AI ANALYTICS

Metrics:

```text
AI Executions
AI Cost
Cost per Tenant
Cost per Feature
Model Usage
Failure Rate
Latency
```

---

# 84. PLATFORM ADMIN USERS

Route:

```text
/platform/admin-users
```

Fields:

```text
Name
Email
Role
Status
MFA
Last Login
Created
```

---

# 85. PLATFORM ROLES & PERMISSIONS

Use granular permissions.

Example:

```text
tenant.read
tenant.create
tenant.update
tenant.suspend
tenant.activate

billing.read
billing.update

subscription.read
subscription.update

usage.read

support.read
support.session.read
support.session.write

security.read

audit.read

ai.read
ai.configure

platform.settings.read
platform.settings.update
```

Do not rely solely on broad role names.

---

# 86. PLATFORM ADMIN PROFILE

Include:

```text
Name
Email
Mobile
Role
MFA
Sessions
Security
Notifications
```

---

# 87. PLATFORM SETTINGS

Global settings may include:

```text
General
Localization
Currency
Timezone
Notifications
Security
Session
Audit
AI
Communication
Billing
```

Sensitive settings require elevated authorization.

---

# 88. TENANT CONTEXT SWITCHING

Platform administrators may have a tenant context selector.

Example:

```text
All Tenants
↓
ABC Maritime Training Institute
```

When a tenant context is selected, the UI must visibly indicate it.

Never make context switching invisible.

---

# 89. TENANT DATA ACCESS PRINCIPLE

Platform-level access to tenant data must be:

```text
Explicit
Authorized
Purpose-bound
Audited
Time-bound where possible
```

Platform users should not casually browse tenant operational data.

---

# 90. DATA ISOLATION

All tenant-scoped backend operations must enforce:

```text
authenticated_user
        ↓
platform/tenant role
        ↓
tenant context
        ↓
authorization
        ↓
data access
```

Never trust a browser-provided tenant identifier for authorization.

---

# 91. API DESIGN PRINCIPLE

Platform APIs should be clearly separated from tenant APIs.

Example:

```text
/platform/api/tenants
/platform/api/subscriptions
/platform/api/billing
/platform/api/usage
/platform/api/platform-users
/platform/api/audit
/platform/api/health
```

Tenant APIs:

```text
/api/tenant/*
```

Exact implementation must follow `ARCHITECTURE.md`.

---

# 92. AUDIT REQUIREMENT

Audit at minimum:

```text
Create Tenant
Update Tenant
Suspend Tenant
Activate Tenant
Change Plan
Change Subscription
Billing Changes
Feature Override
AI Configuration
Integration Changes
Support Session
Privileged Data Access
Platform User Changes
Role Changes
Security Changes
Feature Flag Changes
```

---

# 93. DESTRUCTIVE ACTIONS

Destructive or high-risk actions require:

```text
Confirmation
Reason
Authorization
Audit
```

Examples:

```text
Delete
Deactivate
Suspend
Cancel
Restore
Credential Rotation
Security Policy Change
```

---

# 94. PLATFORM UI SHELL

Platform shell should be visually distinct from tenant application while remaining part of MTI 360.

Header:

```text
MTI 360 Platform
All Tenants
```

Sidebar:

```text
Overview

TENANTS
  Tenants
  Onboarding

COMMERCIAL
  Plans
  Subscriptions
  Billing
  Usage

AI PLATFORM
  Providers
  Models
  Usage
  Guardrails

INTEGRATIONS
  Communication
  Payments
  Global Integrations

OPERATIONS
  Jobs
  Queues
  System Health
  API Monitoring
  Incidents

SUPPORT
  Tickets
  Support Sessions

SECURITY
  Security
  Audit
  Sessions
  Data Access
  Retention
  Backup

ANALYTICS
  Platform
  Tenants
  Revenue
  Retention
  AI

PLATFORM
  Feature Flags
  Notifications
  Admin Users
  Roles
  Settings
```

---

# 95. PLATFORM TOP BAR

Recommended:

```text
MTI 360 Platform
[All Tenants ▼]

Global Search
Notifications
AI Assistant
Help
Admin Profile
```

---

# 96. PLATFORM SEARCH

Global platform search may search:

```text
Tenants
Subscriptions
Invoices
Tickets
Users
Incidents
Audit Events
```

Search results must respect platform permissions.

---

# 97. PLATFORM AI ASSISTANT

Platform AI assistant may answer:

```text
"What needs attention today?"

"Which tenants are approaching usage limits?"

"Show failed payments."

"Which subscriptions expire in the next seven days?"

"Show AI cost anomalies."

"Are any communication providers degraded?"

"Which tenants have open critical support tickets?"
```

The AI must not bypass platform permissions.

---

# 98. PLATFORM AI ACTION CONFIRMATION

For sensitive operations:

```text
AI recommends:
Suspend tenant ABC Maritime Training Institute.

Reason:
Subscription payment failure.

[Review]
[Cancel]
```

AI must not independently perform high-risk platform operations without explicit authorization.

---

# 99. PLATFORM NOTIFICATION CENTER

Notifications may include:

```text
Payment Failure
System Incident
Tenant Provisioning Failure
AI Cost Alert
Communication Provider Failure
Security Event
Backup Failure
Subscription Expiry
```

Prioritize by severity.

---

# 100. PLATFORM ERROR HANDLING

Every platform screen must support:

```text
Loading
Empty
Error
Permission Denied
Partial Failure
Retry
```

Operational screens should expose enough diagnostic information for authorized users without exposing secrets.

---

# 101. PLATFORM RESPONSIVE DESIGN

Platform Admin is primarily desktop-oriented.

Support:

```text
1440px
1280px
1024px
768px
```

Mobile should provide essential monitoring and support functionality but does not need to reproduce every dense operational screen.

---

# 102. PLATFORM DESIGN PRINCIPLES

The Platform Console should feel:

```text
Premium
Enterprise
Operational
Trustworthy
Controlled
Data-rich
Calm
Fast
Secure
```

Avoid:

```text
Legacy ERP
Government portal
Generic admin template
Overly colorful dashboard
Excessive charts
Excessive animation
```

---

# 103. PLATFORM VS TENANT VISUAL DIFFERENCE

Platform UI:

```text
Control Plane
Operational
System-oriented
SaaS metrics
Tenant portfolio
Infrastructure
Revenue
Security
```

Tenant UI:

```text
Institute Operations
Students
Admissions
Training
Finance
Compliance
Placement
```

The two should share the same MTI 360 design system but have different information hierarchy.

---

# 104. PLATFORM SCREEN INVENTORY

The initial Platform screen inventory is:

```text
PLAT-01  Platform Login
PLAT-02  Platform MFA
PLAT-03  Platform Dashboard

PLAT-04  Tenant List
PLAT-05  Tenant 360
PLAT-06  Create Tenant
PLAT-07  Tenant Onboarding
PLAT-08  Tenant Status
PLAT-09  Tenant Usage & Health
PLAT-10  Tenant Users / Support Access

PLAT-11  Plans & Pricing
PLAT-12  Subscription Management
PLAT-13  Billing & Invoices
PLAT-14  Payment Transactions
PLAT-15  Coupons / Discounts / Trials
PLAT-16  Feature Entitlements
PLAT-17  Usage Metering

PLAT-18  Communication Provider Management
PLAT-19  AI Provider / Model Management
PLAT-20  AI Cost & Usage
PLAT-21  Global AI Guardrails
PLAT-22  Global Integrations

PLAT-23  Tenant Provisioning / Jobs
PLAT-24  Background Jobs
PLAT-25  System Health
PLAT-26  API / Webhook Monitoring
PLAT-27  Error / Incident Dashboard

PLAT-28  Support Tickets
PLAT-29  Support Ticket Detail
PLAT-30  Controlled Support Session

PLAT-31  Platform Notifications
PLAT-32  Platform Templates

PLAT-33  Feature Flags
PLAT-34  Global Configuration

PLAT-35  Security Dashboard
PLAT-36  Platform Audit Logs
PLAT-37  Login / Session Audit
PLAT-38  Data Access Audit
PLAT-39  Compliance / Data Retention
PLAT-40  Backup / Restore Status

PLAT-41  System-wide Analytics
PLAT-42  Tenant Growth Analytics
PLAT-43  MRR / ARR / Revenue Analytics
PLAT-44  Churn / Retention Analytics
PLAT-45  Subscription Analytics
PLAT-46  Platform AI Analytics

PLAT-47  API Keys / Service Credentials
PLAT-48  Domain / Branding Management
PLAT-49  Tenant Provisioning Templates

PLAT-50  Platform Admin Users
PLAT-51  Platform Roles & Permissions
PLAT-52  Platform Admin Profile
PLAT-53  Platform Settings
```

---

# 105. PLATFORM SCREEN PRIORITY

## P0

```text
PLAT-01
PLAT-02
PLAT-03
PLAT-04
PLAT-05
PLAT-06
PLAT-07
PLAT-08
PLAT-11
PLAT-12
PLAT-13
PLAT-16
PLAT-17
PLAT-23
PLAT-24
PLAT-25
PLAT-28
PLAT-30
PLAT-35
PLAT-36
PLAT-50
PLAT-51
PLAT-53
```

## P1

```text
PLAT-09
PLAT-10
PLAT-14
PLAT-15
PLAT-18
PLAT-19
PLAT-20
PLAT-21
PLAT-22
PLAT-26
PLAT-27
PLAT-29
PLAT-31
PLAT-32
PLAT-33
PLAT-34
PLAT-37
PLAT-38
PLAT-39
PLAT-41
PLAT-42
PLAT-43
PLAT-44
PLAT-45
PLAT-46
PLAT-52
```

## P2

```text
PLAT-40
PLAT-47
PLAT-48
PLAT-49
```

Priorities may be changed after product/architecture review.

---

# 106. PLATFORM IMPLEMENTATION PRINCIPLE

Do not implement all 53 screens as separate custom applications.

Use reusable templates.

Recommended platform templates:

```text
Platform Dashboard
Tenant List
Tenant 360
Wizard
Commercial List
Usage Analytics
Operations Console
Support Workspace
Security Console
Audit Console
Analytics Dashboard
Settings
```

---

# 107. PLATFORM COMPONENTS

Reusable components:

```text
PlatformShell
TenantContextSelector
PlatformKpiCard
TenantStatusBadge
SubscriptionBadge
UsageMeter
HealthIndicator
SystemHealthCard
AuditTimeline
SecurityEventTable
SupportSessionBanner
ProvisioningProgress
UsageChart
RevenueChart
TenantHealthCard
ConfirmationDialog
StepUpAuthDialog
PermissionGate
```

---

# 108. PLATFORM SECURITY UX PRINCIPLE

The UI must communicate security clearly.

Examples:

```text
Tenant Context
Support Session
Read Only
Privileged Action
MFA Required
Audit Required
Permission Denied
```

Security should be visible but not intrusive.

---

# 109. PLATFORM DATA PRINCIPLE

The platform console should display aggregated tenant information by default.

For example:

```text
Tenant Count
Active Users
Students
Usage
Revenue
```

rather than exposing individual student records.

Detailed tenant data should require an explicit tenant context and appropriate authorization.

---

# 110. PLATFORM AUDITABILITY PRINCIPLE

Every platform administrator action that can affect:

* tenant access
* tenant data
* money
* subscriptions
* AI
* security
* integrations
* platform configuration

must be traceable.

The audit trail must identify:

```text
Who
What
When
Where
Which Tenant
Why
Result
```

---

# 111. PLATFORM BUSINESS PRINCIPLE

MTI 360 should eventually be capable of operating as a true SaaS business.

The platform control plane therefore must support the complete lifecycle:

```text
Acquire Tenant
      ↓
Trial
      ↓
Onboard
      ↓
Activate
      ↓
Monitor Usage
      ↓
Support
      ↓
Bill
      ↓
Expand
      ↓
Renew
```

The platform should provide operators with enough information to understand both:

```text
Business Health
```

and

```text
Technical Health
```

without mixing the two.

---

# 112. FINAL ARCHITECTURAL RULE

MTI 360 consists of:

```text
                    MTI 360
                       │
          ┌────────────┴────────────┐
          │                         │
   PLATFORM CONTROL PLANE      TENANT APPLICATION
          │                         │
    All MTI Tenants             One MTI
          │                         │
   SaaS Operations              Institute Operations
          │                         │
   Billing / AI / Health        Students / Training
   Security / Support           Admissions / Finance
   Analytics / Provisioning     Compliance / Placement
```

The Platform Control Plane must remain logically and visually distinct from the Tenant Application.

---

# 113. DEFINITION OF DONE

The Platform Administration module is considered sufficiently defined when:

* Platform and tenant administration are separated.
* Platform roles are defined.
* Tenant lifecycle is defined.
* Tenant provisioning is defined.
* Subscription lifecycle is defined.
* Billing responsibilities are defined.
* Usage metering is defined.
* AI platform governance is defined.
* Communication provider management is defined.
* Platform operations are defined.
* Support workflow is defined.
* Controlled support sessions are defined.
* Security and audit requirements are defined.
* Platform analytics are defined.
* Platform routes are defined.
* Platform screen IDs are defined.
* Platform P0/P1/P2 priorities are defined.
* Reusable platform templates are defined.
* Multi-tenant isolation principles are documented.
* High-risk operations require authorization and audit.

This document becomes the functional baseline for the MTI 360 Platform Administration UI, API design and implementation.
