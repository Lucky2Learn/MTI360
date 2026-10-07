import { authPost } from "@/lib/session/client";
import { platformAuthPost } from "@/lib/session/platform-client";
import {
  PLATFORM_AUTH_ROUTES,
  platformAuthUrl,
} from "@/lib/session/platform-routes";
import { AUTH_ROUTES, authUrl } from "@/lib/session/routes";

// Authentication realm of a T16 screen (T01-09B). The tenant screens of
// T01-09A also serve the platform realm where the flow is identical
// (sign-in MFA step, forgot and reset password, session ended): only the API
// prefix, the routes, the banner context and a few lines of copy differ.
// Default everywhere: "tenant", so T01-09A behaviour is unchanged.

export type AuthRealm = "tenant" | "platform";

export type AuthRealmConfig = {
  /** POST to the realm's /auth/* routes. */
  post: typeof authPost;
  /** Banner context label (D9B-11). */
  context?: string;
  routes: { login: string; forgotPassword: string };
  /** A sign-in URL with an allow-listed reason and a valid `next`. */
  loginUrl: (params?: { reason?: string; next?: unknown }) => string;
};

export const AUTH_REALMS: Record<AuthRealm, AuthRealmConfig> = {
  tenant: {
    post: authPost,
    routes: {
      login: AUTH_ROUTES.login,
      forgotPassword: AUTH_ROUTES.forgotPassword,
    },
    loginUrl: (params = {}) => authUrl(AUTH_ROUTES.login, params),
  },
  platform: {
    post: platformAuthPost,
    context: "Platform administration",
    routes: {
      login: PLATFORM_AUTH_ROUTES.login,
      forgotPassword: PLATFORM_AUTH_ROUTES.forgotPassword,
    },
    loginUrl: (params = {}) =>
      platformAuthUrl(PLATFORM_AUTH_ROUTES.login, params),
  },
};

export const PLATFORM_CONTEXT = AUTH_REALMS.platform.context!;
