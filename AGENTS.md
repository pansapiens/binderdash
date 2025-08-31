# AGENTS.md

## Project overview

- Single-page app to view results of de novo protein binder design runs
- Frontend: Vite + Typescript + Vue 3 (Composition API) + PrimeVue, Mol* viewer, Vega-Lite plots
- Backend: FastAPI (async) serving API and built frontend static files

## Setup commands

- ALWAYS ensure any existing conda environment is deactivated before running any commands: `conda deactivate; conda deactivate`
- Backend (Python 3.11+, uv):
  - Create venv: `uv venv -p python3.12 .venv && source .venv/bin/activate`
  - Update dependencies if required, modify `backend/pyproject.toml` then run `uv pip compile backend/pyproject.toml -o backend/requirements.txt`
  - Install deps: `uv pip install -r backend/requirements.txt`
  - Start API dev server: `uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend (pnpm, Vite, PrimeVue):
  - `cd frontend && pnpm install`
  - Dev server: `pnpm run dev`
- Build frontend for backend to serve:
  - `pnpm run build` (output configured to backend static dir)
- Containerised (optional):
  - `docker compose up --build`

## Environment configuration

- Use `.env` (create from `.env.example`) and ensure `.env` is in `.gitignore`
- Expected variables:
  - `RUN_BASE_DIRS="/data/runs,/data2/runs"` (comma-separated list of base directories)
  - `ALLOWED_USERS="user1@example.com,user2@example.com"` (optional; Google OAuth allowlist)
  - `LOCAL_USERS="user1:$2b$...,user2:$2b$..."` (optional dev fallback; bcrypt hashes)
- When adding new env vars, update `.env.example` accordingly

## Frontend guidelines (Vite + Vue 3 + PrimeVue)

- Use `pnpm` for package management
- Composition API; component order: `<template>`, `<script>`, `<style>`

## Testing and quality

- Backend: `pytest` for unit/API tests

## Code style

- Python: type hints, guard clauses, meaningful names, log to stderr; import order: stdlib → common externals → other externals → internal
- Vue: Composition API, minimal comments, Australian English spelling in comments
- Secrets: never hardcode; always use environment variables

## PR checklist

- Run backend tests and linters; run frontend build and linters
- Update `.env.example` when env vars change
- Update `CHANGELOG.md` for notable features and fixes
