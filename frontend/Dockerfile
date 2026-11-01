# Frontend Dockerfile
# Supports two targets:
#   --target dev   — install deps only, run `pnpm dev` at container start
#   --target prod  — full build baked in, run the standalone Node server (default if no --target is specified)

ARG PNPM_STORE_PATH=/root/.local/share/pnpm/store
ARG NPM_REGISTRY

# ── Base: shared setup ────────────────────────────────────────────────────────
FROM node:22-alpine AS base
ARG PNPM_STORE_PATH
ARG NPM_REGISTRY
# Configure corepack registry before installing pnpm so the download itself
# succeeds in restricted networks (COREPACK_NPM_REGISTRY controls where
# corepack fetches package managers from).
RUN if [ -n "${NPM_REGISTRY}" ]; then \
      export COREPACK_NPM_REGISTRY="${NPM_REGISTRY}"; \
    fi && \
    corepack enable && corepack install -g pnpm@10.26.2
RUN pnpm config set store-dir ${PNPM_STORE_PATH}
# Optionally override npm registry for restricted networks (e.g. NPM_REGISTRY=https://registry.npmmirror.com)
RUN if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi
WORKDIR /app

# Dependency layer changes only when manifests or the lockfile change.
FROM base AS deps
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/
RUN cd /app/frontend && pnpm install --frozen-lockfile

# ── Dev: full dependencies + source, CMD is overridden by docker-compose ─────
FROM deps AS dev
COPY frontend ./frontend
EXPOSE 3000

# ── Builder: install + compile Next.js ───────────────────────────────────────
FROM deps AS builder
COPY frontend ./frontend
# Skip env validation — runtime vars are injected by nginx/container
# App version stamp for the About page. Nightly CI passes
# APP_VERSION=<base>-nightly.<date>-<sha>; release/local builds leave it empty
# and the frontend falls back to package.json's version.
ARG APP_VERSION=""
ENV NEXT_PUBLIC_APP_VERSION=$APP_VERSION
RUN cd /app/frontend && SKIP_ENV_VALIDATION=1 NEXT_CONFIG_BUILD_OUTPUT=standalone pnpm build

# ── Prod: minimal runtime with pre-built output ───────────────────────────────
FROM node:22-alpine AS prod
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
WORKDIR /app
# Next.js tracing omits public/static assets; copy them explicitly.
COPY --from=builder /app/frontend/.next/standalone ./
COPY --from=builder /app/frontend/public ./public
COPY --from=builder /app/frontend/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
