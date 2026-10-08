"""Cross-tenant route registry (Phase 02-1; tenancy.md §8, ADR-0020 §11, INC-46).

``app/api/coverage.py`` proves that every route requires a permission. It does
not prove that a route keeps another tenant's data out. This registry does,
incrementally:

* :data:`BUSINESS_ROUTES` — every route of the business modules maps to the
  test, in :data:`CROSS_TENANT_SUITE`, that calls it as tenant A with tenant
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

BUSINESS_MODULES: Final = ("app.modules.courses", "app.modules.leads")
CROSS_TENANT_SUITE: Final = "tests/integration/test_courses_leads_cross_tenant.py"

_C = "/api/v1/courses"
_L = "/api/v1/leads"
_F = "/api/v1/lead-follow-ups"

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
