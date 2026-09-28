import {
  AdmissionsIcon,
  CourseIcon,
  DashboardIcon,
  FinanceIcon,
} from "@/design-system/icons";

import type { Navigation } from "./navigation";

// Shared fixtures for shell tests (T00-08). Not product navigation.

export const TEST_NAVIGATION: Navigation = [
  {
    id: "main",
    items: [
      { id: "home", label: "Dashboard", href: "/app", icon: DashboardIcon },
    ],
  },
  {
    id: "operations",
    label: "Operations",
    items: [
      {
        id: "admissions",
        label: "Admissions",
        href: "/app/admissions",
        icon: AdmissionsIcon,
        badge: { count: 12, label: "12 new enquiries" },
        children: [
          { id: "leads", label: "Leads", href: "/app/admissions/leads" },
          {
            id: "applications",
            label: "Applications",
            href: "/app/admissions/applications",
          },
        ],
      },
      {
        id: "academics",
        label: "Academics",
        href: "/app/academics",
        icon: CourseIcon,
        children: [
          { id: "courses", label: "Courses", href: "/app/academics/courses" },
        ],
      },
      {
        id: "finance",
        label: "Finance",
        href: "/app/finance",
        icon: FinanceIcon,
      },
    ],
  },
];
