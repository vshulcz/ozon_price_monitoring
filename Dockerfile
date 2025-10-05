FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

ENV DATABASE_PATH=/app/data/ozonbot.db

RUN mkdir -p /app/data

CMD ["python", "-m", "app.bot"]