import { EXPERIENCE, type PublicExperience } from "./types";

// Tenant Public Website (/site): the future public website of ONE
// Maritime Training Institute (courses, eligibility, fees, admissions,
// enquiry). It is NOT the MTI 360 marketing website (ADR-0003, INC-26).
// Tenant resolution from a verified domain and tenant branding arrive in
// Phase 14; until then this is a neutral structural preview with no tenant
// identity.

export const publicSiteExperience: PublicExperience = {
  id: EXPERIENCE.PUBLIC_SITE,
  label: "Institute Website",
  basePath: "/site",
  navigationLabel: "Website navigation",
  layout: "public",
  pageWidth: "standard",
  navigation: [
    {
      id: "site",
      items: [
        { id: "home", label: "Home", href: "/site" },
        { id: "courses", label: "Courses", href: "/site/courses" },
        { id: "admissions", label: "Admissions", href: "/site/admissions" },
        { id: "about", label: "About", href: "/site/about" },
        { id: "contact", label: "Contact", href: "/site/contact" },
      ],
    },
  ],
};
