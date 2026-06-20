# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user + writable data dir. Rarely changes -> keep high in the cache.
RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /app/data \
    && chown bot:bot /app/data

WORKDIR /app

# 1) Dependency layer: invalidated only when pyproject.toml changes.
#    Build against a stub package so deps install without the real source.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p src && touch src/__init__.py \
    && pip install . \
    && rm -rf src

# 2) App layer: source edits reinstall only the package, not the dependencies.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps --force-reinstall .

USER bot

CMD ["sc-bot"]
