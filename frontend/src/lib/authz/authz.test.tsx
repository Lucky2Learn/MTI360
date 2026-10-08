import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TenantSessionProvider } from "@/lib/session/SessionProvider";
import {
  EXPERIENCE,
  flattenNavigation,
  getExperience,
  type Navigation,
} from "@/shells";
import { readySession } from "@/test/session-fixtures";

import { filterNavigation } from "./navigation";
import { PermissionGate } from "./PermissionGate";
import {
  ALWAYS,
  can,
  canAll,
  canAny,
  meets,
  permission,
  UNRELEASED,
  unreleasedVisible,
} from "./requirements";

// Frontend authorization (T01-05 UI contract §6, §8.4, §12, §16). Advisory
// only — these tests pin what the UI shows; the API authorizes everything.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TENANT_NAVIGATION = getExperience(EXPERIENCE.TENANT).navigation;
const ids = (navigation: Navigation) =>
  flattenNavigation(navigation).map((item) => item.id);

describe("selectors", () => {
  it("compare permission codes for equality only", () => {
    const granted = new Set(["campus.read", "member.read"]);
    expect(can(granted, "campus.read")).toBe(true);
    expect(can(granted, "campus.create")).toBe(false);
    expect(can(granted, "campus.*")).toBe(false);
    expect(can(granted, "campus")).toBe(false);
    expect(can(granted, "")).toBe(false);
    expect(can(["role.read"], "role.read")).toBe(true);
    expect(canAny(granted, ["role.read", "member.read"])).toBe(true);
    expect(canAny(granted, [])).toBe(false);
    expect(canAll(granted, ["campus.read", "member.read"])).toBe(true);
    expect(canAll(granted, ["campus.read", "role.read"])).toBe(false);
    expect(canAll(granted, [])).toBe(false);
  });

  it("decide requirements", () => {
    const context = { permissions: ["audit.read"], showUnreleased: false };
    expect(meets(ALWAYS, context)).toBe(true);
    expect(meets(permission("audit.read"), context)).toBe(true);
    expect(meets(permission("role.read"), context)).toBe(false);
    expect(meets(UNRELEASED, context)).toBe(false);
    expect(meets(UNRELEASED, { ...context, showUnreleased: true })).toBe(true);
    expect(meets(undefined, context)).toBe(false);
  });

  it("show UNRELEASED pages in development only (T01-05 §6)", () => {
    expect(unreleasedVisible("development")).toBe(true);
    expect(unreleasedVisible("test")).toBe(false);
    expect(unreleasedVisible("staging")).toBe(false);
    expect(unreleasedVisible("production")).toBe(false);
    expect(unreleasedVisible("")).toBe(false);
  });
});

describe("requirement map (T01-05 §6)", () => {
  it("every tenant navigation item declares exactly one requirement", () => {
    const missing = flattenNavigation(TENANT_NAVIGATION).filter(
      (item) => item.requirement === undefined,
    );
    expect(missing.map((item) => item.href)).toEqual([]);
  });

  it("maps the T01 administration pages and the dashboard", () => {
    const byHref = new Map(
      flattenNavigation(TENANT_NAVIGATION).map((item) => [
        item.href,
        item.requirement,
      ]),
    );
    expect(byHref.get("/app")).toBe(ALWAYS);
    expect(byHref.get("/app/administration/institute")).toEqual(
      permission("tenant.profile.read"),
    );
    expect(byHref.get("/app/administration/campuses")).toEqual(
      permission("campus.read"),
    );
    expect(byHref.get("/app/administration/users")).toEqual(
      permission("member.read"),
    );
    expect(byHref.get("/app/administration/roles")).toEqual(
      permission("role.read"),
    );
    expect(byHref.get("/app/administration/audit-logs")).toEqual(
      permission("audit.read"),
    );
    // Phase 02-1: the course catalogue and the canonical Leads page (INC-45).
    expect(byHref.get("/app/academics/courses")).toEqual(
      permission("course.read"),
    );
    expect(byHref.get("/app/admissions/leads")).toEqual(
      permission("lead.read"),
    );
    for (const href of [
      "/app/administration/integrations",
      "/app/administration/billing",
      "/app/grow/leads",
      "/app/admissions/applications",
      "/app/academics/batches",
      "/app/ai/sql-data-agent",
    ]) {
      expect(byHref.get(href)).toBe(UNRELEASED);
    }
  });
});

describe("navigation filtering (NAV-01 / NAV-02)", () => {
  const production = (permissions: string[]) =>
    filterNavigation(TENANT_NAVIGATION, { permissions, showUnreleased: false });

  it("with campus.read only: Campuses under Administration, nothing else but Dashboard", () => {
    const navigation = production(["campus.read"]);
    expect(navigation.map((section) => section.id)).toEqual([
      "home",
      "institute",
    ]);
    expect(ids(navigation)).toEqual([
      "dashboard",
      "administration",
      "administration-campuses",
    ]);
    // The group links to its first visible child.
    const group = navigation[1]!.items[0]!;
    expect(group.href).toBe("/app/administration/campuses");
  });

  it("with no permissions: only the Dashboard (never empty)", () => {
    expect(ids(production([]))).toEqual(["dashboard"]);
  });

  it("with the full T01 baseline: the five administration pages in order", () => {
    const navigation = production([
      "audit.read",
      "campus.read",
      "member.read",
      "role.read",
      "tenant.profile.read",
    ]);
    expect(
      navigation[1]!.items[0]!.children!.map((item) => item.label),
    ).toEqual(["Institute", "Campuses", "Users", "Roles", "Audit Logs"]);
    expect(navigation[1]!.items[0]!.href).toBe("/app/administration/institute");
  });

  it("removes empty sections and groups, so no heading sits over an empty list", () => {
    const navigation = production(["member.read"]);
    expect(navigation.every((section) => section.items.length > 0)).toBe(true);
    expect(navigation.map((section) => section.label)).not.toContain(
      "Operations",
    );
  });

  it("shows no demo badge anywhere (INC-45: a badge needs real data)", () => {
    expect(flattenNavigation(production([])).some((item) => item.badge)).toBe(
      false,
    );
    const development = filterNavigation(TENANT_NAVIGATION, {
      permissions: [],
      showUnreleased: true,
    });
    expect(flattenNavigation(development).some((item) => item.badge)).toBe(
      false,
    );
  });

  it("with the admissions permissions: Admissions › Leads and Academics › Courses", () => {
    const navigation = production(["lead.read", "course.read"]);
    expect(ids(navigation)).toEqual([
      "dashboard",
      "admissions",
      "admissions-leads",
      "academics",
      "academics-courses",
    ]);
    // GROW › Leads stays UNRELEASED: one Leads page, under Admissions.
    expect(ids(navigation)).not.toContain("grow-leads");
  });

  it("is the single source for every navigation surface", () => {
    // The shell renders sidebar, rail, drawer and command search from the
    // ONE filtered configuration it receives (tenant-frame.tsx).
    const source = readFileSync(
      path.join(HERE, "..", "..", "app", "app", "tenant-frame.tsx"),
      "utf8",
    );
    expect(source.match(/filterNavigation\(/g)).toHaveLength(1);
  });
});

describe("PermissionGate", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  const gate = (permissions: string[]) =>
    render(
      <TenantSessionProvider initialSession={readySession({ permissions })}>
        <PermissionGate permission="member.invite">
          <button type="button">Invite member</button>
        </PermissionGate>
      </TenantSessionProvider>,
    );

  it("renders its children only with the permission, and nothing otherwise", () => {
    gate(["member.invite"]);
    expect(
      screen.getByRole("button", { name: "Invite member" }),
    ).toBeInTheDocument();
  });

  it("renders nothing at all without it (hide, not disable)", () => {
    const { container } = gate(["member.read"]);
    expect(container).toBeEmptyDOMElement();
  });

  it("ignores permissions planted in browser storage or the URL", () => {
    window.localStorage.setItem(
      "permissions",
      JSON.stringify(["member.invite"]),
    );
    window.localStorage.setItem("mti360.permissions", "member.invite");
    window.sessionStorage.setItem("permissions", "member.invite");
    window.history.replaceState(
      null,
      "",
      "/app?permissions=member.invite&role=ADMIN",
    );
    const { container } = gate([]);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("static checks", () => {
  const SRC = path.resolve(HERE, "..", "..");
  const sources = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) return sources(full);
      return /\.(ts|tsx)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)
        ? [full]
        : [];
    });
  const files = sources(SRC);
  // Code only: comments explain the rules and may name what is forbidden.
  const code = (file: string) =>
    readFileSync(file, "utf8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "")
      .replace(/^\s*\*.*$/gm, "");

  it("has no role-name gating helper or role comparison", () => {
    const offenders = files.filter((file) => {
      const text = code(file);
      return (
        /\bhasRole\b/.test(text) ||
        /roles?\.(?:some|every|find|includes)\(/.test(text) ||
        /role\.name\s*===|===\s*role\.name/.test(text)
      );
    });
    expect(offenders).toEqual([]);
  });

  it("never reads authority from browser storage in session, API and authorization code", () => {
    const scoped = files.filter((file) =>
      /[\\/](lib[\\/](api|session|authz)|features[\\/]identity|app[\\/]app|app[\\/]\(tenant-auth\))[\\/]/.test(
        file,
      ),
    );
    expect(scoped.length).toBeGreaterThan(10);
    const offenders = scoped.filter((file) =>
      /localStorage|sessionStorage|indexedDB|document\.cookie/.test(code(file)),
    );
    expect(offenders).toEqual([]);
  });
});
