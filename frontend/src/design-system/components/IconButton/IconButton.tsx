"use client";

import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
} from "react-aria-components";

import {
  buttonBase,
  buttonVariants,
} from "@/design-system/components/Button/Button";
import { SpinnerIcon, type IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// IconButton (DESIGN-SYSTEM.md §41 "Icon" variant, §69). An icon-only action
// always has an accessible name: `label` is required by the type and becomes
// aria-label (a visible tooltip arrives with the overlay components). Square control-height target;
// medium grows to 44px below the tablet breakpoint (component tokens).

export type IconButtonVariant =
  "primary" | "secondary" | "ghost" | "destructive";
export type IconButtonSize = "sm" | "md" | "lg";

const sizes: Record<IconButtonSize, string> = {
  sm: "size-control-sm",
  md: "size-control-md",
  lg: "size-control-lg",
};

export type IconButtonProps = Omit<
  AriaButtonProps,
  "className" | "style" | "children" | "aria-label"
> & {
  /** Accessible name (required): describes the action, e.g. "Close panel". */
  label: string;
  icon: IconComponent;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
};

export function IconButton({
  label,
  icon: Icon,
  variant = "ghost",
  size = "md",
  ...props
}: IconButtonProps) {
  return (
    <AriaButton
      {...props}
      aria-label={label}
      className={cx(buttonBase, "px-0", sizes[size], buttonVariants[variant])}
    >
      {props.isPending ? (
        <SpinnerIcon
          aria-hidden="true"
          className="size-5 motion-safe:animate-spin"
        />
      ) : (
        <Icon aria-hidden="true" className="size-5" />
      )}
    </AriaButton>
  );
}
