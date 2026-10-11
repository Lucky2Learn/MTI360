"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Form,
  IconButton,
  Input,
  Select,
  toast,
} from "@/design-system/components";
import { AddIcon, DeleteIcon } from "@/design-system/icons";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import type { CourseWire } from "@/lib/api/admissions";
import { ApiError } from "@/lib/api/errors";
import type { FeeStructureWire } from "@/lib/api/finance";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { fieldCodes, focusFirstInvalid } from "../shared/forms";

import { STRUCTURES_PATH, structurePath } from "./labels";
import { formatPaise, MAX_AMOUNT_MINOR, paiseInput, parsePaise } from "./money";

// FIN-03 Create / edit fee structure (Phase 02-5; ADR-0022 §7; readiness plan
// §4). A structure is the fee heads of one course; it is edited only while a
// draft (the server freezes it once active). Amounts are typed in rupees and
// converted to paise by string handling only; the total shown is the exact
// sum of those integers, and the server computes its own. Client checks
// mirror the API for quick feedback; its field codes map to the same copy.

const LINES_MAX = 30;

type Line = { key: number; head: string; amount: string };
type Errors = {
  course?: string;
  name?: string;
  lines?: string;
  rows?: Record<number, { head?: string; amount?: string }>;
};

const AMOUNT_MESSAGE = "Enter an amount in rupees, e.g. 25000 or 1,25,000.50.";
const LINES_MESSAGE: Record<string, string> = {
  line_count: "Add between 1 and 30 fee heads.",
  duplicate_fee_head: "Use each fee head once.",
  amount_out_of_range: "Enter amounts up to ₹1,00,00,00,000.",
  total_out_of_range: "The total must be more than ₹0.",
};

let nextKey = 0;
const line = (head = "", amount = ""): Line => ({
  key: nextKey++,
  head,
  amount,
});

function initialLines(structure?: FeeStructureWire): Line[] {
  if (!structure) return [line("Tuition"), line()];
  return structure.items.map((item) =>
    line(item.fee_head, paiseInput(item.amount_minor)),
  );
}

export function validateStructure(
  values: { course: string | null; name: string; lines: Line[] },
  creating: boolean,
): Errors {
  const errors: Errors = {};
  if (creating && !values.course) errors.course = "Choose the course.";
  if (!values.name.trim()) errors.name = "Enter a name, e.g. DNS fees 2026-27.";
  else if (values.name.trim().length > 200)
    errors.name = "Use at most 200 characters.";
  const rows: NonNullable<Errors["rows"]> = {};
  const heads = new Set<string>();
  let total = 0;
  values.lines.forEach((item, index) => {
    const head = item.head.trim().replace(/\s+/g, " ");
    const amount = parsePaise(item.amount);
    const row: { head?: string; amount?: string } = {};
    if (!head || head.length > 100)
      row.head = "Enter a fee head of up to 100 characters.";
    else if (heads.has(head.toLowerCase()))
      row.head = "Use each fee head once.";
    heads.add(head.toLowerCase());
    if (amount === null) row.amount = AMOUNT_MESSAGE;
    else total += amount;
    if (row.head || row.amount) rows[index] = row;
  });
  if (Object.keys(rows).length > 0) errors.rows = rows;
  if (values.lines.length < 1 || values.lines.length > LINES_MAX) {
    errors.lines = LINES_MESSAGE.line_count;
  } else if (!errors.rows && (total <= 0 || total > MAX_AMOUNT_MINOR)) {
    errors.lines = LINES_MESSAGE.total_out_of_range;
  }
  return errors;
}

export function FeeStructureForm({
  structure,
  courses = [],
}: {
  structure?: FeeStructureWire;
  courses?: CourseWire[];
}) {
  const creating = structure === undefined;
  const router = useRouter();
  const { request } = useTenantSession();
  const formRef = useRef<HTMLDivElement>(null);
  const [course, setCourse] = useState<string | null>(
    structure?.course.id ?? null,
  );
  const [name, setName] = useState(structure?.name ?? "");
  const [lines, setLines] = useState<Line[]>(() => initialLines(structure));
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const total = lines.reduce(
    (sum, item) => sum + (parsePaise(item.amount) ?? 0),
    0,
  );
  const allValid = lines.every((item) => parsePaise(item.amount) !== null);

  const change = (index: number, patch: Partial<Line>) => {
    setLines((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
    setErrors((current) => ({ ...current, rows: undefined, lines: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = validateStructure({ course, name, lines }, creating);
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    const items = lines.map((item) => ({
      fee_head: item.head.trim(),
      amount_minor: parsePaise(item.amount) as number,
    }));
    setPending(true);
    try {
      const saved = creating
        ? await request<FeeStructureWire>("/fee-structures", {
            method: "POST",
            body: { course_id: course, name: name.trim(), items },
          })
        : await request<FeeStructureWire>(`/fee-structures/${structure.id}`, {
            method: "PATCH",
            body: { name: name.trim(), items, version: structure.version },
          });
      toast.success(creating ? "Fee structure created" : "Fee structure saved");
      router.push(structurePath(saved.id));
      router.refresh();
    } catch (error) {
      setPending(false);
      if (!creating && error instanceof ApiError && error.code === "CONFLICT") {
        setFeedback({
          tone: "warning",
          title: "This fee structure changed",
          body: "Someone else saved it first. Reload the page to see the latest version.",
        });
        return;
      }
      const fields = fieldCodes(error);
      const mapped: Errors = {};
      if (fields.course_id) mapped.course = "Choose a draft or active course.";
      if (fields.name) mapped.name = "Enter a name of up to 200 characters.";
      if (fields.items)
        mapped.lines = LINES_MESSAGE[fields.items] ?? LINES_MESSAGE.line_count;
      if (fields.status === "not_editable") {
        setFeedback({
          tone: "warning",
          title: "This fee structure can't be edited",
          body: "Only a draft can be edited. Create a new fee structure instead.",
        });
        return;
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
        aria-label={creating ? "Create fee structure" : "Edit fee structure"}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection title="Fee structure">
          <FormGrid>
            <FormCell>
              {creating ? (
                <Select
                  label="Course"
                  options={courses.map((item) => ({
                    id: item.id,
                    label: `${item.code} · ${item.name}`,
                  }))}
                  value={course}
                  onChange={(value) => {
                    setCourse(value);
                    setErrors((current) => ({ ...current, course: undefined }));
                  }}
                  isRequired
                  isInvalid={Boolean(errors.course)}
                  errorMessage={errors.course}
                />
              ) : (
                <div className="flex flex-col gap-2">
                  <span className="text-body-sm font-medium text-text-primary">
                    Course
                  </span>
                  <span className="text-body text-text-primary">
                    {`${structure.course.code} · ${structure.course.name}`}
                  </span>
                </div>
              )}
            </FormCell>
            <FormCell>
              <Input
                label="Name"
                value={name}
                onChange={(value) => {
                  setName(value);
                  setErrors((current) => ({ ...current, name: undefined }));
                }}
                description="For example: DNS fees 2026-27."
                maxLength={200}
                isRequired
                isInvalid={Boolean(errors.name)}
                errorMessage={errors.name}
              />
            </FormCell>
          </FormGrid>
        </FormSection>
        <FormSection
          title="Fee heads"
          description="Amounts in rupees. Fee invoices copy these lines when they are issued; the amounts can be adjusted for a student, with a reason."
        >
          {errors.lines && (
            <Alert tone="error" title="Check the fee heads">
              {errors.lines}
            </Alert>
          )}
          <ul className="flex flex-col gap-4" aria-label="Fee heads">
            {lines.map((item, index) => (
              <li
                key={item.key}
                className="flex flex-col gap-3 tablet:flex-row tablet:items-start"
              >
                <div className="min-w-0 tablet:flex-1">
                  <Input
                    label={`Fee head ${index + 1}`}
                    value={item.head}
                    onChange={(value) => change(index, { head: value })}
                    maxLength={100}
                    isRequired
                    isInvalid={Boolean(errors.rows?.[index]?.head)}
                    errorMessage={errors.rows?.[index]?.head}
                  />
                </div>
                <div className="tablet:w-48 tablet:shrink-0">
                  <Input
                    label={`Amount ${index + 1} (₹)`}
                    value={item.amount}
                    onChange={(value) => change(index, { amount: value })}
                    inputMode="decimal"
                    maxLength={20}
                    isRequired
                    isInvalid={Boolean(errors.rows?.[index]?.amount)}
                    errorMessage={errors.rows?.[index]?.amount}
                  />
                </div>
                <div className="tablet:pt-7">
                  <IconButton
                    label={`Remove fee head ${index + 1}`}
                    icon={DeleteIcon}
                    variant="ghost"
                    isDisabled={lines.length <= 1}
                    onPress={() =>
                      setLines((current) =>
                        current.filter((_, i) => i !== index),
                      )
                    }
                  />
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
            <Button
              variant="secondary"
              iconStart={AddIcon}
              isDisabled={lines.length >= LINES_MAX}
              onPress={() => setLines((current) => [...current, line()])}
            >
              Add fee head
            </Button>
            <p
              className="text-body font-medium text-text-primary"
              aria-live="polite"
            >
              <span className="text-text-secondary">Total </span>
              <span className="tabular-nums">
                {allValid ? formatPaise(total) : "—"}
              </span>
            </p>
          </div>
        </FormSection>
        <FormActions>
          <Button
            variant="secondary"
            href={creating ? STRUCTURES_PATH : structurePath(structure.id)}
            isDisabled={pending}
          >
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {creating ? "Create draft" : "Save changes"}
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
