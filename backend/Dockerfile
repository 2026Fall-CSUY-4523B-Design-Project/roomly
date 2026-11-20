# Build context is the repository root: the API needs db/migrations next to the wheel.
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM python:3.14-slim

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Dependencies first: a source-only change reuses this layer.
COPY backend/uv.lock backend/pyproject.toml ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --frozen --no-dev

# Migrations ship in the image; the API applies them on start.
COPY db/migrations ./db/migrations
ENV ROOMLY_MIGRATIONS_DIR=/app/db/migrations

RUN groupadd --system --gid 10001 roomly \
 && useradd --system --uid 10001 --gid roomly --no-create-home --shell /usr/sbin/nologin roomly \
 && chown -R 10001:10001 /app

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "roomly.main"]
