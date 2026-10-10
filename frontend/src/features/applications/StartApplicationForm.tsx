"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
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
  ApplicationWire,
  CourseWire,
  LeadWire,
} from "@/lib/api/admissions";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { leadPath } from "../leads/labels";
import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import { APPLICATIONS_PATH, applicationStepPath } from "./labels";
import { FALLBACK } from "./mutations";

// ADM-07 New application, step 1 (Phase 02-2; ADR-0021 §3, Y1): the course
// and campus are chosen first (prefilled from the lead), because they decide
// who may see and work the application. From a lead, the server copies the
// lead's details into the application; a direct (walk-in) application needs
// a name and a contact. The draft is created, then the wizard continues.

type Values = {
  course: string | null;
  campus: string | null;
  fullName: string;
  mobile: string;
  email: string;
};
type Errors = Partial<Record<keyof Values | "lead", string>>;

const SERVER_FIELDS: Record<string, Record<string, [keyof Errors, string]>> = {
  course_id: {
    course_not_active: ["course", "Choose an active course."],
    application_exists: [
      "course",
      "This lead already has an open application for this course.",
    ],
  },
  campus_id: {
    campus_not_available: ["campus", "Choose one of your campuses."],
  },
  lead_id: {
    lead_not_available: ["lead", "This lead is no longer available to you."],
    lead_closed: ["lead", "Reopen the lead before starting an application."],
  },
  full_name: { required: ["fullName", "Enter the applicant's name."] },
  mobile: { invalid: ["mobile", "Enter a valid mobile number."] },
  email: { invalid: ["email", "Enter a valid email address."] },
};

export function StartApplicationForm({
  courses,
  lead,
}: {
  courses: CourseWire[];
  lead: LeadWire | null;
}) {
  const router = useRouter();
  const { session, request } = useTenantSession();
  const formRef = useRef<HTMLDivElement>(null);
  const campuses = session.campusOptions;
  const leadCourse = lead?.interested_course;
  const [values, setValues] = useState<Values>(() => ({
    course:
      leadCourse && courses.some((c) => c.id === leadCourse.id)
        ? leadCourse.id
        : null,
    campus:
      (lead?.campus && campuses.some((c) => c.id === lead.campus?.id)
        ? lead.campus.id
        : null) ??
      session.activeCampus?.id ??
      (campuses.length === 1 ? (campuses[0]?.id ?? null) : null),
    fullName: "",
    mobile: "",
    email: "",
  }));
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const update = <K extends keyof Values>(field: K, value: Values[K]) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found: Errors = {};
    if (!values.course) found.course = "Choose the course.";
    if (!values.campus) found.campus = "Choose the campus.";
    if (!lead) {
      if (!values.fullName.trim())
        found.fullName = "Enter the applicant's name.";
      if (!values.mobile.trim() && !values.email.trim())
        found.mobile = "Enter a mobile number or an email.";
    }
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    try {
      const body: Record<string, string> = {
        course_id: values.course ?? "",
        campus_id: values.campus ?? "",
      };
      if (lead) {
        body.lead_id = lead.id;
      } else {
        body.full_name = values.fullName.trim();
        if (values.mobile.trim()) body.mobile = values.mobile.trim();
        if (values.email.trim()) body.email = values.email.trim();
      }
      const created = await request<ApplicationWire>("/applications", {
        method: "POST",
        body,
      });
      toast.success(`Application ${created.number} started`);
      router.push(applicationStepPath(created.id, "personal"));
    } catch (error) {
      setPending(false);
      const codes = fieldCodes(error);
      const mapped: Errors = {};
      for (const [field, code] of Object.entries(codes)) {
        const known = SERVER_FIELDS[field]?.[code];
        if (known) mapped[known[0]] = known[1];
      }
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
        focusFirstInvalid(formRef.current);
        return;
      }
      setFeedback(formFeedback(error) ?? FALLBACK);
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Start application"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        {errors.lead && (
          <Alert
            tone="error"
            title="This application can't start from the lead"
          >
            {errors.lead}
          </Alert>
        )}
        {lead && (
          <Alert tone="info" title={`From lead: ${lead.full_name}`}>
            {
              "The lead's contact and education details are copied into the application. You can change them in the next steps."
            }
          </Alert>
        )}
        <FormSection title="Course and campus">
          <FormGrid>
            <FormCell>
              <Select
                label="Course"
                options={courses.map((c) => ({
                  id: c.id,
                  label: `${c.code} · ${c.name}`,
                }))}
                value={values.course}
                onChange={(value) => update("course", value)}
                description={
                  courses.length === 0
                    ? "No active courses yet. A manager activates courses in Academics."
                    : undefined
                }
                isRequired
                isInvalid={Boolean(errors.course)}
                errorMessage={errors.course}
              />
            </FormCell>
            <FormCell>
              <Select
                label="Campus"
                options={campuses.map((c) => ({ id: c.id, label: c.name }))}
                value={values.campus}
                onChange={(value) => update("campus", value)}
                description="The campus the applicant will attend. It decides who can see the application."
                isRequired
                isInvalid={Boolean(errors.campus)}
                errorMessage={errors.campus}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        {!lead && (
          <FormSection
            title="Applicant"
            description="For a walk-in applicant without a lead. Enter a mobile number, an email or both."
          >
            <FormGrid>
              <FormCell span="full">
                <Input
                  label="Full name"
                  value={values.fullName}
                  onChange={(value) => update("fullName", value)}
                  autoComplete="off"
                  maxLength={200}
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
                  autoComplete="off"
                  maxLength={32}
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
                  autoComplete="off"
                  maxLength={254}
                  isInvalid={Boolean(errors.email)}
                  errorMessage={errors.email}
                />
              </FormCell>
            </FormGrid>
          </FormSection>
        )}
        <FormActions>
          <Button
            variant="secondary"
            href={lead ? leadPath(lead.id) : APPLICATIONS_PATH}
            isDisabled={pending}
          >
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Start application
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
