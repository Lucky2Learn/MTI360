"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Form,
  Input,
  Select,
  Textarea,
} from "@/design-system/components";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import type {
  ApplicationWire,
  CourseWire,
  SubmitRequirement,
} from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";
import { focusFirstInvalid } from "../shared/forms";

import {
  applicationPath,
  applicationStepPath,
  REQUIREMENT_LABEL,
} from "./labels";
import { useRecordMutation } from "./mutations";

// ADM-07 application wizard (Phase 02-2; APP-FLOW §16, ADR-0021 §3). Each step
// saves only its changed fields (PATCH with the loaded version) and moves on,
// so a draft can be left and resumed at any step. The last step shows what is
// still missing and submits. The server validates every field again; its codes
// map to fixed copy here, and its messages are never shown.

export type WizardStepId =
  "course" | "personal" | "contact" | "education" | "declaration" | "review";

export const WIZARD_STEPS: { id: WizardStepId; label: string }[] = [
  { id: "course", label: "Course and campus" },
  { id: "personal", label: "Personal details" },
  { id: "contact", label: "Contact" },
  { id: "education", label: "Education" },
  { id: "declaration", label: "Declaration" },
  { id: "review", label: "Review and submit" },
];

/** Whether a step's required information is complete (for the step list). */
export function stepComplete(
  step: WizardStepId,
  application: ApplicationWire,
): boolean {
  switch (step) {
    case "course":
      return true;
    case "personal":
      return Boolean(application.full_name && application.date_of_birth);
    case "contact":
      return Boolean(application.mobile || application.email);
    case "education":
      return Boolean(application.highest_qualification);
    case "declaration":
      return application.declared_at !== null;
    case "review":
      return false;
  }
}

type FieldKind = "text" | "tel" | "email" | "textarea" | "date";
type TextField =
  | "full_name"
  | "date_of_birth"
  | "mobile"
  | "email"
  | "address"
  | "city"
  | "state"
  | "postal_code"
  | "highest_qualification"
  | "education_details"
  | "indos_number"
  | "cdc_number"
  | "eligibility_notes";

type FieldDef = {
  name: TextField;
  label: string;
  kind: FieldKind;
  maxLength: number;
  description?: string;
  full?: boolean;
  required?: boolean;
};

const FIELDS: Partial<Record<WizardStepId, FieldDef[]>> = {
  personal: [
    {
      name: "full_name",
      label: "Full name",
      kind: "text",
      maxLength: 200,
      full: true,
      required: true,
    },
    {
      name: "date_of_birth",
      label: "Date of birth",
      kind: "date",
      maxLength: 10,
      description: "Age matters for Pre-Sea eligibility.",
    },
  ],
  contact: [
    { name: "mobile", label: "Mobile", kind: "tel", maxLength: 32 },
    { name: "email", label: "Email", kind: "email", maxLength: 254 },
    {
      name: "address",
      label: "Address",
      kind: "textarea",
      maxLength: 500,
      full: true,
    },
    { name: "city", label: "City", kind: "text", maxLength: 120 },
    { name: "state", label: "State", kind: "text", maxLength: 120 },
    { name: "postal_code", label: "PIN code", kind: "text", maxLength: 16 },
  ],
  education: [
    {
      name: "highest_qualification",
      label: "Highest qualification",
      kind: "text",
      maxLength: 200,
      full: true,
      description: "For example: 12th PCM, 72%.",
    },
    {
      name: "education_details",
      label: "Education details",
      kind: "textarea",
      maxLength: 2000,
      full: true,
      description:
        "Board, year of passing and marks in Physics, Chemistry and Mathematics.",
    },
    {
      name: "indos_number",
      label: "INDoS number",
      kind: "text",
      maxLength: 16,
      description: "If the applicant already has one (Post-Sea courses).",
    },
    { name: "cdc_number", label: "CDC number", kind: "text", maxLength: 32 },
    {
      name: "eligibility_notes",
      label: "Eligibility notes",
      kind: "textarea",
      maxLength: 2000,
      full: true,
      description:
        "Your assessment for the reviewer: age, marks, medical fitness.",
    },
  ],
};

const INVALID: Record<string, string> = {
  full_name: "Enter the applicant's name.",
  date_of_birth: "Enter a date in the past.",
  mobile: "Enter a valid mobile number.",
  email: "Enter a valid email address.",
  postal_code: "Enter a valid PIN code.",
  indos_number: "Enter the INDoS number: 6-16 letters and digits.",
  cdc_number: "Enter the CDC number: letters, digits, / and -.",
  course_id: "Choose an active course.",
  campus_id: "Choose one of your campuses.",
};

function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function stepAfter(step: WizardStepId): WizardStepId {
  const index = WIZARD_STEPS.findIndex((s) => s.id === step);
  return (
    WIZARD_STEPS[Math.min(index + 1, WIZARD_STEPS.length - 1)]?.id ?? "review"
  );
}

function stepBefore(step: WizardStepId): WizardStepId | null {
  const index = WIZARD_STEPS.findIndex((s) => s.id === step);
  return index > 0 ? (WIZARD_STEPS[index - 1]?.id ?? null) : null;
}

export function ApplicationWizardStep({
  application,
  step,
  courses,
}: {
  application: ApplicationWire;
  step: WizardStepId;
  courses: CourseWire[];
}) {
  if (step === "review") return <ReviewStep application={application} />;
  return <EditStep application={application} step={step} courses={courses} />;
}

function EditStep({
  application,
  step,
  courses,
}: {
  application: ApplicationWire;
  step: Exclude<WizardStepId, "review">;
  courses: CourseWire[];
}) {
  const router = useRouter();
  const { session } = useTenantSession();
  const mutate = useRecordMutation("application");
  const formRef = useRef<HTMLDivElement>(null);
  const fields = FIELDS[step] ?? [];
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {
      course_id: application.course.id,
      campus_id: application.campus.id,
    };
    for (const field of fields)
      initial[field.name] = application[field.name] ?? "";
    return initial;
  });
  const [declared, setDeclared] = useState(application.declared_at !== null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const courseOptions = courses.some((c) => c.id === application.course.id)
    ? courses
    : [
        {
          id: application.course.id,
          code: application.course.code,
          name: `${application.course.name} (not active)`,
        },
        ...courses,
      ];

  const update = (name: string, value: string) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: "" }));
  };

  const changes = (): Record<string, unknown> => {
    const body: Record<string, unknown> = {};
    if (step === "course") {
      if (values.course_id !== application.course.id)
        body.course_id = values.course_id;
      if (values.campus_id !== application.campus.id)
        body.campus_id = values.campus_id;
    } else if (step === "declaration") {
      if (declared !== (application.declared_at !== null)) {
        body.declaration_confirmed = declared;
      }
    } else {
      for (const field of fields) {
        const value = (values[field.name] ?? "").trim();
        if (value !== (application[field.name] ?? ""))
          body[field.name] = value || null;
      }
    }
    return body;
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found: Record<string, string> = {};
    for (const field of fields) {
      const value = (values[field.name] ?? "").trim();
      if (field.required && !value)
        found[field.name] = INVALID[field.name] ?? "Required.";
      if (field.kind === "date" && value && value >= today()) {
        found[field.name] = INVALID.date_of_birth ?? "";
      }
    }
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    const body = changes();
    const next = applicationStepPath(application.id, stepAfter(step));
    if (Object.keys(body).length === 0) {
      router.push(next);
      return;
    }
    setPending(true);
    const outcome = await mutate(
      `/applications/${application.id}`,
      { ...body, version: application.version },
      null,
      "PATCH",
    );
    setPending(false);
    if (outcome.kind === "done") {
      router.push(next);
    } else if (outcome.kind === "fields") {
      const mapped: Record<string, string> = {};
      for (const [field, code] of Object.entries(outcome.fields)) {
        mapped[field] =
          code === "application_locked"
            ? "This application can no longer be edited."
            : (INVALID[field] ?? "Check this value.");
      }
      setErrors(mapped);
      focusFirstInvalid(formRef.current);
    } else if (outcome.kind === "feedback") {
      setErrors({ form: outcome.feedback.title });
    }
  };

  const previous = stepBefore(step);
  return (
    <div ref={formRef}>
      <Form
        aria-label={
          WIZARD_STEPS.find((s) => s.id === step)?.label ?? "Application step"
        }
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {errors.form && (
          <Alert tone="error" title={errors.form}>
            Your changes weren&apos;t saved. Try again in a moment.
          </Alert>
        )}
        {errors.status && (
          <Alert
            tone="error"
            title="This application can no longer be edited"
          />
        )}
        {step === "course" && (
          <FormSection
            title="Course and campus"
            description="Only active courses can be chosen. The campus decides who can see the application."
          >
            <FormGrid>
              <FormCell>
                <Select
                  label="Course"
                  options={courseOptions.map((c) => ({
                    id: c.id,
                    label: `${c.code} · ${c.name}`,
                  }))}
                  value={values.course_id ?? null}
                  onChange={(value) => value && update("course_id", value)}
                  isRequired
                  isInvalid={Boolean(errors.course_id)}
                  errorMessage={errors.course_id}
                />
              </FormCell>
              <FormCell>
                <Select
                  label="Campus"
                  options={[
                    ...(session.campusOptions.some(
                      (c) => c.id === application.campus.id,
                    )
                      ? []
                      : [
                          {
                            id: application.campus.id,
                            label: application.campus.name,
                          },
                        ]),
                    ...session.campusOptions.map((c) => ({
                      id: c.id,
                      label: c.name,
                    })),
                  ]}
                  value={values.campus_id ?? null}
                  onChange={(value) => value && update("campus_id", value)}
                  isRequired
                  isInvalid={Boolean(errors.campus_id)}
                  errorMessage={errors.campus_id}
                />
              </FormCell>
            </FormGrid>
          </FormSection>
        )}
        {fields.length > 0 && (
          <FormSection
            title={WIZARD_STEPS.find((s) => s.id === step)?.label ?? ""}
          >
            <FormGrid>
              {fields.map((field) => (
                <FormCell key={field.name} span={field.full ? "full" : "half"}>
                  {field.kind === "date" ? (
                    <DatePicker
                      label={field.label}
                      value={values[field.name] || null}
                      onChange={(iso) => update(field.name, iso ?? "")}
                      maxValue={today()}
                      description={field.description}
                      isInvalid={Boolean(errors[field.name])}
                      errorMessage={errors[field.name]}
                    />
                  ) : field.kind === "textarea" ? (
                    <Textarea
                      label={field.label}
                      value={values[field.name] ?? ""}
                      onChange={(value) => update(field.name, value)}
                      description={field.description}
                      maxLength={field.maxLength}
                      showCount
                      isInvalid={Boolean(errors[field.name])}
                      errorMessage={errors[field.name]}
                    />
                  ) : (
                    <Input
                      label={field.label}
                      type={field.kind}
                      value={values[field.name] ?? ""}
                      onChange={(value) => update(field.name, value)}
                      description={field.description}
                      autoComplete="off"
                      maxLength={field.maxLength}
                      isRequired={field.required}
                      isInvalid={Boolean(errors[field.name])}
                      errorMessage={errors[field.name]}
                    />
                  )}
                </FormCell>
              ))}
            </FormGrid>
          </FormSection>
        )}
        {step === "declaration" && (
          <FormSection
            title="Declaration"
            description="Read the declaration to the applicant. Confirm only when they agree; your name and the time are recorded."
          >
            <p className="text-body-sm text-text-primary">
              I declare that the information in this application and the
              documents provided are true and complete, and I understand that
              admission may be cancelled if any of it is found to be false.
            </p>
            <Checkbox isSelected={declared} onChange={setDeclared}>
              The applicant has confirmed the declaration
            </Checkbox>
            {application.declared_at && application.declared_by && (
              <p className="text-caption text-text-secondary">
                {`Confirmed by ${application.declared_by.display_name} on ${formatDate(application.declared_at)}.`}
              </p>
            )}
          </FormSection>
        )}
        <FormActions>
          {previous ? (
            <Button
              variant="secondary"
              href={applicationStepPath(application.id, previous)}
              isDisabled={pending}
            >
              Back
            </Button>
          ) : (
            <Button
              variant="secondary"
              href={applicationPath(application.id)}
              isDisabled={pending}
            >
              Save later
            </Button>
          )}
          <Button type="submit" isPending={pending}>
            Save and continue
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}

function ReviewStep({ application }: { application: ApplicationWire }) {
  const router = useRouter();
  const mutate = useRecordMutation("application");
  const [pending, setPending] = useState(false);
  const [missing, setMissing] = useState<SubmitRequirement[]>(
    application.missing_for_submit,
  );
  const [problem, setProblem] = useState<string | null>(null);
  const rows: [string, string | null][] = [
    ["Course", `${application.course.code} · ${application.course.name}`],
    ["Campus", application.campus.name],
    ["Name", application.full_name],
    [
      "Date of birth",
      application.date_of_birth ? formatDate(application.date_of_birth) : null,
    ],
    ["Mobile", application.mobile],
    ["Email", application.email],
    ["City", application.city],
    ["Highest qualification", application.highest_qualification],
    ["INDoS number", application.indos_number],
    ["Documents", `${application.documents.total} uploaded`],
  ];

  const submit = async () => {
    setPending(true);
    setProblem(null);
    const outcome = await mutate(
      `/applications/${application.id}/submit`,
      { version: application.version },
      `Application ${application.number} submitted`,
    );
    setPending(false);
    if (outcome.kind === "done") {
      router.push(applicationPath(application.id));
    } else if (outcome.kind === "fields") {
      const fields = Object.keys(outcome.fields);
      const requirements = fields.filter(
        (f): f is SubmitRequirement => f in REQUIREMENT_LABEL,
      );
      setMissing(requirements);
      if (fields.includes("course_id")) {
        setProblem(
          "The course is no longer active. Choose another course first.",
        );
      }
    } else if (outcome.kind === "feedback") {
      setProblem(outcome.feedback.title);
    }
  };

  return (
    <div className="flex min-w-0 flex-col gap-6">
      {missing.length > 0 ? (
        <Alert tone="warning" title="Complete these before submitting">
          <ul className="list-disc pl-5">
            {missing.map((item) => (
              <li key={item}>{REQUIREMENT_LABEL[item]}</li>
            ))}
          </ul>
        </Alert>
      ) : (
        <Alert tone="success" title="Ready to submit">
          Submitting sends the application for review. Documents uploaded so far
          go to verification.
        </Alert>
      )}
      {problem && <Alert tone="error" title={problem} />}
      <dl className="flex flex-col gap-3">
        {rows.map(([term, value]) => (
          <div
            key={term}
            className="flex flex-col gap-1 tablet:flex-row tablet:gap-6"
          >
            <dt className="text-body-sm text-text-secondary tablet:w-48 tablet:shrink-0">
              {term}
            </dt>
            <dd className="min-w-0 text-body-sm break-words text-text-primary">
              {value ?? "Not given"}
            </dd>
          </div>
        ))}
      </dl>
      <FormActions>
        <Button
          variant="secondary"
          href={applicationStepPath(application.id, "declaration")}
          isDisabled={pending}
        >
          Back
        </Button>
        <Button
          onPress={() => void submit()}
          isPending={pending}
          isDisabled={missing.length > 0}
        >
          Submit application
        </Button>
      </FormActions>
    </div>
  );
}
