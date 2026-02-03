FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (ffmpeg for audio conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (locked, no dev deps, no project install yet)
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY app ./app
COPY README.md ./

# Install the project itself (uses the already-cached dependencies)
RUN uv sync --frozen --no-dev

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

# Run via uv so the virtualenv is activated
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
