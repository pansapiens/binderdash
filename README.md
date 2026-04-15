## Binderdash

A single-page web app to explore results from de novo protein binder design runs.

- Frontend: Vite + Vue 3 (Composition API) + PrimeVue, Mol* viewer, Vega-Lite plots
- Backend: FastAPI (async) serving an API and the built frontend static files

### Prerequisites

- Python 3.11+ (tested with 3.12)
- uv (Python package manager and runner)
- pnpm (for frontend)
- Node.js 18+ (for Vite/PrimeVue tooling)
- Docker (optional, for containerised workflow)

### Repository layout

- `backend/`: FastAPI app, static files output directory
- `frontend/`: Vite + Vue SPA source
- `example_runs/`: Example data (optional)

### Environment configuration

This project uses a `.env` file at the repository root. Copy `.env.example` as a starting point.

`.env` contains a `LOCAL_USERS` variable where username/password pairs for local user accounts can be defined.

Generate hashed and salted passwords for `LOCAL_USERS` like:
```bash
python backend/scripts/encrypt_password.py myusername  # Interactive password prompt
```

### Quick start (development)

#### Backend

Create and activate a virtual environment with uv, then install deps:

```bash
uv venv -p python3.12 .venv && source .venv/bin/activate
uv pip install -r backend/requirements.txt
```

Start the backend API dev server (in a separate shell):

```bash
source .venv/bin/activate
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

By default the FastAPI server is on `http://localhost:8000`.

**Backend dependencies:** If you change any backend dependencies, edit `backend/pyproject.toml` and recompile pinned requirements:

```bash
uv pip compile backend/pyproject.toml -o backend/requirements.txt
uv pip install -r backend/requirements.txt
```

#### Frontend

Install dependencies and start the dev server (hot reload):

```bash
cd ./frontend
pnpm install
pnpm run dev
```

By default Vite serves on `http://localhost:5173`.

Alternatively, for development with automatic rebuilding when files change:

```bash
cd ./frontend
pnpm install
pnpm run watch:build
```

This automatically rebuilds the frontend whenever you make changes, outputting to the backend's static directory (`backend/static/`)


### Running with Docker (optional)

#### Development Mode
For development with live reloading and source code watching:

```bash
docker compose -f docker-compose.dev.yml up --build
# Connect to http://localhost:8001

# Watch the logs for the backend
docker compose -f docker-compose.dev.yml logs -f binderdash

# Watch the logs for the frontend
docker compose -f docker-compose.dev.yml logs -f frontend-watcher

# Stop the development environment
docker compose -f docker-compose.dev.yml down
```
The development server is available at: http://localhost:8001

This development setup includes:
- Backend auto-reload when Python code changes
- Frontend watch mode that rebuilds when Vue/TypeScript files change
- Source code mounted from your local filesystem

For detailed Docker setup instructions, troubleshooting, and production deployment guidance, see [DOCKER.md](DOCKER.md).

Tip: Provide environment variables via an `.env` file or `docker compose --env-file` override.

#### Production Mode

Ensure the `DATABASE` folder has been created with permissions for the app user (1000:1000) (e.g. `sudo chown -R 1000:1000 data`).

Build and run using Docker Compose:

```bash
docker compose up --build -d
```

### Testing and quality

- Backend tests (pytest):

```bash
cd ./backend
source .venv/bin/activate
pytest
```

### Common tasks

- Update backend dependencies from `pyproject.toml`:

```bash
uv pip compile backend/pyproject.toml -o backend/requirements.txt
uv pip install -r backend/requirements.txt
```

- Rebuild frontend after UI changes:

```bash
cd /home/perry/projects/binderdash/frontend
pnpm run build
```

### Contributing

- Follow Python typing and import order conventions; log to stderr
- Use Vue 3 Composition API, and keep `.vue` sections ordered as `<template>`, `<script>`, `<style>`
- For notable features or fixes, update `CHANGELOG.md` after merging
