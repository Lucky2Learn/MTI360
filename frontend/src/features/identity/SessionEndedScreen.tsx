import { Button, EmptyState } from "@/design-system/components";
import { LockIcon } from "@/design-system/icons";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import type { SessionEndedReason } from "@/lib/session/routes";

import { AUTH_REALMS, type AuthRealm } from "./realm";

// AUTH-05 Session ended (T01-04 UI contract §8.7). One calm landing place for
// expiry, revocation, a removed membership or institute, and sign-out. It
// never redirects by itself and never says why a session ended beyond
// "signed out" versus "ended" (the API does not report more, and the person
// cannot act differently on it). T01-09B: `realm="platform"` is PAUTH-06
// (/platform/session-ended; "Sign in" goes to /platform/login with a valid
// platform `next`).

const COPY: Record<SessionEndedReason, { title: string; description: string }> =
  {
    "signed-out": {
      title: "You've signed out",
      description: "Sign in again whenever you're ready.",
    },
    ended: {
      title: "Your session has ended",
      description:
        "For your security, you've been signed out. Sign in again to continue. Changes you hadn't saved may need to be entered again.",
    },
  };

export type SessionEndedScreenProps = {
  reason: SessionEndedReason;
  /** Validated `next` (or null), carried to sign-in. */
  next: string | null;
  realm?: AuthRealm;
};

export function SessionEndedScreen({
  reason,
  next,
  realm = "tenant",
}: SessionEndedScreenProps) {
  const copy = COPY[reason];
  const target = AUTH_REALMS[realm];
  return (
    <AuthenticationTemplate context={target.context}>
      <EmptyState
        titleAs="h1"
        icon={LockIcon}
        title={copy.title}
        description={copy.description}
        primaryAction={
          <Button href={target.loginUrl({ next })}>Sign in</Button>
        }
      />
    </AuthenticationTemplate>
  );
}
