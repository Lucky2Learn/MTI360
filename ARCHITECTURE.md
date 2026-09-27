# MTI 360 — System Architecture

**Document:** ARCHITECTURE.md
**Version:** 1.0
**Product:** MTI 360
**Architecture Style:** Modular SaaS + Agent Platform + Event-Driven Automation
**Deployment:** Docker-first, cloud-ready
**Primary Database:** PostgreSQL
**Frontend:** Next.js + React + TypeScript
**Backend:** Python + FastAPI
**AI/Agent Runtime:** Python
**Background Processing:** Redis + Worker/Queue
**Object Storage:** S3-compatible storage
**Containerization:** Docker
**Initial Deployment:** Docker Compose
**Future Deployment:** Managed Cloud / Kubernetes if required

> **Architecture Decision Records (added T00-01, 2026-09-26).**
> Approved architecture decisions are recorded in [`docs/adr/`](docs/adr/). Where an ADR refines this document, the ADR is authoritative and the affected section carries a "T00-01 update" note:
> [ADR-0001 Stack](docs/adr/0001-stack.md) ·
> [ADR-0002 Monorepo layout](docs/adr/0002-monorepo-layout.md) ·
> [ADR-0003 Marketing website vs tenant public website](docs/adr/0003-marketing-vs-tenant-public-website.md) ·
> [ADR-0004 Tenant isolation](docs/adr/0004-tenant-isolation.md) ·
> [ADR-0005 Identity and session realms](docs/adr/0005-identity-and-session-realms.md) ·
> [ADR-0006 API prefixes](docs/adr/0006-api-prefixes.md).
> Design notes: [`docs/architecture/`](docs/architecture/). Known specification inconsistencies: [`spec-inconsistencies.md`](docs/architecture/spec-inconsistencies.md).

---

# 1. Architecture Vision

MTI 360 should not be designed as a traditional monolithic institute ERP.

It should be designed as:

> **A multi-tenant SaaS platform with a reusable AI Agent Platform, modular business services, event-driven workflows and vertical-specific maritime capabilities.**

The architecture must support three levels:

```text
┌───────────────────────────────────────────────┐
│                SaaS PRODUCTS                  │
│                                               │
│       MTI 360     ACRS     Future SaaS       │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│           SHARED PLATFORM SERVICES            │
│                                               │
│ Tenant │ Auth │ RBAC │ CRM │ Documents       │
│ Billing │ Notifications │ Workflow │ Audit   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│             AI AGENT PLATFORM                 │
│                                               │
│ WhatsApp │ Email │ Voice │ SMS │ SQL          │
│ Workflow │ Instagram │ YouTube │ Blog         │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│             VERTICAL DOMAIN LAYER             │
│                                               │
│ MTI Courses │ Maritime Compliance │ Training  │
│ Placement │ Faculty │ Simulator │ Certification│
└───────────────────────────────────────────────┘
```

---

# 2. Architectural Goals

The system must be:

* multi-tenant
* secure
* modular
* AI-ready
* agent-enabled
* workflow-driven
* API-first
* scalable
* observable
* auditable
* cloud-ready
* provider-independent
* reusable across verticals

---

# 3. Architectural Principles

## 3.1 Multi-Tenant by Design

Tenant isolation is a fundamental architectural requirement.

Every tenant-owned business entity must contain:

```text
tenant_id
```

Tenant context must be established from the authenticated session/token and server-side configuration.

The backend must never trust a client-supplied `tenant_id`.

---

# 3.2 API First

All business operations must be exposed through well-defined backend APIs.

The frontend must not directly access the database.

```text
Next.js
   ↓
FastAPI
   ↓
Domain Service
   ↓
Repository
   ↓
PostgreSQL
```

---

# 3.3 Modular Monolith First

The initial system should be a **modular monolith**, not microservices.

Recommended:

```text
One deployable backend
        +
Clear domain modules
        +
Internal service boundaries
        +
Event-driven communication
```

This provides simplicity during early development while keeping the architecture ready for future extraction into services.

---

# 3.4 Extract to Microservices Only When Necessary

Do not create:

```text
20 microservices
```

on day one.

Potential future extraction candidates:

* Agent Runtime
* Voice Service
* Notification Service
* Workflow Engine
* Document Processing
* Analytics
* Search/RAG

Only extract when there is a real scalability, deployment or ownership reason.

---

# 3.5 AI Is a Platform Capability

AI must not be embedded directly into individual business modules.

Avoid:

```text
AdmissionService → OpenAI API
FinanceService → OpenAI API
MarketingService → OpenAI API
```

Instead:

```text
Business Module
      ↓
AI/Agent Platform
      ↓
Provider Abstraction
      ↓
LLM Provider
```

---

# 3.6 Provider Abstraction

AI and communication providers must be replaceable.

Example:

```text
AIProvider
 ├── OpenAIProvider
 ├── AnthropicProvider
 ├── GoogleProvider
 └── FakeAIProvider
```

Communication:

```text
WhatsAppProvider
 ├── ProviderA
 └── ProviderB
```

Voice:

```text
VoiceProvider
 ├── ProviderA
 └── ProviderB
```

The business layer must not depend directly on a specific provider.

---

# 4. High-Level Architecture

```text
                           USERS
                             │
                ┌────────────┴────────────┐
                │                         │
             Browser                  Mobile
                │
                ▼
        ┌──────────────────┐
        │     Next.js      │
        │ React + TypeScript│
        └────────┬─────────┘
                 │ HTTPS
                 ▼
        ┌────────────────────────┐
        │      API Gateway       │
        │       FastAPI          │
        └────────────┬───────────┘
                     │
          ┌──────────┴───────────┐
          │                      │
          ▼                      ▼
   Business Modules         Agent Platform
          │                      │
          │              ┌───────┴────────┐
          │              │                │
          │          Agent Runtime     Workflow
          │              │                │
          │          Tools/Knowledge    Events
          │
          ▼
     Domain Services
          │
          ├───────────────┐
          │               │
          ▼               ▼
     PostgreSQL       Redis/Queue
          │               │
          ▼               ▼
     Object Storage    Workers
          │
          ▼
     External Systems
```

---

# 5. Technology Stack

## Frontend

```text
Next.js
React
TypeScript
Tailwind CSS
Component Library
React Query / TanStack Query
Form validation
```

## Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## Database

```text
PostgreSQL
```

## Cache / Queue

```text
Redis
```

## Background Workers

```text
Python Worker
```

A task queue such as ARQ/Celery/RQ may be selected after evaluating operational requirements.

The first implementation should avoid unnecessary infrastructure complexity.

> **T00-02 update — [`docs/architecture/toolchain.md`](docs/architecture/toolchain.md).**
> Exact versions are pinned there: Node.js 24 LTS, pnpm 11, Python 3.14 (uv-managed), uv 0.12, Next.js 16.3, React 19.2, TypeScript 6.0, FastAPI 0.141, Pydantic 2.13; pnpm workspace + uv, no additional monorepo orchestration.
> Deliberate holds: **TypeScript 6.0** (typescript-eslint does not yet support TS 7) and **ESLint 9** (Next.js's lint plugins do not yet support ESLint 10); SQLAlchemy is targeted at **2.0.x** when database work starts.
> Tailwind CSS 4.3 with semantic design tokens is confirmed by [ADR-0007](docs/adr/0007-styling-tailwind-semantic-tokens.md) (T00-06; [design-tokens.md](docs/architecture/design-tokens.md)); headless component primitives are confirmed in T00-07. SQLAlchemy, Alembic, asyncpg, Redis and S3 clients are added by the task that first uses them.

---

# 6. AI Stack

The AI layer should support:

```text
LLM
Embeddings
RAG
Tool Calling
Structured Output
Agent Runtime
Memory
Evaluation
Tracing
```

Possible components:

```text
LLM Provider
Embedding Provider
Vector Store
Agent Runtime
Evaluation Layer
```

The exact AI framework should remain replaceable.

---

# 7. Storage Architecture

## PostgreSQL

Use PostgreSQL for transactional data:

```text
Users
Tenants
Students
Leads
Applications
Courses
Batches
Payments
Attendance
Examinations
Certificates
Workflows
AI Executions
Audit Logs
```

---

## Object Storage

Use object storage for:

* student documents
* certificates
* institute documents
* course documents
* images
* media
* exported reports

Do not store large binary files directly in PostgreSQL.

Database stores:

```text
object_key
file_name
content_type
size
checksum
tenant_id
entity_reference
```

---

# 8. Multi-Tenant Architecture

Recommended model:

```text
                    MTI 360
                       │
             ┌─────────┴─────────┐
             │                   │
          Tenant A            Tenant B
             │                   │
       ┌─────┴─────┐      ┌─────┴─────┐
       │ Students   │      │ Students   │
       │ Leads      │      │ Leads      │
       │ Courses    │      │ Courses    │
       │ Documents  │      │ Documents  │
       └────────────┘      └────────────┘
```

Initial database strategy:

> Shared PostgreSQL database + shared schema + `tenant_id`.

This is the most practical approach for the initial SaaS.

Future enterprise tenants may use:

```text
Dedicated database
```

if required.

---

# 9. Tenant Resolution

Tenant context should be determined from:

```text
Authenticated User
+
Tenant Membership
+
Server-side Configuration
+
Domain / Channel Mapping
```

For public channels:

```text
WhatsApp Number
      ↓
Channel Configuration
      ↓
Tenant
```

or:

```text
Institute Domain
      ↓
Tenant Configuration
      ↓
Tenant
```

Never accept tenant identity from an untrusted request body.

---

# 10. Identity Architecture

Authentication:

```text
User
 ↓
Authentication
 ↓
Session / JWT
 ↓
User Identity
 ↓
Tenant Membership
 ↓
Role
 ↓
Permissions
```

Authorization must happen server-side.

> **T00-01 update — [ADR-0005](docs/adr/0005-identity-and-session-realms.md).**
> The "Session / JWT" choice is resolved as **opaque server-side sessions** (revocable, `HttpOnly` `Secure` `SameSite` cookies, distinct cookie per realm) rather than browser-held JWTs.
> Identity is split into realms: **platform administrators use a separate `platform_users` identity** (PLATFORM-ADMIN.md §15); tenant staff and students use `users` + membership. The active tenant and campus are held in the server-side session.

---

# 11. RBAC Architecture

Example:

```text
User
 │
 ├── Tenant Membership
 │
 └── Role
       │
       └── Permissions
```

Example permissions:

```text
student.read
student.create
student.update

lead.read
lead.create
lead.assign

application.read
application.approve

payment.read
payment.create

workflow.create
workflow.execute

ai.execute
ai.configure
```

Permission checks must be enforced in the backend.

Frontend hiding is not security.

---

# 12. Domain Modules

The backend should be organized by domain.

Recommended structure:

```text
backend/
│
├── app/
│   ├── core/
│   ├── auth/
│   ├── tenancy/
│   ├── users/
│   ├── roles/
│   │
│   ├── institute/
│   ├── courses/
│   ├── leads/
│   ├── counselling/
│   ├── applications/
│   ├── students/
│   ├── documents/
│   ├── batches/
│   ├── attendance/
│   ├── faculty/
│   ├── timetable/
│   ├── examinations/
│   ├── certificates/
│   ├── finance/
│   ├── compliance/
│   ├── placement/
│   ├── grievance/
│   │
│   ├── communications/
│   ├── notifications/
│   ├── workflows/
│   ├── analytics/
│   ├── audit/
│   │
│   ├── ai/
│   ├── agents/
│   └── integrations/
```

> **T00-01 update — [ADR-0002](docs/adr/0002-monorepo-layout.md).**
> The approved backend layout groups these domains under `backend/app/modules/` with shared infrastructure in `backend/app/core/`, realm routers in `backend/app/api/`, provider adapters in `backend/app/integrations/`, workers in `backend/app/workers/` and Alembic migrations in `backend/migrations/`. Every domain listed above is retained; the mapping and the per-module layering (`router → service → (domain, repository) → models`) are documented in [`docs/architecture/repository-structure.md`](docs/architecture/repository-structure.md#3-backend-architecture).

---

# 13. Domain Dependency Direction

Business modules should depend on shared infrastructure, not on each other unnecessarily.

Example:

```text
Students
  ↓
Documents
  ↓
Notifications
```

is acceptable.

But avoid:

```text
Students
 ↔
Finance
 ↔
Marketing
 ↔
AI
 ↔
Documents
```

with circular dependencies.

Use domain services and events.

---

# 14. Event-Driven Architecture

Important business events should be published internally.

Example:

```text
APPLICATION_SUBMITTED
```

can trigger:

```text
Notification
Document Verification
Counsellor Task
Analytics
Workflow
Audit
```

without the Application module directly calling every system.

---

# 15. Event Flow

```text
Application Service
       ↓
Application Submitted
       ↓
Event Bus
       ├── Notification Handler
       ├── Workflow Handler
       ├── Analytics Handler
       ├── Audit Handler
       └── AI Handler
```

Initially this can be implemented using an internal event abstraction backed by the application/queue infrastructure.

A dedicated Kafka-style infrastructure should not be introduced unless required.

---

# 16. Agent Platform

The Agent Platform is a shared technical capability.

```text
                 AGENT PLATFORM
                       │
        ┌──────────────┼───────────────┐
        │              │               │
 Communication      Business         Growth
        │              │               │
 WhatsApp           SQL/Data        Instagram
 Email              Workflow        YouTube
 Voice                              Blog
 SMS
```

---

# 17. Agent Runtime

Every agent should execute through a common runtime.

Conceptual flow:

```text
Request
 ↓
Agent Identification
 ↓
Tenant Context
 ↓
User/Channel Context
 ↓
Load Agent Configuration
 ↓
Load Knowledge
 ↓
Determine Tools
 ↓
LLM
 ↓
Tool Calls
 ↓
Validation
 ↓
Action
 ↓
Response
 ↓
Audit
```

---

# 18. Agent Definition

An agent should have configuration such as:

```text
Agent
 ├── id
 ├── tenant_id
 ├── type
 ├── name
 ├── instructions
 ├── model configuration
 ├── knowledge configuration
 ├── allowed tools
 ├── permissions
 ├── escalation policy
 └── status
```

---

# 19. Tool Architecture

AI agents must interact with the system through governed tools.

Example:

```text
get_student()
create_lead()
update_lead()
get_course()
create_application()
send_whatsapp()
send_email()
create_task()
get_payment_status()
```

Each tool must define:

```text
Name
Description
Input Schema
Output Schema
Permissions
Tenant Scope
Audit Requirement
```

---

# 20. Agent Security

Agents must not have:

```text
Direct DB access
Root access
Unrestricted API access
Unrestricted file access
```

Instead:

```text
Agent
 ↓
Tool
 ↓
Authorization
 ↓
Tenant Validation
 ↓
Business Service
 ↓
Database
```

---

# 21. WhatsApp Architecture

```text
WhatsApp Provider
       ↓
Webhook
       ↓
Webhook Handler
       ↓
Tenant Resolution
       ↓
Conversation Service
       ↓
Agent Runtime
       ↓
Knowledge / Tools
       ↓
Response
       ↓
WhatsApp Provider
```

The webhook layer must be idempotent.

Duplicate provider events must not create duplicate business actions.

---

# 22. Email Architecture

```text
Email Provider
      ↓
Webhook / Polling
      ↓
Email Processor
      ↓
Thread Resolver
      ↓
Tenant Resolver
      ↓
Email Agent
      ↓
Draft / Action
      ↓
Approval if required
      ↓
Send
```

---

# 23. Voice Architecture

```text
Telephony
    ↓
Voice Gateway
    ↓
Streaming STT
    ↓
Agent Runtime
    ↓
Tools
    ↓
LLM
    ↓
TTS
    ↓
Voice Gateway
    ↓
Caller
```

Voice must be designed around low latency.

---

# 24. SQL Agent Architecture

```text
User
 ↓
SQL Agent
 ↓
Schema Context
 ↓
SQL Generation
 ↓
SQL Validation
 ↓
Tenant Filter Validation
 ↓
Read-Only Database
 ↓
Result
 ↓
Analysis
```

The SQL Agent should never receive a write-capable database credential.

---

# 25. Workflow Engine

The workflow engine should use:

```text
Trigger
Condition
Action
Delay
Branch
Approval
Retry
End
```

Conceptual model:

```text
Workflow
 ├── Trigger
 ├── Nodes
 ├── Conditions
 ├── Connections
 └── Execution State
```

---

# 26. Workflow Execution

```text
Event
 ↓
Find Matching Workflows
 ↓
Create Execution
 ↓
Execute Node
 ↓
Persist State
 ↓
Next Node
 ↓
Complete
```

Execution must be resumable.

If the process fails:

```text
FAILED
 ↓
RETRY
 ↓
SUCCESS
```

or:

```text
FAILED
 ↓
MANUAL INTERVENTION
```

---

# 27. Communication Architecture

Use a common communication abstraction.

```text
CommunicationService
       │
       ├── WhatsApp
       ├── Email
       ├── SMS
       └── Voice
```

Business modules should call:

```text
NotificationService
```

rather than provider-specific APIs.

---

# 28. Notification Architecture

```text
Business Event
       ↓
Notification Service
       ↓
Template Resolver
       ↓
Channel Resolver
       ↓
Provider
       ↓
Delivery Status
       ↓
Audit
```

---

# 29. RAG / Knowledge Architecture

Knowledge should be tenant-specific.

```text
Document
 ↓
Validation
 ↓
Storage
 ↓
Extraction
 ↓
Chunking
 ↓
Embedding
 ↓
Vector Store
```

At query time:

```text
Question
 ↓
Tenant Context
 ↓
Retrieve Relevant Knowledge
 ↓
Apply Visibility/Publication Rules
 ↓
Agent
 ↓
Response
```

Draft or archived knowledge must not automatically become available to production agents.

---

# 30. Knowledge Sources

Potential sources:

* institute policies
* course information
* brochures
* FAQs
* fee rules
* admission rules
* training information
* compliance documents
* approved communication content

Each document should have:

```text
tenant_id
status
visibility
effective_from
effective_to
version
```

---

# 31. Document Processing Architecture

```text
Upload
 ↓
Security Validation
 ↓
File Type Validation
 ↓
Size Validation
 ↓
Malware/Safety Checks
 ↓
Object Storage
 ↓
Extraction
 ↓
Metadata
 ↓
Chunking
 ↓
Embedding
 ↓
Index
```

Large processing should occur asynchronously.

---

# 32. Database Architecture

Core database groups:

### Identity

```text
tenants
users
tenant_users
roles
permissions
role_permissions
```

### Institute

```text
institutes
campuses
departments
```

### Academic

```text
courses
course_modules
batches
batch_students
faculty
timetable
attendance
examinations
results
certificates
```

### Admissions

```text
leads
lead_activities
applications
application_documents
students
```

### Finance

```text
fee_structures
invoices
payments
refunds
```

### Communication

```text
conversations
messages
communication_channels
templates
```

### Automation

```text
workflows
workflow_nodes
workflow_executions
workflow_execution_steps
```

### AI

```text
agents
agent_tools
ai_executions
agent_memory
```

### Governance

```text
audit_logs
tasks
notifications
```

---

# 33. Database Rules

Every tenant-owned table must include:

```text
tenant_id
created_at
updated_at
```

Where appropriate:

```text
created_by
updated_by
deleted_at
version
```

Use UUIDs for externally exposed identifiers.

Avoid exposing sequential database IDs through public APIs.

---

# 34. Soft Delete

Use soft delete where business history must be preserved.

Example:

```text
deleted_at
```

Do not physically delete critical financial, compliance or audit records without an explicit retention policy.

---

# 35. API Architecture

API pattern:

```text
/api/v1/
```

Examples:

```text
POST /api/v1/leads
GET  /api/v1/leads
GET  /api/v1/leads/{id}
PATCH /api/v1/leads/{id}

POST /api/v1/applications
GET  /api/v1/applications/{id}

POST /api/v1/students

GET /api/v1/courses
POST /api/v1/batches
```

> **T00-01 update — [ADR-0006](docs/adr/0006-api-prefixes.md).**
> The examples above remain the **tenant** API. Each realm has its own prefix and realm guard:
> `/api/v1/platform/*` (platform), `/api/v1/*` (tenant), `/api/v1/student/*` (student), `/api/v1/public/*` (tenant public website), `/api/v1/webhooks/*` (providers).
> This supersedes the path examples in PLATFORM-ADMIN.md §91 (recorded in `docs/architecture/spec-inconsistencies.md`).

---

# 36. API Response Standard

Success:

```json
{
  "data": {},
  "meta": {}
}
```

Error:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid application data",
    "details": []
  }
}
```

Do not expose internal stack traces.

---

# 37. Background Processing

Use asynchronous workers for:

* email processing
* document extraction
* embeddings
* AI execution
* bulk notifications
* report generation
* certificate generation
* workflow delays
* scheduled jobs

Architecture:

```text
API
 ↓
Queue
 ↓
Worker
 ↓
Process
 ↓
Persist Result
```

---

# 38. Idempotency

Critical external operations must support idempotency.

Examples:

```text
Payment
WhatsApp message
Email
SMS
Admission creation
Certificate generation
Workflow execution
```

Provider event IDs should be stored where available.

---

# 39. External Integration Architecture

Use adapters:

```text
Integration
 ├── WhatsAppAdapter
 ├── EmailAdapter
 ├── SMSAdapter
 ├── VoiceAdapter
 ├── PaymentAdapter
 └── GovernmentAdapter
```

Business logic should depend on interfaces/contracts rather than providers.

---

# 40. Government Integration

Government/DGS/DGMA systems should be treated as external systems.

```text
MTI 360
    ↓
Integration Layer
    ↓
External Government System
```

Never make the core domain directly dependent on an external API.

If an external system becomes unavailable, MTI 360 should continue operating where possible and record synchronization status.

---

# 41. Frontend Architecture

Recommended:

```text
frontend/
│
├── app/
│
├── components/
│
├── features/
│   ├── dashboard/
│   ├── leads/
│   ├── applications/
│   ├── students/
│   ├── courses/
│   ├── batches/
│   ├── finance/
│   ├── compliance/
│   ├── placement/
│   ├── communications/
│   ├── workflows/
│   └── ai/
│
├── lib/
├── hooks/
├── services/
├── types/
└── validations/
```

Organize UI primarily by feature/domain.

> **T00-01 update — [ADR-0002](docs/adr/0002-monorepo-layout.md), [ADR-0003](docs/adr/0003-marketing-vs-tenant-public-website.md).**
> The approved frontend is **one Next.js application under `frontend/src/`** serving four experiences with separate route trees and shells: `/platform/*` (Platform Control Plane), `/app/*` (Tenant Application), `/student/*` (Student Portal) and `/sites/[site]/*` (Tenant Public Website, reached via host-based rewrite). Shared code lives in `design-system/` (tokens, theme, components, templates T01–T18), `shells/`, `features/` and `lib/`. Organisation by feature/domain is retained. Details: [`docs/architecture/repository-structure.md`](docs/architecture/repository-structure.md#2-frontend-architecture).
> The root `index.html` / `app.js` / `styles.css` is the **MTI 360 marketing website**, not part of this application.

---

# 42. UI Architecture

The UI should provide a common shell:

```text
┌──────────────────────────────────────────┐
│ Top Bar                                  │
├──────────────┬───────────────────────────┤
│ Sidebar      │ Breadcrumb                │
│              ├───────────────────────────┤
│ Dashboard    │                           │
│ Leads        │ Main Content              │
│ Admissions   │                           │
│ Students     │                           │
│ Academics    │                           │
│ Finance      │                           │
│ Compliance   │                           │
│ ...          │                           │
└──────────────┴───────────────────────────┘
```

The interface should be premium, clean and enterprise-oriented.

---

# 43. Frontend Security

Frontend permissions are for UX only.

Backend authorization is mandatory.

Example:

```text
Button hidden
```

does not mean:

```text
API secured
```

The API must independently verify permissions.

---

# 44. Audit Architecture

Audit every important mutation:

```text
Create
Update
Delete
Approve
Reject
Publish
Payment
Certificate
AI Action
Workflow Action
Permission Change
```

Audit record:

```text
tenant_id
user_id
action
entity_type
entity_id
timestamp
metadata
```

---

# 45. AI Execution Traceability

Every production AI execution should create an execution record containing, where applicable:

```text
tenant_id
agent_id
provider
model
decision
confidence
source references
tools invoked
latency
status
business entity
case/workflow link
```

Do not automatically store raw prompts or sensitive payloads unless there is a documented requirement.

---

# 46. Observability

Monitor:

### Application

* API latency
* errors
* throughput
* database performance

### Queue

* queue length
* failed jobs
* retry count
* processing time

### AI

* latency
* token usage
* provider errors
* tool failures
* success rate
* cost

### Business

* lead conversion
* application completion
* payment failures
* workflow failures

---

# 47. Logging

Logs should contain:

```text
timestamp
service
request_id
tenant_id
user_id where appropriate
operation
status
latency
error code
```

Do not log:

* passwords
* authentication tokens
* sensitive personal data unnecessarily
* full payment credentials
* raw AI payloads unnecessarily

---

# 48. Security Architecture

Minimum requirements:

* HTTPS
* secure password hashing
* secure sessions/tokens
* MFA capability
* RBAC
* tenant isolation
* input validation
* output validation
* API rate limiting
* CSRF protection where applicable
* secure file handling
* secret management
* audit logging
* dependency scanning
* security headers

---

# 49. File Upload Security

All uploads must undergo:

```text
Extension Validation
 ↓
MIME Validation
 ↓
Size Validation
 ↓
Filename Sanitization
 ↓
Content Validation
 ↓
Malware/Safety Scan
 ↓
Storage
```

Never trust the extension supplied by the client.

---

# 50. AI Security

AI must be treated as an untrusted reasoning component.

Never allow an LLM to directly:

```text
execute arbitrary SQL
execute shell commands
access unrestricted files
change permissions
delete critical data
send arbitrary bulk messages
```

All actions must pass through governed tools.

---

# 51. AI Prompt Injection Protection

Retrieved documents and user messages must be treated as untrusted content.

For example:

```text
Student message
        ↓
Untrusted
```

and:

```text
Uploaded document
        ↓
Untrusted
```

They must never override system-level policies or tool permissions.

---

# 52. Rate Limiting

Apply rate limits to:

* login
* OTP
* public forms
* AI endpoints
* WhatsApp webhook actions
* email sending
* SMS sending
* bulk campaigns
* file uploads

Tenant-level limits should be configurable.

---

# 53. Reliability

External provider failures should not bring down the core application.

Example:

```text
WhatsApp Provider Down
        ↓
Message queued
        ↓
Retry
        ↓
Fallback / Alert
```

Core business transactions should remain available wherever possible.

---

# 54. Deployment Architecture

Initial:

```text
                    Internet
                       │
                       ▼
                  Cloudflare
                       │
                       ▼
                 Reverse Proxy
                       │
              ┌────────┴────────┐
              │                 │
           Frontend           Backend
           Next.js            FastAPI
              │                 │
              └────────┬────────┘
                       │
          ┌────────────┼─────────────┐
          │            │             │
      PostgreSQL      Redis       Storage
          │            │
          │         Workers
          │
          └───────────────┐
                          │
                    External APIs
```

---

# 55. Docker Architecture

Development:

```text
docker-compose.yml
```

Services:

```text
frontend
backend
worker
postgres
redis
```

Optional later:

```text
vector-db
monitoring
```

Do not add infrastructure unless the application actually requires it.

> **T00-01 update — planned for T00-03.**
> Local development will use a root `compose.yaml` (the current Compose file name) with an `infra` profile (`postgres`, `redis`, an S3-compatible **object-storage emulator**, `mailpit` for local email) and an `app` profile (`migrate` one-shot Alembic service, `api`, `worker`, `frontend`). The backend `api`, `worker` and `migrate` services share one image. Ports bind to `127.0.0.1`. The emulator product and queue library are chosen in T00-03. See [`docs/architecture/repository-structure.md`](docs/architecture/repository-structure.md#6-local-infrastructure-t00-03).

> **T00-03 update — implemented (2026-09-26).**
> - Compose project name fixed to **`mti360`**; volumes `mti360_*`; every host port bound to `127.0.0.1` (defaults 3000, 8000, 5432, 6379, 8333, 1025, 8025, overridable in `.env`) so MTI 360 coexists with other local projects (e.g. ACRS).
> - **Hybrid development:** `infra` profile in Docker (`pnpm infra:up`); Next.js and FastAPI run natively (`pnpm dev`). The `app` profile (`api`, `frontend`) runs the production-shaped images (`pnpm stack:up`).
> - **PostgreSQL 18** (`pgvector/pgvector:0.8.6-pg18-trixie`; pgvector not enabled) with bootstrap roles `mti_owner` / `mti_app` / `mti_readonly` (no BYPASSRLS) for ADR-0004.
> - **Redis 8.8** (`redis:8.8-alpine`).
> - **Object storage: SeaweedFS 4.47** (Apache-2.0) instead of MinIO, whose community repository is archived and whose Docker Hub image is no longer available. Private bucket via a one-shot init service; anonymous access denied.
> - **Mailpit 1.31** for local email.
> - **Deferred (decision D4):** the `migrate` (Alembic) and `worker` services, and therefore the queue-library choice that ADR-0001 placed in T00-03, move to the first tasks that need them. No Alembic, migration, worker or queue library exists yet.
> Details: [`docs/architecture/toolchain.md`](docs/architecture/toolchain.md), [`docs/runbooks/local-development.md`](docs/runbooks/local-development.md).

---

# 56. Environments

Minimum:

```text
development
staging
production
```

Configuration must come from environment variables/secrets.

Never hard-code:

* API keys
* database passwords
* provider credentials
* encryption secrets

> **Implementation note (T00-04, 2026-09-26):** four environments — `development`, `test`, `staging`, `production` — selected by `APP_ENV` and validated at startup (backend `Settings`, frontend server-only `env.ts`). `.env` files are read only in development; staging and production take configuration from the process environment (secret manager) only and refuse placeholder secrets, debug mode, the fake AI provider, permissive CORS and database URLs without TLS. Details: [`docs/architecture/environments.md`](docs/architecture/environments.md).

---

# 57. CI/CD

Pipeline:

```text
Git Push
 ↓
Lint
 ↓
Unit Tests
 ↓
Integration Tests
 ↓
Security Checks
 ↓
Build
 ↓
Deploy Staging
 ↓
Smoke Tests
 ↓
Production Approval
 ↓
Deploy
```

---

# 58. Testing Architecture

Testing layers:

```text
Unit Tests
     ↓
Service Tests
     ↓
API Tests
     ↓
Integration Tests
     ↓
AI Evaluation Tests
     ↓
End-to-End Tests
```

Critical workflows require end-to-end testing.

Example:

```text
Lead
 ↓
Application
 ↓
Document
 ↓
Admission
 ↓
Payment
 ↓
Batch
```

---

# 59. AI Evaluation

AI features require dedicated evaluation.

Test:

* accuracy
* hallucination
* tool selection
* tool arguments
* refusal behavior
* escalation
* tenant isolation
* prompt injection
* response quality

Use deterministic test datasets wherever possible.

---

# 60. Development Strategy

> **T00-01 note — superseded phase list.**
> The phase list in this section predates the engineering roadmap. The authoritative implementation sequence is **`TASKS.md` Phases 00–17** (also PRD.md §77 and CLAUDE.md §81). This list is retained for reference only and is recorded in `docs/architecture/spec-inconsistencies.md`.

The system should be developed in phases.

## Phase 01 — Foundation

```text
Project Setup
Docker
Database
Authentication
Tenant
RBAC
Audit
UI Shell
```

## Phase 02 — Institute Setup

```text
Institute
Campus
Users
Roles
Courses
Configuration
```

## Phase 03 — CRM

```text
Leads
Pipeline
Lead Activities
Follow-up
Dashboard
```

## Phase 04 — Admissions

```text
Applications
Documents
Verification
Students
Student 360
```

## Phase 05 — Communication

```text
WhatsApp
Email
Notification Service
```

## Phase 06 — AI Admission

```text
Knowledge
RAG
Agent Runtime
AI Admission Agent
Human Handover
```

## Phase 07 — Finance

```text
Fee Structure
Invoices
Payments
Outstanding
Receipts
```

## Phase 08 — Academics

```text
Batches
Faculty
Timetable
Attendance
```

## Phase 09 — Examinations & Certificates

```text
Exams
Results
Certificates
```

## Phase 10 — Workflow

```text
Events
Workflow Builder
Workflow Runtime
Automation
```

## Phase 11 — Voice/SMS/SQL

```text
Voice Agent
SMS Agent
SQL Agent
```

## Phase 12 — Compliance & Placement

```text
Compliance
Audit
Placement
```

## Phase 13 — Marketing Agents

```text
Instagram
YouTube
Blog/SEO
```

---

# 61. Reusable Platform Boundary

The following capabilities should eventually become shared platform services:

```text
Authentication
Tenant
RBAC
Users
Documents
Notifications
Communication
Workflow
AI Runtime
Agent Tools
Knowledge/RAG
Audit
Analytics
Billing
Integrations
```

MTI-specific capabilities:

```text
Maritime Courses
Maritime Compliance
Maritime Training
Simulator
Maritime Faculty
Shipboard Training
Maritime Placement
DGS/DGMA Integration
```

---

# 62. Future Institute 360 Architecture

The long-term architecture should support:

```text
                INSTITUTE 360 CORE
                       │
       ┌───────────────┼────────────────┐
       │               │                │
    MTI 360         EDU 360         SKILL 360
       │               │                │
 Maritime           School/          Skill/
 Training           College          Vocational
 Rules              Rules            Rules
```

Shared:

```text
CRM
Students
Courses
Batches
Payments
Documents
Communication
Workflow
AI Agents
Analytics
```

Vertical modules provide:

```text
Rules
Fields
Workflows
Compliance
Integrations
Terminology
```

---

# 63. Configuration vs Code

Business variations should preferably be configuration-driven.

Examples:

```text
Course Types
Document Requirements
Fee Plans
Admission Steps
Approval Steps
Notification Templates
Workflow Rules
AI Knowledge
```

Avoid hard-coding every institute's process.

However, regulatory and security-critical rules should remain controlled by backend code/configuration rather than editable arbitrary scripts.

---

# 64. API and Domain Boundary Rule

A module must expose business operations rather than database operations.

Bad:

```text
POST /students/update-row
```

Better:

```text
PATCH /students/{id}
```

Best where domain behavior matters:

```text
POST /applications/{id}/approve
POST /students/{id}/allocate-batch
POST /payments/{id}/confirm
```

Business transitions should be explicit.

---

# 65. State Machine Principle

Important entities should have controlled state transitions.

Example:

```text
Application

DRAFT
 ↓
SUBMITTED
 ↓
UNDER_REVIEW
 ↓
DOCUMENT_VERIFICATION
 ↓
ELIGIBLE
 ↓
APPROVED
 ↓
ADMITTED
```

Do not allow arbitrary status updates from the frontend.

---

# 66. Transaction Boundary Principle

Business-critical operations must be transactional.

Example:

Admission:

```text
Approve Application
+
Create Admission
+
Generate Admission Number
+
Create Student
```

should either complete successfully or roll back appropriately.

External notifications should generally happen asynchronously after the transaction is committed.

---

# 67. Data Ownership Principle

Every entity must have a clear owner domain.

Example:

```text
Lead          → CRM
Application   → Admissions
Student       → Student Management
Payment       → Finance
Attendance    → Academics
Certificate   → Certification
Workflow      → Automation
AIExecution   → AI Platform
```

Avoid multiple domains independently owning the same data.

---

# 68. Architecture Decision: Modular Monolith

### Decision

Use a modular monolith initially.

### Reason

MTI 360 is still a new product.

This provides:

* faster development
* simpler deployment
* easier debugging
* easier transactions
* lower infrastructure cost
* simpler Claude Code development

The internal module boundaries should be strong enough to allow future extraction.

---

# 69. Architecture Decision: PostgreSQL

### Decision

Use PostgreSQL.

### Reasons

* relational model
* strong transactions
* JSON support
* mature ecosystem
* good reporting
* vector extensions possible
* suitable for multi-tenant SaaS

---

# 70. Architecture Decision: Python + FastAPI

### Decision

Use Python/FastAPI for the new AI-centric backend.

### Reasons

* AI ecosystem
* agent development
* RAG
* ML libraries
* asynchronous APIs
* rapid development
* excellent integration with LLM providers

The user's existing Java expertise remains valuable for enterprise integration and future services.

---

# 71. Architecture Decision: Next.js

### Decision

Use Next.js + React + TypeScript.

Reasons:

* modern SaaS UI
* strong ecosystem
* server-side capabilities
* good routing
* good developer productivity
* suitable for dashboards and portals

---

# 72. Architecture Decision: Docker First

Everything should run locally using:

```text
docker compose up
```

A new developer should be able to clone the repository and start the system with minimal setup.

---

# 73. Architecture Decision: Agent Platform Separation

Agents must not be implemented as random API endpoints.

Instead:

```text
Agent
 ↓
Agent Runtime
 ↓
Tools
 ↓
Business Services
 ↓
Database
```

This allows the same agent technology to be reused by:

```text
MTI 360
ACRS
Future SaaS
```

---

# 74. Claude Code Development Rules

Claude Code must follow these rules.

## Rule 1

Read:

```text
PRD.md
APP-FLOW.md
ARCHITECTURE.md
CLAUDE.md
DEVELOPMENT-STATUS.md
```

before starting a new development phase.

## Rule 2

Never implement the entire product in one operation.

## Rule 3

Never invent major business requirements.

## Rule 4

Do not change architecture without documenting the decision.

## Rule 5

Every feature must include:

```text
Database
API
Business Logic
UI
Validation
Authorization
Tenant Isolation
Tests
```

where applicable.

## Rule 6

Run tests after implementation.

## Rule 7

Do not mark a task complete based only on compilation.

## Rule 8

Update:

```text
DEVELOPMENT-STATUS.md
```

after every completed task/phase.

## Rule 9

Create a Git checkpoint after stable milestones.

## Rule 10

Do not bypass security checks for convenience.

---

# 75. Git Strategy

Use:

```text
main
```

for stable production-ready code.

Feature work:

```text
feature/<feature-name>
```

or the team's selected branching convention.

Every completed phase should have a meaningful commit.

Example:

```text
feat(auth): implement tenant-aware authentication
```

> **T00-01 update — current repository state.**
> The repository currently has a single branch, `claude/compassionate-johnson-gxdgr9`, and no `main`. T00-01 is committed there, one commit per sub-step, with baseline tags `spec-baseline-v1` and `marketing-site-v1`.
> After T00-01 review, `main` is created from the reviewed commit, made the default branch and protected (pull request required, no force-push; required CI checks after T00-05). The existing branch is preserved.
> Thereafter: short-lived branches (`feat/…`, `fix/…`, `docs/…`), one task per pull request, squash merge, conventional commits that include the task ID, and an ADR for every architecture change.

---

# 76. Architecture Evolution

The architecture should evolve:

```text
Phase 1
Modular Monolith

        ↓

Phase 2
Modular Monolith + Workers

        ↓

Phase 3
High-volume Agent Services

        ↓

Phase 4
Selective Service Extraction
```

Do not prematurely adopt distributed architecture.

---

# 77. Target End-State

The mature MTI 360 architecture becomes:

```text
                         MTI 360
                            │
                 ┌──────────┴──────────┐
                 │                     │
             Web Portal            Student Portal
                 │                     │
                 └──────────┬──────────┘
                            │
                         API Layer
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
   Business Domains      AI Platform        Integrations
       │                    │                    │
       │             ┌──────┼──────┐             │
       │             │      │      │             │
       │          Agents  RAG  Workflow       External
       │                                          APIs
       │
       ▼
   PostgreSQL
       +
   Redis/Queue
       +
   Object Storage
       +
   Observability
```

---

# 78. Final Architecture Principle

The most important architectural rule for MTI 360 is:

> **Build the business platform once, build the AI Agent Platform once, and configure vertical-specific intelligence on top of it.**

Therefore:

```text
             SHARED PLATFORM
                   +
             AGENT PLATFORM
                   +
           VERTICAL DOMAIN
                   =
              MTI 360
```

Later:

```text
             SHARED PLATFORM
                   +
             AGENT PLATFORM
                   +
          EDUCATION DOMAIN
                   =
              EDU 360
```

And:

```text
             SHARED PLATFORM
                   +
             AGENT PLATFORM
                   +
           SKILL DOMAIN
                   =
             SKILL 360
```

This architecture gives MTI 360 a path from a **single maritime SaaS product** to the larger **automation SaaS platform** you ultimately want to build.
