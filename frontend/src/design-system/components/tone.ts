import {
  AiIcon,
  ErrorIcon,
  InfoIcon,
  SuccessIcon,
  WarningIcon,
  type IconComponent,
} from "@/design-system/icons";

// Shared status tones (DESIGN-SYSTEM.md §7, §49, §50). Internal to the
// component library. Every tone pairs colour with a distinct icon shape and
// text, so status is never communicated by colour alone.
//
// Text uses the *-text tokens (>= 4.5:1); the state colour itself is only used
// for icons and borders (>= 3:1) — INC-17.

export type Tone = "neutral" | "info" | "success" | "warning" | "error" | "ai";

export const toneIcon: Record<Tone, IconComponent | null> = {
  neutral: null,
  info: InfoIcon,
  success: SuccessIcon,
  warning: WarningIcon,
  error: ErrorIcon,
  ai: AiIcon,
};

/** Default spoken prefix for tones whose meaning must not rely on colour. */
export const toneLabel: Record<Tone, string> = {
  neutral: "Note",
  info: "Information",
  success: "Success",
  warning: "Warning",
  error: "Error",
  ai: "AI",
};

export const toneSurface: Record<Tone, string> = {
  neutral: "border-border-default bg-surface-secondary text-text-secondary",
  info: "border-info bg-info-surface text-info-text",
  success: "border-success bg-success-surface text-success-text",
  warning: "border-warning bg-warning-surface text-warning-text",
  error: "border-error bg-error-surface text-error-text",
  ai: "border-ai-border bg-ai-surface text-ai-primary",
};

export const toneIndicator: Record<Tone, string> = {
  neutral: "text-text-muted",
  info: "text-info",
  success: "text-success",
  warning: "text-warning",
  error: "text-error",
  ai: "text-ai-primary",
};
