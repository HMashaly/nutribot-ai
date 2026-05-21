FROM python:3.11-slim

# System deps for psycopg.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install a pinned uv binary for reproducible builds.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install locked dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable

# Copy the application and install the project itself.
COPY . .
RUN chmod +x docker-entrypoint.sh \
    && uv sync --locked --no-editable

EXPOSE 8000
CMD ["./docker-entrypoint.sh"]
