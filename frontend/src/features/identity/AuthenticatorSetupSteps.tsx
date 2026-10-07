import { CopyButton, SecretValue } from "@/design-system/components";
import { focusRing } from "@/design-system/lib/cx";

// The manual authenticator set-up steps, shared by platform PAUTH-04
// (T01-09B) and tenant AUTH-04 set-up (T01-09C): the setup key (grouped,
// selectable, "Copy key" on press only), the `otpauth://` link from the API
// and the TOTP settings. No QR code (ADR-0017). The caller owns `secret` and
// `uri` in memory and drops them once the code is confirmed.

const SETTINGS = [
  ["Type", "Time-based"],
  ["Digits", "6"],
  ["Interval", "30 seconds"],
] as const;

export function AuthenticatorSetupSteps({
  secret,
  uri,
}: {
  secret: string;
  uri: string;
}) {
  return (
    <ol className="flex list-decimal flex-col gap-4 pl-5 text-body-sm text-text-primary">
      <li>
        <div className="flex flex-col gap-3">
          <span>
            In your authenticator app, add an account and choose to enter a
            setup key.
          </span>
          <SecretValue
            label="Setup key"
            value={secret}
            actions={<CopyButton value={secret} label="Copy key" size="sm" />}
          />
          <a
            href={uri}
            className={`w-fit rounded-sm text-link underline-offset-4 hover:underline ${focusRing}`}
          >
            Open in authenticator app
          </a>
          <dl className="flex flex-col gap-1 text-text-secondary">
            {SETTINGS.map(([term, value]) => (
              <div key={term} className="flex gap-2">
                <dt>{term}:</dt>
                <dd className="text-text-primary">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </li>
      <li>Enter the 6-digit code your app now shows for MTI 360.</li>
    </ol>
  );
}
