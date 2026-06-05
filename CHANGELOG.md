# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Changed (Prepare sequences)**: Per-tag **Include \* stop** (N/C) and optional **double stop**; stops sit after the full body and before padding. Optional **Only use N/C-terminal tag when padding required** omits preset tags on long sequences and adds them only when pad-up-to padding applies.
- **Performance (Designs)**: Large tables load faster (run-scoped SQLite, trimmed list payload, `designs_by_run_id` cache); UI uses `shallowRef`, sampled column inference, stable `binderRowKey`, and flag-based select-all; virtual scroller removed (conflicted with pagination).
- **Added (Designs)**: **`extra_data`** SQLite column for annotations (uploaded CSV/TSV columns, extracted **Sequence**); pipeline fields stay in **`data_json`** and refresh on re-ingest. **`POST /api/designs/merge-table`** merges new columns by **`design_id`** for selected runs; UI **Merge columns** on the Designs table.
- **Added (Auth / API)**: Optional **`BINDERDASH_API_KEY`** — scripted access via `Authorization: Bearer <key>` or `X-Binderdash-Api-Key` without session cookies or CSRF; `GET /api/auth/status` reports `providers.api_key.enabled`.
- **Changed (Designs)**: All Designs table pagination defaults to **12** rows per page; rows-per-page options are **12, 24, 48, 96**.
- **Added (Select Runs)**: **Delete selected runs** — toolbar action with confirmation; removes ingested runs from the **database** only (designs cascade, tag metrics cache cleared); **does not** delete or change files on disk.
- **Added (Ingest Runs)**: **Set project name (project ID)** before ingest — inline edit in the scan results table so the value used and shown after ingestion matches what you enter (replaces scan-time guess only for that ingest).
- **Added (SQLite)**: **`run_path`** column on **`binderdash_runs`** stores the resolved absolute filesystem path of the run directory at ingest time.

## [0.2.0] - 2026-05-13

- **Changed (UI)**: Add [X] buttons to clear text search fields.
- **Added (Prepare sequences / DNA Optimization)**: New `ExcludeRestrictionSite` constraint with a searchable dropdown of common Type II / Golden Gate / 8-cutter restriction enzymes (serialised as `AvoidPattern` with `"<enzyme>_site"` so dnachisel resolves the site via Biopython's restriction table on both strands).
- **Added (Prepare sequences)**: Warn (with acknowledge-before-download) when any in-scope design has a blank or non‑N/C **tag** column so N/C terminal presets are not applied to those rows.
- **Changed (Prepare sequences)**: **Short name** settings live in a collapsible **Panel** (like DNA optimisation); the whole header (title/bar) toggles expand/collapse, not only the chevron.
- **Added (Prepare sequences / Twist)**: **Short names** (≤32 chars) with strategies (regex replace; split + indices + optional hash; prefix + **DNA-set uid** + index; **smart** stem+hash with optional common prefix/suffix strip, regex strip, and extra prefix/suffix). Row hashes use pre-tag amino acid. **`short_name`** stored in SQLite ( **`design_id`** unchanged); **`POST /api/designs/short-names`** bulk-updates. Default Twist download **`name,sequence,original_name`** (values from computed short name); TSV/CSV keep prior columns and append **`short_name`**; **Design** column shows short name on line one. Strategy defaults to **None** if all `design_id`s fit ≤32 chars, else **Smart: stem + hash**, until the user picks a strategy.
- **Changed (Prepare sequences)**: **Pattern** short-name uid is one set-wide base52 hash of sorted per-row **`prepared_dna`** (missing → `""`), `\x1e`-joined — same for all rows; no longer mixes original AA with `computeSetFingerprint`.
- **Changed (Prepare sequences / Twist)**: **Split + take indices** short-name strategy now supports optional **Add prefix** and **Add suffix** fields, applied after split+take (before optional hash append).
- **Fixed (Designs)**: Skip redundant `GET /api/designs` when selected run IDs are unchanged.
- **Fixed (Mol\*)**: Fewer duplicate structure fetches — identical loads skipped, membrane overlay repaints without reloading CIF, binder-tag marker reads terminal CA from Mol*’s loaded model (no second CIF request).
- **Fixed (Mol\*)**: Primary-only structure navigation remounts the viewer instead of `visual.update`, avoiding Firefox aborted downloads (status 0) and Mol* “Invalid data cell” on next/prev.
- **Fixed (Mol\*)**: Aligned reference overlay uses deferred `URL.revokeObjectURL` for blob URLs so Mol* is not left fetching a revoked blob when switching designs (Firefox status 0 / “Invalid data cell”).
- **Fixed (Mol\*)**: Designs viewer passes stable PDB + reference URLs to Mol* only after the aligned reference finishes loading when the overlay is on, avoiding duplicate primary PDB fetches on next/prev.
- **Fixed (Mol\*)**: Mol* PDB/reference URL watcher runs after the reference `filename` / `run_id` watchers so `referenceLoading` is set before props update (fixes double XHR + double flash when overlay is on).
- **Fixed (Select Runs)**: Method protocol icon uses `pointer-events: none` so clicking the Name column still toggles row selection (PrimeVue’s row handler ignores clicks on “clickable” targets such as `<i>`).
- **Added (Select Runs)**: Toolbar with "Show selected" toggle, "Refresh list", and "Re-Ingest Selected" actions; improved empty states.
- **Changed (Select Runs)**: Moved filtering to the DataTable filter row with MultiSelect for project and method.
- **API / Designs**: `GET /api/designs` accepts optional `run_ids` (comma-separated) to return only designs for those runs; omit for all designs (unchanged).
- **Designs / Select Runs**: The client loads designs only for the selected runs (`run_ids` query), debounces selection changes, indexes by `run_id` for column metadata, removes forced DataTable remounts, and loads scoped data when the **Designs** or **Plots** tab is active (with deduplication when selection is unchanged). Ingest completion refreshes runs and reloads designs only for the current selection.
- **Backend**: Pipeline/method/score config lives under `backend/config/` (signatures consumed by `run_discovery`/`cache`; IDs, path heuristics, params keys, basename rules in `method_paths.py`).
- **Frontend**: `frontend/src/config/pipelineDisplay.ts` centralises method tags, score columns, colours, structure helpers, and Select Runs chips; pipeline **Tag**s use theme palette CSS vars instead of `severity`.
- **Docs**: MkDocs skeleton (`mkdocs.yml`, `docs/index.md`, `requirements-docs.txt`); `site/` gitignored.
- **Runs / ingest**: `trajectory_count` from params or CSV line counts; ingest stores `primary_score_stats`; UI shows Accepted/total and Select Runs primary-score stats; merged runs sum `trajectory_count`.
- **Ingest Runs**: Scan calls **`POST /api/runs/scan` once per selected folder** (results merge client-side as on the server). Ingest calls **`POST /api/runs/ingest` once per selected run** (sequential). Scan/ingest handlers run heavy work in a **thread pool** via **`asyncio.to_thread`** so the API event loop stays responsive. The scan results table adds an **Ingested** column (green check when that run’s ingest succeeded).
- **Auth**: Removed support for the `ALLOWED_USERS` environment variable (it was only a legacy fallback for the Google allowlist). Use `GOOGLE_AUTH_ALLOWED_USERS` only.
- **Docker / PAM**: `docker-compose.yml` and `docker-compose.dev.yml` include commented optional bind-mounts for host `/etc/passwd`, `/etc/group`, and `/etc/shadow` (`:ro`) when using PAM for host local users — documented as high-risk; not enabled by default.
- **PAM**: Default PAM stack is `common-auth` (configurable via `PAM_LOCAL_SERVICE`) instead of `login`, which often fails for non-TTY/container use. Dockerfile installs `libpam0g` and `libpam-modules`. Login UI hint about local-then-PAM moved to `.env.example` comments only.
- **Docker / static files**: Resolve `backend/static` from `main.py`’s package directory (not the process cwd) so `StaticFiles` works when the working directory is not the repo root. If the frontend build is missing, log a warning and skip `/assets` and `/static` mounts instead of crashing; `/` returns 503 with a plain-text hint. Docker image build with `BUILD_FRONTEND=true` now fails if `backend/static/assets` is not produced.
- **Authentication**: Optional **PAM** (Unix password) and **Google OAuth** sign-in alongside existing **LOCAL_USERS** (bcrypt). JWT session cookies include `provider` (`local` / `pam` / `google`); allowlists are re-checked on each request. SQLite persistence adds **`binderdash_auth_users`** for login audit (`record_login`). **`GET /api/auth/status`** returns enabled providers; login UI shows password and/or Google when configured. Dependencies: **authlib**, **python-pam**, **itsdangerous** (sessions). Requires **SessionMiddleware** (same `SECRET_KEY` as JWT).
- **Prepare sequences tab / DNA Optimization**: Added server-side DNA sequence optimization with customizable synthesis constraints (GC content, hairpins, rare codons, etc.) and Twist Bioscience defaults.
- **Prepare sequences tab / DNA Optimization**: Added warnings and acknowledgment checkboxes when attempting to download unoptimized DNA or when settings have changed.
- **Prepare sequences tab / DNA Optimization**: "Optimize DNA" can now be triggered directly from the amino-acid view, alongside UI improvements for managing constraints.
- **Prepare sequences tab**: Added post-stop DNA padding, allowing sequences to be padded to a target nucleotide length.
- **Prepare sequences tab**: Added a toggle to show or hide post-stop padding in the amino acid view and exports.
- **Prepare sequences tab**: Added calculated protein metrics (ε₂₈₀, pI) and sequence warnings (Cys, no-Trp). Warnings must be acknowledged before export and are included in CSV/TSV downloads.
- **Prepare sequences tab**: Added row filters for the Design and Tag End columns.
- **Fix (Prepare sequences)**: Table column sorting now works consistently for Tagged length, Warnings, and ε₂₈₀.
- **Fix (Prepare sequences)**: Stop codons (`*`) are properly included in the amino acid preview and length calculations.
- **Fix (Prepare sequences)**: Sequence warnings now correctly only evaluate the coding sequence before the first stop codon.
- **Docs**: `.env.example` SQLite `DATABASE` example fixed: `sqlite:///app/db.sqlite` was parsed as a **relative** path `app/db.sqlite` (→ `/app/app/db.sqlite` when cwd is `/app`). Use `sqlite:///db.sqlite` (relative to cwd) or `sqlite:////app/db.sqlite` (absolute) for `/app/db.sqlite`.
- **Navigation**: Add icons to **Tabs** and split tab string into two groups. Replaced deprecated **TabView** with PrimeVue v4 **Tabs** + **TabList** + **Tab** + **TabPanels** + **TabPanel** (`v-model:value`, string tab ids).
- **Plots** and **Select Runs**: Add search filters to dropdowns.
- **API**: `GET /api/sequences/codon-tables` lists builtin codon usage tables; `GET /api/sequences/codon-tables/{table_id}` returns frequencies (`python_codon_tables`) for Prepare Sequences and similar clients.
- **Prepare sequences tab**: Prepared-sequence table paginator defaults to **5** rows per page with options **5, 10, 24, 48, 96**; **Design** column shows design ID, project, and run as three labelled lines in one cell; **Tagged length** column (aa or nt by view mode); **Good only** as an **InputSwitch** (All / Good only) beside the AA/NT bar; terminal/stop/chain/padding/min-DNA options in a **card** above **Extract missing sequences**; **min/max tagged length** line under the preview table; N/C tag presets (`TAG_PRESET_DEFS`), terminal additions, optional stop, good-only scope, structure extraction (`POST /api/designs/sequences`), preview, FASTA/TSV/CSV export; persists `Sequence` and `binder_chain` when persistence is on; preset tag chip colours match palette buttons (CSS variables + scoped `!important`; global chip/text overrides no longer mask them). **Mixed-case** custom tags and N/C/padding fields: uppercase = AA (`A–Z`, `*`), lowercase `a/c/g/t` = nucleotides (in-frame triplets in AA view; leftover bases styled, exported as `-` in AA mode). Invalid characters show errors and block downloads. **Amino acid / Nucleotide** `InputSwitch` above the table; **Codon table** select is filled from `GET /api/sequences/codon-tables` with per-table usage from `GET /api/sequences/codon-tables/{id}` (offline fallback keeps E. coli). DNA view uses literal stop codons (e.g. `TAA`) with strong red styling; AA exports keep `*` (FASTA no longer strips stops).
- **Fix (Designs)**: Score and length range filters no longer hide entire runs (e.g. boltzgen) when those bounds were left over from another method: rows with none of the known score columns, or without a length field, are not excluded by min/max score or length filters.
- **Designs**: **Toggle Columns** and custom-filter **column** dropdown list only fields that appear in designs for the runs currently selected in **Select Runs**; other loaded runs no longer add extra columns to those lists. The data table’s visible columns follow the same set. **`columns`** in the store remains the full schema after load (for type hints on persisted custom filters that reference columns not in the current run set).
- **SQLite database**: **`DATABASE`** (SQLite by default) stores ingested runs and per-design **tag**/**good** (no CSV writes). **`POST /api/runs/scan`** (disk only; optional **`force_rescan_of_ingested`**), **`/ingest`**, **`/ingest-preview`**; stable **`run_id`** per **`run_group_key`**. Tabs: **Designs**, **Prepare Sequences**, **Select Runs**, **Plots**, **Ingest Runs**; Designs use **Select Runs** selection only. Re-ingest is confirmed by name (resets tag/good).
- **Client persistence (IndexedDB)**: UI state is stored in a single **`binderdash-app`** IndexedDB database via the **`idb`** helper and `frontend/src/persistence/` (`kv` store, central keys). Hydration runs before `app.mount()`. **Removed** `pinia-plugin-persistedstate` (folder tree state now uses the same layer). Prior **`localStorage`** keys for these features are **not** migrated. **`kvSet`** JSON-round-trips values before `put` so Vue/Pinia reactive proxies are not passed to IndexedDB (avoids **Proxy object could not be cloned**).
- **Selection/view persistence**: Selected runs, design rows, and current structure navigation are restored after reload (via the IndexedDB persistence layer).
- **Tag placement (Designs)**: Collapsible batch His-tag prediction/metrics (**`POST /api/designs/tag-placement`**, **`tag-metrics`**); Mol\* toolbar **N/C** toggle and **`PATCH /api/designs/tag`** (DB). Options saved in **IndexedDB** per run.
- **Tag metrics (lazy + cache)**: Placement metrics table starts with placeholders (—); **`POST /api/designs/tag-metrics`** supports **`cache_only`** (SQLite cache hits only, no heavy compute) and **`ignore_cache`** (skip reads, recompute). **`binderdash_tag_metrics_cache`** in SQLite keys **`run_id`**, **`design_id`**, **`source_path`**, structure basename, and SASA / chain / threshold parameters; populated after compute and after successful **Auto detect**. UI: progress bar above **Auto detect**, **Ignore cache, force recalculate** checkbox; rows refresh after each placement when persistence is enabled.
- **Fix**: Tag-metrics cache **`INSERT`** had an extra **`?`** for **`updated_at`** (should use **`datetime('now')`** only), which caused SQLite **14 values for 13 columns** on **tag-placement** when persistence was enabled.
- **Tag placement**: **Ignore cache, force recalculate** no longer triggers a full metrics recomputation when toggled; it applies only when **Auto detect** runs. The metrics table still hydrates from cache on open or parameter changes.
- **Tag placement performance**: Auto-detect now sends frontend requests in batches (instead of one design per request), refreshes tag-metrics per batch, and avoids duplicate backend metrics recomputation during `/api/designs/tag-placement` when persistence is enabled.
- **Mol\* reference toggle**: The **Ref** visibility choice persists when changing design or run; reference reload no longer clears the blob URL before the new fetch (which had reset visibility). Clearing the overlay from **Reference structure** resets preference to visible for the next load. PDBTM membrane plane overlay hides and shows with the reference.
- **Designs / reference UI**: Advanced **Reference structure** adds a **Source** dropdown (**RCSB PDB**, **PDBTM**, **URL**). A 4-letter code uses RCSB or PDBTM (`pdbtm.unitmp.org/entry/{id}`) accordingly; values starting with `http://` or `https://` are always sent as URLs. **Enter** in **Chains** submits the reference load (same as **Reference structure**). **Reference structure** (text + source), **Chains**, and **Show input target structure** are saved to **IndexedDB**. Floating Mol\* toolbar adds a **Ref** button (outlined when hidden) to show or hide the overlaid reference structure.
- **Designs custom filters**: Filter panel includes **Custom filters** with a (+) control to add rows of **column**, **operator**, and **value**. All custom rules combine with **AND** with existing filters and affect the visible table rows and structure navigation. Custom filters are persisted in **IndexedDB**. Numeric operator dropdown lists **<=** and **>=** first.
- **Reference chains**: Advanced options include an optional **Chains** field (comma or space separated IDs). When set, TM-align uses only those reference chains and the overlaid structure shows only those chains; leave blank for previous behaviour (longest reference chain for alignment, full reference in the overlay).
- **Structure viewer details**: Columns turned on in **Toggle Columns** also appear as cards next to the fixed **Design Data** / **Scores** blocks—numeric (including numeric strings) and boolean values under **Scores** (with colour bars; booleans Yes/No with green/red), other strings under **Design Data**. Omits fields already shown in the fixed rows or in the primary scores list to avoid duplicates.
- **PDBTM reference URLs**: the reference field accepts PDBTM **entry** URLs (`https://pdbtm.unitmp.org/entry/{pdb_id}`) or **JSON API** URLs (`https://pdbtm.unitmp.org/api/v1/entry/{pdb_id}.json`). The backend fetches membrane metadata from PDBTM, TM-aligns the **RCSB mmCIF** onto the design, and returns `X-Binderdash-Membrane-*` response headers. The Mol\* viewer draws semi-transparent membrane discs (PLY shape) using the same **molstar** `5.0.0` instance as **pdbe-molstar** `3.8.0` (bundled in the app, not the PDBe CDN script).
- **Reference fetch cache**: `fetch_reference_structure` keeps an in-process LRU (128 entries) for RCSB PDB IDs, PDBTM-derived fetches (entry and JSON URLs share one key per PDB ID), and other `http(s)` structure URLs so repeated loads do not re-request remote servers.
- Add option to load a **reference structure** superimposed on the current design via **TM-align** (server-side, `tmtools`) 4-character PDB ID (RCSB) or `http(s)` URL to `.pdb` / `.cif` (`.gz` supported). Optional **Show input target structure** reads candidate paths from run `params.json` / settings (method-specific keys plus a generic scan for structure-like strings); multiple hits show a dropdown. 
  - API: `GET /api/runs/{run_id}/input-targets`, `GET /api/runs/{run_id}/files/reference` (aligned **mmCIF** + `X-Binderdash-*` metric headers). Preferences are persisted in **IndexedDB** per run.
- **Performance**: `parse_designs_from_run` caches **target sequence** per `source_path` (per merged fragment) after the first successful `get_target_sequence` call. All designs in a run share the same target; previously every row re-parsed each mmCIF/PDB (~3+ minutes for 1000 rfd3 rows in logs).
- **Diagnostics**: Phase timings use `Timer(logger, event, **fields).start()` then `.log(**extra)` (optional `min_ms=` on `log` for sparse events e.g. `detect_run_type`); `.stop()` freezes elapsed ms for a later `log()`. `timing_log` remains for ad-hoc lines. Log lines are `DEBUG timing <event> k=v ...` including `duration_ms`. Set `LOG_LEVEL=DEBUG` (see `.env.example`) for folder scan breakdowns: `find_runs_recursive`, `detect_run_type`, `run_glob`, `load_run_table`, `parse_designs`, `refresh_designs_cache`, `POST /scan`.
- **RFD3 (nf-binder-design)**: Detect runs with `results/rfd3/combined_scores.tsv`, `results/rfd3/rosettafold3/`, and `results/rfd3/rfdiffusion3/`; load scores from `combined_scores.tsv`; default structures from RosettaFold3 (`results/rfd3/rosettafold3/output/{id}/{id}_model.cif`, plus `.pdb` / `.gz` variants); primary sort/score columns `iptm`, `pair_pae`, `rf3_ipsae_min`, `rf3_rmsd_target_aligned_binder_rmsd_all`. Structure download endpoint serves gzip-compressed PDB/mmCIF with decompressed body and correct content type; optional `additional_pdb_patterns` on signatures for extra structure globs. Frontend: method filter, plots defaults, table columns, and Mol\* format detection for `.cif.gz` / `.pdb.gz` URLs. `get_chain_sequences` reads mmCIF and gzip-compressed PDB/mmCIF for target-sequence extraction.
- **Boltzgen**: Scores panel in the structure viewer includes `interaction_pae`, min interaction PAE (`min_interation_pae` or `min_interaction_pae`), and `design_ipsae_min` when present; `design_ipsae_min` uses the same colour scale as ipTM (0–1); `pae_interaction` / `interaction_pae` use ≤10 green, 10–15 orange, >15 red; min interaction PAE uses ≤5 green, >5–≤7 orange, >7 red.
- **Mol\* viewer**: pLDDT (AlphaFold) toggle uses the same coordinate format as the loaded URL (PDB vs mmCIF) so the structure no longer disappears until next/previous,
- Show **sequence** (`sequencePanel: true`), **left / right** panels (`leftPanel` / `rightPanel`), and canvas **selection** (empty `hideCanvasControls`) when control panel is open.
- **Designs table**: structure viewer next/previous navigation and the position counter follow the table’s current sort order (same ordering as the DataTable), not the original API row order.
- **Designs viewer**: thumbs up / down on the floating Mol\* control bar update the `good` column (persisted to the run results TSV/CSV via `PATCH /api/designs/good`). Clicking the active thumb clears the rating (`good: null` in the API; empty cell in the table file). A **drag handle** (vertical ellipsis) on floating toolbar inside Molstar; **double-click** the handle to restore the default centred position. Toolbar position is persisted in **IndexedDB**.
- **Refactored cache scoring to use run_folder_signatures config**
  - Removed hardcoded method-specific scoring/sorting logic from `cache.py`
  - Cache now reads `primary_score_columns` and `sort_ascending` from `run_folder_signatures`
  - New run types only need to define config in `run_folder_signatures` - no changes to cache logic required
- **Refactored run discovery to use declarative signatures**
  - Replaced hardcoded detection functions with a declarative `run_folder_signatures` configuration for parsing runs from nf-binder-design, and 'vanilla' runs
- Added explicit support for nf-binder-design runs
  - New detection functions for nf-binder-design bindcraft and RFD runs
  - nf-binder-design bindcraft runs: `{run_name}/results/bindcraft/final_design_stats.csv` and `{run_name}/results/bindcraft/accepted/`
  - nf-binder-design RFD runs: `{run_name}/results/combined_scores.tsv` with `af2_initial_guess/`, `proteinmpnn/`, and `rfdiffusion/` directories
  - Prevents recursive walking into `batches/` subdirectories for nf-binder-design bindcraft runs
  - Correctly handles PDB file paths for nf-binder-design runs vs regular runs
- Normalised run table columns on the backend to coalesce equivalent fields (e.g., `Sequence`/`sequence`, `Length`/`length`) during ingestion. This prevents duplicate columns appearing in `DesignsView` when mixing RFD and BindCraft runs.
- **Folder browser**: Removed redundant **Select All** / **Deselect All** buttons above Scan Results; selection uses the DataTable header checkbox. Removed the **Detected Runs** / “x of y selected” table header bar (the **Scan Results** heading above the table remains).
- **Ingest Runs**: **Scan Results** appears above the folder tree; after a scan, all discovered runs are selected by default (still adjustable per row or via the header checkbox).

### Fixed
- **Mol\* viewer / design switching**: Rapid table or floating prev/next selection could overlap async Mol\* loads and trigger **`Invalid data cell`** in **`parseTrajectory`** (stale data-tree refs). **`loadStructure`** is now **serialised** via a promise chain, **`toggleAlphaFoldView`** uses **`loadStructure()`** instead of a concurrent **`fullReload`**, and **`viewerAlive` / `onBeforeUnmount`** plus checks after awaits avoid work on a torn-down viewer.
- **Docker dev (`frontend-watcher`)**: `vite build --watch` hit **JavaScript heap out of memory** (~1 GiB default old-space) inside the container while the same build succeeded on the host. `docker-compose.dev.yml` now sets **`NODE_OPTIONS=--max-old-space-size=3072`** for that service and raises its **memory limit to 4 GiB** so Rollup can hold the molstar/pdbe-molstar graph.
- **Mol\* PDBTM membrane overlay**: Membrane planes are drawn as **semi-transparent 2D discs** on a **`canvas` overlay** aligned to Mol\*’s WebGL canvas, using **`plugin.canvas3d.camera.project`** and **`didDraw`** for sync. This avoids **StateTransforms** / PLY inside the plugin state tree, which could throw **`No suitable parent found`** when transform or `StateObject` identities did not match the PDBe plugin. The viewer still imports **pdbe-molstar** `3.8.0` from npm (with **pdbe-molstar-light** SCSS). **Vite** keeps `resolve.dedupe` + **`molstar`** alias + **`manualChunks`** for a single **molstar** async chunk where relevant.
- **Reference URL field**: Before fetching an aligned reference, the app reads the **Reference structure** input’s live DOM value (and sets `id="adv-reference-source"` on PrimeVue **InputText**) so paste or automation that updates the field without firing Vue `input` events still enables **Load reference** and sends the correct URL.
- **PrimeVue tooltips**: Registered the `tooltip` directive globally in `main.ts` so `v-tooltip` on non-Button elements (e.g. the reference-structure info icon) works.
- **Mol\* reference / mmCIF blob**: Aligned references are written as **mmCIF** (BioPython `MMCIFIO`) and served as `chemical/x-mmcif`; the viewer uses **`referenceDataFormat: mmcif`** because **blob** URLs have no `.cif` suffix and were previously parsed as **PDB**. Het / nonStandard / coarse use **spacefill** on the reference overlay; **`alphafoldView: false`** for that load. Reference **LRU cache** key includes a format token so old PDB-shaped cache entries are not reused.
- **Mol\* autorotation**: After enabling spin, the viewer applies **`canvas3d.setProps`** to set trackball spin **speed `0.25`** (quarter of PDBe’s default `1`).
- **Mol\* control panel (spanner)**: `visual.update` reapplied `hideControls` on every update; when **`plugin.layout.state.showControls`** was not yet a boolean, the fallback treated the viewer as “panels hidden” and kept sending `hideControls: true`, undoing the spanner. Updates now prefer live **`showControls`**, then a **cached** value seeded after `render`, then the Vue prop. Initial options set **`hideCanvasControls: []`** so the canvas wrench is not stripped (standalone Mol\* URL `hide-controls` is unrelated — we embed PDBe Mol\*). **Reference overlay**: each `visual.update` shallow-merges with PDBe **DefaultParams**, so omitted **`reactive: true`** (used in `render`) reverted to **`reactive: false`**, changing **`controlsDisplay`** and leaving the spanner inert; all update paths now merge the same **interface** fields as **`fullReload`** (`reactive`, `landscape`, `expanded`, `hideCanvasControls`, etc.).
- **Designs table / advanced viewer**: Deferred `GET /api/runs/.../input-targets` until the Advanced options panel is opened (or an active input-target overlay needs a refresh on run change), and guarded the run watcher with `try/catch`, to avoid watcher/API edge cases during load. **Select top N** `InputNumber` now uses `max >= 1` so an empty filtered table does not pass `max=0` with `min=1` (invalid for PrimeVue `InputNumber`).
- **Run scan / tree paths**: Folder scans and `/api/tree` now resolve `RUN_BASE_DIRS` and requested paths before checking containment. Relative bases such as `./example_runs` no longer fail when the browser sends absolute paths (e.g. `/home/.../example_runs/boltzgen-nanobody`), which previously caused scans to be skipped and produced empty design lists.
- **Designs table score filters**: Min/max score filters now consider boltzgen fields `design_to_target_iptm` and `quality_score`, not only bindcraft/RFD score columns, so boltzgen rows are not incorrectly filtered out.
- **Boltzgen metrics CSV**: When several `final_designs_metrics_*.csv` files exist, the newest is chosen by numeric suffix (e.g. `_10` over `_2`), not lexicographic sort.
- **Plots tab**: Restored visible charts after scanning runs. A watcher was replacing API-loaded plot data with an empty set whenever the designs table had no run scope (`selectedRunIds` empty), and opening the Plots tab only refreshed the run list without auto-selecting a run or reloading combined data. The watcher now skips that overwrite when no runs are scoped in the designs store; switching to Plots calls `loadRunData` (fetch runs, auto-select, load plot data); scanning also refreshes the runs store.
- **Boltzgen run support**: Add support for nf-binder-design boltzgen runs.
- Plots now show one datapoint per design across selected runs
  - Frontend `plots` store now coerces numeric-like strings to numbers and derives a stable `design_id` per row
  - Uses backend `/api/runs/plots/columns` to prefer sensible axis defaults; falls back to columns with the highest valid coverage
  - Scatter and histogram filters now treat numeric strings correctly, preventing near-empty plots

### Added
- Designs table exports and PDBs archive download
  - Added SplitButton in `DesignsView.vue` with actions: Download TSV (default), Download CSV, Download PDBs
  - Checkbox "Include all columns" to export all columns or only currently visible columns
  - CSV/TSV export respects selection (exports selected rows, or all filtered rows if none selected)
  - Backend endpoint `POST /api/pdbs/tar` streams a tarball of requested PDBs without loading all files into memory
  - Frontend integrates tar download, packaging selected (or all filtered) PDBs into a single `.tar`
- **Target sequence filtering**: Added regex-based filtering for target sequences in designs table
  - New `target_sequence` filter in designs store with regex pattern matching support
  - Case-insensitive regex matching with fallback to simple string contains for invalid patterns
  - Target sequence column available in designs table (toggleable via column selector)
  - Enables advanced filtering of designs based on target protein sequence patterns

### Added
- **Folder selection persistence**: Added localStorage persistence for folder browser selections
  - Installed and configured `pinia-plugin-persistedstate` for Pinia store persistence
  - Selected folders, expanded tree nodes, and folder selection state now persist across page reloads
  - Only persists user preferences (selectedFolders, selectedKeys, expandedKeys) - not the entire folder tree or scan results
  - Improved user experience by maintaining folder browser state between sessions
- **Configurable API proxy target**: Added `API_BASE` environment variable for frontend development
  - Frontend Vite proxy now reads `API_BASE` environment variable to determine backend target
  - Defaults to `http://localhost:8000` if not set
  - Allows flexible configuration for different development environments

### Fixed
- **Authentication logic fix**: Fixed issue where login page wasn't showing correctly in production
  - Fixed auth store logic to properly handle initialization state when `authStatus` is `null`
  - Ensured `shouldShowLogin` correctly evaluates to `false` when authentication is disabled
  - Verified `DISABLE_AUTHENTICATION="true"` properly bypasses login page and shows main app directly
- **App.vue template logic**: Fixed template rendering logic to properly use `shouldShowLogin` computed property
  - Updated template to use `authStore.shouldShowLogin` instead of `shouldShowMainApp` for login page display
  - Removed unused `shouldShowMainApp` computed property
  - Ensured proper fallback behavior: show login by default until auth status is determined
- **Folder browser state synchronization**: Fixed folder selection and expansion state persistence issues
  - Unified folder selection system to use single `selectedKeys` state instead of duplicate `selectedFolders`
  - Fixed "Scan Selected Folders" button not recognizing persisted selections after page reload
  - Fixed tree expansion state mismatch where expanded icons showed but nodes appeared collapsed
  - Added automatic restoration of expanded state by loading children for persisted expanded nodes
  - Improved state persistence to only store user preferences (selectedKeys, expandedKeys) not entire tree

### Docker Containerization
- **Complete Docker setup**: Added full containerization support for production deployment
  - **Multi-stage Dockerfile**: Backend Dockerfile that builds frontend and serves static files via FastAPI
  - **Docker Compose configuration**: Complete setup with environment variables, volume mounts, and health checks
  - **Health check endpoint**: Added `/health` endpoint for container health monitoring
  - **Security hardening**: Non-root user, read-only data volumes, resource limits
  - **Comprehensive documentation**: Added DOCKER.md with setup instructions, troubleshooting, and production deployment guidance
  - **Environment configuration**: Simplified `.env` file handling using Docker Compose's `env_file` directive
  - **Data volume mounting**: Secure mounting of `RUN_BASE_DIRS` as read-only volumes
  - **Build optimization**: Added `.dockerignore` for efficient builds and smaller image sizes
  - **Development mode**: Added `docker-compose.dev.yml` with live reloading and source code watching
    - **Backend auto-reload**: FastAPI server automatically restarts when Python code changes
    - **Frontend watch mode**: Vite automatically rebuilds when Vue/TypeScript files change
    - **Full project mounting**: Entire project directory mounted for access to all files (playwright.config.js, etc.)
    - **Two-container setup**: Separate containers for backend and frontend watcher
    - **Single Dockerfile**: Unified Dockerfile with conditional frontend building for both production and development

### Enhanced Structure Viewer
- **Improved MolstarViewer performance**: Replaced destroy/recreate approach with PDBe Molstar `update()` helper method for smoother navigation
  - **Faster structure loading**: Uses `visual.update()` method to load new structures without recreating the entire viewer instance
  - **Auto-focus functionality**: Automatically focuses on new structures when navigating between designs
  - **Enhanced viewer controls**: Added focus and spin toggle buttons to the structure viewer interface
  - **Configurable viewer options**: Added props for auto-focus, show controls, and background color customization
  - **Helper method exposure**: Exposed useful PDBe Molstar helper methods (focus, spin, highlight, background color) for programmatic control
  - **Better error handling**: Improved error handling with fallback to full reload if update method fails
  - **Control panel preservation**: Fixed control panel disappearing after loading second structure by using minimal update parameters
  - **Theme consistency**: Restored visual theme parameters (visualStyle, hideStructure, bgColor) while preserving control panel state
  - **Improved structure details**: Enhanced structure information display with better formatted table layout
  - **Filtered navigation**: Fixed next/prev buttons to only cycle through visible/filtered rows in the table instead of all designs

### Security Improvements
- **Migrated to secure HttpOnly cookies**: Replaced localStorage token storage with industry-standard secure cookie authentication
  - **XSS Protection**: Authentication tokens now stored in HttpOnly cookies, preventing JavaScript access and XSS token theft
  - **CSRF Protection**: Added comprehensive CSRF protection middleware with token validation
  - **Secure Cookie Attributes**: Implemented `HttpOnly`, `Secure`, and `SameSite` cookie attributes for maximum security
  - **Automatic Cookie Management**: Browser automatically handles cookie transmission, eliminating manual Authorization header management
  - **PDB File Security**: Removed insecure query parameter authentication for PDB file access, now uses secure cookies
  - **Backward Compatibility**: Maintained support for both cookie and header-based authentication during transition

### Added
- **Local username/password authentication**: Implemented comprehensive authentication system
  - Added JWT token-based authentication with configurable expiration (30 minutes default)
  - Created password encryption utility script (`backend/scripts/encrypt_password.py`) for generating bcrypt hashes
  - Added authentication endpoints: `/api/auth/login`, `/api/auth/me`, `/api/auth/status`, `/api/auth/logout`
  - Implemented `DISABLE_AUTHENTICATION` environment variable to completely disable auth when set to 'true'
  - Protected all previously unsecured endpoints: runs management, designs management, and plotting APIs
  - Added Vue.js login component with modern UI using PrimeVue components
  - Added authentication state management with Pinia store
  - Updated webapi.ts to use secure cookie-based authentication with CSRF token support
  - Added user info display and logout functionality in the main app header
  - Authentication is optional - only enforced when `LOCAL_USERS` is configured and `DISABLE_AUTHENTICATION` is not 'true'
  - Fixed PDB file access authentication by supporting token-based authentication via query parameters for external viewers like Mol*
  - Fixed frontend authentication flow to prevent premature data loading before authentication is complete
  - Added proper loading states and authentication-aware data fetching to prevent "Failed to load designs" errors on login page
  - Improved logout button styling and positioning - now uses primary styling and positioned in top right of header
  - Enhanced authentication error handling - expired tokens now automatically redirect to login page without showing error toasts
  - Fixed logout button positioning to properly appear in top right corner of header
- **Configurable CORS origins**: Added support for `CORS_ALLOWED_ORIGINS` environment variable
  - Allows specifying comma-separated list of allowed origins for CORS requests
  - Defaults to `*` (allow all origins) if not configured
  - Supports both development (localhost) and production (domain) origins
  - Updated `.env.example` with configuration examples
- **Improved password encryption utility**: Enhanced `encrypt_password.py` script usability
  - Made interactive mode the default (username as positional argument)
  - Added support for password input via stdin (useful for scripts)
  - Simplified command-line interface with `--password` option
  - Updated documentation and examples throughout
- Rename: Column and UI label "Protocol" → "Method" across backend and frontend to avoid clash with BindCraft's internal "Protocol" column. Update your environment and API consumers accordingly.

### Changed
- **Simplified plotting architecture**: Removed unnecessary backend plotting API endpoints (`/api/runs/plots/scatter` and `/api/runs/plots/histogram`). Frontend now fetches raw data directly and handles all plotting logic with Vega-Lite, reducing API complexity and improving performance.

### Fixed
- **JSON serialization error**: Fixed `ValueError: Out of range float values are not JSON compliant: nan` by properly handling NaN and infinite values in DataFrame-to-JSON conversion in the `/api/runs/{run_id}/table` endpoint.
- **Initial scatter plot rendering**: Fixed issue where scatter plots wouldn't render immediately when runs are first selected, requiring users to change axis dropdowns to see the plot. Added proper DOM timing and container dimension checks.
- **Backend API endpoints**:
  - `GET /api/tree` - Return folder structure for the file browser
  - `POST /api/runs/scan` - Scan selected folders for valid run directories
  - `GET /api/runs/{run_id}/table` - Get results table data for specific runs
  - `GET /api/runs/{run_id}/files/pdb/{filename}` - Stream PDB files for structure viewing
  - `GET /api/runs` - List all cached runs
  - `DELETE /api/runs/{run_id}` - Remove specific run from cache
  - `DELETE /api/runs` - Clear all runs from cache
  - `GET /api/designs` - List all designs from all cached runs
  - `DELETE /api/designs` - Clear all designs from cache
  - `POST /api/runs/plots/columns` - Get combined columns from multiple runs
  - `POST /api/runs/plots/scatter` - Get raw data for scatter plots from multiple runs
  - `POST /api/runs/plots/histogram` - Get raw data for histograms from multiple runs
- **Run metadata enhancements**:
  - Added `project_id` field to RunMetadata with intelligent detection
  - Implemented `guess_project_id()` function for project ID detection from directory structure
  - Implemented `guess_run_name()` function for intelligent run name detection
  - Project ID guessing avoids disallowed names: 'runs', 'bindcraft', 'rfd', and numeric-only names
  - Run name guessing uses regex patterns to avoid disallowed names: 'results.*', 'bindcraft', 'batches', and numeric-only names
  - Both functions traverse directory hierarchy to find appropriate names
- **Run detection logic** based on prototypes:
  - BindCraft runs: detects `final_design_stats.csv` and `Accepted/` folder
  - RFD runs: detects `combined_scores.tsv` or `.cs` files in `af2_initial_guess/`
  - Recursive scanning with proper path validation
  - In-memory caching of scan results
- **Design parsing and aggregation**:
  - Unified design structure combining data from all runs
  - Automatic column detection for bindcraft (`Design`, `Average_i_pTM`) and RFD (`description`, `pae_interaction`)
  - Score columns handled as regular data columns in frontend instead of backend preprocessing
  - Smart sorting by appropriate scores (ascending for pae_interaction, descending for i_pTM)
  - PDB file association for structure viewing
  - Support for arbitrary additional columns from source tables with dynamic frontend column generation
- **Frontend components**:
  - Main app layout with TabView (Designs, Plots, Folder Browser)
  - FolderBrowser component with TreeTable for folder navigation and DataTable for scan results
  - RunsView component renamed to Designs view with comprehensive DataTable
  - PlotsView component with Vega-Lite based plotting system (scatter plots and histograms)
  - Automatic data refresh when switching to Plots tab
  - Multi-run data merging for combined plots
  - Frontend-based Vega-Lite specification generation
  - Structure viewer integrated below designs table
  - Added Project ID column to both Designs and Folder Browser tables
  - Centralized API client (`webapi.js`) for all frontend API calls with proper error handling
- **UI/UX improvements**:
  - Modern responsive design with PrimeVue components
  - Toast notifications for user feedback
  - Loading states and error handling
  - Pagination and sorting for data tables
  - Multi-select functionality for runs and designs
  - Column toggle functionality for designs table positioned above the table
  - Close button (X) in top-right corner of column selector panel
  - Comprehensive filter panel with global search, column-specific filters, and score range filtering
  - Default PrimeVue styling with checkbox row selection
- **Structure viewer integration**:
  - Molstar viewer for 3D protein structure visualization
  - PDB file loading via backend API endpoints
  - Navigation between selected structures with next/previous buttons
  - Row-based navigation reflecting filtered table state
  - Loading states and error handling for structure viewer
  - Proper cleanup and resource management

### Changed
- Updated project structure to support full-stack application
- Enhanced error handling and logging throughout backend
- Improved path validation and security measures
- Renamed "Runs & Structure Viewer" tab to "Designs"
- Restructured RunsView component to show designs instead of runs
- Updated FolderBrowser to show scan results as DataTable with run selection
- Integrated structure viewer below designs table instead of separate tab
- **Architecture improvements**:
  - Moved score column logic from backend to frontend for better separation of concerns
  - Backend now focuses on data parsing and metadata assignment
  - Frontend dynamically generates columns based on available data
  - Score columns (`pae_interaction`, `Average_i_pTM`) are now treated as regular data columns
- **Plots system refactoring**:
  - Moved Vega-Lite specification generation from backend to frontend for multiple-run endpoints
  - Multiple-run backend APIs now return raw data rows instead of Vega-Lite specs
  - Frontend creates Vega-Lite specifications locally for better customization
  - Added support for multiple runs data merging in plots
  - Implemented automatic data refresh when switching to Plots tab
  - Removed unused single-run plot endpoints (`/api/runs/{run_id}/plots/*`) to simplify API surface

### Fixed
- Static file serving configuration for frontend assets
- API endpoint routing and response formatting
- Toast component imports and usage across components
- **Molstar integration**: Refactored to separate component and fixed API issues
  - Created dedicated MolstarViewer.vue component for better modularity
  - Removed problematic molstar npm package that caused build failures
  - Switched to PDBe Molstar implementation from CDN (https://cdn.jsdelivr.net/npm/pdbe-molstar@latest/)
  - Fixed API usage to use direct PDBeMolstarPlugin constructor instead of non-existent create() method
  - Implemented proper PDB ID extraction from URLs for PDBe Molstar
  - Added extensive debugging and error handling for structure viewer
  - Separated Molstar logic from DesignsView component for better maintainability
  - Fixed TypeError: window.PDBeMolstarPlugin.create is not a function error
- **Automated Testing**: Added comprehensive Playwright test suite
  - Created reusable test script for complete workflow automation
  - Tests: Configure folders → Scan → View designs → Load structure
  - Added additional tests for design navigation and filter functionality
  - Configured automatic server startup and browser management
  - Added screenshot capture and HTML reporting for debugging
  - Created helper scripts and documentation for test execution

## [0.1.0] - 2025-08-31

### Added
- Initial project scaffolding
- FastAPI backend with basic static file serving
- Vue 3 frontend with Vite and PrimeVue
- Environment configuration with `.env` support
- Basic folder tree API endpoint (`GET /api/tree`)
- Project documentation and setup instructions
