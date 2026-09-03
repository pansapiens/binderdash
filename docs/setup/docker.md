# Docker Setup

This document describes the Docker containerization setup for Binderdash.

## Overview

The application is containerized using a single Docker image that:

- Builds the frontend (Vue.js + Vite) during the Docker build process
- Serves both the backend API and frontend static files via FastAPI
- Mounts data directories as read-only volumes for security
- Includes health checks and resource limits

For PAM authentication inside Docker (bind-mounting `/etc/passwd`/`/etc/group`/`/etc/shadow`, the `shadow` group requirement, and container-recreate gotchas), see [Authentication setup](authentication.md#auth-type-3-pam-usernamepassword-unix-accounts).

## Prerequisites

### Host Directory Setup

Before running the containerized application, ensure the directories specified in `RUN_BASE_DIRS` exist and are accessible on the host. They should contain your protein binder design run data; the container mounts them as read-only volumes.

```bash
# Example: make directories readable by the container user (UID 1000)
sudo chown -R 1000:1000 /data/runs /data2/runs
sudo chmod -R 755 /data/runs /data2/runs
```

### Environment Configuration

1. **Create `.env` file**: copy from `.env.example` and configure:

   ```bash
   cp .env.example .env
   ```

2. **Configure your environment variables** in the `.env` file:

   ```bash
   # Required: set the paths to your data directories
   RUN_BASE_DIRS="/data/runs,/data2/runs"

   # Optional: Google OAuth allowlist (use with GOOGLE_AUTH_* vars)
   GOOGLE_AUTH_ALLOWED_USERS="user1@example.com,user2@example.com"

   # Optional: for local authentication (dev only)
   LOCAL_USERS="alice:$2b$12$...,bob:$2b$12$..."
   ```

Docker Compose automatically loads all environment variables from the `.env` file.

## Building and Running

### Production Mode

```bash
# Build the Docker image
docker compose build
# Or build with no cache (if you need a fresh build)
docker compose build --no-cache

# Start the application
docker compose up
# Run in detached mode
docker compose up -d
# View logs
docker compose logs -f
# Stop the application
docker compose down
```

### Development Mode

For development with live reloading and source code watching:

```bash
docker compose -f docker-compose.dev.yml up
# (or run in detached mode)
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop the development environment
docker compose -f docker-compose.dev.yml down
```

The development setup includes:

- **Backend auto-reload**: FastAPI server automatically restarts when Python code changes
- **Frontend watch mode**: Vite automatically rebuilds the frontend when Vue/TypeScript files change
- **Full project mounting**: entire project directory mounted for access to all files
- **Selective write access**: frontend directory is writable for Vite temp files and build outputs
- **Two-container setup**: separate containers for the backend and frontend watcher for better resource management
- **Single Dockerfile**: uses the same Dockerfile as production with conditional frontend building

### Alternative Development Approach

For a simpler development setup, you can also run with a development server using volume mounts:

```bash
docker compose run --rm -p 8000:8000 \
  -v $(pwd)/backend:/app \
  -v $(pwd)/frontend:/app/frontend \
  binderdash uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Health Checks

The application includes health checks that verify the FastAPI server is responding on `/health`, run every 30 seconds with a 10-second timeout.

```bash
# View health status
docker compose ps

# Test health endpoint directly
curl http://localhost:8000/health
```

## Resource Limits

The container is configured with resource limits:

- **Memory**: 2GB limit, 512MB reservation
- **CPU**: 1.0 CPU limit, 0.5 CPU reservation

Adjust these in `docker-compose.yml` if needed for your environment.

## Security Considerations

1. **Non-root user**: the container runs as user ID 1000 (non-root)
2. **Read-only volumes**: data directories are mounted as read-only
3. **Environment variables**: sensitive configuration is passed via environment variables, not baked into the image
4. **Network**: only port 8000 is exposed to the host

## Troubleshooting

### Common Issues

1. **Permission denied on data directories**:

   ```bash
   sudo chown -R 1000:1000 /data/runs /data2/runs
   ```

2. **Container won't start**:

   ```bash
   docker compose logs binderdash
   netstat -tulpn | grep :8000
   cat .env
   ```

3. **Health check failing**:

   ```bash
   curl -v http://localhost:8000/health
   docker compose logs -f binderdash
   ```

4. **Frontend not loading**:
   - Ensure the frontend was built during the Docker build process
   - Check that static files are being served correctly
   - Verify the build output in the container: `docker compose exec binderdash ls -la /app/backend/static/`

5. **Development mode issues**:

   ```bash
   docker compose -f docker-compose.dev.yml ps
   docker compose -f docker-compose.dev.yml logs frontend-watcher
   docker compose -f docker-compose.dev.yml exec binderdash ls -la /app/backend/
   docker compose -f docker-compose.dev.yml exec frontend-watcher ls -la /app/frontend/
   ```

### Debugging

```bash
# Access the container shell
docker compose exec binderdash /bin/bash

# Check application status
docker compose exec binderdash ps aux
```

## Production Deployment

For production deployment:

1. **Use a reverse proxy** (nginx, traefik, or Caddy — see `Caddyfile` and `DOMAIN` in `.env.example`) in front of the container
2. **Set up SSL/TLS** termination at the reverse proxy
3. **Configure proper logging** and log rotation
4. **Set up monitoring** and alerting
5. **Use secrets management** for sensitive environment variables
6. **Consider using Docker Swarm or Kubernetes** for orchestration

### Example nginx configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Environment Variables Reference

| Variable                    | Description                                                       | Default                  | Required |
| --------------------------- | ------------------------------------------------------------------| ------------------------ | -------- |
| `RUN_BASE_DIRS`             | Comma-separated list of base directories to scan                  | `/data/runs,/data2/runs` | Yes      |
| `GOOGLE_AUTH_ALLOWED_USERS` | Comma-separated allowed Google sign-in emails (with Google OAuth)  | Empty                    | No       |
| `LOCAL_USERS`               | Comma-separated list of local users with bcrypt hashes             | Empty                    | No       |
| `SECRET_KEY`                | JWT secret key (auto-generated if not provided)                    | Auto-generated           | No       |
| `CORS_ALLOWED_ORIGINS`      | Comma-separated list of allowed CORS origins                       | `*`                      | No       |
| `DISABLE_AUTHENTICATION`    | Set to `true` to disable all authentication                        | `false`                  | No       |

See `.env.example` for the full, current list of supported variables.
