#!/usr/bin/env node
// MTI 360 — local port preflight.
//
//   pnpm ports:check                       same as `dev` (also runs before pnpm dev)
//   node scripts/port-preflight.mjs dev    native apps (pnpm dev) + their infrastructure
//   node scripts/port-preflight.mjs infra  before pnpm infra:up
//   node scripts/port-preflight.mjs stack  before pnpm stack:up (infra + app containers)
//
// Dependency-free (Node built-ins only). Read-only: it never stops, kills or
// restarts anything and never changes a port. It only
//   1. binds each MTI 360 host port for an instant on 127.0.0.1, 0.0.0.0, ::1
//      and :: (IPv6 only). Each family is probed separately because on Windows
//      a listener on one address does not block a bind on another: a foreign
//      [::]:3000 listener let MTI 360 bind 127.0.0.1:3000 while browsers sent
//      "localhost" to the other service (V-02);
//   2. asks `docker compose ps` (project "mti360", fixed in compose.yaml) which
//      ports are published by running MTI 360 containers, so its own
//      infrastructure is recognised and anything else is a conflict;
//   3. checks that the backend and frontend configuration point at those ports.
//
// Exits 1 on any conflict or configuration problem, 2 on a usage error.
// Output names variables, hosts and ports only — never credentials or values.

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Host ports. Defaults come from .env.example; `target` is the container port.
export const SERVICES = [
  { id: "frontend", label: "Frontend", variable: "FRONTEND_PORT", service: "frontend", target: 3000, group: "app" },
  { id: "api", label: "Backend API", variable: "API_PORT", service: "api", target: 8000, group: "app" },
  { id: "postgres", label: "PostgreSQL", variable: "POSTGRES_PORT", service: "postgres", target: 5432, group: "infra" },
  { id: "redis", label: "Redis", variable: "REDIS_PORT", service: "redis", target: 6379, group: "infra" },
  { id: "s3", label: "Object storage (S3)", variable: "S3_PORT", service: "object-storage", target: 8333, group: "infra" },
  { id: "smtp", label: "Mailpit SMTP", variable: "MAILPIT_SMTP_PORT", service: "mailpit", target: 1025, group: "infra" },
  { id: "mail-ui", label: "Mailpit web UI", variable: "MAILPIT_UI_PORT", service: "mailpit", target: 8025, group: "infra" },
];

export const MODES = ["dev", "infra", "stack"];

export const PROBES = [
  { host: "127.0.0.1", family: 4, label: "127.0.0.1" },
  { host: "0.0.0.0", family: 4, label: "0.0.0.0" },
  { host: "::1", family: 6, label: "::1" },
  { host: "::", family: 6, label: "::", ipv6Only: true },
];

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
const DATABASE_URLS = ["DATABASE_URL", "MIGRATIONS_DATABASE_URL", "READONLY_DATABASE_URL"];

// --- Environment files -------------------------------------------------------------

/** Minimal dotenv parser: KEY=VALUE, optional `export`, quotes and comments. */
export function parseEnv(text) {
  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/.exec(line);
    if (!match || line.trimStart().startsWith("#")) continue;
    let value = match[2].trim();
    const quoted = /^(['"])(.*)\1$/.exec(value);
    value = quoted ? quoted[2] : value.replace(/\s+#.*$/, "");
    values[match[1]] = value;
  }
  return values;
}

function readEnvFile(root, file) {
  const full = path.join(root, file);
  return existsSync(full) ? parseEnv(readFileSync(full, "utf8")) : {};
}

/** First defined, non-empty value across the sources (highest precedence first). */
function pick(name, ...sources) {
  for (const source of sources) {
    const value = source[name];
    if (value !== undefined && value !== "") return value;
  }
  return undefined;
}

/**
 * Effective host ports for a mode. Compose interpolates the shell environment,
 * then the root .env. The native dev servers (pnpm dev) read only the shell.
 */
export function resolvePorts({ mode, env, rootEnv, template }) {
  const ports = {};
  const problems = [];
  const warnings = [];
  for (const svc of SERVICES) {
    const native = mode === "dev" && svc.group === "app";
    const raw = native
      ? pick(svc.variable, env, template)
      : pick(svc.variable, env, rootEnv, template);
    const port = Number(raw);
    if (!Number.isInteger(port) || port < 1 || port > 65_535) {
      problems.push(`${svc.variable} must be a port number from 1 to 65535`);
      continue;
    }
    ports[svc.id] = port;
    const fromRoot = rootEnv[svc.variable];
    if (native && env[svc.variable] === undefined && fromRoot && Number(fromRoot) !== port) {
      warnings.push(
        `${svc.variable} in .env is ${fromRoot}, but pnpm dev reads only the shell and uses ${port}; export it or align .env`,
      );
    }
  }
  const seen = new Map();
  for (const svc of SERVICES) {
    const port = ports[svc.id];
    if (port === undefined) continue;
    if (seen.has(port)) problems.push(`${seen.get(port)} and ${svc.variable} both use port ${port}`);
    else seen.set(port, svc.variable);
  }
  return { ports, problems, warnings };
}

// --- Port probes -------------------------------------------------------------------

/** Bind host:port for an instant. Never connects to, or signals, another process. */
export function probeAddress(host, port, ipv6Only = false) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", (error) => {
      if (error.code === "EADDRINUSE") resolve("in-use");
      else if (error.code === "EACCES") resolve("reserved");
      else if (["EADDRNOTAVAIL", "EAFNOSUPPORT", "EINVAL"].includes(error.code)) resolve("unavailable");
      else resolve(`error:${error.code ?? "unknown"}`);
    });
    server.listen({ host, port, ipv6Only, exclusive: true }, () => {
      server.close(() => resolve("free"));
    });
  });
}

export async function probePort(port, probeFn = probeAddress) {
  const results = [];
  for (const probe of PROBES) {
    results.push({ ...probe, result: await probeFn(probe.host, port, probe.ipv6Only ?? false) });
  }
  return results;
}

// --- MTI 360 containers ------------------------------------------------------------

/** Parse `docker compose ps --format json` (one object per line, or an array). */
export function parseComposePs(text) {
  const trimmed = text.trim();
  if (!trimmed) return [];
  let rows;
  if (trimmed.startsWith("[")) {
    rows = JSON.parse(trimmed);
  } else {
    rows = trimmed.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  }
  return rows
    .filter((row) => (row.Project ?? "mti360") === "mti360")
    .map((row) => ({
      service: row.Service,
      name: row.Name ?? row.Names ?? row.Service,
      state: row.State,
      publishers: (row.Publishers ?? [])
        .filter((p) => p.PublishedPort)
        .map((p) => ({
          url: p.URL ?? "",
          published: Number(p.PublishedPort),
          target: Number(p.TargetPort),
          protocol: p.Protocol ?? "tcp",
        })),
    }));
}

/** Running MTI 360 containers. Docker being unavailable is reported, not fatal. */
export function readMtiContainers(root, run = execFileSync) {
  try {
    const output = run("docker", ["compose", "ps", "--format", "json"], {
      cwd: root,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 15_000,
    });
    return { available: true, containers: parseComposePs(output).filter((c) => c.state === "running") };
  } catch {
    return { available: false, containers: [] };
  }
}

// --- Classification ----------------------------------------------------------------

const labels = (probes) => probes.map((p) => p.label).join(", ");

/**
 * Who holds a port: "free", "mti" (the expected MTI 360 container) or
 * "conflict". MTI 360 publishes on 127.0.0.1 only, so with an MTI owner the
 * IPv4 probes are expected to be busy and any IPv6 listener is foreign.
 */
export function classifyPort(svc, port, probes, docker) {
  const reserved = probes.filter((p) => p.result === "reserved");
  if (reserved.length > 0) {
    return {
      status: "conflict",
      detail: `reserved by the operating system on ${labels(reserved)} (for example a Windows excluded port range)`,
    };
  }
  const errors = probes.filter((p) => p.result.startsWith("error:"));
  if (errors.length > 0) {
    return { status: "conflict", detail: `could not be checked on ${labels(errors)} (${errors[0].result})` };
  }
  const used = probes.filter((p) => p.result === "in-use");
  const owner = docker.containers.find((c) =>
    c.publishers.some((p) => p.published === port && p.protocol === "tcp"),
  );
  if (owner) {
    const publisher = owner.publishers.find((p) => p.published === port && p.protocol === "tcp");
    if (owner.service !== svc.service || publisher.target !== svc.target) {
      return {
        status: "conflict",
        detail: `published by MTI 360 service "${owner.service}" (container port ${publisher.target}), not "${svc.service}" (${svc.target})`,
      };
    }
    if (publisher.url && publisher.url !== "127.0.0.1") {
      return { status: "conflict", detail: `published on ${publisher.url}; MTI 360 publishes on 127.0.0.1 only` };
    }
    const foreignV6 = used.filter((p) => p.family === 6);
    if (foreignV6.length > 0) {
      return {
        status: "conflict",
        detail: `MTI 360 container ${owner.name} holds IPv4, but another listener holds ${labels(foreignV6)}; "localhost" can reach it instead`,
      };
    }
    return { status: "mti", detail: `MTI 360 container ${owner.name}` };
  }
  if (used.length === 0) return { status: "free", detail: "free" };
  const unknown = docker.available ? "" : " (Docker is not reachable, so MTI 360 containers could not be recognised)";
  return {
    status: "conflict",
    detail: `in use on ${labels(used)} by a process that is not a running MTI 360 container${unknown}`,
  };
}

/** Turn a classification into ok / warning / conflict for the mode. */
export function judge(mode, svc, classification) {
  const { status, detail } = classification;
  if (status === "conflict") return { level: "conflict", detail };
  if (mode === "dev" && svc.group === "app") {
    return status === "free"
      ? { level: "ok", detail }
      : { level: "conflict", detail: `${detail} already serves it (stop the app profile, or run only one of pnpm dev / pnpm stack:up)` };
  }
  if (mode === "dev" && status === "free") {
    return { level: "warning", detail: "not running (start it with pnpm infra:up)" };
  }
  return { level: "ok", detail };
}

// --- Configuration consistency ---------------------------------------------------------

function parseUrl(value) {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function urlPort(url, fallback) {
  return url.port ? Number(url.port) : fallback;
}

/**
 * Do the backend and frontend settings target the MTI 360 host ports? Only
 * loopback targets are compared; a remote host is the developer's choice.
 */
export function checkConfiguration({ ports, backend, frontendApiBaseUrl }) {
  const problems = [];
  const warnings = [];

  const target = (where, name, value, expected, label, variable, defaultPort) => {
    if (value === undefined || value === "") return;
    const url = parseUrl(value);
    if (!url) {
      problems.push(`${where} ${name} is not a valid URL`);
      return;
    }
    if (!LOOPBACK.has(url.hostname)) return;
    const port = urlPort(url, defaultPort);
    if (port !== expected) {
      problems.push(
        `${where} ${name} points to ${url.hostname}:${port}, but ${label} is on ${expected} (${variable})`,
      );
    }
    if (url.hostname === "localhost") {
      warnings.push(`${where} ${name} uses "localhost"; prefer 127.0.0.1 so IPv6 (::1) listeners cannot intercept it`);
    }
  };

  for (const name of DATABASE_URLS) {
    target("backend", name, backend[name], ports.postgres, "PostgreSQL", "POSTGRES_PORT", 5432);
  }
  target("backend", "REDIS_URL", backend.REDIS_URL, ports.redis, "Redis", "REDIS_PORT", 6379);
  target("backend", "S3_ENDPOINT_URL", backend.S3_ENDPOINT_URL, ports.s3, "object storage", "S3_PORT", 80);
  target("frontend", "API_BASE_URL", frontendApiBaseUrl, ports.api, "the backend API", "API_PORT", 80);

  if (backend.SMTP_HOST && LOOPBACK.has(backend.SMTP_HOST)) {
    const smtpPort = Number(backend.SMTP_PORT);
    if (smtpPort !== ports.smtp) {
      problems.push(`backend SMTP_PORT is ${backend.SMTP_PORT}, but Mailpit SMTP is on ${ports.smtp} (MAILPIT_SMTP_PORT)`);
    }
  }

  const origin = `http://localhost:${ports.frontend}`;
  const origins = (backend.CORS_ALLOWED_ORIGINS ?? "")
    .split(",")
    .map((o) => o.trim().replace(/\/+$/, ""))
    .filter(Boolean);
  if (!origins.includes(origin)) {
    problems.push(`backend CORS_ALLOWED_ORIGINS does not include ${origin} (the frontend origin)`);
  }
  for (const other of origins) {
    const url = parseUrl(other);
    if (other !== origin && url && LOOPBACK.has(url.hostname)) {
      warnings.push(`backend CORS_ALLOWED_ORIGINS also allows ${other}, which is not the MTI 360 frontend`);
    }
  }

  const base = (backend.APP_BASE_URL ?? "").replace(/\/+$/, "");
  const baseUrl = parseUrl(base);
  if (!baseUrl) {
    problems.push("backend APP_BASE_URL is not a valid URL");
  } else if (LOOPBACK.has(baseUrl.hostname) && base !== origin) {
    problems.push(`backend APP_BASE_URL is ${base}, but the frontend origin is ${origin}`);
  }

  return { problems, warnings };
}

/** Effective backend and frontend settings, mirroring how each app loads them. */
export function loadAppSettings(root, env) {
  const backendTemplate = readEnvFile(root, "backend/.env.example");
  const backendFile = readEnvFile(root, "backend/.env");
  const backend = {};
  for (const name of [...DATABASE_URLS, "REDIS_URL", "S3_ENDPOINT_URL", "SMTP_HOST", "SMTP_PORT", "CORS_ALLOWED_ORIGINS", "APP_BASE_URL"]) {
    backend[name] = pick(name, env, backendFile, backendTemplate);
  }
  // Next.js precedence in development (frontend/.env.example holds the default).
  const frontendSources = [
    ".env.development.local",
    ".env.local",
    ".env.development",
    ".env",
    ".env.example",
  ].map((file) => readEnvFile(root, `frontend/${file}`));
  return { backend, frontendApiBaseUrl: pick("API_BASE_URL", env, ...frontendSources) };
}

// --- Report ------------------------------------------------------------------------

export async function runPreflight({
  mode,
  root = ROOT,
  env = process.env,
  rootEnv = readEnvFile(root, ".env"),
  probe = probePort,
  docker = () => readMtiContainers(root),
  settings = () => loadAppSettings(root, env),
}) {
  const lines = [`MTI 360 port preflight (${mode})`];
  const template = readEnvFile(root, ".env.example");
  const resolved = resolvePorts({ mode, env, rootEnv, template });
  const problems = [...resolved.problems];
  const warnings = [...resolved.warnings];
  let conflicts = 0;

  if (problems.length === 0) {
    const state = docker();
    const services = SERVICES.filter((svc) => mode !== "infra" || svc.group === "infra");
    for (const svc of services) {
      const port = resolved.ports[svc.id];
      const verdict = judge(mode, svc, classifyPort(svc, port, await probe(port), state));
      if (verdict.level === "conflict") conflicts += 1;
      const tag = { ok: "ok", warning: "warning", conflict: "CONFLICT" }[verdict.level];
      lines.push(`  ${tag.padEnd(9)} ${svc.label.padEnd(20)} ${String(port).padEnd(6)} ${verdict.detail}`);
    }
    if (mode === "dev") {
      const config = checkConfiguration({ ports: resolved.ports, ...settings() });
      problems.push(...config.problems);
      warnings.push(...config.warnings);
    }
  }

  for (const problem of problems) lines.push(`  PROBLEM   ${problem}`);
  for (const warning of warnings) lines.push(`  warning   ${warning}`);
  const failed = conflicts > 0 || problems.length > 0;
  lines.push(
    failed
      ? "Preflight failed. Nothing was stopped or changed. Free each conflicting port or choose another *_PORT, and align the settings above (docs/runbooks/local-development.md, Ports)."
      : "Preflight passed.",
  );
  return { exitCode: failed ? 1 : 0, lines };
}

const invokedDirectly = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (invokedDirectly) {
  const mode = process.argv[2] ?? "dev";
  if (!MODES.includes(mode)) {
    console.error(`usage: node scripts/port-preflight.mjs [${MODES.join("|")}]`);
    process.exit(2);
  }
  const { exitCode, lines } = await runPreflight({ mode });
  (exitCode === 0 ? console.log : console.error)(lines.join("\n"));
  process.exitCode = exitCode;
}
