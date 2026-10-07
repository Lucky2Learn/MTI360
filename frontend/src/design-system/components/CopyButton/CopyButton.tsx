"use client";

import { useEffect, useRef, useState } from "react";

import { Button, type ButtonSize } from "@/design-system/components/Button";
import { CheckIcon, CopyIcon } from "@/design-system/icons";

// CopyButton (T01-09B, design-system extension). Copies `value` to the
// clipboard ONLY when pressed — never automatically. The outcome is announced
// in an always-mounted polite live region next to the button ("Copied" or a
// fallback hint), so it works where no ToastRegion is mounted (T16 pages).
// The value is never rendered, logged or announced by this component.

export type CopyButtonProps = {
  /** Text placed on the clipboard. */
  value: string;
  /** Visible label, e.g. "Copy key". */
  label: string;
  /** Announced after a successful copy. */
  copiedLabel?: string;
  /** Announced when the clipboard is unavailable or refuses. */
  failedLabel?: string;
  size?: ButtonSize;
};

const RESET_MS = 4000;

export function CopyButton({
  value,
  label,
  copiedLabel = "Copied to the clipboard.",
  failedLabel = "Couldn't copy. Select the text and copy it instead.",
  size = "md",
}: CopyButtonProps) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const copy = async () => {
    if (timer.current) clearTimeout(timer.current);
    try {
      if (!navigator.clipboard?.writeText) throw new Error("unavailable");
      await navigator.clipboard.writeText(value);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
    timer.current = setTimeout(() => setStatus("idle"), RESET_MS);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="secondary"
        size={size}
        iconStart={status === "copied" ? CheckIcon : CopyIcon}
        onPress={() => void copy()}
      >
        {label}
      </Button>
      <span role="status" className="text-body-sm text-text-secondary">
        {status === "copied"
          ? copiedLabel
          : status === "failed"
            ? failedLabel
            : ""}
      </span>
    </div>
  );
}
