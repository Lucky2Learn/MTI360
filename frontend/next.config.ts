import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// The pnpm workspace root (pnpm-workspace.yaml, pnpm-lock.yaml) is the
// repository root, one level above frontend/. File tracing must start there so
// the standalone output includes workspace-linked dependencies.
const workspaceRoot = fileURLToPath(new URL("..", import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Do not advertise the framework in response headers.
  poweredByHeader: false,
  // Self-contained server for the Docker image (T00-03):
  // .next/standalone/frontend/server.js
  output: "standalone",
  outputFileTracingRoot: workspaceRoot,
};

export default nextConfig;
