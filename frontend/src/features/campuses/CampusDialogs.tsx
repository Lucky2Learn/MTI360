"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Dialog,
  Form,
  Input,
  toast,
} from "@/design-system/components";
import { AddIcon, EditIcon } from "@/design-system/icons";
import { ApiError } from "@/lib/api/errors";
import type { TenantCampusWire } from "@/lib/api/tenant-admin";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import {
  CAMPUS_CREATE,
  CAMPUS_UPDATE,
  CODE_MAX,
  CODE_MESSAGE,
  CODE_TAKEN,
  codeError,
  NAME_MAX,
  NAME_MESSAGE,
  nameError,
  normalizeCode,
} from "./labels";

// Add campus (ADMIN-03; POST /campuses, campus.create, institute-wide) and
// Rename campus (ADMIN-04; PATCH /campuses/{id}, campus.update, with the
// campus version). The code is set once, uppercase, and never changes
// (INC-41): the rename form has no code field. Server authoritative: the
// page re-renders from the server after the API answers.
//
// Refusals: 422 → field errors; 409 on add → the code is taken (the dialog
// stays open); 409 on rename → changed in the meantime (warning, latest
// data); 404 on rename → no longer visible (the page re-renders as not
// found); 403 → an Alert in the dialog. Server messages are never shown.

type Errors = Partial<Record<"name" | "code", string>>;

const FALLBACK: FormFeedback = {
  tone: "error",
  title: "Something went wrong",
  body: "Something went wrong. Try again in a moment.",
};

function deniedFeedback(action: string): FormFeedback {
  return {
    tone: "error",
    title: `You can't ${action}`,
    body: "Your access changed, or this campus is outside your campuses. Ask an administrator.",
  };
}

function Actions({
  onCancel,
  pending,
  submitLabel,
}: {
  onCancel: () => void;
  pending: boolean;
  submitLabel: string;
}) {
  return (
    <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
      <Button variant="secondary" onPress={onCancel} isDisabled={pending}>
        Cancel
      </Button>
      <Button type="submit" isPending={pending}>
        {submitLabel}
      </Button>
    </div>
  );
}

// --- Add campus -------------------------------------------------------------------

export function AddCampusButton() {
  const { can } = useTenantSession();
  const [open, setOpen] = useState(false);
  if (!can(CAMPUS_CREATE)) return null;
  return (
    <>
      <Button iconStart={AddIcon} onPress={() => setOpen(true)}>
        Add campus
      </Button>
      {open && (
        <Dialog
          isOpen
          onOpenChange={setOpen}
          title="Add campus"
          description="Members with access to all campuses can work with it straight away."
        >
          {(close) => <AddCampusForm onDone={close} />}
        </Dialog>
      )}
    </>
  );
}

function AddCampusForm({ onDone }: { onDone: () => void }) {
  const router = useRouter();
  const { request } = useTenantSession();
  const wrapper = useRef<HTMLDivElement>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found: Errors = { name: nameError(name), code: codeError(code) };
    setErrors(found);
    setFeedback(null);
    if (found.name || found.code) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    try {
      const created = await request<TenantCampusWire>("/campuses", {
        method: "POST",
        body: { name: name.trim(), code: normalizeCode(code) },
      });
      toast.success(`${created.name} (${created.code}) added.`);
      router.refresh();
      onDone();
    } catch (error) {
      setPending(false);
      const fields = fieldCodes(error);
      const mapped: Errors = {};
      if (fields.name) mapped.name = NAME_MESSAGE;
      if (fields.code) mapped.code = CODE_MESSAGE;
      if (error instanceof ApiError && error.code === "CONFLICT") {
        mapped.code = CODE_TAKEN;
      }
      if (mapped.name || mapped.code) {
        setErrors(mapped);
        focusFirstInvalid(wrapper.current);
        return;
      }
      if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
        setFeedback(deniedFeedback("add campuses"));
        return;
      }
      setFeedback(formFeedback(error) ?? FALLBACK);
    }
  };

  return (
    <div ref={wrapper}>
      <Form
        aria-label="Add campus"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Input
          label="Campus name"
          value={name}
          onChange={(value) => {
            setName(value);
            setErrors((current) => ({ ...current, name: undefined }));
          }}
          autoComplete="off"
          maxLength={NAME_MAX}
          isRequired
          isInvalid={Boolean(errors.name)}
          errorMessage={errors.name}
        />
        <Input
          label="Campus code"
          value={code}
          onChange={(value) => {
            setCode(value.toUpperCase());
            setErrors((current) => ({ ...current, code: undefined }));
          }}
          description="A short reference such as KOCHI or VSK-01. It can't be changed later."
          autoComplete="off"
          autoCapitalize="characters"
          maxLength={CODE_MAX}
          isRequired
          isInvalid={Boolean(errors.code)}
          errorMessage={errors.code}
        />
        <Actions onCancel={onDone} pending={pending} submitLabel="Add campus" />
      </Form>
    </div>
  );
}

// --- Rename campus ----------------------------------------------------------------

export function RenameCampusButton({ campus }: { campus: TenantCampusWire }) {
  const { can } = useTenantSession();
  const [open, setOpen] = useState(false);
  if (!can(CAMPUS_UPDATE)) return null;
  return (
    <>
      <Button
        variant="secondary"
        iconStart={EditIcon}
        onPress={() => setOpen(true)}
      >
        Rename
      </Button>
      {open && (
        <Dialog
          isOpen
          onOpenChange={setOpen}
          title="Rename campus"
          description={`The code ${campus.code} stays the same.`}
        >
          {(close) => <RenameCampusForm campus={campus} onDone={close} />}
        </Dialog>
      )}
    </>
  );
}

function RenameCampusForm({
  campus,
  onDone,
}: {
  campus: TenantCampusWire;
  onDone: () => void;
}) {
  const router = useRouter();
  const { request } = useTenantSession();
  const wrapper = useRef<HTMLDivElement>(null);
  const [name, setName] = useState(campus.name);
  const [error, setError] = useState<string | undefined>();
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = nameError(name);
    setError(found);
    setFeedback(null);
    if (found) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    try {
      await request<TenantCampusWire>(`/campuses/${campus.id}`, {
        method: "PATCH",
        body: { name: name.trim(), version: campus.version },
      });
      toast.success("Campus renamed.");
      router.refresh();
      onDone();
    } catch (failure) {
      setPending(false);
      if (fieldCodes(failure).name) {
        setError(NAME_MESSAGE);
        focusFirstInvalid(wrapper.current);
        return;
      }
      if (failure instanceof ApiError && failure.code === "CONFLICT") {
        toast.warning(
          "The campus wasn't renamed. Someone else changed it in the meantime. The latest details are shown.",
        );
        router.refresh();
        onDone();
        return;
      }
      if (failure instanceof ApiError && failure.code === "NOT_FOUND") {
        toast.info("This campus is no longer available to you.");
        router.refresh();
        onDone();
        return;
      }
      if (failure instanceof ApiError && failure.code === "PERMISSION_DENIED") {
        setFeedback(deniedFeedback("rename this campus"));
        return;
      }
      setFeedback(formFeedback(failure) ?? FALLBACK);
    }
  };

  return (
    <div ref={wrapper}>
      <Form
        aria-label="Rename campus"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Input
          label="Campus name"
          value={name}
          onChange={(value) => {
            setName(value);
            setError(undefined);
          }}
          autoComplete="off"
          maxLength={NAME_MAX}
          isRequired
          isInvalid={Boolean(error)}
          errorMessage={error}
        />
        <Actions onCancel={onDone} pending={pending} submitLabel="Save name" />
      </Form>
    </div>
  );
}
