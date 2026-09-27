"use client";

import { useId, type ReactNode } from "react";
import {
  DateInput,
  DateSegment,
  I18nProvider,
  TimeField,
  type TimeFieldProps,
  type TimeValue,
} from "react-aria-components";

import { MTI360_DEFAULT_LOCALE } from "@/design-system/components/DatePicker/date";
import {
  FieldDescription,
  FieldErrorMessage,
  FieldLabel,
  FieldSuccessMessage,
  fieldFocusWithin,
  fieldStack,
  fieldSurface,
  type ErrorMessage,
} from "@/design-system/components/Field/Field";
import { cx } from "@/design-system/lib/cx";

import { isoToTime, normalizeLiteral, timeToIso } from "./time";

// TimePicker (T00-07C; DESIGN-SYSTEM.md §42), following DatePicker's
// conventions: ISO "HH:mm" values (24-hour) in and out, en-IN display by
// default (12-hour clock with am/pm, leading zeros) through I18nProvider, no
// time zones. React Aria TimeField: hour / minute / day-period segments are
// spinbuttons (type digits, Up/Down, Tab between). Validation: isRequired,
// min / max, validate(iso), server errors via <Form validationErrors>.
// `name` submits React Aria's ISO value "HH:mm:ss" with the form.
// It is a keyboard-first field (no dropdown list of times — React Aria
// provides none; a list can be composed with Select where a fixed set of
// slots is needed).

type Omitted =
  | "className"
  | "style"
  | "children"
  | "value"
  | "defaultValue"
  | "onChange"
  | "minValue"
  | "maxValue"
  | "granularity"
  | "placeholderValue"
  | "validate";

export type TimePickerProps = Omit<TimeFieldProps<TimeValue>, Omitted> & {
  label: string;
  /** ISO "HH:mm" (controlled); null = empty. */
  value?: string | null;
  defaultValue?: string | null;
  onChange?: (iso: string | null) => void;
  minValue?: string;
  maxValue?: string;
  validate?: (
    iso: string | null,
  ) => string | string[] | true | null | undefined;
  /** Override the locale's clock (en-IN default: 12-hour). */
  hourCycle?: 12 | 24;
  locale?: string;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  successMessage?: string;
};

export function TimePicker({
  label,
  value,
  defaultValue,
  onChange,
  minValue,
  maxValue,
  validate,
  locale = MTI360_DEFAULT_LOCALE,
  description,
  errorMessage,
  successMessage,
  ...props
}: TimePickerProps) {
  const successId = useId();
  return (
    <I18nProvider locale={locale}>
      <TimeField
        {...props}
        value={isoToTime(value)}
        defaultValue={isoToTime(defaultValue)}
        onChange={(time) => onChange?.(timeToIso(time))}
        minValue={isoToTime(minValue) ?? undefined}
        maxValue={isoToTime(maxValue) ?? undefined}
        validate={validate ? (time) => validate(timeToIso(time)) : undefined}
        granularity="minute"
        shouldForceLeadingZeros
        aria-describedby={
          cx(props["aria-describedby"], successMessage && successId) ||
          undefined
        }
        className={cx(fieldStack, "group")}
      >
        <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
        <DateInput
          className={cx(
            fieldSurface,
            fieldFocusWithin,
            "flex h-control-md items-center gap-0 px-3",
          )}
        >
          {(segment) => (
            <DateSegment
              segment={
                segment.type === "literal"
                  ? { ...segment, text: normalizeLiteral(segment.text) }
                  : segment
              }
              className="rounded-xs px-1 tabular-nums outline-none data-focused:bg-brand-primary data-focused:text-text-inverse data-placeholder:text-text-muted data-[type=literal]:px-0"
            />
          )}
        </DateInput>
        {description && <FieldDescription>{description}</FieldDescription>}
        <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
        {successMessage && (
          <FieldSuccessMessage id={successId}>
            {successMessage}
          </FieldSuccessMessage>
        )}
      </TimeField>
    </I18nProvider>
  );
}
