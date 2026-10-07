import {
  AuditIcon,
  DashboardIcon,
  HealthIcon,
  InstituteIcon,
  IntegrationIcon,
  SettingsIcon,
  UsersIcon,
} from "@/design-system/icons";
import { ALWAYS, permission, UNRELEASED } from "@/lib/authz/requirements";

import { EXPERIENCE, type ApplicationExperience } from "./types";

// Platform Administration (/platform): the MTI 360 SaaS control plane,
// used by platform administrators. Navigation placeholders only; the modules
// are built in Phase 02. Platform users are a separate security domain from
// tenant administrators (CLAUDE.md §7).
//
// Requirement map (T01-09B UI contract §8): every item declares one
// requirement — the single source for navigation filtering and page access.
// Items without a platform permission yet are UNRELEASED. Advisory only: the
// platform API authorizes every request.

export const platformExperience: ApplicationExperience = {
  id: EXPERIENCE.PLATFORM,
  label: "Platform Administration",
  basePath: "/platform",
  navigationLabel: "Platform navigation",
  layout: "application",
  sidebar: "collapsible",
  search: true,
  notifications: true,
  pageWidth: "wide",
  navigation: [
    {
      id: "platform",
      items: [
        {
          id: "overview",
          label: "Overview",
          href: "/platform",
          requirement: ALWAYS,
          icon: DashboardIcon,
        },
        {
          id: "tenants",
          label: "Tenants",
          href: "/platform/tenants",
          requirement: permission("tenant.read"),
          icon: InstituteIcon,
        },
        {
          id: "platform-users",
          label: "Platform Users",
          href: "/platform/users",
          requirement: permission("platform_user.read"),
          icon: UsersIcon,
        },
        {
          id: "system-health",
          label: "System Health",
          href: "/platform/system-health",
          requirement: UNRELEASED,
          icon: HealthIcon,
        },
        {
          id: "integrations",
          label: "Integrations",
          href: "/platform/integrations",
          requirement: UNRELEASED,
          icon: IntegrationIcon,
        },
        {
          id: "audit",
          label: "Audit",
          href: "/platform/audit",
          requirement: permission("audit.read"),
          icon: AuditIcon,
        },
        {
          id: "settings",
          label: "Settings",
          href: "/platform/settings",
          requirement: UNRELEASED,
          icon: SettingsIcon,
        },
      ],
    },
  ],
  demo: {
    account: {
      name: "Platform operator",
      detail: "Demo account · Platform",
      initials: "PO",
    },
    notifications: [
      {
        id: "platform-n1",
        title: "Tenant workspace provisioned",
        description: "A new institute workspace finished provisioning.",
        timestamp: "2026-09-28T09:40:00+05:30",
        timeLabel: "20 min ago",
        read: false,
      },
      {
        id: "platform-n2",
        title: "Maintenance window confirmed",
        description: "Database maintenance on Sunday, 02:00–03:00 IST.",
        timestamp: "2026-09-27T18:05:00+05:30",
        timeLabel: "Yesterday",
        read: false,
      },
      {
        id: "platform-n3",
        title: "Monthly usage report available",
        timestamp: "2026-09-25T08:00:00+05:30",
        timeLabel: "3 days ago",
        read: true,
      },
    ],
  },
};
