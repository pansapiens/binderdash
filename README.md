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

This project uses a `.env` file at the repository root. Create one (and keep `.env` in `.gitignore`). When adding new variables, also update `.env.example`.

Variables:

```
RUN_BASE_DIRS="/data/runs,/data2/runs"   # Comma-separated list of directories containing design runs
ALLOWED_USERS="user1@example.com,user2@example.com"  # Optional; Google OAuth allowlist
LOCAL_USERS="user1:$2b$...,user2:$2b$..."           # Optional dev fallback; bcrypt password hashes
```

Generate password hashes for LOCAL_USERS:
```bash
python backend/scripts/encrypt_password.py username  # Interactive password prompt
```

### Quick start (development)

1) Ensure any active conda environment is deactivated:

```bash
conda deactivate; conda deactivate
```

2) Backend: create and activate a virtual environment with uv, then install deps:

```bash
uv venv -p python3.12 .venv && source .venv/bin/activate
uv pip install -r backend/requirements.txt
```

If you changed backend dependencies, edit `backend/pyproject.toml` and recompile pinned requirements:

```bash
uv pip compile backend/pyproject.toml -o backend/requirements.txt
uv pip install -r backend/requirements.txt
```

3) Frontend: install dependencies and start the dev server (hot reload):

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

This automatically rebuilds the frontend whenever you make changes, outputting to the backend's static directory.

4) Backend API dev server (in a separate shell):

```bash
cd /home/perry/projects/binderdash
source .venv/bin/activate
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

By default the FastAPI server is on `http://localhost:8000`.

### Building the frontend (served by the backend)

Build the SPA so the backend can serve it from `backend/static/`:

```bash
cd ./frontend
pnpm run build
```

This outputs production assets to the backend’s static directory. Start the backend to serve both the API and the static site:

```bash
cd ..
source .venv/bin/activate
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` to access the app.

### Running with Docker (optional)

Build and run using Docker Compose:

```bash
docker compose up --build
```

Tip: Provide environment variables via an `.env` file or `docker compose --env-file` override.

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
- Never hardcode secrets; use environment variables
- For notable features or fixes, update `CHANGELOG.md` after merging
