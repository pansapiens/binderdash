# Storage architecture

Binderdash reads/writes data in three distinct places. This page is the map of
"where does X live" — useful when reasoning about backups, multi-user
deployments, or what survives a container rebuild.

## 1. Server-side database (SQLite by default)

Controlled by the `DATABASE` env var (see `AGENTS.md`), resolved in
`backend/persistence/factory.py`. If `DATABASE` is unset, persistence is
disabled entirely (`NoopDesignsRepository` — nothing below is stored, and the
app relies purely on the in-memory cache hydrated at startup from disk scans).

With `DATABASE=sqlite:///path/to/file` (or left to the default,
`backend/data/binderdash.sqlite`), the following tables exist
(`backend/persistence/sqlite_repo.py`):

| Table | What it stores |
|---|---|
| `binderdash_runs` | One row per discovered run: method, run name, project ID, resolved run path, and a `run_json` blob of run-level metadata. |
| `binderdash_designs` | One row per design: indexed columns (`run_id`, `design_id`, `tag`, `good`, `binder_chain`, `short_name`) plus a `data_json` blob holding all method-specific score columns, and `extra_data` for user-added fields. This is the durable copy of what gets loaded into the in-memory `designs_cache` at startup (see `cache.py`). |
| `binderdash_auth_users` | Login history per (provider, identifier) — provider name, identifier, email, first/last login timestamps. Not credentials — those live in env vars (`LOCAL_USERS` bcrypt hashes) or are delegated (PAM, Google OAuth). |
| `binderdash_tag_metrics_cache` | Cached results of tag-placement metric computation (SASA-based tag-site scoring), keyed by run/design/structure file/tag parameters, so repeated UI requests with the same parameters don't recompute. |
| `binderdash_structural_metrics_cache` | Cached results of structural metrics computation (`backend/filtering/structural_metrics.py` — secondary structure, hydrophobic patch area, hbonds/saltbridges, delta SASA), keyed by run/design/structure file/chain selection. |
| `binderdash_saved_sets` | **Saved Sets** (Filtering tab "save as a named set"): id, name, created timestamp, the source run IDs, the filter/ranking/diversity recipe (`filter_params` JSON), and a `result_summary` JSON. Yes — Saved Sets are server-side, not browser-local; they're visible to every user of the same Binderdash server/database and survive a browser reset. |
| `binderdash_saved_set_designs` | The frozen list of designs belonging to each Saved Set at the time it was created (design/run/source-path identity, final rank, quality score, whether it was in the diversity-selected subset, and a metrics snapshot). Saved Sets are immutable snapshots — the only allowed mutation after creation is rename (`PATCH /api/saved-sets/{id}`); "reapply filters" in the UI builds a *new* set rather than editing one in place. |

None of these tables store the structure files themselves (PDB/CIF) or raw
run output — only metadata, computed metrics, and references (paths) back to
files on the server filesystem (§3).

If `DATABASE` points at Postgres, the URL is currently accepted but falls
back to the no-op repository (`Postgres repository not implemented yet`) —
SQLite is the only real backend today.

## 2. Browser storage (per-user, per-browser, client-side only)

Binderdash uses **no `localStorage`**. All client-persisted UI state lives in
**IndexedDB**, via `frontend/src/persistence/` (`db.ts`, `store.ts`,
`keys.ts`, `hydrate.ts`) — a single IndexedDB database (`binderdash-app`,
object store `kv`) holding a handful of namespaced keys
(`PERSISTENCE_KEYS` in `keys.ts`):

| Key | What it holds |
|---|---|
| `binderdash:designs-view-state-v1` | DesignsView table state: selections, column visibility/order, sort, tag placements. |
| `binderdash:plots-scatter-axes-v1` | Persisted X/Y axis choices per method for the Plots tab. |
| `binderdash:filtering-view-state-v1` | Filtering tab: hard filters, ranking metrics, alpha/budget, diversity toggle state, etc. (this is the *in-progress* filter builder state — not the same thing as a Saved Set, which is committed server-side once you explicitly save it). |
| `binderdash-viewer-controls-pos` | Mol* viewer floating-controls panel position. |
| `binderdash-adv-ref-ui-global` | Advanced reference/overlay UI toggles (global). |
| `binderdash-adv-ref:<runId>` | Per-run advanced-reference overlay state. |
| `binderdash-tag-placement:<runId>` | Per-run tag placement UI state (independent of the DB-cached tag metrics in §1). |
| `binderdash:folders-ui-v1` | Folder Browser UI state (expanded folders, selection). |

Because this is IndexedDB, it is scoped to one browser profile on one
machine — it is **not** shared across users or devices, does not survive
"clear site data," and is unrelated to anything the server persists. Session
auth itself is a separate, small piece of client state: a signed cookie
(`SessionMiddleware`, `backend/main.py`, keyed by `SECRET_KEY`), not
IndexedDB/localStorage.

## 3. Server filesystem

Two independent things live on disk, outside the database:

- **Run output directories** — the original, unmodified pipeline output
  (results tables, structure files) under whatever directories `RUN_BASE_DIRS`
  points at (or ad hoc folders picked via the Folder Browser). Binderdash never
  copies or moves these; it only reads them (scanning in `run_discovery.py`,
  and serving structure files on demand via `backend/routers/files.py`). The
  DB only stores the resolved `run_path`/`source_path` references back into
  this tree, so if a run folder is moved or deleted, structure-file requests
  and Mol* viewing for that run will start failing even though the run's
  design rows still exist in the DB/cache.
- **The SQLite file itself** — by default `backend/data/binderdash.sqlite`
  (see `default_sqlite_url()` in `backend/persistence/factory.py`), i.e. the
  `data/` directory at the repo root when run via Docker Compose (mounted as a
  volume — see `docker-compose.dev.yml`) so it survives container rebuilds.

## Quick answers

- **Are Saved Sets stored server-side?** Yes — `binderdash_saved_sets` /
  `binderdash_saved_set_designs` tables in the SQLite DB. They're shared
  across all users/browsers hitting the same server and DB file, and persist
  independently of any browser's IndexedDB state.
- **What's lost if I clear browser storage?** Only UI convenience state (table
  column layout, in-progress/unsaved filter builder state, viewer panel
  positions, tag placement scratch state) — no run data, computed metrics, or
  Saved Sets.
- **What's lost if the SQLite file is deleted?** All ingested run/design rows,
  cached tag/structural metrics (both are cheap to recompute), login history,
  and — unlike everything else in that list — **all Saved Sets**, since
  they're not derivable from the run output on disk. The original run output
  directories on the filesystem are unaffected either way.
