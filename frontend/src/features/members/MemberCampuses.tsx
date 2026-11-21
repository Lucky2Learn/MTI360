"use client";

import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  Form,
} from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { MemberWire, TenantCampusWire } from "@/lib/api/tenant-admin";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { focusFirstInvalid } from "../shared/forms";

import {
  CAMPUS_MESSAGES,
  CAMPUS_SCOPE_MESSAGES,
  CampusScopeFields,
  type CampusScopeValue,
} from "./CampusScopeFields";
import {
  isOwnMembership,
  MEMBER_UPDATE,
  OWNER_SCOPE_ERROR,
  OWNER_SCOPE_NOTE,
} from "./labels";
import { useMemberMutation } from "./mutations";

// ADMIN-06 campus access (02-C; PUT /members/{id}/campus-scope,
// member.update, versioned). Campus names come from GET /campuses, which
// lists only the caller's own campuses (D-B1): other selected campuses are
// counted, never named. Never offered on one's own membership (D8-4). An
// Institute owner keeps all campuses (ADR-0023): "Selected campuses" is
// disabled and says why; the API's 422 is shown at the same field.

export function MemberCampuses({
  member,
  campuses,
}: {
  member: MemberWire;
  /** The campuses the caller can see; null when they can't be read. */
  campuses: TenantCampusWire[] | null;
}) {
  const { session, can } = useTenantSession();
  const [editing, setEditing] = useState(false);
  const own = isOwnMembership(member, session.user.email);
  const byId = new Map((campuses ?? []).map((campus) => [campus.id, campus]));
  const named = member.campus_ids.flatMap((id) => byId.get(id) ?? []);
  const hidden = member.campus_ids.length - named.length;
  const editable = can(MEMBER_UPDATE) && !own && campuses !== null;

  return (
    <Card as="section">
      <CardHeader
        title="Campus access"
        titleAs="h2"
        description="The campuses whose records this member works with."
        actions={
          editable ? (
            <Button
              variant="secondary"
              size="sm"
              iconStart={EditIcon}
              onPress={() => setEditing(true)}
            >
              Change access
            </Button>
          ) : undefined
        }
      />
      <CardBody>
        {member.campus_scope === "ALL" ? (
          <p className="text-body-sm text-text-primary">
            All campuses, including campuses your institute adds later.
          </p>
        ) : (
          <ul className="flex flex-col gap-1 text-body-sm text-text-primary">
            {named.map((campus) => (
              <li key={campus.id}>{`${campus.name} (${campus.code})`}</li>
            ))}
            {hidden > 0 && (
              <li className="text-text-secondary">
                {`${named.length > 0 ? "And " : ""}${hidden} ${hidden === 1 ? "campus" : "campuses"} outside your access`}
              </li>
            )}
          </ul>
        )}
        {can(MEMBER_UPDATE) && own && (
          <p className="mt-3 text-caption text-text-secondary">
            You can&apos;t change your own campus access. Ask another
            administrator.
          </p>
        )}
      </CardBody>
      {editing && campuses && (
        <Dialog
          isOpen
          onOpenChange={setEditing}
          title={`Campus access for ${member.user.display_name}`}
          description="They work with the records of these campuses from their next action."
        >
          {(close) => (
            <CampusScopeForm
              member={member}
              campuses={campuses}
              onDone={close}
            />
          )}
        </Dialog>
      )}
    </Card>
  );
}

function CampusScopeForm({
  member,
  campuses,
  onDone,
}: {
  member: MemberWire;
  campuses: TenantCampusWire[];
  onDone: () => void;
}) {
  const mutate = useMemberMutation();
  const wrapper = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState<CampusScopeValue>({
    scope: member.campus_scope,
    campusIds: member.campus_ids,
  });
  const [error, setError] = useState<string | undefined>();
  const [scopeError, setScopeError] = useState<string | undefined>();
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const owner = member.is_owner;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setFeedback(null);
    if (owner && value.scope === "SELECTED") {
      setScopeError(OWNER_SCOPE_ERROR);
      focusFirstInvalid(wrapper.current);
      return;
    }
    if (value.scope === "SELECTED" && value.campusIds.length === 0) {
      setError(CAMPUS_MESSAGES.required);
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    const outcome = await mutate({
      path: `/members/${member.id}/campus-scope`,
      method: "PUT",
      body: {
        campus_scope: value.scope,
        campus_ids: value.scope === "SELECTED" ? value.campusIds : [],
        version: member.version,
      },
      success: `Campus access updated for ${member.user.display_name}.`,
      conflict:
        "Campus access wasn't changed. This member was changed by someone else. The latest details are shown.",
    });
    setPending(false);
    if (outcome.kind === "done") onDone();
    else if (outcome.kind === "fields") {
      const scopeCode = outcome.fields.campus_scope;
      if (scopeCode) {
        setScopeError(CAMPUS_SCOPE_MESSAGES[scopeCode] ?? OWNER_SCOPE_ERROR);
      } else {
        const code = outcome.fields.campus_ids;
        setError(
          code
            ? (CAMPUS_MESSAGES[code] ?? CAMPUS_MESSAGES.unknown)
            : CAMPUS_MESSAGES.unknown,
        );
      }
      focusFirstInvalid(wrapper.current);
    } else setFeedback(outcome.feedback);
  };

  return (
    <div ref={wrapper}>
      <Form
        aria-label="Campus access"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <CampusScopeFields
          campuses={campuses}
          value={value}
          onChange={(next) => {
            setValue(next);
            setError(undefined);
            setScopeError(undefined);
          }}
          errorMessage={error}
          scopeNote={owner ? OWNER_SCOPE_NOTE : undefined}
          isSelectedDisabled={owner}
          scopeErrorMessage={scopeError}
          isDisabled={pending}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onDone} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Save access
          </Button>
        </div>
      </Form>
    </div>
  );
}
