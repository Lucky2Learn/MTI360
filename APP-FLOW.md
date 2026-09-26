# MTI 360

## Application Flow Specification

**Product:** MTI 360
**Product Type:** Maritime Training Institute Growth & Operations SaaS
**Positioning:** Growth & Operations OS for Maritime Training Institutes
**Version:** 1.0

---

# 1. Purpose

This document defines the end-to-end application flow of MTI 360.

It describes:

* user journeys
* navigation
* module relationships
* business workflows
* screen transitions
* AI interactions
* automation triggers
* approval points
* notifications
* major system states

This document is intended to be used as a reference for:

* UI/UX design
* architecture
* API design
* database design
* Claude Code implementation
* QA and acceptance testing

---

# 2. Product Flow at a Glance

The primary MTI 360 business journey is:

```text
MARKETING
    ↓
LEAD
    ↓
ENQUIRY
    ↓
COUNSELLING
    ↓
APPLICATION
    ↓
DOCUMENT VERIFICATION
    ↓
ADMISSION
    ↓
FEE PAYMENT
    ↓
BATCH ALLOCATION
    ↓
TRAINING
    ↓
ATTENDANCE
    ↓
EXAMINATION
    ↓
CERTIFICATION
    ↓
PLACEMENT
    ↓
ALUMNI
```

Cross-cutting services:

```text
WhatsApp
Email
Voice
SMS
AI
Workflow Automation
Notifications
Documents
Analytics
Audit
```

---

# 3. Primary Navigation

The main navigation should be organized around business activities rather than technical modules.

```text
MTI 360
│
├── Dashboard
│
├── GROW
│   ├── Marketing
│   ├── Campaigns
│   ├── Website
│   ├── Leads
│   └── Content & Social
│
├── ADMISSIONS
│   ├── Leads
│   ├── Counselling
│   ├── Applications
│   ├── Documents
│   └── Students
│
├── ACADEMICS
│   ├── Courses
│   ├── Batches
│   ├── Timetable
│   ├── Attendance
│   ├── Faculty
│   ├── Training
│   └── Examinations
│
├── FINANCE
│   ├── Fee Structure
│   ├── Invoices
│   ├── Payments
│   ├── Outstanding
│   └── Reports
│
├── COMPLIANCE
│   ├── Compliance Dashboard
│   ├── Documents
│   ├── Inspections
│   ├── Corrective Actions
│   └── Audit
│
├── PLACEMENT
│   ├── Students
│   ├── Companies
│   ├── Opportunities
│   └── Placement Tracking
│
├── COMMUNICATION
│   ├── WhatsApp
│   ├── Email
│   ├── SMS
│   └── Voice
│
├── AUTOMATION
│   ├── Workflows
│   ├── AI Agents
│   └── Automation History
│
├── ANALYTICS
│   ├── Executive Dashboard
│   ├── Admissions
│   ├── Finance
│   ├── Academic
│   ├── Marketing
│   └── AI Analytics
│
└── ADMINISTRATION
    ├── Institute
    ├── Users
    ├── Roles
    ├── Settings
    ├── Integrations
    ├── AI Configuration
    └── Audit Logs
```

---

# 4. Authentication Flow

```text
Login
  ↓
Enter Email/Mobile
  ↓
Authentication
  ↓
MFA if enabled
  ↓
Identify Tenant
  ↓
Load User Role
  ↓
Load Permissions
  ↓
Dashboard
```

For a multi-campus institute:

```text
Login
 ↓
Select Institute/Campus
 ↓
Load Campus Context
 ↓
Dashboard
```

---

# 5. First-Time Institute Setup

After creating a new tenant:

```text
Create Institute
      ↓
Basic Information
      ↓
Logo / Branding
      ↓
Campus
      ↓
Courses
      ↓
Fee Structure
      ↓
Users & Roles
      ↓
Communication Channels
      ↓
Admission Configuration
      ↓
Notification Templates
      ↓
AI Knowledge
      ↓
Setup Complete
      ↓
Dashboard
```

The setup wizard should show:

```text
Step 1/8
Step 2/8
...
Step 8/8
```

Users should be able to save and continue later.

---

# 6. Executive Dashboard Flow

After login:

```text
Dashboard
│
├── Today's Summary
│
├── Admissions
│   ├── New Leads
│   ├── Applications
│   └── Admissions
│
├── Finance
│   ├── Collection
│   └── Outstanding
│
├── Students
│   ├── Active
│   └── Attendance Alerts
│
├── Compliance
│   └── Pending Items
│
├── Placement
│   └── Pending Actions
│
└── AI Assistant
```

The dashboard should be role-aware.

A counsellor should not see the same dashboard as an institute owner.

---

# 7. GROW Flow

## 7.1 Marketing Campaign

```text
Create Campaign
      ↓
Campaign Details
      ↓
Select Course
      ↓
Select Audience
      ↓
Select Channels
      ↓
Create Content
      ↓
AI Content Assistance
      ↓
Preview
      ↓
Approval
      ↓
Schedule
      ↓
Publish
      ↓
Track Leads
      ↓
Track Conversion
```

---

# 8. Website Lead Capture Flow

```text
Prospective Student
        ↓
Institute Website
        ↓
Course Page
        ↓
View Course
        ↓
Enquiry / Apply
        ↓
Lead Form
        ↓
Lead Created
        ↓
Lead Source Recorded
        ↓
AI/Automation Trigger
```

Possible immediate actions:

```text
Lead Created
     ↓
WhatsApp message
     +
Email
     +
Counsellor notification
     +
Lead assignment
```

---

# 9. Lead Management Flow

## Lead Creation

Lead can originate from:

```text
Website
WhatsApp
Phone
Walk-in
Instagram
Facebook
YouTube
Google
Referral
Manual Entry
API
```

Flow:

```text
Lead Created
     ↓
Duplicate Check
     ↓
Lead Enrichment
     ↓
Lead Scoring
     ↓
Assign Counsellor
     ↓
Create Follow-up Task
```

---

# 10. Lead Pipeline

```text
NEW
 ↓
CONTACTED
 ↓
QUALIFIED
 ↓
COUNSELLING
 ↓
INTERESTED
 ↓
APPLICATION
 ↓
ADMITTED
```

Alternative paths:

```text
NOT ELIGIBLE
LOST
DEFERRED
DUPLICATE
```

Every state transition must be recorded.

---

# 11. AI Lead Qualification

When a new lead arrives:

```text
Lead Created
     ↓
AI Lead Agent
     ↓
Identify:
 ├── Course Interest
 ├── Qualification
 ├── Location
 ├── Age
 ├── Intent
 └── Readiness
     ↓
Lead Score
     ↓
Recommended Action
```

Example:

```text
HIGH INTENT
→ Voice Agent

MEDIUM INTENT
→ WhatsApp follow-up

LOW INTENT
→ Marketing nurture
```

Human staff should be able to override AI recommendations.

---

# 12. WhatsApp Agent Flow

```text
Student sends WhatsApp message
          ↓
Webhook
          ↓
Identify Tenant
          ↓
Identify Contact
          ↓
Load Conversation
          ↓
AI Agent
          ↓
Knowledge / Tool
          ↓
Response
          ↓
WhatsApp
```

Possible AI actions:

```text
Answer FAQ
Course information
Eligibility
Fee information
Application status
Schedule counselling
Create lead
Update lead
Send document
Create task
Escalate to human
```

---

# 13. AI Counselling Flow

```text
Student asks question
        ↓
AI understands intent
        ↓
Retrieve approved knowledge
        ↓
Generate response
        ↓
Student responds
        ↓
Continue conversation
```

If the AI cannot safely answer:

```text
AI confidence insufficient
        ↓
Human Handover
        ↓
Counsellor receives conversation
        ↓
Counsellor responds
```

---

# 14. Voice Agent Flow

```text
Lead
 ↓
Voice Campaign / Incoming Call
 ↓
Voice Agent
 ↓
Identity / Context
 ↓
Conversation
 ↓
Course Questions
 ↓
Qualification
 ↓
Capture Information
 ↓
CRM Update
 ↓
Optional WhatsApp Follow-up
 ↓
Call Summary
```

The system should store:

* call status
* duration
* transcript where permitted
* summary
* outcome
* next action

---

# 15. Counsellor Flow

Counsellor opens:

```text
Lead
 ↓
Lead 360
```

Lead 360 should display:

```text
Profile
Course Interest
Lead Score
Communication
Follow-ups
Applications
Documents
Payments
Activities
Notes
AI Recommendations
```

Counsellor actions:

```text
Call
WhatsApp
Email
Schedule Follow-up
Start Application
Mark Interested
Mark Lost
Convert to Applicant
```

---

# 16. Application Flow

```text
Lead
 ↓
Start Application
 ↓
Personal Information
 ↓
Contact Information
 ↓
Education
 ↓
Course Selection
 ↓
Eligibility
 ↓
Documents
 ↓
Declaration
 ↓
Review
 ↓
Submit
```

Application status:

```text
DRAFT
 ↓
SUBMITTED
 ↓
UNDER REVIEW
 ↓
DOCUMENT VERIFICATION
 ↓
ELIGIBLE
 ↓
APPROVED
 ↓
ADMITTED
```

Alternative:

```text
REJECTED
DOCUMENT CORRECTION REQUIRED
NOT ELIGIBLE
```

---

# 17. Document Verification Flow

```text
Document Uploaded
       ↓
File Validation
       ↓
Document Type Detection
       ↓
AI Extraction (optional)
       ↓
Verification Queue
       ↓
Reviewer
       ↓
Approve / Reject
```

Rejected:

```text
Reject
 ↓
Reason
 ↓
Student Notification
 ↓
Re-upload
 ↓
Re-verification
```

---

# 18. Admission Flow

```text
Approved Application
       ↓
Admission Confirmation
       ↓
Generate Admission Number
       ↓
Fee Plan
       ↓
Payment
       ↓
Receipt
       ↓
Student Created
       ↓
Batch Allocation
       ↓
Welcome Communication
```

---

# 19. Student 360 Flow

Once admission is complete:

```text
Student
│
├── Profile
├── Admission
├── Course
├── Batch
├── Documents
├── Fees
├── Attendance
├── Timetable
├── Exams
├── Certificates
├── Communication
├── Complaints
└── Placement
```

Student 360 becomes the central record throughout the student's lifecycle.

---

# 20. Course Management Flow

```text
Course Master
 ↓
Course Information
 ↓
Eligibility
 ↓
Duration
 ↓
Fee Structure
 ↓
Curriculum
 ↓
Training Requirements
 ↓
Assessment
 ↓
Certification
 ↓
Publish
```

Course should support configurable:

* Pre-Sea
* Post-Sea
* course type
* duration
* eligibility
* capacity
* fee structure

---

# 21. Batch Creation Flow

```text
Create Batch
 ↓
Select Course
 ↓
Set Dates
 ↓
Set Capacity
 ↓
Assign Faculty
 ↓
Assign Classroom
 ↓
Assign Resources
 ↓
Publish Batch
```

Students can then be allocated:

```text
Admission
 ↓
Eligible Batch
 ↓
Batch Allocation
 ↓
Student Notification
```

---

# 22. Timetable Flow

```text
Select Batch
 ↓
Select Course Module
 ↓
Select Faculty
 ↓
Select Room/Resource
 ↓
Select Date/Time
 ↓
Conflict Check
 ↓
Publish
 ↓
Notify Students/Faculty
```

The system should prevent or flag:

* faculty conflicts
* classroom conflicts
* simulator conflicts
* overlapping sessions

---

# 23. Attendance Flow

```text
Batch
 ↓
Session
 ↓
Attendance
 ↓
Present / Absent
 ↓
Save
 ↓
Attendance Calculation
 ↓
Threshold Check
```

If shortage occurs:

```text
Attendance < Threshold
        ↓
Alert
        ↓
Student Notification
        ↓
Faculty/Principal Notification
```

---

# 24. Examination Flow

```text
Create Examination
 ↓
Select Batch
 ↓
Select Course/Module
 ↓
Schedule
 ↓
Notify Students
 ↓
Conduct Examination
 ↓
Enter Marks
 ↓
Validate
 ↓
Calculate Result
 ↓
Review
 ↓
Publish
```

Result:

```text
PASS
FAIL
RE-EXAMINATION
```

---

# 25. Certificate Flow

```text
Course Completed
      ↓
Eligibility Check
      ↓
Attendance Check
      ↓
Exam Result Check
      ↓
Fee Clearance
      ↓
Certificate Approval
      ↓
Generate Certificate
      ↓
Digital Verification
      ↓
Student Notification
```

---

# 26. Fee Management Flow

```text
Admission
 ↓
Fee Plan
 ↓
Invoice
 ↓
Payment
 ↓
Receipt
 ↓
Balance
```

Automated reminder:

```text
Due Date Approaching
 ↓
WhatsApp
 ↓
Email
 ↓
SMS
```

Overdue:

```text
Payment Overdue
 ↓
Workflow
 ↓
Reminder
 ↓
Escalation
 ↓
Accounts Task
```

---

# 27. Placement Flow

```text
Student Eligible
 ↓
Placement Profile
 ↓
Company Opportunity
 ↓
Student Matching
 ↓
Application
 ↓
Interview
 ↓
Selection
 ↓
Joining
 ↓
Placement Record
```

Possible future maritime extension:

```text
Placement
 ↓
Shipboard Training
 ↓
Sign-on
 ↓
Training
 ↓
Sign-off
```

This should remain a separate configurable lifecycle.

---

# 28. Compliance Flow

```text
Compliance Dashboard
        ↓
Open Requirement
        ↓
Required Evidence
        ↓
Upload / Link Evidence
        ↓
Verification
        ↓
Status
```

Statuses:

```text
COMPLIANT
PENDING
EXPIRING
NON-COMPLIANT
UNDER REVIEW
```

---

# 29. Compliance Alert Flow

Example:

```text
Faculty Certificate
        ↓
Expiry Date
        ↓
30 Days Remaining
        ↓
Alert
        ↓
Email + WhatsApp
        ↓
Compliance Task
```

The alert period should be configurable.

---

# 30. Workflow Automation Flow

Every workflow follows:

```text
TRIGGER
   ↓
CONDITIONS
   ↓
ACTIONS
   ↓
WAIT / DELAY
   ↓
CONDITIONS
   ↓
NEXT ACTION
```

Example:

```text
TRIGGER:
Lead Created

ACTION:
Send WhatsApp

WAIT:
2 days

CONDITION:
No response?

YES
 ↓
Send Email

NO
 ↓
End
```

---

# 31. SQL Agent Flow

```text
Management Question
       ↓
SQL Agent
       ↓
Understand Intent
       ↓
Identify Relevant Data
       ↓
Generate SQL
       ↓
Validate SQL
       ↓
Tenant Security Check
       ↓
Read-only Execution
       ↓
Result
       ↓
Natural Language Response
```

Example:

> "Show this month's admissions by course."

The agent should return:

* table
* summary
* optional chart
* underlying query reference/audit

---

# 32. Marketing Content Flow

## Blog

```text
Topic
 ↓
Keyword Research
 ↓
Content Brief
 ↓
AI Draft
 ↓
Human Review
 ↓
SEO Validation
 ↓
Publish
```

## YouTube

```text
Topic
 ↓
Research
 ↓
Script
 ↓
Title
 ↓
Description
 ↓
Thumbnail Brief
 ↓
Human Approval
 ↓
Publish
```

## Instagram

```text
Campaign
 ↓
Content Idea
 ↓
Caption
 ↓
Creative
 ↓
Approval
 ↓
Schedule
 ↓
Publish
```

---

# 33. Cross-Agent Flow

A major MTI 360 capability is agent-to-agent orchestration.

Example:

```text
Lead Created
      ↓
Workflow Agent
      ↓
WhatsApp Agent
      ↓
Student Responds
      ↓
AI Admission Agent
      ↓
Lead Qualified
      ↓
Voice Agent
      ↓
Counselling
      ↓
Email Agent
      ↓
Course Details
      ↓
Application
      ↓
SMS Agent
      ↓
Application Confirmation
```

No agent should directly bypass platform authorization.

---

# 34. Notification Flow

All notifications should pass through a common notification service.

```text
Business Event
      ↓
Notification Engine
      ↓
Determine Channel
      ↓
Template
      ↓
Personalization
      ↓
Provider
      ↓
Delivery
      ↓
Status
      ↓
Audit
```

Supported channels:

```text
WhatsApp
Email
SMS
Push
In-App
Voice
```

---

# 35. AI Business Assistant Flow

Institute owner:

> "What needs my attention today?"

```text
Question
 ↓
AI Business Assistant
 ↓
Retrieve authorized data
 ↓
Analyze
 ↓
Identify important actions
 ↓
Return prioritized action list
```

Example:

```text
5 high-priority leads
3 overdue payments
7 documents expiring
2 attendance alerts
1 unresolved complaint
```

Each item should link directly to the relevant screen.

---

# 36. Role-Based Application Flow

## Institute Owner

```text
Login
 ↓
Executive Dashboard
 ↓
Business Metrics
 ↓
AI Assistant
 ↓
Actions
```

## Counsellor

```text
Login
 ↓
Lead Dashboard
 ↓
New Leads
 ↓
Lead 360
 ↓
Communication
 ↓
Follow-up
```

## Accounts

```text
Login
 ↓
Finance Dashboard
 ↓
Payments
 ↓
Outstanding
 ↓
Receipts
 ↓
Reports
```

## Faculty

```text
Login
 ↓
My Dashboard
 ↓
Today's Classes
 ↓
Attendance
 ↓
Training
 ↓
Assessments
```

## Compliance Manager

```text
Login
 ↓
Compliance Dashboard
 ↓
Pending Items
 ↓
Evidence
 ↓
Corrective Actions
 ↓
Audit
```

## Student

```text
Login
 ↓
Student Dashboard
 ↓
My Course
 ↓
Attendance
 ↓
Fees
 ↓
Exams
 ↓
Certificates
 ↓
Support
```

---

# 37. Global Search Flow

A global search should allow authorized users to search:

```text
Student
Lead
Application
Batch
Course
Payment
Document
Certificate
Complaint
Company
```

Flow:

```text
Search
 ↓
Identify Entity
 ↓
Permission Check
 ↓
Results
 ↓
Open Record
```

---

# 38. Global Activity Timeline

Important entities should have an activity timeline.

Example:

```text
24 Sep
Application submitted

24 Sep
Document uploaded

25 Sep
Document verified

25 Sep
Fee invoice generated

26 Sep
Payment received

26 Sep
Admission confirmed

27 Sep
Batch allocated
```

This becomes a critical audit and support feature.

---

# 39. Error & Exception Flow

Every important operation should have:

```text
Success
Failure
Retry
Manual Intervention
```

Example:

```text
WhatsApp Send
 ↓
Provider Error
 ↓
Retry
 ↓
Retry Failed
 ↓
Mark Failed
 ↓
Create Alert
```

AI failure:

```text
AI Failure
 ↓
Fallback
 ↓
Human Handover
```

---

# 40. Human-in-the-Loop Flow

AI should escalate when:

* confidence is insufficient
* sensitive operation is requested
* user explicitly asks for human
* policy requires approval
* tool fails
* information is unavailable

Flow:

```text
AI
 ↓
Cannot Safely Proceed
 ↓
Create Human Task
 ↓
Assign
 ↓
Human Action
 ↓
Continue Workflow
```

---

# 41. Core End-to-End Student Journey

This is the most important business flow.

```text
                 STUDENT JOURNEY

Google / Social / Referral
          ↓
       Website
          ↓
        Lead
          ↓
  AI/WhatsApp/Voice
          ↓
     Counselling
          ↓
     Application
          ↓
     Documents
          ↓
    Verification
          ↓
      Admission
          ↓
        Fees
          ↓
   Batch Allocation
          ↓
      Training
          ↓
     Attendance
          ↓
     Examination
          ↓
    Certification
          ↓
      Placement
          ↓
       Alumni
```

---

# 42. Core Business Event Model

Major events should be represented as system events.

Examples:

```text
LEAD_CREATED
LEAD_QUALIFIED
FOLLOWUP_DUE
APPLICATION_CREATED
APPLICATION_SUBMITTED
DOCUMENT_UPLOADED
DOCUMENT_VERIFIED
APPLICATION_APPROVED
ADMISSION_CREATED
PAYMENT_RECEIVED
PAYMENT_OVERDUE
BATCH_CREATED
STUDENT_ALLOCATED
ATTENDANCE_RECORDED
ATTENDANCE_SHORTAGE
EXAM_CREATED
RESULT_PUBLISHED
CERTIFICATE_GENERATED
PLACEMENT_CREATED
COMPLAINT_CREATED
COMPLAINT_RESOLVED
```

These events can trigger workflows and AI agents.

---

# 43. MVP Application Flow

The first implementation should NOT attempt the entire application.

## Phase 1

```text
Login
 ↓
Institute Setup
 ↓
Dashboard
 ↓
Courses
 ↓
Leads
 ↓
Lead 360
 ↓
WhatsApp
 ↓
AI Counselling
 ↓
Application
 ↓
Documents
 ↓
Student
```

## Phase 2

```text
Fees
 ↓
Payments
 ↓
Batches
 ↓
Attendance
 ↓
Faculty
```

## Phase 3

```text
Exams
 ↓
Certificates
 ↓
Compliance
 ↓
Placement
```

## Phase 4

```text
Voice
 ↓
SMS
 ↓
SQL Agent
 ↓
Workflow Builder
```

## Phase 5

```text
Instagram
 ↓
YouTube
 ↓
Blog/SEO
 ↓
Advanced Marketing Automation
```

---

# 44. Critical Design Principle

The system must distinguish between:

### Human-initiated action

```text
User clicks → action
```

### AI-suggested action

```text
AI suggests → human approves → action
```

### AI-automated action

```text
Event → workflow → AI → action
```

Each action should be auditable.

---

# 45. Claude Code Implementation Rule

Claude Code must treat this APP-FLOW as the functional navigation and workflow reference.

It should:

1. Never implement the entire product in one step.
2. Implement one phase at a time.
3. Complete database/API/UI/test work for the phase.
4. Verify tenant isolation.
5. Verify RBAC.
6. Verify validation.
7. Verify audit requirements.
8. Run automated tests.
9. Update `DEVELOPMENT-STATUS.md`.
10. Create a Git checkpoint before moving to the next phase.

If an implementation requirement is not defined in the PRD or APP-FLOW, Claude Code should **not silently invent a major business rule**.

Minor implementation details may be selected by Claude Code when they do not alter business behavior.

---

# 46. Definition of a Completed Flow

A workflow is considered complete only when:

```text
UI
 ↓
API
 ↓
Business Logic
 ↓
Database
 ↓
Validation
 ↓
Authorization
 ↓
Tenant Isolation
 ↓
Audit
 ↓
Notifications
 ↓
Automated Tests
 ↓
Manual Verification
```

are implemented as applicable.

---

# 47. Product Flow Summary

MTI 360 ultimately connects five journeys:

```text
                 MTI 360
                    |
      ┌─────────────┼─────────────┐
      ↓             ↓             ↓
    GROW          ADMIT          RUN
      ↓             ↓             ↓
 Marketing       Leads        Courses
 Campaigns       CRM          Batches
 Content         Application  Attendance
 Website         Documents    Exams
      |             |             |
      └─────────────┼─────────────┘
                    ↓
                 COMPLY
                    ↓
               Compliance
               Audit
               Certification
                    ↓
                PLACEMENT
                    ↓
                  GROW
```

Across every stage:

```text
AI
+
Automation
+
WhatsApp
+
Email
+
Voice
+
SMS
+
Analytics
```

This creates the central MTI 360 product loop:

> **Acquire → Convert → Operate → Comply → Place → Grow**
