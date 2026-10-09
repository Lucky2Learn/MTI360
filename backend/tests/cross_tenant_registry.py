"""Cross-tenant route registry (Phase 02-1; tenancy.md §8, ADR-0020 §11, INC-46).

``app/api/coverage.py`` proves that every route requires a permission. It does
not prove that a route keeps another tenant's data out. This registry does,
incrementally:

* :data:`BUSINESS_ROUTES` — every route of the business modules maps to the
  test, in one of :data:`CROSS_TENANT_SUITES`, that calls it as tenant A with tenant
  B's identifiers (or checks that its lists and lookups contain none of B's
  rows). ``test_cross_tenant_registry.py`` fails when a business-module route
  is missing here, or when a named test does not exist.
* :data:`T01_SUITES` — the T01 tenant routes, recorded as covered by their
  existing isolation suites. They were not re-audited route by route in
  02-1; a Phase 16 hardening task can move them into the explicit registry.

Every later business module (applications, documents, students, …) adds its
modules to :data:`BUSINESS_MODULES` and its routes here.
"""

from types import MappingProxyType
from typing import Final

BUSINESS_MODULES: Final = (
    "app.modules.courses",
    "app.modules.leads",
    "app.modules.applications",  # Phase 02-2
    "app.modules.documents",
    "app.modules.students",
)
CROSS_TENANT_SUITES: Final = (
    "tests/integration/test_courses_leads_cross_tenant.py",
    "tests/integration/test_admissions_cross_tenant.py",
)

_C = "/api/v1/courses"
_L = "/api/v1/leads"
_F = "/api/v1/lead-follow-ups"
_A = "/api/v1/applications"
_AI = f"{_A}/{{application_id}}"
_D = "/api/v1/documents"
_DI = f"{_D}/{{document_id}}"
_S = "/api/v1/students"
_SI = f"{_S}/{{student_id}}"
_APP_READS = "test_other_tenant_application_reads_are_not_found"
_APP_CHANGES = "test_other_tenant_application_changes_are_not_found"
_STUDENT_READS = "test_other_tenant_student_reads_are_not_found"

BUSINESS_ROUTES: Final = MappingProxyType(
    {
        ("GET", _C): "test_course_list_holds_no_other_tenant_course",
        ("POST", _C): "test_course_create_ignores_a_body_tenant",
        ("GET", f"{_C}/{{course_id}}"): "test_other_tenant_course_reads_are_not_found",
        ("PATCH", f"{_C}/{{course_id}}"): "test_other_tenant_course_changes_are_not_found",
        ("POST", f"{_C}/{{course_id}}/status"): "test_other_tenant_course_changes_are_not_found",
        ("GET", _L): "test_lead_list_holds_no_other_tenant_lead",
        ("POST", _L): "test_lead_create_rejects_other_tenant_references",
        ("POST", f"{_L}/duplicate-check"): "test_duplicate_check_never_matches_another_tenant",
        ("GET", f"{_L}/assignees"): "test_assignees_never_include_another_tenant",
        ("GET", f"{_L}/{{lead_id}}"): "test_other_tenant_lead_reads_are_not_found",
        ("PATCH", f"{_L}/{{lead_id}}"): "test_other_tenant_lead_changes_are_not_found",
        ("POST", f"{_L}/{{lead_id}}/transition"): "test_other_tenant_lead_changes_are_not_found",
        ("POST", f"{_L}/{{lead_id}}/assign"): "test_other_tenant_lead_changes_are_not_found",
        ("GET", f"{_L}/{{lead_id}}/follow-ups"): "test_other_tenant_lead_reads_are_not_found",
        ("POST", f"{_L}/{{lead_id}}/follow-ups"): "test_other_tenant_lead_changes_are_not_found",
        ("GET", f"{_L}/{{lead_id}}/activity"): "test_other_tenant_lead_reads_are_not_found",
        ("POST", f"{_L}/{{lead_id}}/notes"): "test_other_tenant_lead_changes_are_not_found",
        ("PATCH", f"{_F}/{{follow_up_id}}"): "test_other_tenant_follow_ups_are_not_found",
        ("POST", f"{_F}/{{follow_up_id}}/complete"): "test_other_tenant_follow_ups_are_not_found",
        ("POST", f"{_F}/{{follow_up_id}}/cancel"): "test_other_tenant_follow_ups_are_not_found",
        # Phase 02-2 (ADR-0021)
        ("GET", _A): "test_application_list_holds_no_other_tenant_application",
        ("POST", _A): "test_application_create_rejects_other_tenant_references",
        ("GET", _AI): _APP_READS,
        ("PATCH", _AI): _APP_CHANGES,
        ("POST", f"{_AI}/submit"): _APP_CHANGES,
        ("POST", f"{_AI}/review"): _APP_CHANGES,
        ("POST", f"{_AI}/admit"): "test_admission_never_links_another_tenants_student",
        ("GET", f"{_AI}/activity"): _APP_READS,
        ("GET", f"{_AI}/student-candidates"): _APP_READS,
        ("GET", f"{_AI}/documents"): _APP_READS,
        ("POST", f"{_AI}/documents"): _APP_CHANGES,
        ("GET", _D): "test_document_queue_holds_no_other_tenant_document",
        ("GET", f"{_DI}/download"): "test_other_tenant_documents_are_not_found",
        ("POST", f"{_DI}/verify"): "test_other_tenant_documents_are_not_found",
        ("POST", f"{_DI}/reject"): "test_other_tenant_documents_are_not_found",
        ("GET", _S): "test_student_list_holds_no_other_tenant_student",
        ("GET", _SI): _STUDENT_READS,
        ("GET", f"{_SI}/documents"): _STUDENT_READS,
        ("GET", f"{_SI}/activity"): _STUDENT_READS,
    }
)

T01_SUITES: Final = MappingProxyType(
    {
        "app.modules.institute": "tests/integration/test_tenant_roles_campuses_api.py",
        "app.modules.access": "tests/integration/test_tenant_roles_campuses_api.py",
        "app.modules.identity": "tests/integration/test_members_api.py",
        "app.modules.audit": "tests/integration/test_tenant_audit_api.py",
    }
)
