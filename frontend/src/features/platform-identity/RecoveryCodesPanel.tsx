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

// PAUTH-05 Recovery codes, shown once (T01-09B UI contract §6, D9B-5). Used
// after enrolment (in the sign-in card) and after regeneration on Sign-in
// security (in a Dialog). The codes are owned by the caller's state, which
// drops them when `onContinue` runs; this component never stores, logs or
// sends them. Copy only on a button press; no download, print or sync.
//
// The "I've saved my recovery codes" checkbox VALIDATES the action: Continue
// stays enabled and an unchecked box shows a field error (accessible). While
// the codes are shown, leaving the page asks first (beforeunload).

export const RECOVERY_CODES_TITLE = "Save your recovery codes";

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
};

export function RecoveryCodesPanel({
  codes,
  onContinue,
  continueLabel = "Continue",
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
        you can&apos;t use your authenticator app. You can generate new codes
        from Sign-in security.
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
