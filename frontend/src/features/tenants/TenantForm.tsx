"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import { Alert, Button, Form, Input, toast } from "@/design-system/components";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import { ApiError } from "@/lib/api/errors";
import type { ProvisionedTenantWire } from "@/lib/api/platform-tenants";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import { TENANTS_PATH, tenantPath } from "./labels";

// PLAT-06 Create tenant (POST /platform/tenants, tenant.create). Provisioning
// creates the institute in TRIAL, its primary campus, the system roles and
// an invitation for its administrator, whose email is sent after the
// response. Client checks mirror the API (name ≤ 200, campus code format,
// email) for quick feedback; the API validates again and its field paths map
// to the same copy. Server messages are never shown.

const CODE_FORMAT = /^[A-Z0-9][A-Z0-9-]*$/;
const EMAIL_FORMAT = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NAME_MAX = 200;
const EMAIL_MAX = 254;

type Values = {
  name: string;
  campusName: string;
  campusCode: string;
  ownerName: string;
  ownerEmail: string;
};

type Field = keyof Values;
type Errors = Partial<Record<Field, string>>;

const NAME_MESSAGE = "Enter a name of up to 200 characters.";
const CODE_MESSAGE =
  "Use up to 32 letters, digits or hyphens, starting with a letter or digit.";
const EMAIL_MESSAGE = "Enter an email address like name@institute.edu.";

/** API field path → form field and copy (422 details). */
const SERVER_FIELDS: Record<string, [Field, string]> = {
  name: ["name", NAME_MESSAGE],
  "campus.name": ["campusName", NAME_MESSAGE],
  "campus.code": ["campusCode", CODE_MESSAGE],
  "owner.display_name": ["ownerName", NAME_MESSAGE],
  "owner.email": ["ownerEmail", EMAIL_MESSAGE],
};

const EMPTY: Values = {
  name: "",
  campusName: "",
  campusCode: "",
  ownerName: "",
  ownerEmail: "",
};

function nameError(value: string, missing: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return missing;
  return trimmed.length > NAME_MAX ? NAME_MESSAGE : undefined;
}

export function validateTenant(values: Values): Errors {
  const errors: Errors = {
    name: nameError(values.name, "Enter the institute's name."),
    campusName: nameError(values.campusName, "Enter the primary campus name."),
    ownerName: nameError(values.ownerName, "Enter the administrator's name."),
  };
  const code = values.campusCode.trim().toUpperCase();
  if (!code || code.length > 32 || !CODE_FORMAT.test(code)) {
    errors.campusCode = CODE_MESSAGE;
  }
  const email = values.ownerEmail.trim();
  if (!email || email.length > EMAIL_MAX || !EMAIL_FORMAT.test(email)) {
    errors.ownerEmail = EMAIL_MESSAGE;
  }
  for (const field of Object.keys(errors) as Field[]) {
    if (errors[field] === undefined) delete errors[field];
  }
  return errors;
}

export function TenantForm() {
  const router = useRouter();
  const { request } = usePlatformSession();
  const formRef = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const update = (field: Field, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = validateTenant(values);
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    try {
      const created = await request<ProvisionedTenantWire>("/tenants", {
        method: "POST",
        body: {
          name: values.name.trim(),
          campus: {
            name: values.campusName.trim(),
            code: values.campusCode.trim().toUpperCase(),
          },
          owner: {
            display_name: values.ownerName.trim(),
            email: values.ownerEmail.trim(),
          },
        },
      });
      // The API emails the invitation after it answers: say it is being sent,
      // never that it arrived.
      toast.success(
        created.owner_account === "existing"
          ? "Tenant created. The administrator's existing account is being emailed an invitation."
          : "Tenant created. The invitation is being emailed to the administrator.",
      );
      router.push(tenantPath(created.tenant.id));
      router.refresh();
    } catch (error) {
      setPending(false);
      const fields = fieldCodes(error);
      const mapped: Errors = {};
      for (const field of Object.keys(fields)) {
        const known = SERVER_FIELDS[field];
        if (known) mapped[known[0]] = known[1];
      }
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
        focusFirstInvalid(formRef.current);
        return;
      }
      if (error instanceof ApiError && error.code === "CONFLICT") {
        setFeedback({
          tone: "error",
          title: "The tenant wasn't created",
          body: "The administrator's email may belong to a disabled account. Use another email, or try again in a moment.",
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
    <div ref={formRef}>
      <Form
        aria-label="Create tenant"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection
          title="Institute"
          description="The institute starts in Trial with one primary campus."
        >
          <FormGrid>
            <FormCell span="full">
              <Input
                label="Institute name"
                value={values.name}
                onChange={(value) => update("name", value)}
                description="For example: Konkan Maritime Training Institute."
                maxLength={NAME_MAX}
                isRequired
                isInvalid={Boolean(errors.name)}
                errorMessage={errors.name}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Primary campus name"
                value={values.campusName}
                onChange={(value) => update("campusName", value)}
                maxLength={NAME_MAX}
                isRequired
                isInvalid={Boolean(errors.campusName)}
                errorMessage={errors.campusName}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Campus code"
                value={values.campusCode}
                onChange={(value) => update("campusCode", value)}
                description="Short code staff use, e.g. MUM. It can't be changed later."
                autoCapitalize="characters"
                maxLength={32}
                isRequired
                isInvalid={Boolean(errors.campusCode)}
                errorMessage={errors.campusCode}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormSection
          title="Administrator"
          description="This person becomes the institute owner and receives an invitation by email. An existing account is invited without being changed."
        >
          <FormGrid>
            <FormCell>
              <Input
                label="Full name"
                value={values.ownerName}
                onChange={(value) => update("ownerName", value)}
                autoComplete="off"
                maxLength={NAME_MAX}
                isRequired
                isInvalid={Boolean(errors.ownerName)}
                errorMessage={errors.ownerName}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Email"
                type="email"
                value={values.ownerEmail}
                onChange={(value) => update("ownerEmail", value)}
                autoComplete="off"
                maxLength={EMAIL_MAX}
                isRequired
                isInvalid={Boolean(errors.ownerEmail)}
                errorMessage={errors.ownerEmail}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button variant="secondary" href={TENANTS_PATH} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Create tenant
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
