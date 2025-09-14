FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend dependencies first
COPY backend/pyproject.toml backend/requirements.txt ./
COPY backend/scripts/ ./scripts/
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend files and install dependencies
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/ ./
RUN pnpm install

# Copy backend files
COPY backend/ ./

# Build frontend after backend files are in place
ARG BUILD_FRONTEND=true
RUN if [ "$BUILD_FRONTEND" = "true" ]; then \
        mkdir -p backend/static && \
        cd /app && pnpm run build; \
    fi

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]