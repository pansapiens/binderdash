# AGENTS.md

## Project overview

- Single-page app to view results of de novo protein binder design runs
- Frontend: Vite + Typescript + Vue 3 (Composition API) + PrimeVue, Mol* viewer, Vega-Lite plots
- Backend: FastAPI (async) serving API and built frontend static files
- **Pipeline config** (method IDs, run folder signatures, score columns, plot defaults, path heuristics, structure-file rules, score column names matching source files): `backend/config/` (`run_signatures.py`, `plot_defaults.py`, `method_paths.py`, `score_labels.py`). Import `backend.config` or submodules; `run_discovery` still imports `run_folder_signatures` from there.

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
  - Watch mode (auto-rebuild): `pnpm run watch:build`
- Build frontend for backend to serve:
  - `pnpm run build` (output configured to backend static dir)
- Containerised (optional):
  - `docker compose up --build`

## Environment configuration

- Use `.env` (create from `.env.example`) and ensure `.env` is in `.gitignore`
- Expected variables:
  - `RUN_BASE_DIRS="/data/runs,/data2/runs"` (comma-separated list of base directories)
  - `DISABLE_AUTHENTICATION="true|false"`
  - `BINDERDASH_API_KEY` (optional; when set, API clients use `Authorization: Bearer <key>` or `X-Binderdash-Api-Key` instead of login + CSRF)
  - `LOCAL_USERS="user1:$2b$...,user2:$2b$..."` (optional; bcrypt hashes; enabled when non-empty)
  - `PAM_LOCAL_ENABLED` / `PAM_LOCAL_ALLOWED_USERS` / `PAM_LOCAL_SERVICE` (optional; PAM after `LOCAL_USERS`; default service `common-auth`; Docker: either `LOCAL_USERS`, add users in the image, or optional bind-mounts of host `/etc/passwd` + `/etc/group` + `/etc/shadow` — commented in `docker-compose.yml`, security-sensitive)
  - `GOOGLE_AUTH_ENABLED`, `GOOGLE_AUTH_CLIENT_ID`, `GOOGLE_AUTH_CLIENT_SECRET`, `GOOGLE_AUTH_REDIRECT_URI`, `GOOGLE_AUTH_ALLOWED_USERS` (optional; Google OAuth; emails case-insensitive)
  - `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DATABASE`, `CORS_ALLOWED_ORIGINS` as needed
- When adding new env vars, update `.env.example` accordingly
- Do not delete `.env`, but ensure it is in `.gitignore`

## Frontend guidelines (Vite + Vue 3 + PrimeVue)

- Use `pnpm` for package management
- Composition API; component order: `<template>`, `<script>`, `<style>`

## Design style guide and principles

- Use default PrimeVue styling and components, unless otherwise specified
- Use checkboxes for row selection in DataTables, where row selection is required: https://primevue.org/datatable/#checkbox_row_selection

## Testing and quality

- Backend: `pytest` for unit/API tests
- Frontend: Playwright for end-to-end testing
  - Install root dependencies: `pnpm install` (first time only)
  - Run tests: `pnpm test` (installs browsers and runs full suite)
  - Individual commands: `pnpm test:playwright`, `pnpm test:ui`, `pnpm test:headed`, `pnpm test:debug`
  - Test configuration: `playwright.config.js` with automatic server startup
  - Test documentation: `tests/README.md` with comprehensive workflow testing
  - Helper script: `run-tests.js` for automated test execution

## Code style

- Do not write extraneous comments in the code; comment where code deviates from typical patterns or is particularly complex / cryptic. Don't comment on lines that would be self-explanatory to a junior developer.
- Python: type hints, guard clauses, meaningful names, log to stderr; import order: stdlib → common externals → other externals → internal
- Vue: Composition API, minimal comments, Australian English spelling in comments
- Secrets: never hardcode; always use environment variables

## PR checklist

- Run backend tests (`pytest`) and linters
- Run frontend build  (`pnpm run build`) and linters
- Run Playwright tests: `pnpm test` (from project root)
- Update `.env.example` when env vars change
- Update `CHANGELOG.md` for notable features and fixes
