# syntax=docker/dockerfile:1
# =============================================================================
# MTI 360 frontend image (T00-03) — production-shaped, multi-stage.
#
# Build context: REPOSITORY ROOT (the pnpm workspace and lockfile live there):
#     docker build -f frontend/Dockerfile -t mti360-frontend .
# The context is restricted by frontend/Dockerfile.dockerignore (allowlist).
#
# - Frozen, locked install with the pinned pnpm (packageManager, via Corepack).
# - Next.js standalone output (output: "standalone", outputFileTracingRoot =
#   repository root); the runtime contains only the traced server files.
# - Runtime runs as the non-root "node" user; application files are root-owned.
# - No secrets are baked in; .env files never enter the build context.
# =============================================================================

ARG NODE_IMAGE=node:24.21.0-trixie-slim

# --- base: Node + pinned pnpm -------------------------------------------------
FROM ${NODE_IMAGE} AS base
ENV PNPM_HOME=/pnpm \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    NEXT_TELEMETRY_DISABLED=1
ENV PATH="${PNPM_HOME}:${PATH}"
RUN corepack enable pnpm
WORKDIR /repo

# --- deps: install from the lockfile (cached layer) ----------------------------
FROM base AS deps
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/package.json ./frontend/
RUN --mount=type=cache,id=mti360-pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile

# --- builder: production build -------------------------------------------------
FROM deps AS builder
COPY frontend ./frontend
RUN pnpm --filter @mti360/frontend build

# --- runtime ---------------------------------------------------------------------
FROM ${NODE_IMAGE} AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
WORKDIR /app

# Standalone server (root-owned, read-only for the runtime user) + static assets.
COPY --from=builder /repo/frontend/.next/standalone ./
COPY --from=builder /repo/frontend/.next/static ./frontend/.next/static

# Only the Next.js cache directory is writable by the runtime user.
RUN mkdir -p /app/frontend/.next/cache && chown node:node /app/frontend/.next/cache

USER node

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "frontend/server.js"]
