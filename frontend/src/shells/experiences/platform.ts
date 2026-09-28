import {
  AuditIcon,
  DashboardIcon,
  HealthIcon,
  InstituteIcon,
  IntegrationIcon,
  SettingsIcon,
  UsersIcon,
} from "@/design-system/icons";

import { EXPERIENCE, type ApplicationExperience } from "./types";

// Platform Administration (/platform): the MTI 360 SaaS control plane,
// used by platform administrators. Navigation placeholders only; the modules
// are built in Phase 02. Platform users are a separate security domain from
// tenant administrators (CLAUDE.md §7).

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
          icon: DashboardIcon,
        },
        {
          id: "tenants",
          label: "Tenants",
          href: "/platform/tenants",
          icon: InstituteIcon,
        },
        {
          id: "platform-users",
          label: "Platform Users",
          href: "/platform/users",
          icon: UsersIcon,
        },
        {
          id: "system-health",
          label: "System Health",
          href: "/platform/system-health",
          icon: HealthIcon,
        },
        {
          id: "integrations",
          label: "Integrations",
          href: "/platform/integrations",
          icon: IntegrationIcon,
        },
        {
          id: "audit",
          label: "Audit",
          href: "/platform/audit",
          icon: AuditIcon,
        },
        {
          id: "settings",
          label: "Settings",
          href: "/platform/settings",
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
