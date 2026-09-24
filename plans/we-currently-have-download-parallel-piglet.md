# Plan: Design Bundle downloads (reproducible, versioned, round-trippable)

## Context

Binderdash's downloads today are a scatter of single-format exports with no record of
*how* the data was selected. The Designs tab offers TSV, CSV, PDBs (a tar, despite the
label) and FASTA; Prepare Sequences offers FASTA/TSV/CSV/Twist CSV; a Saved Set downloads
a minimal zip of `designs.csv` plus `structures/`. None of them record the selected runs,
the table sort, the active hard filters, the target-contact conditions, the ranking
metrics, or the tag and codon-optimisation settings that produced the output.

The practical consequence is that a downloaded folder of PDBs and sequences cannot be
explained six months later, and cannot be reproduced. Computed target-contact SASA values
are worse off again: they live in a SQLite cache, are never written into a design dict,
and so are invisible to every current export.

This change introduces a **design bundle** - one zip per download carrying the data files
plus versioned JSON describing the UI state that produced them, with JSON Schemas
alongside. The goal is reproducibility and preservation; the stretch goal, included here,
is round-trip restore of that state into a running Binderdash.

### Decisions taken

| Decision | Choice |
|---|---|
| Restore scope | Export **plus** JSON import (drop a `binderdash_session.json` / `prepare_sequences.json` to rehydrate). Zip import deferred. |
| Bundle scope | Exactly the rows currently in the Designs table - selected designs if any, else filtered designs (today's `getRowsToExport()`). **Not** every design in the selected runs. |
| Structure files | Always included. Server caps are a safety net only, with a pre-flight estimate in the UI. |
| SASA / target contacts | **Cached values only** - a download never triggers a computation. Coverage recorded in the manifest. |
| Designs tab menu | Keep TSV/CSV/PDBs/FASTA in the dropdown; the bundle becomes the SplitButton's default action. |
| Archive format | zip. The existing `/api/pdbs/tar` stays untouched for the quick PDB grab. |

---

## 1. Bundle layout

One shape for all three producers (Designs tab, Prepare Sequences tab, Saved Set). The
member list is invariant across sources - that is the property the tests lock down.

```
manifest.json                   build info, file inventory with sha256, coverage counts
designs.tsv                     union-of-keys table of the bundled rows
binders.fasta                   binder sequences, >design_id
binderdash_session.json         the UI state (schema-versioned)
target_contacts.tsv             per-design, per-residue cached SASA/distance (long format)
target_contacts_reference.json  per-run apo-SASA map, target key, compute params
structures/rank0001_<run>_<name>.pdb …
schemas/*.schema.json           JSON Schema for each JSON member
README.txt                      plain-text map of the above
```

Prepare Sequences adds `constructs.tsv`, `constructs_aa.fasta`, `constructs_dna.fasta`,
`constructs_twist.csv` and `prepare_sequences.json`. `kind` is the only switch - the
writer emits these iff `spec.prepared is not None`, so there is no second code path.
(`constructs_twist.csv` stays CSV because it is a vendor upload format, not a general
table.)

The bundle carries **TSV only** for the designs table - the CSV variant stays available as
a separate dropdown item for people who want it, but duplicating the same rows in two
delimiters inside one archive earns nothing.

`target_contacts.tsv` is long format: `run_id, design_id, residue_label, chain, resseq,
icode, resname, d_ca, d_cb, d_heavy, sasa_bound, sasa_apo, delta_sasa,
delta_sasa_percent`. Residues beyond the 12 Å record cutoff are not emitted; the reference
JSON plus the documented cutoff make them recoverable, which is the contract the filter
engine already relies on (`plans/target_contacts_filtering.md` §1).

**Correctness trap**: `sasa_apo` normally comes from `RunContext.apo_by_label`, but for a
run where `target_moves` is true the per-design record carries its own apo value and must
win. Getting this backwards silently exports wrong ΔSASA for exactly the runs where it
matters.

---

## 2. Backend

### 2.1 New package `backend/bundles/`

The central abstraction is a **bundle spec**: a resolved, source-agnostic description of
the zip's contents. Resolution and serialisation are separate phases, so the writer never
touches the DB and never knows where rows came from.

```
backend/bundles/__init__.py     re-exports BundleSpec, write_bundle, BundleCapsError
backend/bundles/spec.py         BundleSpec, StructureRef, ContactExport, check_caps, estimate
backend/bundles/models.py       Pydantic request bodies + JSON payload models
backend/bundles/sources.py      spec_from_live_request(), spec_from_saved_set()
backend/bundles/members.py      one writer per member (tsv/fasta/contacts/constructs)
backend/bundles/hashing.py      HashingWriter: sha256 while streaming into the zip
backend/bundles/writer.py       BundleSpec -> spooled temp zip; the only zipfile code
backend/bundles/json_schemas.py schema emission + SCHEMA_VERSION registry
backend/routers/bundles.py      the endpoints
```

`backend/routers/saved_sets.py` loses `_build_download_zip_sync` entirely and calls
`spec_from_saved_set()` → `write_bundle()`.

Both sources are sync (DB + filesystem) and are called under `asyncio.to_thread`, matching
the existing convention in `saved_sets.py`.

**The client posts design *keys*, not rows.** `DesignKey` already exists
(`backend/filtering/schemas.py:99`). The server re-reads design dicts from `backend/cache.py`.
This keeps a 20k-design request at ~1 MB rather than ~200 MB, and makes the bundle's
`designs.tsv` byte-identical to `GET /api/designs?format=tsv`. The only genuinely
client-side data - the prepared seq-prep rows, the UI state, and any client-computed
column such as the Binderdash ranking - is posted explicitly as an overlay keyed by
design key.

Divergence between the two sources is confined to row production:

- **live**: rows from the cache filtered to the posted keys, deduped preserving first-seen
  order; rank = position in the posted order.
- **saved set**: the frozen `row.metrics` from `service.get_saved_set_designs()`,
  deliberately *not* re-read from cache so an immutable set stays immutable; rank =
  `final_rank`.

Shared private helpers do the rest. `_resolve_structures()` is the single place that calls
`get_run_metadata()` + `_resolve_structure_path()`, `stat()`s each hit, and **records a
warning per miss** instead of the silent `continue` the current saved-set builder does -
that silent skip is a real defect, and the manifest's coverage counts now surface it.

`_arcname_for()` must namespace by run: two runs can share a structure basename, and today
`zipfile` drops the second with only a `UserWarning`. Use
`structures/rank{n:04d}_{run_short}_{basename}`, with a `seen` set and a `_2` suffix
fallback.

### 2.2 Streaming the tables

Do **not** build member content as one big string. 30k designs × 200 columns is a ~150 MB
Python `str` - a bigger RAM risk than the structures, which stream anyway. Each member
writer takes the open `ZipFile` and writes through
`zf.open(arcname, "w")` wrapped in `io.TextIOWrapper(..., newline="")`.

This needs a small refactor of `backend/util/design_list.py`, keeping the existing
signature as a thin wrapper so `routers/designs.py` is untouched:

```python
def design_columns(designs) -> list[str]                    # extracted union-of-keys logic
def write_designs_tsv(fh, designs, *, columns=None) -> None
def designs_to_tsv(designs) -> str                          # unchanged, wraps the above
```

**Checksums.** Every member is written through a small `HashingWriter` wrapper that
updates a `hashlib.sha256` as bytes pass into `zf.open(arcname, "w")`. Structures are read
in chunks by the same helper rather than via `zf.write(path)`, so one pass produces both
the archive entry and its digest - no second read over the structure files. The digest
goes in `manifest.files[].sha256`.

FASTA goes in a new `backend/util/design_fasta.py`. Seed the sequence-field probe from the
existing `SEQUENCE_EXTRA_KEYS` in `backend/persistence/protocol.py:383` and extend it to
match the frontend's order (`Sequence, sequence, binder_sequence, binder_seq, seq`) rather
than introducing a third list.

### 2.3 State models and schema versioning

Models live in `backend/bundles/models.py`, except `SessionState`, which goes in a leaf
module `backend/session_state.py` - `filtering/schemas.py` needs it (§2.6) and `bundles`
already imports from `filtering.schemas`, so a leaf module avoids the cycle outright.

**Typed spine with `extra="allow"` for the client-supplied payloads; strict typing for the
manifest.** The manifest is backend-authored and is what consumers parse, so type it
fully. `SessionState` and `PrepareSequencesPayload` mirror Pinia stores that change faster
than the backend; strict models would turn every frontend field addition into a 422 on
download, and would commit presentational junk (`segments_aa` CSS spans) to an archival
schema. Pin the archivally meaningful fields, let the rest ride along - and strip the
presentational fields on write via an explicit column list plus `model_dump(exclude=...)`
for `segments_aa`, `segments_dna`, `*_display` and `design_filter_text`.

Where a backend schema already exists, reuse it rather than redeclaring: `FilterSpec`,
`RankingMetric`, `TargetContactGroup`, `SizeBucket` (`backend/filtering/schemas.py`) and
`DnaOptConstraintSpec` (`backend/schemas.py`).

Every JSON member carries the same envelope:

```json
{
  "schema_version": "1.0",
  "kind": "binderdash.session",
  "generated_at": "2026-09-24T...Z",
  "binderdash": { "app_version": "0.3.0", "git_commit": "8074aeb", "git_dirty": false,
                  "build_source": "git" }
}
```

Bump the major only on a breaking change; additive optional fields bump the minor.
Readers reject a major above the one they know and ignore unknown keys.

`manifest.json` is typed as `BundleManifest`: `bundle_id`, `bundle_kind`, `created_at`,
`label`, `build: BuildInfo`, `provenance: BundleProvenance`, `coverage: BundleCoverage`,
`files: list[BundleFileEntry]`, `warnings`. Each file entry carries `path, size_bytes,
sha256, media_type, description`. Write the manifest last; it cannot list itself, and its
own description should say so - so verifying the manifest's own integrity is the zip's
CRC, and `unzip -t` covers it (note that in `README.txt`).

`BundleCoverage` records `designs, designs_with_sequence, structures_requested,
structures_included, structures_missing, designs_with_contacts, designs_without_contacts,
contact_params_key, constructs`. The `params_key` matters: records cached under an older
key are invisible to `load_contact_data`, so the bundle must not claim full coverage.

### 2.4 JSON Schemas

`backend/bundles/json_schemas.py` holds a `BUNDLE_SCHEMAS` registry mapping name →
(model, version), and emits schemas at request time from `model_json_schema()`, stamped
with `$id`, `$schema` and `x-binderdash-schema-version`. Generating on the fly makes the
shipped schema definitionally consistent with the data in the same zip; committed files
drift the moment someone adds a field.

Discipline is enforced by test, not convention: commit golden snapshots under
`backend/tests/fixtures/bundle_schemas/<name>.<version>.schema.json`. Any model change
fails with a diff, and the fix is either regenerate-and-bump-minor (additive) or
new-golden-and-bump-major (breaking). Because the client payloads are `extra="allow"`,
frontend additions don't change the schema at all - which is the main argument for the
loose typing there.

### 2.5 `backend/version.py`

`build_identity()` (`lru_cache`d, resolved lazily at first bundle download, never at
import) returns `app_version, git_commit, git_dirty, source`. Resolution order:

1. `BINDERDASH_GIT_COMMIT` / `BINDERDASH_VERSION` env - wired as a Docker build arg and
   in `.github/workflows/desktop-release.yml`.
2. `backend/_build_info.json` - gitignored, written by the PyInstaller build and added to
   `desktop/binderdash.spec` `datas`. **This is the only mechanism that works frozen**,
   where there is no `.git` and no dist-info.
3. `git rev-parse --short=12 HEAD` plus `git status --porcelain`, guarded by a `.git`
   existence check, `timeout=2`, and try/except for `FileNotFoundError`/`TimeoutExpired`.
4. Unknown.

`app_version()` independently falls back to `importlib.metadata` then the pyproject regex.
Refactor `backend/routers/desktop.py:18` to `from ..version import app_version` so there
is one implementation and `test_desktop_api.py` keeps passing.

### 2.6 Saved sets carry UI state

Add `ui_state: SessionState | None = None` to `FilteringRunRequest`. Because
`run_filtering()` stores `filter_params = request.model_dump()`, it lands in the existing
`filter_params` JSON column with no migration.

Sets created before this change have no key. `spec_from_saved_set()` must still emit
`binderdash_session.json`, with `{"captured": false, "note": "This saved set predates UI
state capture."}` - omitting the file would break the invariant member list. Also strip
`ui_state` from the `provenance.filter_params` copy so the same data isn't duplicated
twice in one zip.

`frontend/src/stores/filtering.ts` `loadRecipe()` gains `ui_state` handling, so "Reapply
filters" restores the table sort too.

### 2.7 Endpoints - `backend/routers/bundles.py`

| Endpoint | Purpose |
|---|---|
| `POST /api/bundles/estimate` | Pre-flight. Resolves paths and `stat()`s them; reads nothing. Returns counts, `structure_bytes`, an `estimated_zip_bytes`, the caps, and `exceeds_cap`. |
| `POST /api/bundles/designs` | Streams the designs bundle. |
| `POST /api/bundles/prepare-sequences` | Superset; body adds `prepared`. |
| `GET /api/saved-sets/{id}/download` | Existing route, rewritten onto the shared path. |

Mount in `backend/main.py` beside the other routers.

**Memory.** `write_bundle()` builds into a `tempfile.SpooledTemporaryFile(max_size=32 MiB,
dir=bundle_spool_dir())` - RAM for small bundles, spilling to disk for large ones - then
returns a file object the router streams with an explicit `Content-Length` and a
`BackgroundTask` that closes it. Not `FileResponse`: a spooled file has no stable path.
Not a generator-based zip writer: `zipfile` can write to a non-seekable stream, but you
lose `Content-Length` (no browser progress bar), a mid-stream exception becomes a
truncated zip with a 200 status, and `zf.write(path)` streams file-by-file regardless - so
the RAM saving over the spooled file is zero.

`bundle_spool_dir()`: `BINDERDASH_BUNDLE_SPOOL_DIR` → `user_data_dir()/bundle_spool` when
frozen → `tempfile.gettempdir()`. The frozen case matters because `/tmp` is often tmpfs,
i.e. RAM, which would silently defeat the spill. Check
`shutil.disk_usage(...).free` against the estimate up front and fail with 507 rather than
an `ENOSPC` traceback halfway through.

Compression `ZIP_DEFLATED` level 6, `allowZip64=True`. PDB/CIF text compresses 4-6×, which
matters far more than the CPU.

**Caps** in `backend/settings.py`, following the existing `RawSettings`/`AppSettings`
pattern, added to `.env.example`: `bundle_max_structure_files` (5000),
`bundle_max_structure_bytes` (2 GiB), `bundle_max_total_bytes` (4 GiB). Exceeding any
returns 413 with a structured body carrying the estimate, so the UI can say "2,847
structures / 3.1 GB exceeds the 2 GB limit". Since a bundle only ever covers rows in the
table, these are guards against a runaway request rather than part of normal use.

**Auth.** Standard `get_current_user_optional` + CSRF on the POSTs; the frontend already
POSTs and saves a `Blob` in `runsApi.downloadPdbsTar`, so no `download_tokens.py` minting
is needed. The saved-set route stays a cookie-authenticated `GET` so `window.open` keeps
working. Note `response.blob()` materialises the whole zip in browser memory - that, not
the server, is why the UI warns above ~500 MB. If genuinely huge bundles are needed later,
the additive upgrade is a two-phase prepare/fetch flow with a `PURPOSE_BUNDLE_DOWNLOAD`
token; don't build it now, as the spool file is process-local and would break under
multiple uvicorn workers.

Other sharp edges: `zipfile` errors on file mtimes before 1980 (catch per structure, warn,
continue); `ZipFile` is not thread-safe, so don't parallelise structure writes; log build
duration via the existing `backend/util/profiling.py`, since one long build occupies a
`to_thread` worker.

---

## 3. Frontend

### 3.1 Designs tab - `frontend/src/components/DesignsView.vue`

SplitButton's main action becomes **"Download Design Bundle (zip)"**; the four existing
items stay in `exportMenuItems`. `onDownloadBundle()` calls `bundlesApi.estimate()` first,
shows a confirm dialog above ~500 MB, then POSTs and hands the `Blob` to the existing
`downloadBlob()`. Row scope stays `getRowsToExport()`; only the keys are sent.

### 3.2 Session state - new `frontend/src/session/sessionState.ts`

`buildSessionState()` collects from the stores: `designs` (`selectedRunIds`, resolved
design keys, `visibleColumns`, `tableMultiSortMeta`, `bestMpnnOnly`, `selectedSavedSetIds`),
`filtering` (the six fields it already persists, plus `diversityEnabled`), `plots`
(`scatterAxisPreferences`), and `runs` for per-run metadata.

`applySessionState()` is the inverse, delegating the filter/ranking half to the existing
`filteringStore.loadRecipe()`. It reuses the defensive per-field validation style of the
existing `hydrateFromPersistence()` methods and reports per-section outcomes (applied /
skipped / run not found) rather than failing wholesale.

`frontend/src/session/prepareState.ts` does the same for the ~40 `seqPrep` settings
fields. `seqPrep` persists nothing today, so wiring `buildPrepareState`/`applyPrepareState`
into `PERSISTENCE_KEYS` and `hydrate.ts` also fixes losing tag and codon settings on
refresh - a small bonus for the same work.

### 3.3 Prepare Sequences - `PrepareSequencesView.vue`

SplitButton default becomes **"Download Design Bundle (zip)"**; FASTA/TSV/CSV/Twist stay in
the dropdown, and `guardDownload()` runs first unchanged. The POST sends design keys,
`buildSessionState()`, `buildPrepareState()`, and `seqPrep.preparedRows` minus the
presentational fields.

### 3.4 Import

A **"Restore session from JSON"** item in `App.vue` opening a `.json` file input,
dispatching on the envelope `kind` to `applySessionState` or `applyPrepareState`, then
toasting a summary of what was restored and what was skipped. Reject an unknown `kind` or
an unsupported major `schema_version` with a clear message.

### 3.5 `frontend/src/webapi.ts`

Add `bundlesApi` with `estimate()`, `downloadDesignsBundle()`, `downloadPrepareBundle()`,
following the `runsApi.downloadPdbsTar` pattern (raw `fetch`, `X-CSRF-Token`,
`credentials: 'include'`, returns `Blob`), plus the session/prepare DTOs.

---

## 4. Files touched

**New**: `backend/bundles/{__init__,spec,models,sources,members,writer,json_schemas}.py`,
`backend/session_state.py`, `backend/version.py`, `backend/routers/bundles.py`,
`backend/util/design_fasta.py`, `frontend/src/session/{sessionState,prepareState}.ts`,
`frontend/src/components/RestoreSessionDialog.vue`, and the test files in §5.

**Modified**: `backend/routers/{saved_sets,desktop}.py`, `backend/main.py`,
`backend/settings.py`, `backend/util/design_list.py`, `backend/filtering/schemas.py`,
`backend/Dockerfile`, `desktop/binderdash.spec`,
`frontend/src/components/{DesignsView,PrepareSequencesView,App}.vue`,
`frontend/src/webapi.ts`, `frontend/src/stores/filtering.ts`,
`frontend/src/persistence/{keys,hydrate}.ts`, `.env.example`, `CHANGELOG.md`,
`docs/development/storage.md`.

---

## 5. Verification

Backend (`conda deactivate; conda deactivate; source .venv/bin/activate`), using the
existing `api_client` and `sqlite_designs_repo` fixtures in `backend/tests/conftest.py`:

1. **`test_bundle_spec.py`** - key dedupe preserves first-seen order and ranks 1..n; a
   missing structure yields a warning and a coverage increment, not an exception; two runs
   sharing a basename get distinct arcnames; `check_caps` raises at both the file-count and
   byte caps with the estimate attached.
2. **`test_bundle_writer.py`** - exact member list for both kinds, and no `designs.csv`;
   `designs.tsv` bytes equal `designs_to_tsv(rows)` (locks the shared-serialiser
   refactor); every `manifest.files[].sha256` matches `hashlib.sha256` recomputed over the
   extracted member, including a structure file (proves the single-pass hashing is right);
   monkeypatch the spool threshold to 1 KB and confirm a rolled-to-disk bundle still opens.
3. **`test_bundle_routes.py`** - 200 with `Content-Length == len(content)`; the prepare
   bundle has the construct members and the designs bundle does not; an unknown field in a
   posted prepared row gives 200 (proving `extra="allow"`) while a missing `prepared_aa`
   gives 422; over-cap gives 413 with structured detail; estimate counts match the bundle
   actually produced; CSRF-less POST with auth enabled gives 403 (see `test_api_key_auth.py`
   for the client fixture pattern).
4. **`test_saved_set_bundle.py`** - the saved-set download and an equivalent
   `POST /api/bundles/designs` produce the same member set; `provenance.source ==
   "saved_set"`; `ui_state` is stripped from the manifest's `filter_params` copy; a legacy
   set with no `ui_state` still emits `binderdash_session.json` with `captured: false`.
   Adapt any existing saved-set download assertions rather than leaving two contradictory
   expectations.
5. **`test_bundle_schemas.py`** - every registry entry matches its committed golden;
   every schema carries `$id`/`$schema`/`x-binderdash-schema-version` equal to the model's
   default; `BundleManifest.model_validate()` round-trips from a real bundle. Add
   `jsonschema` to the **dev extra only**, never `backend/requirements.txt` (PyInstaller
   installs from that file).
6. **`test_version.py`** - env beats build file beats git; with none available and
   `subprocess.run` monkeypatched to raise, returns `source="unknown"` without raising;
   `routers/desktop._app_version()` still returns the pyproject version.
7. Extend **`test_target_contacts_e2e.py`** with one case asserting that a run with
   `target_moves` true exports `sasa_apo` from the per-design record, not the run reference.
8. `pytest` (full suite) - regression guard on the `design_list.py` and `desktop.py`
   refactors.

Frontend and end-to-end:

9. `cd frontend && pnpm run build`, then `pnpm run watch:build` and drive :8000.
10. Manual: select a run, sort by two columns, add a hard filter and a ranking metric,
    download the bundle. Unzip; confirm `binderdash_session.json` records the sort and both
    filter sections, and `structures/` holds only the filtered rows.
11. Manual round trip: clear IndexedDB, reload, restore the JSON from step 10, confirm
    runs, sort, filters and ranking come back.
12. Prepare Sequences: place an N-terminal His tag, optimise DNA, download; confirm
    `constructs_dna.fasta` matches the table and `prepare_sequences.json` carries the tags,
    codon table and constraint list.
13. `pnpm test` from the repo root, plus a new Playwright case clicking the default
    download action and asserting a zip arrives.
