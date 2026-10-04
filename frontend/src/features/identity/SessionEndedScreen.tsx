import { Button, EmptyState } from "@/design-system/components";
import { LockIcon } from "@/design-system/icons";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import {
  AUTH_ROUTES,
  authUrl,
  type SessionEndedReason,
} from "@/lib/session/routes";

// AUTH-05 Session ended (T01-04 UI contract §8.7). One calm landing place for
// expiry, revocation, a removed membership or institute, and sign-out. It
// never redirects by itself and never says why a session ended beyond
// "signed out" versus "ended" (the API does not report more, and the person
// cannot act differently on it).

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
};

export function SessionEndedScreen({ reason, next }: SessionEndedScreenProps) {
  const copy = COPY[reason];
  return (
    <AuthenticationTemplate>
      <EmptyState
        titleAs="h1"
        icon={LockIcon}
        title={copy.title}
        description={copy.description}
        primaryAction={
          <Button href={authUrl(AUTH_ROUTES.login, { next })}>Sign in</Button>
        }
      />
    </AuthenticationTemplate>
  );
}
