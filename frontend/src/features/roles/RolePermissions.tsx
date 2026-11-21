import {
  Alert,
  Badge,
  Card,
  CardBody,
  CardHeader,
} from "@/design-system/components";
import type {
  TenantPermissionWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";

import { countLabel, groupPermissions, SCOPE_LABEL } from "./labels";

// ADMIN-07 role permissions (02-C; GET /permissions, role.read), read-only:
// the tenant catalogue grouped by module, each permission marked granted or
// not for this role (badge text and icon, never colour alone). Without the
// catalogue, the role's permission codes are listed as they are.

function GrantState({ granted }: { granted: boolean }) {
  return granted ? (
    <Badge tone="success">Granted</Badge>
  ) : (
    <span className="text-caption text-text-secondary">Not granted</span>
  );
}

export function RolePermissions({
  role,
  catalogue,
  reference,
}: {
  role: TenantRoleWire;
  /** The permission catalogue; null when it couldn't be read. */
  catalogue: TenantPermissionWire[] | null;
  /** Support reference of a failed catalogue read. */
  reference?: string | null;
}) {
  const summary = `${countLabel(role.permissions.length, "permission", "permissions")} granted`;

  if (catalogue === null) {
    return (
      <Card as="section" aria-labelledby="role-permissions">
        <CardHeader
          title="Permissions"
          titleAs="h2"
          titleId="role-permissions"
          description={summary}
        />
        <CardBody>
          <div className="flex flex-col gap-4">
            <Alert tone="warning" title="Permission details couldn't be loaded">
              The role&apos;s permissions are listed by code.
              {reference ? ` Reference: ${reference}.` : null}
            </Alert>
            <CodeList codes={role.permissions} label="Granted permissions" />
          </div>
        </CardBody>
      </Card>
    );
  }

  const { groups, unlisted } = groupPermissions(catalogue, role.permissions);
  return (
    <Card as="section" aria-labelledby="role-permissions">
      <CardHeader
        title="Permissions"
        titleAs="h2"
        titleId="role-permissions"
        description={`${summary}, of ${catalogue.length} available.`}
      />
      <CardBody>
        <div className="flex flex-col gap-6">
          {groups.map((group) => (
            <section
              key={group.module}
              aria-labelledby={`module-${group.module}`}
              className="flex min-w-0 flex-col gap-2"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3
                  id={`module-${group.module}`}
                  className="text-body font-semibold text-text-primary"
                >
                  {group.label}
                </h3>
                <span className="text-caption text-text-secondary">
                  {group.granted} of {group.permissions.length} granted
                </span>
              </div>
              <ul className="flex flex-col divide-y divide-border-subtle">
                {group.permissions.map((permission) => (
                  <li
                    key={permission.code}
                    className="flex min-h-control-lg flex-col gap-2 py-2 tablet:flex-row tablet:items-center tablet:justify-between"
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="text-body-sm break-words text-text-primary">
                        {permission.description}
                      </span>
                      <span className="text-caption break-all text-text-secondary">
                        <code>{permission.code}</code> ·{" "}
                        {SCOPE_LABEL[permission.scope] ?? permission.scope}
                      </span>
                    </span>
                    <span className="shrink-0">
                      <GrantState granted={permission.granted} />
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          {groups.length === 0 && (
            <p className="text-body-sm text-text-secondary">
              No permissions are available to roles yet.
            </p>
          )}
          {unlisted.length > 0 && (
            <section
              aria-labelledby="module-unlisted"
              className="flex min-w-0 flex-col gap-2"
            >
              <h3
                id="module-unlisted"
                className="text-body font-semibold text-text-primary"
              >
                Not in the permission catalogue
              </h3>
              <CodeList
                codes={unlisted}
                label="Granted permissions without a description"
              />
            </section>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

function CodeList({ codes, label }: { codes: string[]; label: string }) {
  if (codes.length === 0) {
    return (
      <p className="text-body-sm text-text-secondary">
        This role has no permissions.
      </p>
    );
  }
  return (
    <ul
      aria-label={label}
      className="flex flex-col divide-y divide-border-subtle"
    >
      {codes.map((code) => (
        <li
          key={code}
          className="flex min-h-control-lg items-center justify-between gap-3 py-2"
        >
          <code className="text-body-sm break-all text-text-primary">
            {code}
          </code>
          <GrantState granted />
        </li>
      ))}
    </ul>
  );
}
