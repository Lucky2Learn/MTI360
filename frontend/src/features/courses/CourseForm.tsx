"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Form,
  Input,
  Select,
  Textarea,
  toast,
} from "@/design-system/components";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import type {
  CourseCategory,
  CourseWire,
  DurationUnit,
} from "@/lib/api/admissions";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import { COURSES_PATH, coursePath } from "./labels";

// ACA-03 Create / edit course (Phase 02-1; blueprint §4-§5, §21). The code is
// set once (upper-cased, campus-code format) and shown read-only when
// editing. Duration is a value with its unit, both or neither. Client checks
// mirror the API for quick feedback; the API validates again and its field
// codes map to the same copy. Edits send the loaded `version`: a 409 means
// someone else changed the course first.

const CODE_FORMAT = /^[A-Z0-9][A-Z0-9-]*$/;
const TEXT_MAX = 2000;
const NONE = "none";

type Values = {
  code: string;
  name: string;
  category: CourseCategory | null;
  durationValue: string;
  durationUnit: DurationUnit | null;
  eligibility: string;
  description: string;
};

type Field = keyof Values;
type Errors = Partial<Record<Field, string>>;

const CODE_MESSAGE =
  "Use up to 32 letters, digits or hyphens, starting with a letter or digit.";
const NAME_MESSAGE = "Enter a name of up to 200 characters.";
const DURATION_MESSAGE =
  "Enter a duration from 1 to 1000 with its unit, or leave both empty.";
const LONG_TEXT_MESSAGE = "Use at most 2000 characters.";

/** API field → form field and copy (422 details). */
const SERVER_FIELDS: Record<string, [Field, string]> = {
  code: ["code", CODE_MESSAGE],
  name: ["name", NAME_MESSAGE],
  duration_value: ["durationValue", DURATION_MESSAGE],
  description: ["description", LONG_TEXT_MESSAGE],
  eligibility_summary: ["eligibility", LONG_TEXT_MESSAGE],
};

function initial(course?: CourseWire): Values {
  return {
    code: course?.code ?? "",
    name: course?.name ?? "",
    category: course?.category ?? null,
    durationValue: course?.duration_value ? String(course.duration_value) : "",
    durationUnit: course?.duration_unit ?? null,
    eligibility: course?.eligibility_summary ?? "",
    description: course?.description ?? "",
  };
}

export function validateCourse(values: Values, creating: boolean): Errors {
  const errors: Errors = {};
  const code = values.code.trim().toUpperCase();
  if (creating && (!code || code.length > 32 || !CODE_FORMAT.test(code))) {
    errors.code = CODE_MESSAGE;
  }
  if (!values.name.trim()) errors.name = "Enter the course name.";
  else if (values.name.trim().length > 200) errors.name = NAME_MESSAGE;
  if (!values.category) errors.category = "Choose a category.";
  const hasValue = values.durationValue.trim() !== "";
  const number = Number(values.durationValue);
  if (
    hasValue !== Boolean(values.durationUnit) ||
    (hasValue && (!Number.isInteger(number) || number < 1 || number > 1000))
  ) {
    errors.durationValue = DURATION_MESSAGE;
  }
  if (values.eligibility.length > TEXT_MAX) {
    errors.eligibility = LONG_TEXT_MESSAGE;
  }
  if (values.description.length > TEXT_MAX) {
    errors.description = LONG_TEXT_MESSAGE;
  }
  return errors;
}

function payload(values: Values) {
  const duration = values.durationValue.trim();
  return {
    name: values.name.trim(),
    category: values.category,
    duration_value: duration ? Number(duration) : null,
    duration_unit: duration ? values.durationUnit : null,
    eligibility_summary: values.eligibility.trim() || null,
    description: values.description.trim() || null,
  };
}

export function CourseForm({ course }: { course?: CourseWire }) {
  const creating = course === undefined;
  const router = useRouter();
  const { request } = useTenantSession();
  const formRef = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Values>(() => initial(course));
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const update = <K extends Field>(field: K, value: Values[K]) => {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = validateCourse(values, creating);
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    try {
      const saved = creating
        ? await request<CourseWire>("/courses", {
            method: "POST",
            body: {
              code: values.code.trim().toUpperCase(),
              ...payload(values),
            },
          })
        : await request<CourseWire>(`/courses/${course.id}`, {
            method: "PATCH",
            body: { ...payload(values), version: course.version },
          });
      toast.success(creating ? "Course created" : "Course saved");
      router.push(coursePath(saved.id));
      router.refresh();
    } catch (error) {
      setPending(false);
      if (creating && error instanceof ApiError && error.code === "CONFLICT") {
        setErrors({ code: "A course with this code already exists." });
        focusFirstInvalid(formRef.current);
        return;
      }
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
        aria-label={creating ? "Create course" : "Edit course"}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection title="Course">
          <FormGrid>
            <FormCell>
              {creating ? (
                <Input
                  label="Code"
                  value={values.code}
                  onChange={(value) => update("code", value)}
                  description="Short code staff use, e.g. GPR or STCW-BST. It can't be changed later."
                  autoCapitalize="characters"
                  maxLength={32}
                  isRequired
                  isInvalid={Boolean(errors.code)}
                  errorMessage={errors.code}
                />
              ) : (
                <div className="flex flex-col gap-2">
                  <span className="text-body-sm font-medium text-text-primary">
                    Code
                  </span>
                  <span className="text-body text-text-primary">
                    {course.code}
                  </span>
                  <span className="text-caption text-text-secondary">
                    {"The code can't be changed."}
                  </span>
                </div>
              )}
            </FormCell>
            <FormCell>
              <Input
                label="Name"
                value={values.name}
                onChange={(value) => update("name", value)}
                maxLength={200}
                isRequired
                isInvalid={Boolean(errors.name)}
                errorMessage={errors.name}
              />
            </FormCell>
            <FormCell>
              <Select
                label="Category"
                options={[
                  { id: "PRE_SEA", label: "Pre-sea" },
                  { id: "POST_SEA", label: "Post-sea" },
                  { id: "OTHER", label: "Other" },
                ]}
                value={values.category}
                onChange={(value) =>
                  update("category", value as CourseCategory | null)
                }
                isRequired
                isInvalid={Boolean(errors.category)}
                errorMessage={errors.category}
              />
            </FormCell>
            <FormCell>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Duration"
                  value={values.durationValue}
                  onChange={(value) =>
                    update("durationValue", value.replace(/\D/g, ""))
                  }
                  inputMode="numeric"
                  maxLength={4}
                  isInvalid={Boolean(errors.durationValue)}
                  errorMessage={errors.durationValue}
                />
                <Select
                  label="Unit"
                  options={[
                    { id: NONE, label: "No duration" },
                    { id: "DAYS", label: "Days" },
                    { id: "WEEKS", label: "Weeks" },
                    { id: "MONTHS", label: "Months" },
                    { id: "YEARS", label: "Years" },
                  ]}
                  value={values.durationUnit ?? NONE}
                  onChange={(value) =>
                    update(
                      "durationUnit",
                      value === NONE ? null : (value as DurationUnit | null),
                    )
                  }
                  isInvalid={Boolean(errors.durationValue)}
                />
              </div>
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormSection
          title="Details for counsellors"
          description="Shown on the course page and used when counselling enquirers."
        >
          <FormGrid>
            <FormCell span="full">
              <Textarea
                label="Eligibility"
                value={values.eligibility}
                onChange={(value) => update("eligibility", value)}
                description="For example: 10th pass with 40% in Science, Maths and English; age 17½–25."
                maxLength={TEXT_MAX}
                showCount
                isInvalid={Boolean(errors.eligibility)}
                errorMessage={errors.eligibility}
              />
            </FormCell>
            <FormCell span="full">
              <Textarea
                label="Description"
                value={values.description}
                onChange={(value) => update("description", value)}
                maxLength={TEXT_MAX}
                showCount
                isInvalid={Boolean(errors.description)}
                errorMessage={errors.description}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button
            variant="secondary"
            href={creating ? COURSES_PATH : coursePath(course.id)}
            isDisabled={pending}
          >
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {creating ? "Create course" : "Save changes"}
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
