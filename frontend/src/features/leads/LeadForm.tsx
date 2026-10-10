"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  AlertDialog,
  Button,
  Combobox,
  DatePicker,
  Form,
  Input,
  Select,
  toast,
} from "@/design-system/components";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import type {
  AssigneeWire,
  CourseWire,
  DuplicateCandidateWire,
  LeadSource,
  LeadWire,
} from "@/lib/api/admissions";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";
import { MemberPicker } from "../shared/MemberPicker";

import { DuplicateWarning } from "./DuplicateWarning";
import {
  LEAD_ASSIGN,
  LEADS_PATH,
  leadPath,
  options,
  SOURCE_LABEL,
} from "./labels";

// Lead create / edit (Phase 02-1; blueprint §7-§8, §21, §24). Contact fields
// first; a mobile number or an email is required. The course list holds
// ACTIVE courses (plus the lead's current course when editing, marked if no
// longer active). Campus and owner are chosen on create only; afterwards they
// change through "Assign…". Owner: "Me" or "Unassigned", or any eligible
// member with lead.assign. The duplicate check runs when a contact field
// loses focus; it only warns. Server field codes map to fixed copy.

const POOL = "pool";
const ME = "me";
const NONE = "none";
const MOBILE = /^[0-9+\-() ]+$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

type Values = {
  fullName: string;
  mobile: string;
  email: string;
  source: LeadSource | null;
  courseId: string | null;
  campus: string;
  owner: string | null;
  dateOfBirth: string | null;
  city: string;
  qualification: string;
};
type Field = keyof Values;
type Errors = Partial<Record<Field, string>>;

const SERVER: Record<string, Record<string, [Field, string]>> = {
  full_name: { "*": ["fullName", "Enter the enquirer's name."] },
  mobile: {
    contact_required: ["mobile", "Enter a mobile number or an email."],
    "*": ["mobile", "Enter a valid mobile number."],
  },
  email: { "*": ["email", "Enter a valid email address."] },
  interested_course_id: {
    "*": [
      "courseId",
      "This course is no longer active. Choose an active course.",
    ],
  },
  campus_id: {
    "*": ["campus", "Choose one of your campuses, or institute-wide."],
  },
  owner: {
    "*": [
      "owner",
      "This team member doesn't work with the chosen campus or can't take leads.",
    ],
  },
  date_of_birth: { "*": ["dateOfBirth", "Enter a date in the past."] },
  city: { "*": ["city", "Use at most 120 characters."] },
  highest_qualification: {
    "*": ["qualification", "Use at most 200 characters."],
  },
};

function digits(value: string) {
  return value.replace(/\D/g, "").length;
}

export function validateLead(values: Values, today: string): Errors {
  const errors: Errors = {};
  if (!values.fullName.trim()) errors.fullName = "Enter the enquirer's name.";
  const mobile = values.mobile.trim();
  const email = values.email.trim();
  if (!mobile && !email) errors.mobile = "Enter a mobile number or an email.";
  if (
    mobile &&
    (!MOBILE.test(mobile) || digits(mobile) < 6 || digits(mobile) > 15)
  ) {
    errors.mobile = "Enter a valid mobile number.";
  }
  if (email && !EMAIL.test(email))
    errors.email = "Enter a valid email address.";
  if (!values.source) errors.source = "Choose where the enquiry came from.";
  if (values.dateOfBirth && values.dateOfBirth >= today) {
    errors.dateOfBirth = "Enter a date in the past.";
  }
  return errors;
}

function initial(lead?: LeadWire): Values {
  return {
    fullName: lead?.full_name ?? "",
    mobile: lead?.mobile ?? "",
    email: lead?.email ?? "",
    source: lead?.source ?? null,
    courseId: lead?.interested_course?.id ?? null,
    campus: POOL,
    owner: ME,
    dateOfBirth: lead?.date_of_birth ?? null,
    city: lead?.city ?? "",
    qualification: lead?.highest_qualification ?? "",
  };
}

function profile(values: Values) {
  return {
    full_name: values.fullName.trim(),
    mobile: values.mobile.trim() || null,
    email: values.email.trim() || null,
    source: values.source,
    interested_course_id: values.courseId,
    date_of_birth: values.dateOfBirth,
    city: values.city.trim() || null,
    highest_qualification: values.qualification.trim() || null,
  };
}

function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function LeadForm({
  lead,
  courses,
}: {
  lead?: LeadWire;
  courses: CourseWire[];
}) {
  const creating = lead === undefined;
  const router = useRouter();
  const { session, can, request } = useTenantSession();
  const wrapper = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Values>(() => initial(lead));
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const [candidates, setCandidates] = useState<DuplicateCandidateWire[]>([]);
  const [confirming, setConfirming] = useState(false);
  const checked = useRef("");
  const found = useRef<DuplicateCandidateWire[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const update = <K extends Field>(field: K, value: Values[K]) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({
      ...current,
      [field]: undefined,
      ...(field === "email" || field === "mobile" ? { mobile: undefined } : {}),
    }));
  };

  /** POST /leads/duplicate-check (never a gate: failures show nothing). */
  const runCheck = async (
    current: Values,
  ): Promise<DuplicateCandidateWire[]> => {
    const mobile = current.mobile.trim();
    const email = current.email.trim();
    const key = `${mobile}|${email}`;
    if (key === checked.current) return found.current;
    checked.current = key;
    const show = (items: DuplicateCandidateWire[]) => {
      found.current = items;
      setCandidates(items);
      return items;
    };
    if (!mobile && !email) return show([]);
    try {
      const result = await request<{ candidates: DuplicateCandidateWire[] }>(
        "/leads/duplicate-check",
        {
          method: "POST",
          body: {
            mobile: mobile || null,
            email: email || null,
            exclude_lead_id: lead?.id ?? null,
          },
        },
      );
      return show(result.candidates);
    } catch {
      return show([]);
    }
  };
  const scheduleCheck = () => {
    if (timer.current) clearTimeout(timer.current);
    const snapshot = values;
    timer.current = setTimeout(() => void runCheck(snapshot), 400);
  };

  const save = async () => {
    setPending(true);
    setFeedback(null);
    try {
      const saved = creating
        ? await request<LeadWire>("/leads", {
            method: "POST",
            body: {
              ...profile(values),
              campus_id: values.campus === POOL ? null : values.campus,
              owner: values.owner === null ? null : values.owner,
            },
          })
        : await request<LeadWire>(`/leads/${lead.id}`, {
            method: "PATCH",
            body: { ...profile(values), version: lead.version },
          });
      toast.success(creating ? "Lead created" : "Lead saved");
      router.push(leadPath(saved.id));
      router.refresh();
    } catch (error) {
      setPending(false);
      const fields = fieldCodes(error);
      const mapped: Errors = {};
      for (const [field, code] of Object.entries(fields)) {
        const rule = SERVER[field]?.[code] ?? SERVER[field]?.["*"];
        if (rule) mapped[rule[0]] = rule[1];
      }
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
        focusFirstInvalid(wrapper.current);
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

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const problems = validateLead(values, todayIso());
    setErrors(problems);
    if (Object.keys(problems).length > 0) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    const duplicates = await runCheck(values);
    if (creating && duplicates.length > 0) {
      setConfirming(true);
      return;
    }
    await save();
  };

  const courseOptions = [
    ...courses
      .filter((c) => c.status === "ACTIVE")
      .map((c) => ({ id: c.id, label: `${c.code} · ${c.name}` })),
    ...(lead?.interested_course && lead.interested_course.status !== "ACTIVE"
      ? [
          {
            id: lead.interested_course.id,
            label: `${lead.interested_course.code} · ${lead.interested_course.name} (no longer active)`,
          },
        ]
      : []),
  ];
  const campusParam = values.campus === POOL ? "none" : values.campus;

  return (
    <div ref={wrapper}>
      <Form
        aria-label={creating ? "Create lead" : "Edit lead"}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection
          title="Contact"
          description="Enter a mobile number, an email, or both."
        >
          <FormGrid>
            <FormCell span="full">
              <Input
                label="Full name"
                value={values.fullName}
                onChange={(value) => update("fullName", value)}
                maxLength={200}
                autoComplete="off"
                isRequired
                isInvalid={Boolean(errors.fullName)}
                errorMessage={errors.fullName}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Mobile"
                type="tel"
                value={values.mobile}
                onChange={(value) => update("mobile", value)}
                onBlur={scheduleCheck}
                maxLength={32}
                autoComplete="off"
                description="With or without +91."
                isInvalid={Boolean(errors.mobile)}
                errorMessage={errors.mobile}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Email"
                type="email"
                value={values.email}
                onChange={(value) => update("email", value)}
                onBlur={scheduleCheck}
                maxLength={254}
                autoCapitalize="none"
                autoComplete="off"
                isInvalid={Boolean(errors.email)}
                errorMessage={errors.email}
              />
            </FormCell>
            <FormCell span="full">
              <DuplicateWarning candidates={candidates} />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormSection title="Enquiry">
          <FormGrid>
            <FormCell>
              <Select
                label="Source"
                options={options(SOURCE_LABEL)}
                value={values.source}
                onChange={(value) =>
                  update("source", value as LeadSource | null)
                }
                isRequired
                isInvalid={Boolean(errors.source)}
                errorMessage={errors.source}
              />
            </FormCell>
            <FormCell>
              <Combobox
                label="Interested course"
                options={courseOptions}
                value={values.courseId}
                onChange={(value) => update("courseId", value)}
                emptyMessage="No active course matches"
                description={
                  courses.length === 0 ? "No active courses yet." : undefined
                }
                isInvalid={Boolean(errors.courseId)}
                errorMessage={errors.courseId}
              />
            </FormCell>
            {creating && (
              <FormCell>
                <Select
                  label="Campus"
                  options={[
                    { id: POOL, label: "Institute-wide (all campuses)" },
                    ...session.campusOptions.map((c) => ({
                      id: c.id,
                      label: c.name,
                    })),
                  ]}
                  value={values.campus}
                  onChange={(value) => {
                    update("campus", value ?? POOL);
                    if (can(LEAD_ASSIGN) && values.owner !== ME)
                      update("owner", null);
                  }}
                  description="Institute-wide enquiries are visible to every campus."
                  isInvalid={Boolean(errors.campus)}
                  errorMessage={errors.campus}
                />
              </FormCell>
            )}
            {creating && (
              <FormCell>
                {can(LEAD_ASSIGN) ? (
                  <MemberPicker
                    label="Owner"
                    allowUnassigned
                    loadKey={campusParam}
                    load={async () => [
                      { id: ME, label: "Me" },
                      ...(
                        await request<{ items: AssigneeWire[] }>(
                          `/leads/assignees?campus_id=${encodeURIComponent(campusParam)}`,
                        )
                      ).items.map((m) => ({
                        id: m.membership_id,
                        label: m.display_name,
                      })),
                    ]}
                    value={values.owner}
                    onChange={(value) => update("owner", value)}
                    errorMessage={errors.owner}
                  />
                ) : (
                  <Select
                    label="Owner"
                    options={[
                      { id: ME, label: "Me" },
                      { id: NONE, label: "Unassigned" },
                    ]}
                    value={values.owner ?? NONE}
                    onChange={(value) =>
                      update("owner", value === NONE ? null : value)
                    }
                    isInvalid={Boolean(errors.owner)}
                    errorMessage={errors.owner}
                  />
                )}
              </FormCell>
            )}
          </FormGrid>
        </FormSection>
        <FormSection
          title="More about the enquirer"
          description="Optional. Helps counselling and carries over to the application."
        >
          <FormGrid>
            <FormCell>
              <DatePicker
                label="Date of birth"
                value={values.dateOfBirth}
                onChange={(value) => update("dateOfBirth", value)}
                maxValue={todayIso()}
                isInvalid={Boolean(errors.dateOfBirth)}
                errorMessage={errors.dateOfBirth}
              />
            </FormCell>
            <FormCell>
              <Input
                label="City"
                value={values.city}
                onChange={(value) => update("city", value)}
                maxLength={120}
                isInvalid={Boolean(errors.city)}
                errorMessage={errors.city}
              />
            </FormCell>
            <FormCell span="full">
              <Input
                label="Highest qualification"
                value={values.qualification}
                onChange={(value) => update("qualification", value)}
                maxLength={200}
                description="For example: 12th PCM, 68%."
                isInvalid={Boolean(errors.qualification)}
                errorMessage={errors.qualification}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button
            variant="secondary"
            href={creating ? LEADS_PATH : leadPath(lead.id)}
            isDisabled={pending}
          >
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {creating ? "Create lead" : "Save changes"}
          </Button>
        </FormActions>
      </Form>
      <AlertDialog
        isOpen={confirming}
        onOpenChange={setConfirming}
        title="Create anyway?"
        description="A lead you can see has the same mobile number or email. It may be the same person."
        confirmLabel="Create lead"
        cancelLabel="Cancel"
        onConfirm={() => {
          setConfirming(false);
          void save();
        }}
      >
        <DuplicateWarning candidates={candidates} />
      </AlertDialog>
    </div>
  );
}
