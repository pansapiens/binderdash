FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpam0g \
    libpam-modules \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Create user early to avoid permission issues
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copy backend dependencies first
COPY --chown=app:app backend/pyproject.toml backend/requirements.txt ./backend/
COPY --chown=app:app backend/scripts/ ./backend/scripts/
RUN pip install uv
RUN uv pip compile backend/pyproject.toml -o backend/requirements.txt && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy frontend files and install dependencies
COPY --chown=app:app frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./frontend/
COPY --chown=app:app frontend/ ./frontend/
RUN cd frontend && pnpm install

# Copy remaining backend files
COPY --chown=app:app backend/ ./backend/

# Build frontend after backend files are in place
ARG BUILD_FRONTEND=true
RUN if [ "$BUILD_FRONTEND" = "true" ]; then \
        cd frontend && \
        pnpm run build && \
        test -d ../backend/static/assets \
        || (echo "frontend build did not produce backend/static/assets" && exit 1); \
    fi

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]