// Tests for scripts/port-preflight.mjs (pnpm test:scripts).
//
// Real sockets on OS-assigned ports cover free, IPv4, IPv6 and wildcard
// listeners; the rest uses injected probes and container lists. Nothing here
// touches Docker, the network beyond loopback, or any fixed port.

import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";

import {
  checkConfiguration,
  classifyPort,
  judge,
  loadAppSettings,
  parseComposePs,
  parseEnv,
  probePort,
  resolvePorts,
  ROOT,
  runPreflight,
  SERVICES,
} from "./port-preflight.mjs";

const read = (file) => readFileSync(path.join(ROOT, file), "utf8");
const svc = (id) => SERVICES.find((s) => s.id === id);
const NO_DOCKER = { available: true, containers: [] };

function listen(host, ipv6Only = false) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen({ host, port: 0, ipv6Only }, () => resolve(server));
  });
}
const close = (server) => new Promise((resolve) => server.close(resolve));

async function freePort() {
  const server = await listen("127.0.0.1");
  const { port } = server.address();
  await close(server);
  return port;
}

const ipv6 = await listen("::1").then(
  async (server) => {
    await close(server);
    return true;
  },
  () => false,
);

const byHost = (results) => Object.fromEntries(results.map((r) => [r.host, r.result]));
const probesWith = (busy = {}) =>
  ["127.0.0.1", "0.0.0.0", "::1", "::"].map((host) => ({
    host,
    family: host.includes(":") ? 6 : 4,
    label: host,
    result: busy[host] ?? "free",
  }));
const container = (service, published, target, url = "127.0.0.1") => ({
  service,
  name: `mti360-${service}-1`,
  state: "running",
  publishers: [{ url, published, target, protocol: "tcp" }],
});

describe("probePort (real sockets)", () => {
  it("reports a free port as free on every address", async () => {
    const results = byHost(await probePort(await freePort()));
    assert.deepEqual(results["127.0.0.1"], "free");
    assert.deepEqual(results["0.0.0.0"], "free");
    if (ipv6) {
      assert.equal(results["::1"], "free");
      assert.equal(results["::"], "free");
    }
  });

  it("detects an IPv4 loopback listener", async () => {
    const server = await listen("127.0.0.1");
    try {
      const results = byHost(await probePort(server.address().port));
      assert.equal(results["127.0.0.1"], "in-use");
    } finally {
      await close(server);
    }
  });

  it("detects an IPv4 wildcard listener", async () => {
    const server = await listen("0.0.0.0");
    try {
      const results = await probePort(server.address().port);
      assert.ok(results.some((r) => r.family === 4 && r.result === "in-use"));
    } finally {
      await close(server);
    }
  });

  it("detects an IPv6 loopback listener that leaves 127.0.0.1 free", { skip: !ipv6 && "no IPv6" }, async () => {
    const server = await listen("::1");
    try {
      const results = byHost(await probePort(server.address().port));
      assert.equal(results["::1"], "in-use");
      const verdict = classifyPort(svc("frontend"), server.address().port, await probePort(server.address().port), NO_DOCKER);
      assert.equal(verdict.status, "conflict");
    } finally {
      await close(server);
    }
  });

  it("detects an IPv6 wildcard listener", { skip: !ipv6 && "no IPv6" }, async () => {
    const server = await listen("::", true);
    try {
      const results = await probePort(server.address().port);
      assert.ok(results.some((r) => r.family === 6 && r.result === "in-use"));
    } finally {
      await close(server);
    }
  });
});

describe("classifyPort", () => {
  it("is free when nothing listens", () => {
    assert.equal(classifyPort(svc("api"), 8100, probesWith(), NO_DOCKER).status, "free");
  });

  it("is a conflict when a non-MTI process listens on any family", () => {
    for (const host of ["127.0.0.1", "0.0.0.0", "::1", "::"]) {
      const verdict = classifyPort(svc("api"), 8100, probesWith({ [host]: "in-use" }), NO_DOCKER);
      assert.equal(verdict.status, "conflict", host);
      assert.match(verdict.detail, /not a running MTI 360 container/);
    }
  });

  it("recognises the expected running MTI 360 container", () => {
    const docker = { available: true, containers: [container("postgres", 15432, 5432)] };
    const verdict = classifyPort(svc("postgres"), 15432, probesWith({ "127.0.0.1": "in-use", "0.0.0.0": "in-use" }), docker);
    assert.deepEqual(verdict, { status: "mti", detail: "MTI 360 container mti360-postgres-1" });
  });

  it("flags a foreign IPv6 listener beside the MTI 360 container", () => {
    const docker = { available: true, containers: [container("postgres", 15432, 5432)] };
    const verdict = classifyPort(svc("postgres"), 15432, probesWith({ "127.0.0.1": "in-use", "::1": "in-use" }), docker);
    assert.equal(verdict.status, "conflict");
    assert.match(verdict.detail, /localhost/);
  });

  it("flags a port published by the wrong MTI 360 service or beyond loopback", () => {
    const wrong = { available: true, containers: [container("redis", 15432, 6379)] };
    assert.equal(classifyPort(svc("postgres"), 15432, probesWith({ "127.0.0.1": "in-use" }), wrong).status, "conflict");
    const exposed = { available: true, containers: [container("postgres", 15432, 5432, "0.0.0.0")] };
    assert.equal(classifyPort(svc("postgres"), 15432, probesWith({ "0.0.0.0": "in-use" }), exposed).status, "conflict");
  });

  it("treats an OS-reserved port as a conflict", () => {
    const verdict = classifyPort(svc("frontend"), 3100, probesWith({ "127.0.0.1": "reserved" }), NO_DOCKER);
    assert.equal(verdict.status, "conflict");
    assert.match(verdict.detail, /reserved/);
  });

  it("says when Docker could not be asked", () => {
    const verdict = classifyPort(svc("redis"), 16379, probesWith({ "127.0.0.1": "in-use" }), { available: false, containers: [] });
    assert.match(verdict.detail, /Docker is not reachable/);
  });
});

describe("judge (per mode)", () => {
  const mti = { status: "mti", detail: "MTI 360 container mti360-api-1" };
  const free = { status: "free", detail: "free" };

  it("dev: app ports must be free, even of MTI 360 containers", () => {
    assert.equal(judge("dev", svc("api"), free).level, "ok");
    assert.equal(judge("dev", svc("api"), mti).level, "conflict");
  });

  it("dev: stopped infrastructure is a warning, running MTI infrastructure is fine", () => {
    assert.equal(judge("dev", svc("postgres"), free).level, "warning");
    assert.equal(judge("dev", svc("postgres"), mti).level, "ok");
  });

  it("infra and stack: free or already MTI 360 is fine", () => {
    for (const mode of ["infra", "stack"]) {
      assert.equal(judge(mode, svc("redis"), free).level, "ok");
      assert.equal(judge(mode, svc("redis"), mti).level, "ok");
      assert.equal(judge(mode, svc("redis"), { status: "conflict", detail: "x" }).level, "conflict");
    }
  });
});

describe("parseComposePs", () => {
  const row = {
    Project: "mti360",
    Service: "postgres",
    Name: "mti360-postgres-1",
    State: "running",
    Publishers: [{ URL: "127.0.0.1", TargetPort: 5432, PublishedPort: 15432, Protocol: "tcp" }],
  };

  it("reads one object per line and arrays", () => {
    const expected = [container("postgres", 15432, 5432)];
    assert.deepEqual(parseComposePs(`${JSON.stringify(row)}\n`), expected);
    assert.deepEqual(parseComposePs(JSON.stringify([row])), expected);
    assert.deepEqual(parseComposePs(""), []);
  });

  it("ignores other projects and unpublished ports", () => {
    const other = { ...row, Project: "another" };
    const internal = { ...row, Publishers: [{ URL: "", TargetPort: 5432, PublishedPort: 0, Protocol: "tcp" }] };
    assert.deepEqual(parseComposePs([other, internal].map((r) => JSON.stringify(r)).join("\n")), [
      { ...container("postgres", 15432, 5432), publishers: [] },
    ]);
  });
});

describe("resolvePorts", () => {
  const template = parseEnv(read(".env.example"));

  it("uses the MTI 360 port policy by default", () => {
    const { ports, problems } = resolvePorts({ mode: "stack", env: {}, rootEnv: {}, template });
    assert.deepEqual(problems, []);
    assert.deepEqual(ports, {
      frontend: 3100,
      api: 8100,
      postgres: 15432,
      redis: 16379,
      s3: 18333,
      smtp: 11025,
      "mail-ui": 18025,
    });
  });

  it("native dev reads app ports from the shell only and warns about .env drift", () => {
    const rootEnv = { API_PORT: "8200", POSTGRES_PORT: "25432" };
    const { ports, warnings } = resolvePorts({ mode: "dev", env: {}, rootEnv, template });
    assert.equal(ports.api, 8100);
    assert.equal(ports.postgres, 25432);
    assert.match(warnings.join("\n"), /API_PORT in .env is 8200/);
    assert.equal(resolvePorts({ mode: "dev", env: { API_PORT: "8300" }, rootEnv, template }).ports.api, 8300);
  });

  it("rejects invalid and duplicate ports", () => {
    const bad = resolvePorts({ mode: "stack", env: { API_PORT: "http" }, rootEnv: {}, template });
    assert.match(bad.problems.join("\n"), /API_PORT must be a port number/);
    const dup = resolvePorts({ mode: "stack", env: { REDIS_PORT: "15432" }, rootEnv: {}, template });
    assert.match(dup.problems.join("\n"), /POSTGRES_PORT and REDIS_PORT both use port 15432/);
  });
});

describe("checkConfiguration", () => {
  const ports = { frontend: 3100, api: 8100, postgres: 15432, redis: 16379, s3: 18333, smtp: 11025, "mail-ui": 18025 };
  const backend = parseEnv(read("backend/.env.example"));
  const frontendApiBaseUrl = parseEnv(read("frontend/.env.example")).API_BASE_URL;

  it("accepts the committed templates without problems or warnings", () => {
    assert.deepEqual(checkConfiguration({ ports, backend, frontendApiBaseUrl }), { problems: [], warnings: [] });
  });

  it("reports stale ports, origins and localhost targets without printing credentials", () => {
    const secret = "s3cr3t-Value-42";
    const stale = {
      ...backend,
      DATABASE_URL: `postgresql+asyncpg://mti_app:${secret}@localhost:5432/mti360`,
      REDIS_URL: "redis://127.0.0.1:6379/0",
      CORS_ALLOWED_ORIGINS: "http://localhost:3000",
      APP_BASE_URL: "http://localhost:3000",
      SMTP_PORT: "1025",
    };
    const { problems, warnings } = checkConfiguration({ ports, backend: stale, frontendApiBaseUrl: "http://localhost:8000" });
    const text = [...problems, ...warnings].join("\n");
    assert.match(text, /DATABASE_URL points to localhost:5432, but PostgreSQL is on 15432/);
    assert.match(text, /REDIS_URL points to 127.0.0.1:6379/);
    assert.match(text, /CORS_ALLOWED_ORIGINS does not include http:\/\/localhost:3100/);
    assert.match(text, /APP_BASE_URL is http:\/\/localhost:3000/);
    assert.match(text, /SMTP_PORT is 1025/);
    assert.match(text, /API_BASE_URL points to localhost:8000/);
    assert.match(text, /prefer 127.0.0.1/);
    assert.ok(!text.includes(secret), "a credential leaked into the output");
    assert.ok(!text.includes("mti_app"), "a user name leaked into the output");
  });

  it("leaves remote (non-loopback) targets alone", () => {
    const remote = { ...backend, REDIS_URL: "redis://cache.internal:6379/0" };
    assert.deepEqual(checkConfiguration({ ports, backend: remote, frontendApiBaseUrl }).problems, []);
  });
});

describe("single source of truth", () => {
  const template = parseEnv(read(".env.example"));

  it("compose.yaml fallbacks match .env.example", () => {
    const fallbacks = [...read("compose.yaml").matchAll(/\$\{([A-Z_]+_PORT):-(\d+)\}/g)];
    assert.ok(fallbacks.length >= SERVICES.length);
    for (const [, variable, value] of fallbacks) assert.equal(value, template[variable], variable);
  });

  it("the native dev scripts and frontend default match .env.example", () => {
    for (const file of ["package.json", "frontend/package.json"]) {
      for (const [, variable, value] of read(file).matchAll(/\$\{([A-Z_]+_PORT):-(\d+)\}/g)) {
        assert.equal(value, template[variable], `${file} ${variable}`);
      }
    }
    assert.match(read("frontend/src/lib/env.ts"), new RegExp(`"http://127\\.0\\.0\\.1:${template.API_PORT}"`));
  });

});

describe("loadAppSettings", () => {
  it("applies shell > local file > template, as the apps do", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "mti360-preflight-"));
    try {
      mkdirSync(path.join(dir, "backend"));
      mkdirSync(path.join(dir, "frontend"));
      writeFileSync(path.join(dir, "backend/.env.example"), "REDIS_URL=redis://127.0.0.1:16379/0\nSMTP_PORT=11025\n");
      writeFileSync(path.join(dir, "backend/.env"), "REDIS_URL=redis://127.0.0.1:26379/0\n");
      writeFileSync(path.join(dir, "frontend/.env.example"), "API_BASE_URL=http://127.0.0.1:8100\n");
      writeFileSync(path.join(dir, "frontend/.env.local"), "API_BASE_URL=http://127.0.0.1:8200\n");

      const fromFiles = loadAppSettings(dir, {});
      assert.equal(fromFiles.backend.REDIS_URL, "redis://127.0.0.1:26379/0");
      assert.equal(fromFiles.backend.SMTP_PORT, "11025");
      assert.equal(fromFiles.frontendApiBaseUrl, "http://127.0.0.1:8200");

      const fromShell = loadAppSettings(dir, { API_BASE_URL: "http://127.0.0.1:8300" });
      assert.equal(fromShell.frontendApiBaseUrl, "http://127.0.0.1:8300");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("runPreflight", () => {
  const docker = () => NO_DOCKER;
  const settings = () => ({
    backend: parseEnv(read("backend/.env.example")),
    frontendApiBaseUrl: parseEnv(read("frontend/.env.example")).API_BASE_URL,
  });

  it("passes with free app ports and warns that infrastructure is stopped", async () => {
    const { exitCode, lines } = await runPreflight({ mode: "dev", env: {}, rootEnv: {}, probe: async () => probesWith(), docker, settings });
    assert.equal(exitCode, 0, lines.join("\n"));
    assert.match(lines.join("\n"), /warning\s+PostgreSQL\s+15432\s+not running/);
  });

  it("fails on an occupied port without changing anything", async () => {
    const probe = async (port) => probesWith(port === 8100 ? { "::": "in-use" } : {});
    const { exitCode, lines } = await runPreflight({ mode: "dev", env: {}, rootEnv: {}, probe, docker, settings });
    assert.equal(exitCode, 1);
    assert.match(lines.join("\n"), /CONFLICT\s+Backend API\s+8100/);
    assert.match(lines.at(-1), /Nothing was stopped or changed/);
  });

  it("infra mode checks infrastructure ports only", async () => {
    const seen = [];
    const probe = async (port) => {
      seen.push(port);
      return probesWith();
    };
    const { exitCode } = await runPreflight({ mode: "infra", env: {}, rootEnv: {}, probe, docker, settings });
    assert.equal(exitCode, 0);
    assert.deepEqual(seen.sort(), [11025, 15432, 16379, 18025, 18333]);
  });
});
