"use client";

import {
  Button as AriaButton,
  Link as AriaLink,
  type ButtonProps as AriaButtonProps,
} from "react-aria-components";

import { SpinnerIcon, type IconComponent } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Button (DESIGN-SYSTEM.md §41; contract: docs/architecture/components.md).
// Built on React Aria: keyboard (Enter/Space), press states, disabled and
// pending semantics. Destructive buttons never confirm by themselves —
// confirmation is Dialog's job (07C, §62).

export type ButtonVariant =
  "primary" | "secondary" | "tertiary" | "ghost" | "destructive" | "success";
export type ButtonSize = "sm" | "md" | "lg";

export const buttonBase = cx(
  "inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap select-none",
  "transition-colors motion-reduce:transition-none",
  "data-disabled:cursor-not-allowed data-disabled:opacity-50 data-pending:cursor-progress",
  focusRing,
);

export const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-control-sm px-3 text-body-sm",
  md: "h-control-md px-4 text-body-sm",
  lg: "h-control-lg px-5 text-body",
};

export const buttonVariants: Record<ButtonVariant, string> = {
  // Brand action: Deep Ocean (Light) / Sea Glass (Dark) with text-inverse.
  primary:
    "bg-brand-primary text-text-inverse data-hovered:bg-brand-primary-hover data-pressed:bg-brand-primary-hover",
  secondary:
    "border border-border-strong bg-surface-primary text-text-primary data-hovered:bg-surface-hover data-pressed:bg-surface-selected",
  // Text-style action (link colour, underline on hover) — decision D13.
  tertiary:
    "bg-transparent text-link underline-offset-4 data-hovered:underline data-pressed:underline",
  // Transparent with a hover surface — decision D13.
  ghost:
    "bg-transparent text-text-primary data-hovered:bg-surface-hover data-pressed:bg-surface-selected",
  destructive:
    "bg-error-strong text-text-inverse data-hovered:shadow-md data-pressed:shadow-none",
  // success-strong: the specification success colour fails 4.5:1 with white.
  success:
    "bg-success-strong text-text-inverse data-hovered:shadow-md data-pressed:shadow-none",
};

type CommonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon (decorative; the label carries the meaning). */
  iconStart?: IconComponent;
  /** Trailing icon (decorative). */
  iconEnd?: IconComponent;
  /** Stretch to the container width (for example stacked mobile actions). */
  fullWidth?: boolean;
  children: ReactNode;
};

export type ButtonProps = CommonProps &
  Omit<AriaButtonProps, "className" | "style" | "children"> & {
    /** Renders a link styled as a button (navigation, not an action). */
    href?: string;
    target?: string;
    rel?: string;
  };

function Content({
  iconStart: Start,
  iconEnd: End,
  isPending,
  children,
}: Pick<CommonProps, "iconStart" | "iconEnd" | "children"> & {
  isPending?: boolean;
}) {
  return (
    <>
      {isPending ? (
        <SpinnerIcon
          aria-hidden="true"
          className="size-4 motion-safe:animate-spin"
        />
      ) : (
        Start && <Start aria-hidden="true" className="size-4" />
      )}
      <span>{children}</span>
      {End && !isPending && <End aria-hidden="true" className="size-4" />}
    </>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  iconStart,
  iconEnd,
  fullWidth = false,
  children,
  href,
  target,
  rel,
  ...props
}: ButtonProps) {
  const className = cx(
    buttonBase,
    buttonSizes[size],
    buttonVariants[variant],
    fullWidth && "w-full",
  );
  const content = (
    <Content
      iconStart={iconStart}
      iconEnd={iconEnd}
      isPending={props.isPending}
    >
      {children}
    </Content>
  );

  if (href !== undefined) {
    return (
      <AriaLink
        href={href}
        target={target}
        rel={target === "_blank" ? (rel ?? "noopener noreferrer") : rel}
        isDisabled={props.isDisabled}
        onPress={props.onPress}
        aria-label={props["aria-label"]}
        className={className}
      >
        {content}
      </AriaLink>
    );
  }

  return (
    <AriaButton {...props} className={className}>
      {content}
    </AriaButton>
  );
}
