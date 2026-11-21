"use client";

import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import {
  Alert,
  Button,
  Dialog,
  Form,
  Input,
  LoadingRegion,
  SkeletonText,
  toast,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import { ApiError } from "@/lib/api/errors";
import type {
  InvitedMemberWire,
  TenantCampusWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import {
  CAMPUS_MESSAGES,
  CAMPUS_SCOPE_MESSAGES,
  CampusScopeFields,
  type CampusScopeValue,
} from "./CampusScopeFields";
import {
  CAMPUS_READ,
  MEMBER_INVITE,
  OWNER_SCOPE_ERROR,
  OWNER_SCOPE_NOTE,
  ROLE_ASSIGN,
  ROLE_READ,
} from "./labels";
import { MEMBER_DENIED as DENIED } from "./mutations";
import { RoleChoices } from "./RoleChoices";

// Invite member (02-C; ADMIN-05; POST /members/invitations, member.invite).
// A new person gets an INVITED account; an existing account is invited
// unchanged (D8-1). Initial roles go through role.assign and the
// no-escalation rule, so they are offered only with role.assign and
// role.read; campuses come from GET /campuses. The invitation email is sent
// after the API answers: the UI says it is being sent, never that it
// arrived. Client checks mirror the API; the API validates again. With the
// Institute owner role, the invitation needs all campuses (ADR-0023): the
// form says so and never switches the access by itself.

const EMAIL_FORMAT = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NAME_MAX = 200;
const EMAIL_MAX = 254;
const NAME_MESSAGE = "Enter a name of up to 200 characters.";
const EMAIL_MESSAGE = "Enter an email address like name@institute.edu.";

type Field = "email" | "name" | "campuses" | "roles" | "scope";
type Errors = Partial<Record<Field, string>>;

type Options =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "ready"; roles: TenantRoleWire[]; campuses: TenantCampusWire[] };

export function InviteMemberButton() {
  const { can } = useTenantSession();
  const [open, setOpen] = useState(false);
  if (!can(MEMBER_INVITE)) return null;
  return (
    <>
      <Button iconStart={AddIcon} onPress={() => setOpen(true)}>
        Invite member
      </Button>
      {open && (
        <Dialog
          isOpen
          onOpenChange={setOpen}
          size="lg"
          title="Invite member"
          description="They receive an email invitation to join your institute."
        >
          {(close) => <InviteForm onDone={close} />}
        </Dialog>
      )}
    </>
  );
}

function useInviteOptions(withRoles: boolean, withCampuses: boolean) {
  const { request } = useTenantSession();
  const [options, setOptions] = useState<Options>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([
      withRoles ? request<TenantRoleWire[]>("/roles") : Promise.resolve([]),
      withCampuses
        ? request<TenantCampusWire[]>("/campuses")
        : Promise.resolve([]),
    ]).then(
      ([roles, campuses]) =>
        active && setOptions({ kind: "ready", roles, campuses }),
      () => active && setOptions({ kind: "failed" }),
    );
    return () => {
      active = false;
    };
  }, [request, withRoles, withCampuses, attempt]);
  const reload = useCallback(() => {
    setOptions({ kind: "loading" });
    setAttempt((current) => current + 1);
  }, []);
  return { options, reload };
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const router = useRouter();
  const { session, can, request } = useTenantSession();
  const wrapper = useRef<HTMLDivElement>(null);
  const withRoles = can(ROLE_ASSIGN) && can(ROLE_READ);
  const { options, reload } = useInviteOptions(withRoles, can(CAMPUS_READ));
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [campus, setCampus] = useState<CampusScopeValue>({
    scope: "ALL",
    campusIds: [],
  });
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  // The API's is_owner flag on each role, never its name (ADR-0023).
  const ownerRoleIds = new Set(
    options.kind === "ready"
      ? options.roles.filter((role) => role.is_owner).map((role) => role.id)
      : [],
  );
  const ownerChosen = roleIds.some((id) => ownerRoleIds.has(id));

  const validate = (): Errors => {
    const found: Errors = {};
    const trimmedEmail = email.trim();
    if (
      !trimmedEmail ||
      trimmedEmail.length > EMAIL_MAX ||
      !EMAIL_FORMAT.test(trimmedEmail)
    ) {
      found.email = EMAIL_MESSAGE;
    }
    const trimmedName = name.trim();
    if (!trimmedName) found.name = "Enter the person's name.";
    else if (trimmedName.length > NAME_MAX) found.name = NAME_MESSAGE;
    if (ownerChosen && campus.scope === "SELECTED") {
      found.scope = OWNER_SCOPE_ERROR;
    } else if (campus.scope === "SELECTED" && campus.campusIds.length === 0) {
      found.campuses = CAMPUS_MESSAGES.required;
    }
    return found;
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = validate();
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    try {
      const invited = await request<InvitedMemberWire>("/members/invitations", {
        method: "POST",
        body: {
          email: email.trim(),
          display_name: name.trim(),
          role_ids: roleIds,
          campus_scope: campus.scope,
          campus_ids: campus.scope === "SELECTED" ? campus.campusIds : [],
        },
      });
      toast.success(
        invited.account === "existing"
          ? `${invited.member.user.display_name} already has an MTI 360 account. An invitation to join your institute is being emailed.`
          : `An invitation is being emailed to ${invited.member.user.email}.`,
      );
      router.refresh();
      onDone();
    } catch (error) {
      setPending(false);
      const fields = fieldCodes(error);
      const mapped: Errors = {};
      if (fields.email) mapped.email = EMAIL_MESSAGE;
      if (fields.display_name) mapped.name = NAME_MESSAGE;
      if (fields.campus_ids) {
        mapped.campuses =
          CAMPUS_MESSAGES[fields.campus_ids] ?? CAMPUS_MESSAGES.unknown;
      }
      if (fields.campus_scope) {
        mapped.scope =
          CAMPUS_SCOPE_MESSAGES[fields.campus_scope] ?? OWNER_SCOPE_ERROR;
      }
      if (fields.role_ids) mapped.roles = "Choose at most 20 roles.";
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
        focusFirstInvalid(wrapper.current);
        return;
      }
      if (error instanceof ApiError && error.code === "CONFLICT") {
        setFeedback({
          tone: "error",
          title: "This person wasn't invited",
          body: "They may already be a member of your institute (a removed member is re-invited from their page), or their account is disabled.",
        });
        return;
      }
      if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
        setFeedback(DENIED);
        return;
      }
      if (error instanceof ApiError && error.code === "NOT_FOUND") {
        setFeedback({
          tone: "warning",
          title: "A role or campus is no longer available",
          body: "Close this dialog, then try again.",
        });
        return;
      }
      setFeedback(
        formFeedback(error) ?? {
          tone: "error",
          title: "Something went wrong",
          body: "Something went wrong. Try again in a moment.",
        },
      );
    }
  };

  return (
    <div ref={wrapper}>
      <Form
        aria-label="Invite member"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(value) => {
            setEmail(value);
            setErrors((current) => ({ ...current, email: undefined }));
          }}
          autoComplete="off"
          autoCapitalize="none"
          maxLength={EMAIL_MAX}
          isRequired
          isInvalid={Boolean(errors.email)}
          errorMessage={errors.email}
        />
        <Input
          label="Full name"
          value={name}
          onChange={(value) => {
            setName(value);
            setErrors((current) => ({ ...current, name: undefined }));
          }}
          description="Used for a new account. A person who already has an account keeps their own name."
          autoComplete="off"
          maxLength={NAME_MAX}
          isRequired
          isInvalid={Boolean(errors.name)}
          errorMessage={errors.name}
        />
        {options.kind === "loading" ? (
          <LoadingRegion label="Loading roles and campuses">
            <SkeletonText lines={4} />
          </LoadingRegion>
        ) : options.kind === "failed" ? (
          <Alert
            tone="error"
            title="Roles and campuses couldn't be loaded"
            action={
              <Button variant="secondary" size="sm" onPress={reload}>
                Try again
              </Button>
            }
          >
            Try again in a moment.
          </Alert>
        ) : (
          <>
            {withRoles && (
              <RoleChoices
                roles={options.roles}
                permissions={session.permissions}
                selected={roleIds}
                onChange={(ids) => {
                  setRoleIds(ids);
                  setErrors((current) => ({
                    ...current,
                    roles: undefined,
                    scope: undefined,
                  }));
                }}
                errorMessage={errors.roles}
                isDisabled={pending}
              />
            )}
            <CampusScopeFields
              campuses={options.campuses}
              value={campus}
              onChange={(value) => {
                setCampus(value);
                setErrors((current) => ({
                  ...current,
                  campuses: undefined,
                  scope: undefined,
                }));
              }}
              errorMessage={errors.campuses}
              scopeNote={ownerChosen ? OWNER_SCOPE_NOTE : undefined}
              scopeErrorMessage={errors.scope}
              isDisabled={pending}
            />
          </>
        )}
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onDone} isDisabled={pending}>
            Cancel
          </Button>
          <Button
            type="submit"
            isPending={pending}
            isDisabled={options.kind !== "ready"}
          >
            Send invitation
          </Button>
        </div>
      </Form>
    </div>
  );
}
