"use client";

import { useId, type ReactNode } from "react";
import {
  Button as AriaButton,
  Calendar,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  DateInput,
  DatePicker as AriaDatePicker,
  DateSegment,
  Dialog,
  Group,
  Heading,
  I18nProvider,
  Popover,
  type DatePickerProps as AriaDatePickerProps,
  type DateValue,
} from "react-aria-components";

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
import {
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import {
  calendarDateToIso,
  isoToCalendarDate,
  MTI360_DEFAULT_LOCALE,
  MTI360_FIRST_DAY_OF_WEEK,
  type FirstDayOfWeek,
} from "./date";

// DatePicker (DESIGN-SYSTEM.md §42; T00-07B D2/D3, T00-07 D10).
// - Value: ISO "YYYY-MM-DD" strings (null = empty); dates only, no time zone.
// - Locale: en-IN by default (DD/MM/YYYY segments with leading zeros),
//   fixed through I18nProvider so server and client render identically.
// - First day of week: Monday by MTI 360 product default, independent of the
//   locale; override with `firstDayOfWeek`.
// - Keyboard: segments are spinbuttons (type digits, Up/Down, Tab between);
//   the calendar button opens a grid (arrows, PageUp/PageDown, Enter, Escape).
// - Validation: required, min/max, unavailable dates, validate(), server
//   errors via <Form validationErrors>. `name` submits the ISO value.
// - Popover on all sizes (decision D9); fits a 390px viewport.

type Omitted =
  | "className"
  | "style"
  | "children"
  | "value"
  | "defaultValue"
  | "onChange"
  | "minValue"
  | "maxValue"
  | "isDateUnavailable"
  | "firstDayOfWeek"
  | "granularity"
  | "placeholderValue"
  | "validate";

export type DatePickerProps = Omit<AriaDatePickerProps<DateValue>, Omitted> & {
  label: string;
  /** ISO date "YYYY-MM-DD" (controlled); null = empty. */
  value?: string | null;
  defaultValue?: string | null;
  onChange?: (iso: string | null) => void;
  /** Earliest allowed ISO date. */
  minValue?: string;
  /** Latest allowed ISO date. */
  maxValue?: string;
  isDateUnavailable?: (iso: string) => boolean;
  /** Custom validation on the ISO value; return an error message or null. */
  validate?: (
    iso: string | null,
  ) => string | string[] | true | null | undefined;
  /** BCP 47 locale for formatting; default "en-IN". */
  locale?: string;
  /** Default "mon" (MTI 360 product default, independent of the locale). */
  firstDayOfWeek?: FirstDayOfWeek;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  successMessage?: string;
};

const iconButtonBase = cx(
  "flex cursor-pointer items-center justify-center rounded-md text-text-secondary",
  "data-hovered:bg-surface-hover data-disabled:cursor-not-allowed data-disabled:opacity-50",
  focusRing,
);

export function DatePicker({
  label,
  value,
  defaultValue,
  onChange,
  minValue,
  maxValue,
  isDateUnavailable,
  validate,
  locale = MTI360_DEFAULT_LOCALE,
  firstDayOfWeek = MTI360_FIRST_DAY_OF_WEEK,
  description,
  errorMessage,
  successMessage,
  ...props
}: DatePickerProps) {
  const successId = useId();
  return (
    <I18nProvider locale={locale}>
      <AriaDatePicker
        {...props}
        value={isoToCalendarDate(value)}
        defaultValue={isoToCalendarDate(defaultValue)}
        onChange={(date) => onChange?.(calendarDateToIso(date))}
        minValue={isoToCalendarDate(minValue) ?? undefined}
        maxValue={isoToCalendarDate(maxValue) ?? undefined}
        isDateUnavailable={
          isDateUnavailable
            ? (date) => isDateUnavailable(calendarDateToIso(date)!)
            : undefined
        }
        validate={
          validate ? (date) => validate(calendarDateToIso(date)) : undefined
        }
        firstDayOfWeek={firstDayOfWeek}
        granularity="day"
        shouldForceLeadingZeros
        aria-describedby={
          cx(props["aria-describedby"], successMessage && successId) ||
          undefined
        }
        className={cx(fieldStack, "group")}
      >
        <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
        <Group
          className={cx(
            fieldSurface,
            fieldFocusWithin,
            "flex h-control-md items-center gap-2 pr-1 pl-3",
          )}
        >
          <DateInput className="flex flex-1 items-center">
            {(segment) => (
              <DateSegment
                segment={segment}
                className="rounded-xs px-1 tabular-nums outline-none data-focused:bg-brand-primary data-focused:text-text-inverse data-placeholder:text-text-muted data-[type=literal]:px-0"
              />
            )}
          </DateInput>
          <AriaButton className={cx(iconButtonBase, "size-control-sm")}>
            <CalendarIcon aria-hidden="true" className="size-4" />
          </AriaButton>
        </Group>
        {description && <FieldDescription>{description}</FieldDescription>}
        <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
        {successMessage && (
          <FieldSuccessMessage id={successId}>
            {successMessage}
          </FieldSuccessMessage>
        )}
        <Popover
          placement="bottom end"
          offset={4}
          className="z-(--z-dropdown) rounded-md border border-border-default bg-surface-elevated p-3 text-text-primary shadow-lg outline-none"
        >
          <Dialog className="outline-none">
            <Calendar className="flex flex-col gap-2">
              <header className="flex items-center justify-between gap-2">
                <AriaButton
                  slot="previous"
                  className={cx(iconButtonBase, "size-control-md")}
                >
                  <ChevronLeftIcon aria-hidden="true" className="size-4" />
                </AriaButton>
                <Heading className="text-body-sm font-semibold text-text-primary" />
                <AriaButton
                  slot="next"
                  className={cx(iconButtonBase, "size-control-md")}
                >
                  <ChevronRightIcon aria-hidden="true" className="size-4" />
                </AriaButton>
              </header>
              <CalendarGrid className="border-collapse">
                <CalendarGridHeader>
                  {(day) => (
                    <CalendarHeaderCell className="pb-1 text-caption font-medium text-text-muted">
                      {day}
                    </CalendarHeaderCell>
                  )}
                </CalendarGridHeader>
                <CalendarGridBody>
                  {(date) => (
                    <CalendarCell
                      date={date}
                      className={cx(
                        "flex size-11 cursor-pointer items-center justify-center rounded-md text-body-sm text-text-primary tabular-nums tablet:size-9",
                        "data-hovered:bg-surface-hover",
                        "data-today:font-semibold data-today:underline data-today:underline-offset-4",
                        "data-selected:bg-brand-primary data-selected:text-text-inverse",
                        "data-outside-month:text-text-muted",
                        "data-unavailable:cursor-not-allowed data-unavailable:text-text-muted data-unavailable:line-through",
                        "data-disabled:cursor-not-allowed data-disabled:opacity-40",
                        focusRing,
                      )}
                    />
                  )}
                </CalendarGridBody>
              </CalendarGrid>
            </Calendar>
          </Dialog>
        </Popover>
      </AriaDatePicker>
    </I18nProvider>
  );
}
