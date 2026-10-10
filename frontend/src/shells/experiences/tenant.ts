import {
  AcademicsIcon,
  AdmissionsIcon,
  AiIcon,
  AnalyticsIcon,
  ComplianceIcon,
  DashboardIcon,
  FinanceIcon,
  MarketingIcon,
  MessageIcon,
  PlacementIcon,
  SettingsIcon,
  WorkflowIcon,
  type IconComponent,
} from "@/design-system/icons";
import {
  ALWAYS,
  permission,
  UNRELEASED,
  type Requirement,
} from "@/lib/authz/requirements";

import { EXPERIENCE, type ApplicationExperience } from "./types";

import type { NavItem } from "../navigation";

// Tenant Application (/app): one Maritime Training Institute's workspace.
// Navigation definitions only — no module is built in T00-08. The tenant is
// NOT part of the URL and is never taken from the browser: it is derived
// server-side from the authenticated session (ADR-0004, T01-04).
//
// Requirement map (T01-05 UI contract §6; T01-09A): every item declares one
// requirement. It is the single source for navigation filtering, command
// search and page access. Modules without a permission yet are UNRELEASED;
// they replace it with their own permission when they ship.

const slug = (label: string) =>
  label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

function group(
  label: string,
  icon: IconComponent,
  pages: string[],
  extra: Partial<NavItem> = {},
  requirements: Partial<Record<string, Requirement>> = {},
): NavItem {
  const href = `/app/${slug(label)}`;
  return {
    id: slug(label),
    label,
    href,
    icon,
    // The group's own overview page has no permission yet.
    requirement: UNRELEASED,
    ...extra,
    children: pages.map((page) => ({
      id: `${slug(label)}-${slug(page)}`,
      label: page,
      href: `${href}/${slug(page)}`,
      requirement: requirements[page] ?? UNRELEASED,
    })),
  };
}

export const tenantExperience: ApplicationExperience = {
  id: EXPERIENCE.TENANT,
  label: "Tenant Application",
  basePath: "/app",
  navigationLabel: "Institute navigation",
  layout: "application",
  sidebar: "collapsible",
  search: true,
  notifications: true,
  pageWidth: "wide",
  navigation: [
    {
      id: "home",
      items: [
        {
          id: "dashboard",
          label: "Dashboard",
          href: "/app",
          icon: DashboardIcon,
          requirement: ALWAYS,
        },
      ],
    },
    {
      id: "operations",
      label: "Operations",
      items: [
        // GROW › Leads stays UNRELEASED: the canonical Leads page is under
        // Admissions (Phase 02-1, INC-45); GROW defines a marketing view later.
        group("Grow", MarketingIcon, [
          "Marketing",
          "Campaigns",
          "Website",
          "Leads",
        ]),
        // No badge: the T00-08 demo count ("12 new enquiries") was removed in
        // Phase 02-1 (INC-45). A badge returns only when real data backs it.
        group(
          "Admissions",
          AdmissionsIcon,
          ["Leads", "Counselling", "Applications", "Documents", "Students"],
          {},
          // Leads: list and board (ADM-02, ?view=board), Phase 02-1.
          // Applications (ADM-05…ADM-10), the document verification queue
          // (ADM-09) and Students (ADM-11/12), Phase 02-2. Counselling stays
          // UNRELEASED (P1).
          {
            Leads: permission("lead.read"),
            Applications: permission("application.read"),
            Documents: permission("document.read"),
            Students: permission("student.read"),
          },
        ),
        group(
          "Academics",
          AcademicsIcon,
          [
            "Courses",
            "Batches",
            "Timetable",
            "Attendance",
            "Faculty",
            "Training",
            "Examinations",
            "Certificates",
          ],
          {},
          // The institute course catalogue (ACA-01), Phase 02-1.
          { Courses: permission("course.read") },
        ),
        group("Finance", FinanceIcon, [
          "Fee Structure",
          "Invoices",
          "Payments",
          "Outstanding",
          "Refunds",
          "Reports",
        ]),
        group("Compliance", ComplianceIcon, [
          "Dashboard",
          "Requirements",
          "Documents",
          "Inspections",
          "Corrective Actions",
          "Audit",
        ]),
        group("Placement", PlacementIcon, [
          "Dashboard",
          "Students",
          "Companies",
          "Opportunities",
          "Placement Tracking",
          "Alumni",
        ]),
      ],
    },
    {
      id: "engagement",
      label: "Engagement & Intelligence",
      items: [
        group("Communication", MessageIcon, [
          "WhatsApp",
          "Email",
          "SMS",
          "Voice",
          "Templates",
        ]),
        group("Automation", WorkflowIcon, [
          "Workflows",
          "AI Agents",
          "Executions",
        ]),
        group("AI", AiIcon, [
          "Assistant",
          "Resolution",
          "Analytics",
          "SQL/Data Agent",
          "Knowledge",
        ]),
        group("Analytics", AnalyticsIcon, [
          "Executive",
          "Admissions",
          "Finance",
          "Academic",
          "Marketing",
          "AI",
        ]),
      ],
    },
    {
      id: "institute",
      label: "Institute",
      items: [
        group(
          "Administration",
          SettingsIcon,
          [
            "Institute",
            "Campuses",
            "Users",
            "Roles",
            "Integrations",
            "AI Config",
            "Notifications",
            "Billing",
            "Audit Logs",
            "Settings",
          ],
          {},
          {
            Institute: permission("tenant.profile.read"),
            Campuses: permission("campus.read"),
            Users: permission("member.read"),
            Roles: permission("role.read"),
            "Audit Logs": permission("audit.read"),
          },
        ),
      ],
    },
  ],
  demo: {
    account: {
      name: "Institute administrator",
      detail: "Demo account · Institute",
      initials: "IA",
    },
    notifications: [
      {
        id: "tenant-n1",
        title: "New enquiry for B.Sc. Nautical Science",
        description: "Submitted through the website enquiry form.",
        timestamp: "2026-09-28T09:15:00+05:30",
        timeLabel: "45 min ago",
        read: false,
      },
      {
        id: "tenant-n2",
        title: "DNS 2026-B timetable published",
        description: "Classes start on Monday, 5 October.",
        timestamp: "2026-09-27T17:30:00+05:30",
        timeLabel: "Yesterday",
        read: false,
      },
      {
        id: "tenant-n3",
        title: "STCW refresher batch is full",
        timestamp: "2026-09-26T11:00:00+05:30",
        timeLabel: "2 days ago",
        read: true,
      },
    ],
  },
};
