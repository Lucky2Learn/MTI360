"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
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
import type { BatchWire, RefWire } from "@/lib/api/batches";
import { ApiError } from "@/lib/api/errors";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import { BATCHES_PATH, batchPath } from "./labels";

// ACA-07 Create / edit batch (Phase 02-6). Course and campus are chosen once
// (active courses; the member's campuses) and shown read-only when editing.
// The code is upper-cased and unique per institute. Capacity 1-500, never
// below the students already allocated (the server checks with the batch
// locked). Edits send the loaded `version`: 409 means someone else changed
// the batch first. Client checks mirror the API for quick feedback only.

const CODE_FORMAT = /^[A-Z0-9][A-Z0-9-]*$/;

type Values = {
  course: string | null;
  campus: string | null;
  code: string;
  name: string;
  intake: string;
  start: string | null;
  end: string | null;
  capacity: string;
};
type Field = keyof Values;
type Errors = Partial<Record<Field, string>>;

const CODE_MESSAGE =
  "Use up to 32 letters, digits or hyphens, starting with a letter or digit.";
const CAPACITY_MESSAGE = "Enter a capacity from 1 to 500.";
const DATES_MESSAGE = "The end date can't be before the start date.";

/** API `field → code` → form field and copy (422 details). */
const SERVER: Record<string, Record<string, [Field, string]>> = {
  course_id: {
    course_not_active: ["course", "Choose an active course."],
  },
  campus_id: {
    campus_not_available: ["campus", "Choose one of your campuses."],
  },
  code: { invalid: ["code", CODE_MESSAGE] },
  name: { invalid: ["name", "Enter a name of up to 200 characters."] },
  intake_label: { invalid: ["intake", "Use at most 100 characters."] },
  end_date: { invalid_dates: ["end", DATES_MESSAGE] },
  capacity: {
    invalid: ["capacity", CAPACITY_MESSAGE],
    capacity_below_allocated: [
      "capacity",
      "More students are already allocated than this capacity allows.",
    ],
  },
};

function initial(batch?: BatchWire): Values {
  return {
    course: batch?.course.id ?? null,
    campus: batch?.campus.id ?? null,
    code: batch?.code ?? "",
    name: batch?.name ?? "",
    intake: batch?.intake_label ?? "",
    start: batch?.start_date ?? null,
    end: batch?.end_date ?? null,
    capacity: batch ? String(batch.capacity) : "",
  };
}

export function validateBatch(
  values: Values,
  creating: boolean,
  allocated = 0,
): Errors {
  const errors: Errors = {};
  if (creating) {
    if (!values.course) errors.course = "Choose a course.";
    if (!values.campus) errors.campus = "Choose a campus.";
    const code = values.code.trim().toUpperCase();
    if (!code || code.length > 32 || !CODE_FORMAT.test(code)) {
      errors.code = CODE_MESSAGE;
    }
  }
  if (!values.name.trim()) errors.name = "Enter the batch name.";
  else if (values.name.trim().length > 200) {
    errors.name = "Enter a name of up to 200 characters.";
  }
  if (values.intake.trim().length > 100) {
    errors.intake = "Use at most 100 characters.";
  }
  if (!values.start) errors.start = "Enter the start date.";
  if (!values.end) errors.end = "Enter the end date.";
  else if (values.start && values.end < values.start)
    errors.end = DATES_MESSAGE;
  const capacity = Number(values.capacity);
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > 500) {
    errors.capacity = CAPACITY_MESSAGE;
  } else if (capacity < allocated) {
    errors.capacity = `${allocated} students are allocated. Capacity can't be lower than that.`;
  }
  return errors;
}

function ReadOnly({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-body-sm font-medium text-text-primary">
        {label}
      </span>
      <span className="text-body text-text-primary">{value}</span>
      <span className="text-caption text-text-secondary">{note}</span>
    </div>
  );
}

export function BatchForm({
  batch,
  courses = [],
}: {
  batch?: BatchWire;
  courses?: RefWire[];
}) {
  const creating = batch === undefined;
  const router = useRouter();
  const { request, session } = useTenantSession();
  const formRef = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Values>(() => {
    const start = initial(batch);
    if (creating && session.campusOptions.length === 1) {
      start.campus = session.campusOptions[0]!.id;
    }
    return start;
  });
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
    const found = validateBatch(values, creating, batch?.allocated_count ?? 0);
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    const common = {
      name: values.name.trim(),
      intake_label: values.intake.trim() || null,
      start_date: values.start,
      end_date: values.end,
      capacity: Number(values.capacity),
    };
    setPending(true);
    try {
      const saved = creating
        ? await request<BatchWire>("/batches", {
            method: "POST",
            body: {
              course_id: values.course,
              campus_id: values.campus,
              code: values.code.trim().toUpperCase(),
              ...common,
            },
          })
        : await request<BatchWire>(`/batches/${batch.id}`, {
            method: "PATCH",
            body: { ...common, version: batch.version },
          });
      toast.success(creating ? "Batch created" : "Batch saved");
      router.push(batchPath(saved.id));
      router.refresh();
    } catch (error) {
      setPending(false);
      if (error instanceof ApiError && error.code === "CONFLICT") {
        if (creating) {
          setErrors({ code: "A batch with this code already exists." });
          focusFirstInvalid(formRef.current);
        } else {
          setFeedback({
            tone: "warning",
            title: "This batch was changed by someone else",
            body: "Reload the page to see the latest details, then make your changes again.",
          });
        }
        return;
      }
      const mapped: Errors = {};
      for (const [field, code] of Object.entries(fieldCodes(error))) {
        const known = SERVER[field]?.[code];
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
        aria-label={creating ? "Create batch" : "Edit batch"}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection
          title="Course and campus"
          description={
            creating
              ? "A batch belongs to one course at one campus. These can't be changed later."
              : undefined
          }
        >
          <FormGrid>
            <FormCell>
              {creating ? (
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
                      ? "No active courses. Activate a course first."
                      : "Only active courses can have batches."
                  }
                  isRequired
                  isInvalid={Boolean(errors.course)}
                  errorMessage={errors.course}
                />
              ) : (
                <ReadOnly
                  label="Course"
                  value={`${batch.course.code} · ${batch.course.name}`}
                  note="The course can't be changed."
                />
              )}
            </FormCell>
            <FormCell>
              {creating ? (
                <Select
                  label="Campus"
                  options={session.campusOptions.map((c) => ({
                    id: c.id,
                    label: c.name,
                  }))}
                  value={values.campus}
                  onChange={(value) => update("campus", value)}
                  isRequired
                  isInvalid={Boolean(errors.campus)}
                  errorMessage={errors.campus}
                />
              ) : (
                <ReadOnly
                  label="Campus"
                  value={batch.campus.name}
                  note="The campus can't be changed."
                />
              )}
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormSection title="Batch">
          <FormGrid>
            <FormCell>
              {creating ? (
                <Input
                  label="Batch code"
                  value={values.code}
                  onChange={(value) => update("code", value)}
                  description="Unique in your institute, e.g. DNS-2026-B. It can't be changed later."
                  autoCapitalize="characters"
                  maxLength={32}
                  isRequired
                  isInvalid={Boolean(errors.code)}
                  errorMessage={errors.code}
                />
              ) : (
                <ReadOnly
                  label="Batch code"
                  value={batch.code}
                  note="The code can't be changed."
                />
              )}
            </FormCell>
            <FormCell>
              <Input
                label="Batch name"
                value={values.name}
                onChange={(value) => update("name", value)}
                maxLength={200}
                isRequired
                isInvalid={Boolean(errors.name)}
                errorMessage={errors.name}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Intake"
                value={values.intake}
                onChange={(value) => update("intake", value)}
                description="Optional, e.g. July 2026."
                maxLength={100}
                isInvalid={Boolean(errors.intake)}
                errorMessage={errors.intake}
              />
            </FormCell>
            <FormCell>
              <Input
                label="Capacity"
                value={values.capacity}
                onChange={(value) =>
                  update("capacity", value.replace(/\D/g, ""))
                }
                description={
                  batch && batch.allocated_count > 0
                    ? `Seats, 1 to 500. ${batch.allocated_count} already allocated.`
                    : "Seats, 1 to 500."
                }
                inputMode="numeric"
                maxLength={3}
                isRequired
                isInvalid={Boolean(errors.capacity)}
                errorMessage={errors.capacity}
              />
            </FormCell>
            <FormCell>
              <DatePicker
                label="Start date"
                value={values.start}
                onChange={(iso) => update("start", iso)}
                isRequired
                isInvalid={Boolean(errors.start)}
                errorMessage={errors.start}
              />
            </FormCell>
            <FormCell>
              <DatePicker
                label="End date"
                value={values.end}
                minValue={values.start ?? undefined}
                onChange={(iso) => update("end", iso)}
                isRequired
                isInvalid={Boolean(errors.end)}
                errorMessage={errors.end}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button
            variant="secondary"
            href={creating ? BATCHES_PATH : batchPath(batch.id)}
            isDisabled={pending}
          >
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {creating ? "Create batch" : "Save changes"}
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
