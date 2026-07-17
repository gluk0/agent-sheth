# --- build stage --------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependency layer (cached unless lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Project layer
COPY . .
RUN uv sync --frozen --no-dev

# --- runtime stage --------------------------------------------------------------
FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 scaffold
WORKDIR /app

COPY --from=builder --chown=scaffold:scaffold /app /app
# Pre-create with correct ownership so the VOLUME isn't root-owned.
RUN mkdir -p /app/data && chown scaffold:scaffold /app /app/data

USER scaffold
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data

VOLUME ["/app/data"]
CMD ["scaffold"]
