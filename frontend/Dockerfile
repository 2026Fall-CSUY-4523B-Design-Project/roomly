# Build context is the repository root.
FROM node:24-slim AS build

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NEXT_TELEMETRY_DISABLED=1
RUN npm install --global pnpm@10.10.0

WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
# Baked into the /api rewrite at build time; also read from the environment at runtime.
ARG ROOMLY_API_URL=http://api:8000
ENV ROOMLY_API_URL=${ROOMLY_API_URL}
RUN pnpm build && pnpm prune --prod


FROM node:24-slim

ENV NODE_ENV=production \
    NODE_OPTIONS=--openssl-legacy-provider \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app

RUN groupadd --system --gid 10001 roomly \
 && useradd --system --uid 10001 --gid roomly --no-create-home --shell /usr/sbin/nologin roomly

USER 10001:10001
EXPOSE 3000

CMD ["node_modules/.bin/next", "start", "-H", "0.0.0.0", "-p", "3000"]
