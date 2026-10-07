"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Checkbox,
  CodeList,
  CopyButton,
  Form,
} from "@/design-system/components";

// Recovery codes, shown once: platform PAUTH-05 (T01-09B UI contract §6,
// D9B-5) and tenant AUTH-04 set-up (T01-09C UI contract §5). Used after
// enrolment (in the sign-in card or a Dialog) and after platform
// regeneration on Sign-in security (in a Dialog). `hint` says how to get new
// codes in the caller's realm (the tenant realm has no regeneration). The codes are owned by the caller's state, which
// drops them when `onContinue` runs; this component never stores, logs or
// sends them. Copy only on a button press; no download, print or sync.
//
// The "I've saved my recovery codes" checkbox VALIDATES the action: Continue
// stays enabled and an unchecked box shows a field error (accessible). While
// the codes are shown, leaving the page asks first (beforeunload).

export const RECOVERY_CODES_TITLE = "Save your recovery codes";

/** Platform realm: codes can be regenerated (with step-up). */
export const PLATFORM_RECOVERY_HINT =
  "You can generate new codes from Sign-in security.";

/**
 * Tenant realm: there is no regeneration endpoint (T01-09C BG-T1); turning
 * two-step verification off and on again issues new codes.
 */
export const TENANT_RECOVERY_HINT =
  "To get new codes later, turn two-step verification off and on again from Sign-in security.";

const NOT_SAVED = "Confirm that you've saved your recovery codes.";

/**
 * Asks before the page unloads while `armed` is true. `release()` disarms it
 * synchronously, before an intentional navigation.
 */
export function useLeaveGuard() {
  const armed = useRef(true);
  useEffect(() => {
    armed.current = true;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!armed.current) return;
      event.preventDefault();
      // Legacy browsers need a value; the text is not shown.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);
  return {
    release: () => {
      armed.current = false;
    },
  };
}

export type RecoveryCodesPanelProps = {
  codes: readonly string[];
  /** Runs after the acknowledgement; the caller drops the codes. */
  onContinue: () => void;
  continueLabel?: string;
  /** How to get new codes later, in the caller's realm. */
  hint: string;
};

export function RecoveryCodesPanel({
  codes,
  onContinue,
  continueLabel = "Continue",
  hint,
}: RecoveryCodesPanelProps) {
  const checkbox = useRef<HTMLInputElement>(null);
  const [saved, setSaved] = useState(false);
  const [unsaved, setUnsaved] = useState(false);
  const guard = useLeaveGuard();

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!saved) {
      setUnsaved(true);
      checkbox.current?.focus();
      return;
    }
    guard.release();
    onContinue();
  };

  return (
    <div className="flex flex-col gap-4">
      <Alert tone="warning" title="This is the only time these codes are shown">
        Each code works once. They can&apos;t be retrieved later. Use one when
        you can&apos;t use your authenticator app. {hint}
      </Alert>
      <CodeList label="Recovery codes" codes={codes} />
      <CopyButton value={codes.join("\n")} label="Copy codes" />
      <Form aria-label="Confirm your recovery codes" onSubmit={submit}>
        <Checkbox
          inputRef={checkbox}
          isSelected={saved}
          onChange={(value) => {
            setSaved(value);
            if (value) setUnsaved(false);
          }}
          validationBehavior="aria"
          isInvalid={unsaved}
          errorMessage={NOT_SAVED}
        >
          I&apos;ve saved my recovery codes
        </Checkbox>
        <Button type="submit" size="lg" fullWidth>
          {continueLabel}
        </Button>
      </Form>
    </div>
  );
}
