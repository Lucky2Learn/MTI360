import "server-only";

// Frontend environment contract (T00-04). Server-only: importing this module
// from a Client Component fails the build, so server configuration can never
// reach the browser bundle. The frontend holds no secrets (CLAUDE.md §65); the
// only browser-visible value is NEXT_PUBLIC_APP_NAME.
//
// Rules (docs/architecture/environments.md):
//   APP_ENV              development | test | staging | production
//                        (default: development)
//   API_BASE_URL         http(s) URL without credentials, query or fragment.
//                        Defaults to the local API in development and test;
//                        required in staging and production.
//   NEXT_PUBLIC_APP_NAME display name (default: "MTI 360").

export const APP_ENVS = [
  "development",
  "test",
  "staging",
  "production",
] as const;
export type AppEnv = (typeof APP_ENVS)[number];

/** Server-side values. Never pass these to Client Components. */
export interface ServerEnv {
  readonly appEnv: AppEnv;
  readonly apiBaseUrl: string;
}

/** Values that are safe to ship to the browser. */
export interface PublicEnv {
  readonly appName: string;
}

type EnvSource = Readonly<Record<string, string | undefined>>;

const LOCAL_API_BASE_URL = "http://localhost:8000";
const DEFAULT_APP_NAME = "MTI 360";

/** Invalid environment. The message names variables and rules, never values. */
export class EnvironmentError extends Error {
  readonly problems: readonly string[];

  constructor(problems: readonly string[]) {
    super(
      `Invalid environment:\n${problems.map((p) => `  - ${p}`).join("\n")}`,
    );
    this.name = "EnvironmentError";
    this.problems = problems;
  }
}

function isAppEnv(value: string): value is AppEnv {
  return (APP_ENVS as readonly string[]).includes(value);
}

function parseApiBaseUrl(value: string): string | null {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  const isHttp = url.protocol === "http:" || url.protocol === "https:";
  if (!isHttp || url.username || url.password || url.search || url.hash) {
    return null;
  }
  return url.toString().replace(/\/+$/, "");
}

export function parseServerEnv(source: EnvSource): ServerEnv {
  const problems: string[] = [];

  const rawAppEnv = source.APP_ENV?.trim() || "development";
  const appEnv: AppEnv = isAppEnv(rawAppEnv) ? rawAppEnv : "development";
  if (!isAppEnv(rawAppEnv)) {
    problems.push(`APP_ENV: must be one of ${APP_ENVS.join(", ")}`);
  }

  const deployed = appEnv === "staging" || appEnv === "production";
  const rawApiBaseUrl = source.API_BASE_URL?.trim();
  let apiBaseUrl = LOCAL_API_BASE_URL;
  if (!rawApiBaseUrl) {
    if (deployed) {
      problems.push(`API_BASE_URL: must be set explicitly in ${appEnv}`);
    }
  } else {
    const parsed = parseApiBaseUrl(rawApiBaseUrl);
    if (parsed === null) {
      problems.push(
        "API_BASE_URL: must be an http(s) URL without credentials, query or fragment",
      );
    } else {
      apiBaseUrl = parsed;
    }
  }

  if (problems.length > 0) {
    throw new EnvironmentError(problems);
  }
  return { appEnv, apiBaseUrl };
}

export function parsePublicEnv(source: EnvSource): PublicEnv {
  return {
    appName: source.NEXT_PUBLIC_APP_NAME?.trim() || DEFAULT_APP_NAME,
  };
}

let cachedServerEnv: ServerEnv | undefined;

/** Validated server environment for the running process (read once). */
export function getServerEnv(): ServerEnv {
  cachedServerEnv ??= parseServerEnv(process.env);
  return cachedServerEnv;
}

/** Browser-safe values. NEXT_PUBLIC_* must be read with literal property access. */
export function getPublicEnv(): PublicEnv {
  return parsePublicEnv({
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  });
}
