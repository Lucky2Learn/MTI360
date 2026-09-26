#!/usr/bin/env node
// MTI 360 — environment template and secret hygiene check (T00-04).
//
//   pnpm check:env        (also part of `pnpm check`)
//
// Dependency-free (Node built-ins only). Fails when:
//   1. a real environment file (.env, .env.local, *.env, .envrc …) is tracked;
//   2. a tracked *.env.example template holds anything other than an empty
//      value or the `change-me` placeholder in a secret-like variable
//      (*SECRET*, *PASSWORD*, *TOKEN*, *_KEY) or in URL credentials;
//   3. a NEXT_PUBLIC_* variable (in a template or in frontend source) has a
//      secret-like name — NEXT_PUBLIC_ values are shipped to every browser;
//   4. backend/.env.example and the backend Settings fields drift apart.
//
// Output names files, lines and variables only — never values.
// Full secret scanning (gitleaks) is added in CI by T00-05.

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const PLACEHOLDERS = new Set(["", "change-me"]);
const SECRET_NAME = /SECRET|PASSWORD|TOKEN|_KEY$/;
const PUBLIC_NAME = /\bNEXT_PUBLIC_[A-Z0-9_]+/g;
const URL_CREDENTIALS = /^[a-z][a-z0-9+.-]*:\/\/[^/@:\s]*:([^/@\s]*)@/i;

const BACKEND_TEMPLATE = "backend/.env.example";
const BACKEND_SETTINGS = "backend/app/core/config.py";

const root = execFileSync("git", ["rev-parse", "--show-toplevel"], {
  encoding: "utf8",
}).trim();
const tracked = execFileSync("git", ["ls-files", "-z"], {
  cwd: root,
  encoding: "utf8",
})
  .split("\0")
  .filter((file) => file && existsSync(path.join(root, file)));

const problems = [];
const read = (file) => readFileSync(path.join(root, file), "utf8");

function isEnvFile(file) {
  const name = path.posix.basename(file);
  if (name.endsWith(".example")) return false;
  return /^\.env(\..+)?$/.test(name) || name.endsWith(".env") || name === ".envrc";
}

function parseTemplate(file) {
  const entries = [];
  read(file)
    .split(/\r?\n/)
    .forEach((line, index) => {
      const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/.exec(line);
      if (match && !line.trimStart().startsWith("#")) {
        const value = match[2].trim().replace(/^(['"])(.*)\1$/, "$2");
        entries.push({ name: match[1], value, line: index + 1 });
      }
    });
  return entries;
}

function settingsFields(file) {
  const lines = read(file).split(/\r?\n/);
  const start = lines.findIndex((line) => /^class Settings\b/.test(line));
  if (start === -1) return null;
  const fields = new Set();
  for (const line of lines.slice(start + 1)) {
    if (/^\S/.test(line) && !line.startsWith("#")) break; // end of class body
    const match = /^ {4}([a-z][a-z0-9_]*)\s*:\s/.exec(line);
    if (match) fields.add(match[1].toUpperCase());
  }
  return fields;
}

// 1. Real environment files must never be tracked.
for (const file of tracked.filter(isEnvFile)) {
  problems.push(`${file}: real environment file is tracked (remove it from git)`);
}

// 2 + 3. Templates hold placeholders only; no secret-like public variables.
const templates = tracked.filter((file) => path.posix.basename(file).endsWith(".env.example"));
for (const file of templates) {
  for (const { name, value, line } of parseTemplate(file)) {
    const where = `${file}:${line} ${name}`;
    if (SECRET_NAME.test(name) && !PLACEHOLDERS.has(value)) {
      problems.push(`${where}: secret-like variable must be empty or "change-me"`);
    }
    const credentials = URL_CREDENTIALS.exec(value);
    if (credentials && !PLACEHOLDERS.has(decodeURIComponent(credentials[1]))) {
      problems.push(`${where}: URL password must be "change-me"`);
    }
    if (name.startsWith("NEXT_PUBLIC_") && SECRET_NAME.test(name)) {
      problems.push(`${where}: NEXT_PUBLIC_ variables are public and must not hold secrets`);
    }
  }
}

const frontendSources = tracked.filter((file) => /^frontend\/src\/.+\.(ts|tsx|mts|js|jsx)$/.test(file));
for (const file of frontendSources) {
  for (const name of new Set(read(file).match(PUBLIC_NAME) ?? [])) {
    if (SECRET_NAME.test(name)) {
      problems.push(`${file} ${name}: NEXT_PUBLIC_ variables are public and must not hold secrets`);
    }
  }
}

// 4. backend/.env.example <-> Settings.
if (!tracked.includes(BACKEND_TEMPLATE) || !tracked.includes(BACKEND_SETTINGS)) {
  problems.push(`${BACKEND_TEMPLATE} and ${BACKEND_SETTINGS} must both exist`);
} else {
  const fields = settingsFields(BACKEND_SETTINGS);
  if (fields === null) {
    problems.push(`${BACKEND_SETTINGS}: class Settings not found`);
  } else {
    const declared = new Set(parseTemplate(BACKEND_TEMPLATE).map((entry) => entry.name));
    for (const name of declared) {
      if (!fields.has(name)) problems.push(`${BACKEND_TEMPLATE} ${name}: no matching Settings field`);
    }
    for (const name of fields) {
      if (!declared.has(name)) problems.push(`${BACKEND_SETTINGS} ${name}: missing from ${BACKEND_TEMPLATE}`);
    }
  }
}

if (problems.length > 0) {
  console.error(`check:env failed (${problems.length} problem(s)):`);
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}
console.log(
  `check:env passed: ${templates.length} template(s), ${tracked.length} tracked file(s), no real .env files.`,
);
