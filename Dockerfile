# ──────────────────────────────────────────────────────────────
# Stage 1: System deps + CUDA runtime (rarely changes → cached)
# ──────────────────────────────────────────────────────────────
FROM nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Python 3.11 + ffmpeg — this layer changes almost never
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3.11-dev \
    ffmpeg \
    ca-certificates \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ──────────────────────────────────────────────────────────────
# Stage 2: uv + Python deps (rebuilds only when lock changes)
# ──────────────────────────────────────────────────────────────
FROM base AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Only dependency manifests — layer is cached until these change
COPY pyproject.toml uv.lock ./

# Install all deps WITHOUT the project itself
# --python ensures uv uses the system python, not a downloaded one
RUN uv sync --frozen --no-install-project --no-dev --python /usr/bin/python3.11

# ──────────────────────────────────────────────────────────────
# Stage 3: App code (rebuilds only when app/ or README changes)
# ──────────────────────────────────────────────────────────────
FROM deps AS app

COPY README.md ./
COPY app ./app

# Install the project package (deps already cached above)
RUN uv sync --frozen --no-dev --python /usr/bin/python3.11

# ──────────────────────────────────────────────────────────────
# Stage 4: Final runtime (slim — no uv, no build artifacts)
# ──────────────────────────────────────────────────────────────
FROM base AS runtime

WORKDIR /app

# Copy only the venv + app code from the build stage
COPY --from=app /app /app

RUN mkdir -p /app/uploads

# NVIDIA runtime env — tells the container to expose GPUs
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
