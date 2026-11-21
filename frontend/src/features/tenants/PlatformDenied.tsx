import { PLATFORM_HOME } from "@/lib/session/platform-routes";
import { ShellAccessDenied } from "@/shells";

// The platform access-denied state at the requested URL (T01-09B UI contract
// §8), the same copy as the navigation-derived platform pages: it never names
// the permission or a role.

const PLATFORM_DENIED =
  "Your platform access doesn't include this page. If you need it, ask a Super Admin.";

export function PlatformDenied() {
  return (
    <ShellAccessDenied
      homeHref={PLATFORM_HOME}
      homeLabel="Go to overview"
      description={PLATFORM_DENIED}
    />
  );
}
