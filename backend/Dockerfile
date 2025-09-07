# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and pnpm for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend dependencies first for better caching
COPY backend/pyproject.toml backend/requirements.txt ./
COPY backend/scripts/ ./scripts/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend package files
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/ ./

# Install frontend dependencies and build
RUN pnpm install && pnpm run build

# Copy backend source code
COPY backend/ ./

# Move static files to the correct location for the backend
RUN if [ -d "static" ]; then \
        mkdir -p backend/static && \
        cp -r static/* backend/static/; \
    fi

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
