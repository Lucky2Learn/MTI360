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

import { EXPERIENCE, type ApplicationExperience } from "./types";

import type { NavItem } from "../navigation";

// Tenant Application (/app): one Maritime Training Institute's workspace.
// Navigation definitions only — no module is built in T00-08. The tenant is
// NOT part of the URL and is never taken from the browser: it will be derived
// server-side from the authenticated session (ADR-0004, Phase 01).

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
): NavItem {
  const href = `/app/${slug(label)}`;
  return {
    id: slug(label),
    label,
    href,
    icon,
    ...extra,
    children: pages.map((page) => ({
      id: `${slug(label)}-${slug(page)}`,
      label: page,
      href: `${href}/${slug(page)}`,
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
        },
      ],
    },
    {
      id: "operations",
      label: "Operations",
      items: [
        group("Grow", MarketingIcon, [
          "Marketing",
          "Campaigns",
          "Website",
          "Leads",
        ]),
        group(
          "Admissions",
          AdmissionsIcon,
          ["Leads", "Counselling", "Applications", "Documents", "Students"],
          // Demo count; real counts come from the server in Phase 04.
          { badge: { count: 12, label: "12 new enquiries" } },
        ),
        group("Academics", AcademicsIcon, [
          "Courses",
          "Batches",
          "Timetable",
          "Attendance",
          "Faculty",
          "Training",
          "Examinations",
          "Certificates",
        ]),
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
        group("Administration", SettingsIcon, [
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
        ]),
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
