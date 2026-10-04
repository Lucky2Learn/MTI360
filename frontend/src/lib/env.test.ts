// @vitest-environment node
import { readFileSync } from "node:fs";

import { describe, expect, it, vi } from "vitest";

import {
  EnvironmentError,
  parsePublicEnv,
  parseServerEnv,
  type PublicEnv,
} from "./env";

// "server-only" throws outside a React Server environment by design; the build
// guard itself is verified with `next build`, not in unit tests.
vi.mock("server-only", () => ({}));

function problemsFor(source: Record<string, string>): string {
  try {
    parseServerEnv(source);
  } catch (error) {
    expect(error).toBeInstanceOf(EnvironmentError);
    return (error as EnvironmentError).message;
  }
  throw new Error("expected an EnvironmentError");
}

describe("parseServerEnv", () => {
  it("works with zero configuration in development", () => {
    expect(parseServerEnv({})).toEqual({
      appEnv: "development",
      apiBaseUrl: "http://localhost:8000",
      trustedProxyHops: 0,
    });
  });

  it("reads TRUSTED_PROXY_HOPS as an integer from 0 to 10 (T01-09A)", () => {
    expect(parseServerEnv({ TRUSTED_PROXY_HOPS: "2" }).trustedProxyHops).toBe(
      2,
    );
    expect(parseServerEnv({ TRUSTED_PROXY_HOPS: " 0 " }).trustedProxyHops).toBe(
      0,
    );
    for (const value of ["-1", "11", "two", "1.5", "0x2"]) {
      expect(problemsFor({ TRUSTED_PROXY_HOPS: value })).toContain(
        "TRUSTED_PROXY_HOPS: must be an integer from 0 to 10",
      );
    }
  });

  it.each(["development", "test", "staging", "production"])(
    "accepts APP_ENV=%s with an explicit API_BASE_URL",
    (appEnv) => {
      const env = parseServerEnv({
        APP_ENV: appEnv,
        API_BASE_URL: "https://api.mti360.example/",
      });

      expect(env.appEnv).toBe(appEnv);
      expect(env.apiBaseUrl).toBe("https://api.mti360.example");
    },
  );

  it("accepts the internal container URL", () => {
    expect(parseServerEnv({ API_BASE_URL: "http://api:8000" }).apiBaseUrl).toBe(
      "http://api:8000",
    );
  });

  it("rejects an unknown APP_ENV", () => {
    expect(problemsFor({ APP_ENV: "prod" })).toContain("APP_ENV");
  });

  it.each(["staging", "production"])(
    "requires API_BASE_URL in %s",
    (appEnv) => {
      expect(problemsFor({ APP_ENV: appEnv })).toContain(
        `API_BASE_URL: must be set explicitly in ${appEnv}`,
      );
    },
  );

  it.each([
    "not a url",
    "ftp://api.internal",
    "https://user:SENTINEL-4b1d@api.internal",
    "https://api.internal/?token=SENTINEL-4b1d",
    "https://api.internal/#SENTINEL-4b1d",
  ])("rejects API_BASE_URL %s without echoing it", (value) => {
    const message = problemsFor({ API_BASE_URL: value });

    expect(message).toContain("API_BASE_URL");
    expect(message).not.toContain("SENTINEL");
    expect(message).not.toContain(value);
  });
});

describe("parsePublicEnv", () => {
  it("exposes only the application name", () => {
    const env: PublicEnv = parsePublicEnv({
      NEXT_PUBLIC_APP_NAME: "MTI 360",
      API_BASE_URL: "http://api:8000",
      APP_ENV: "production",
    });

    expect(env).toEqual({ appName: "MTI 360" });
  });

  it("defaults the application name", () => {
    expect(parsePublicEnv({ NEXT_PUBLIC_APP_NAME: "  " }).appName).toBe(
      "MTI 360",
    );
  });
});

describe("env module", () => {
  it("is marked server-only", () => {
    const source = readFileSync(new URL("./env.ts", import.meta.url), "utf8");

    expect(source.split("\n")[0]).toBe('import "server-only";');
  });
});
