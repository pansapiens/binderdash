# Plan: "Target contacts" filtering section

Adds a new **"2. Target contacts"** section to the Filtering tab. It lets the user pick
target residues (multi-select with search) and require, per design, that those residues
are within/further than X Å of the binder, and/or that their SASA in the complex or
their change in SASA on binding meets a threshold. The resulting conditions are hard
filters, applied alongside section 1's Hard Filters, so they narrow the Designs table,
the filter cascade, ranking, diversity selection and Saved Sets with no changes needed
in any of those.

Two related pieces come with it: per-target subsections, so one filter set can express
conditions against more than one target whose residue numbering differs (§3.3, §4.2),
and a "Target contact map" section in the Designs tab's structure viewer that colours
the target by mean ΔSASA or contact frequency across a design set (§6). The filters are
also exposed through the MCP server, alongside two new tools for discovering residue
labels and reading the per-residue profile (§5).

Decisions already taken (from the kickoff discussion):

- **Compute on demand**, via a button in the new section, batched with a progress bar,
  results cached in SQLite. No background-job infrastructure is added.
- **Store per-design records only for target residues within 12 Å** (heavy-atom) of the
  binder, plus a per-run reference apo-SASA map for every target residue.
- **Offer both** absolute "SASA when bound" and "ΔSASA on binding" filters.
- The SASA computation follows
  [`bin/complex_sasa.py`](https://github.com/Australian-Protein-Design-Initiative/nf-binder-design/blob/main/bin/complex_sasa.py)
  from `nf-binder-design`, so Binderdash numbers agree with that pipeline's TSV output.
  See §3.0 for what Binderdash already has and what actually needs porting.

---

## 1. Why the storage scope is sufficient

A target residue more than 12 Å (heavy atom to heavy atom) from the binder has
identical SASA in the complex and in the apo target, so its ΔSASA is 0 and its bound
SASA equals its reference apo SASA. Both are recoverable from the per-run reference map
without a per-design record. The only capability lost is a distance threshold above
12 Å, which the UI caps accordingly. This keeps a per-design record at roughly 60-120
residues rather than the full target (often 200-600), about 5-8 KB of JSON per design.

The assumption behind the reference map is that the target coordinates are the same in
every design of a run. That holds for the fixed-target methods Binderdash ingests. The
compute step verifies it cheaply (hash of target backbone coordinates of the first
structure vs. a sample of others) and records a per-run warning if it does not, in which
case apo SASA is computed and stored per design rather than per run.

## 2. Metric definitions

Per design, per target residue within the record cutoff:

| Field | Meaning |
| --- | --- |
| `d_ca` | Distance from this residue's CA to the nearest binder CA |
| `d_cb` | Same for CB (CA used for glycine) |
| `d_heavy` | Minimum heavy-atom to heavy-atom distance to the binder |
| `sasa_bound` | Residue SASA in the complex, Å² |
| `sasa_apo` | Residue SASA with the binder chains removed, Å² (per-run reference unless the target moves) |

Derived on read, not stored:

- `delta_sasa = sasa_apo - sasa_bound` (Å²), the buried area. Positive means the binder
  occludes the residue.
- `delta_sasa_pct = 100 * delta_sasa / TIEN_MAX[resname]`, matching
  `complex_sasa.py`'s `delta_percent`, i.e. the fraction of the residue's theoretical
  maximum surface that the binder buries. Using the Tien 2013 maximum rather than the
  apo value is deliberate: it keeps the number comparable across residues and identical
  to the Nextflow pipeline's column.
- `sasa_bound_pct = 100 * sasa_bound / TIEN_MAX[resname]`, relative solvent
  accessibility in the complex. This is the quantity that answers "is this residue still
  exposed once the binder is bound", and it is the one that is misleading on its own for
  an already-buried residue, hence offering ΔSASA alongside it.

`TIEN_2023_THEORETICAL` already exists in `backend/tag_placement.py`; move it to
`backend/util/sasa_constants.py` and import from both places.

## 3. Backend

### 3.0 What Binderdash already has

Checked before deciding to port anything. There are two existing SASA code paths, and
neither computes per-target-residue apo-vs-complex SASA:

| Existing | What it does | Reusable here? |
| --- | --- | --- |
| `backend/tag_placement.py` | BioPython `PDBParser` + `ShrakeRupley` at residue level, `%SASA` via `TIEN_2023_THEORETICAL`, CA-distance contact check against target residues at a 6 Å cutoff | Yes, partly. Same library, same Tien table, same `probe_radius`/`n_points` plumbing and the `warnings.filterwarnings` incantations. But it only looks at the binder's two terminal residues, computes SASA in a single state (no apo pass), and returns booleans rather than per-residue values. |
| `backend/filtering/structural_metrics.py::delta_sasa` | biotite `struc.sasa`, target-alone minus target-in-complex | Concept matches exactly, but it is a single whole-interface total, not per residue, and it is biotite rather than BioPython. |

So the genuinely new work is the per-residue apo/complex pair plus the distance vector.
The plan reuses the Tien table and the BioPython conventions already in
`tag_placement.py`, and ports from `complex_sasa.py` only the parts with no in-repo
equivalent: `make_apo_structure`, `compute_residue_sasa_map`, `iter_target_residues`,
`parse_residue_token`/`default_residue_label`, and the `site_percent` aggregation.
Sticking with BioPython (rather than the biotite path in `structural_metrics.py`) keeps
the numbers directly comparable to the Nextflow pipeline's TSV, which is the point of
following that script.

`structural_metrics.delta_sasa` stays as it is; it answers a different question (total
interface burial as a single design-level metric) and is already wired into
`/api/designs/structural-metrics`. Worth a cross-reference comment in both modules so
the two are not mistaken for duplicates.

### 3.1 `backend/filtering/target_contacts.py` (new)

Ported from `complex_sasa.py` where §3.0 says there is no in-repo equivalent, keeping
its structure and naming where they carry over:

- `ResidueKey = Tuple[str, int, str]` (chain, resseq, icode), `residue_key_sort_key`,
  `default_residue_label`, `parse_residue_token`, `iter_target_residues`,
  `compute_residue_sasa_map`, `make_apo_structure` all port essentially unchanged.
  BioPython `PDBParser` for parsing and BioPython's SASA conventions (its `ATOMIC_RADII`
  and golden-spiral point mesh), matching the source script and `tag_placement.py`.
  Those conventions are now applied by biotite's kernel rather than
  `Bio.PDB.SASA`, which is ~20x faster on identical inputs - see §7 and the
  `target_contacts` module docstring. `make_apo_structure` is gone with it: dropping the
  binder from the occluder set replaces deep-copying the structure.
- New: `residue_min_distances(structure, binder_chains) -> Dict[ResidueKey, Tuple[float, float, float]]`,
  a single scipy `cKDTree` query over binder heavy atoms giving `d_ca`, `d_cb`,
  `d_heavy` per target residue.
- `compute_target_contacts(pdb_path, binder_chains, *, record_cutoff=12.0, probe_radius=1.4, n_points=100, apo_sasa=None) -> TargetContactRecord`
  runs the complex SASA pass, the apo pass (skipped when `apo_sasa` is supplied from the
  run reference), and the distance pass, then keeps only residues with
  `d_heavy <= record_cutoff`.
- `compute_reference_residues(pdb_path, binder_chains) -> List[TargetResidueInfo]`
  produces the per-run residue catalogue (chain, resseq, icode, resname, one-letter,
  label, apo SASA) used to populate the UI dropdown and to fill in out-of-cutoff
  residues at filter time.
- A `ProcessPoolExecutor`-based `compute_many(...)` mirroring
  `analyse_structures_parallel`, defaulting to `os.cpu_count()` workers, used by the
  compute endpoint. `engine.py` already sets the precedent for a process pool inside a
  request.

Also port the `--site` idea as a follow-up hook: a named residue set is exactly what the
UI's residue multi-select produces, so the aggregate "site burial %" is available for
free as a filterable quantity (see §3.3 `scope: "site_percent"`).

### 3.2 Persistence

Two new tables in `backend/persistence/sqlite_repo.py` (`init_schema`), matching the
existing `binderdash_structural_metrics_cache` shape and conventions:

```sql
CREATE TABLE IF NOT EXISTS binderdash_target_contacts_cache (
    run_id TEXT NOT NULL,
    design_id TEXT NOT NULL,
    source_path TEXT NOT NULL DEFAULT '',
    structure_filename TEXT NOT NULL,
    binder_chains TEXT NOT NULL DEFAULT '',
    target_chains TEXT NOT NULL DEFAULT '',
    params_key TEXT NOT NULL,          -- hash of cutoff/probe_radius/n_points
    contacts_json TEXT NOT NULL,       -- {label: [d_ca, d_cb, d_heavy, sasa_bound, sasa_apo|null]}
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, design_id, source_path, structure_filename,
                 binder_chains, target_chains, params_key)
);

CREATE TABLE IF NOT EXISTS binderdash_target_residues (
    run_id TEXT NOT NULL,
    params_key TEXT NOT NULL,
    binder_chains TEXT NOT NULL DEFAULT '',
    target_chains TEXT NOT NULL DEFAULT '',
    residues_json TEXT NOT NULL,       -- [{chain, resseq, icode, resname, aa1, label, sasa_apo}]
    target_moves INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, params_key, binder_chains, target_chains)
);
```

Values are stored as a positional array per residue rather than a nested object to keep
the JSON small. New repository methods on the `DesignsRepository` Protocol
(`protocol.py`), the SQLite implementation and `noop_repo.py`:

- `get_target_contacts_cache(...)` / `upsert_target_contacts_cache_bulk(items)`
  (bulk, since the compute endpoint writes hundreds of rows per batch)
- `list_target_contacts_for_runs(run_ids, params_key) -> Dict[design_key, record]`
- `count_target_contacts_for_runs(run_ids, params_key) -> Dict[run_id, int]` for coverage
- `get_target_residues(run_id, ...)` / `upsert_target_residues(...)`

`delete_run` gains `DELETE FROM` for both tables, alongside the existing structural
metrics cleanup at `sqlite_repo.py:856`.

### 3.3 Schemas (`backend/filtering/schemas.py`)

```python
class TargetContactFilterSpec(BaseModel):
    residues: List[str]                  # labels, e.g. "A166" or "A166A" with icode
    scope: Literal["any", "all", "count", "site_percent"] = "any"
    min_count: Optional[int] = None      # for scope="count"
    metric: Literal["distance", "sasa_bound", "delta_sasa"]
    distance_type: Literal["ca", "cb", "heavy"] = "heavy"   # metric="distance" only
    unit: Literal["angstrom", "percent"] = "angstrom"       # SASA metrics only
    operator: Literal["<", "<=", ">", ">="]
    value: float
    enabled: bool = True                 # UI-only, stripped before send (see store)


class TargetContactGroup(BaseModel):
    """One target's worth of contact filters. Multiple groups let a filter set express
    'residue A166 on target X, and the equivalent residue B142 on target Y', where the
    two targets have different numbering or constructs."""

    target_key: str                      # see TargetInfo below
    run_ids: List[str] = []              # empty = every run whose target is target_key
    label: Optional[str] = None          # display only, e.g. "PD-L1 (chain A)"
    filters: List[TargetContactFilterSpec] = []
```

`target_contact_groups: List[TargetContactGroup] = []` is added to
`FilteringApplyRequest`, `FilteringPreviewRequest`, `FilteringRankRequest`,
`FilteringDiversityRequest` and `FilteringRunRequest`. Because `filter_params` on a
Saved Set stores `request.model_dump()` wholesale, recipes round-trip with no extra
work.

**Applicability rules**, all following the engine's existing "not applicable to this
row ⇒ the row passes" convention in `_filter_mask`:

1. A design whose run is outside a group's scope is exempt from every filter in that
   group. Consequently, with one group per target, a design is only ever constrained by
   the filters written against its own target.
2. Within a group, a design whose run lacks a residue with that label is exempt from
   that filter. This covers minor numbering drift inside one target group.
3. A design whose run *has* the residue but has no computed contact record *fails*, and
   the UI warns about the uncomputed runs rather than silently emptying the table.

A single-target run scope is the common case and produces exactly one group, so the UI
only shows the target selector and the (+) control once more than one target is present
in the scope (see §4.2).

**Target identity.** `target_key` is `sha256(target_chain_sequences)[:16]`, computed from
the run's reference structure via the chains that `resolve_chain_roles_cached` classified
as target. Runs sharing a target sequence therefore share a key and a residue catalogue
regardless of run name or method. It is stored on the `binderdash_target_residues` row
so the mapping survives restarts. Two constructs of the same protein that differ by a
tag or a truncation get different keys, which is the desired behaviour: their numbering
differs, so they need separate groups.

New request/response models:

- `TargetResiduesRequest{run_ids}` / `TargetResiduesResponse{targets: [TargetInfo], coverage: [...], warnings: [...]}`
  where `TargetInfo` is `{target_key, label, run_ids, chain_ids, length, residues: [...]}`
  and each residue carries `label`, `resname`, `aa1`, `chain`, `resseq`, `sasa_apo`.
  `coverage` is per-run `{run_id, target_key, total_designs, computed_designs, target_moves}`.
- `TargetContactsComputeRequest{run_ids, design_keys?, ignore_cache=False, max_workers?}`
  / `TargetContactsComputeResponse{computed, cached, failed, errors, coverage}`.
- `TargetContactProfileRequest{run_ids, design_keys?, target_key, metric, distance_type, contact_threshold?}`
  / `TargetContactProfileResponse{target_key, residues: [{label, chain, resseq, resname, mean, median, min, max, contact_fraction, n}], n_designs}`
  backing the structure-viewer colour map (§6).

### 3.4 Evaluation: a virtual-column pre-pass

The engine stays untouched. A new
`backend/filtering/target_contacts_service.py` provides:

```python
def augment_with_target_contacts(
    df: pl.DataFrame, groups: List[TargetContactGroup]
) -> Tuple[pl.DataFrame, List[FilterSpec], List[str]]
```

It loads the cached records for the run scope once, then for each filter in each group
evaluates the condition per design in Python (rows outside the group's run scope are set
to `True` per applicability rule 1) and appends a boolean column `__tc_{g}_{i}` to the
DataFrame, returning a matching `FilterSpec(column="__tc_{g}_{i}", operator="equals", text_value="true")`
(or a dedicated boolean path, whichever reads better).

Both the REST service and the MCP tools build their own DataFrame and call the engine
directly, so the augmentation must not live inside `service.py` alone. It is exposed as
one shared entry point that replaces the bare `build_designs_dataframe` call in every
one of those places:

```python
def build_filter_inputs(
    run_ids: List[str],
    filters: List[FilterSpec],
    target_contact_groups: List[TargetContactGroup],
) -> FilterInputs        # .df, .specs, .labels, .warnings
```

Call sites: the five in `backend/filtering/service.py` (`compute_apply`,
`compute_preview`, `compute_rank`, `compute_diversity_preview`,
`run_filtering_and_save`) and the three in the MCP tools (see §5). Ordering:
target-contact stages come after the plain hard filters in the cascade, so section
numbering and the cascade table agree.

The displayed name for a `__tc_{g}_{i}` column comes from a parallel list of human
labels passed back to the cascade builder, e.g.
`PD-L1: any of A166,A167,A170 within 8 Å (heavy)`.
`FilterCascadeStage` gains an optional `label` field so the preview response can carry
it without the frontend re-deriving it.

`__tc_*` columns are excluded from `compute_available_columns` (add to
`is_excluded_metric_column`) so they never appear in the section-1 column picker, and
are stripped from the `metrics` blob written by `run_filtering_and_save`.

### 3.5 Router (`backend/routers/filtering.py`)

- `POST /api/filtering/target-residues` -> `TargetResiduesResponse`. Resolves chain roles
  via `resolve_chain_roles_cached`, reads or computes the per-run residue catalogue (one
  structure per run, cheap), groups runs into targets by `target_key`, and reports
  per-run coverage.
- `POST /api/filtering/target-contacts/compute` -> `TargetContactsComputeResponse`.
  Computes (process pool) and caches for the designs named in the request, skipping
  those already cached unless `ignore_cache`. The frontend batches, so each call stays
  well inside a normal request timeout; batch size is a frontend constant (see §4.3).
- `POST /api/filtering/target-contacts/profile` -> `TargetContactProfileResponse`.
  Aggregates cached records across a design set into per-residue statistics for the
  structure-viewer colour map (§6). Read-only, no computation; residues with no record
  in a design contribute `delta_sasa = 0` / `distance > cutoff`, per §1.

All wrapped in `asyncio.to_thread` like the rest of the router.

## 4. Frontend

### 4.1 Store (`frontend/src/stores/filtering.ts`)

New state: `targetContactGroups`, `targets` (the `TargetInfo` list for the run scope),
`targetCoverage`, `targetsLoading/Error`, `contactsComputeProgress {done, total, running}`,
`contactsComputeError`.

New getters: `activeTargetContactGroups` (strips `enabled`, drops disabled rows and
empty groups, same pattern as `activeFilters`), `runsMissingContacts`,
`hasUncomputedContacts`, `hasMultipleTargets` (drives the target selector's visibility).

New actions: `fetchTargets`, `computeTargetContacts` (batched loop updating progress),
`addTargetContactGroup`, `removeTargetContactGroup`, `addTargetContactFilter(groupIdx)`,
`removeTargetContactFilter`, `toggleTargetContactFilterEnabled`, and
`fetchTargetContactProfile` shared with the viewer section (§6.3).

Every outgoing request body in the store gains
`target_contact_groups: activeTargetContactGroups.value`. `scheduleApply` is reused
verbatim, so contact filters live-narrow the Designs table on the same 300 ms debounce.
`resetFilterSet`, `loadRecipe`, the IndexedDB persist payload and `hydrateFromPersistence`
all gain `targetContactGroups`. The persistence key stays
`binderdash:filtering-view-state-v1`; the extra field is additive and absent payloads
hydrate to `[]`, so no key bump and no `DB_VERSION` bump.

When the run scope changes, groups whose `target_key` is no longer present are kept but
flagged inactive rather than dropped, so switching runs and switching back does not lose
a carefully built residue list.

`filterChain` gains the target-contact rows, prefixed with their group's target label so
two targets' stages are distinguishable, and `FilterChainSummary.vue` and the cascade
table pick them up with no change beyond a new `type: 'target_contact'` branch in
`utils/filterLabel.ts`.

### 4.2 `TargetContactFilters.vue` (new component)

Rendered by `FilterSetBuilder.vue` as `<Panel header="2. Target contacts">`, with the
existing panels renumbered to "3. Ranking Metrics", "4. Diversity Selection",
"5. Filter cascade", "6. Create Saved Set".

The panel is a list of **target subsections**, one per `TargetContactGroup`:

```
┌ Target: PD-L1 (chain A, 221 aa) · 3 runs  ▾                             [×] ┐
│ [≡] [Residues ▾ (multiselect, searchable, chips)] [condition ▾] [value] …   │
│ [≡] [Residues ▾]                                  [condition ▾] [value] …   │
│ (+) Add condition                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
(+) Add target
```

The target dropdown lists the `TargetInfo` entries returned for the current run scope,
labelled `<name or chain summary> · N runs`, with the run names on hover. Picking a
target sets the subsection's `target_key` and repopulates its residue options. Two
subsections on different targets is how equivalent residues under different numbering
are expressed: `A166` on one, `B142` on the other, each constraining only its own runs.

When the run scope contains a single target (the common case) exactly one subsection is
shown, its header collapses to a plain "Target residues" label, and "Add target" is
hidden. It reappears as soon as the scope spans more than one target, and a hint offers
to split the existing subsection per target.

Layout per condition row inside a subsection:

```
[≡] [Residues ▾ (multiselect, searchable, chips)] [condition ▾] [value] [unit ▾] [scope ▾] [×]
```

- **Residues**: PrimeVue `MultiSelect` with `filter`, `display="chip"`, options from
  the subsection's target residue catalogue, labelled `A166 GLU` (one-letter form `E166` shown as secondary text),
  grouped by chain. A "paste list" input accepts `A166,A167,A170` or whitespace-separated
  tokens for quick entry from a target card.
- **Condition**: `within X Å of binder` / `further than X Å from binder` /
  `SASA when bound ≤` / `SASA when bound ≥` / `ΔSASA on binding ≥` / `ΔSASA on binding ≤`.
  These map onto `(metric, operator)` pairs; the wording rather than raw operators keeps
  the direction unambiguous.
- **Unit** appears only for SASA conditions: `Å²` or `% of max`. For distance conditions
  a **distance type** dropdown appears instead: `CA distance` / `CB distance` /
  `Heavy atoms` (default heavy).
- **Scope**: `any residue` / `all residues` / `at least N residues` / `site total`
  (the last one sums ΔSASA over the selected residues and compares as a percentage of
  their combined theoretical maximum, i.e. `complex_sasa.py`'s `site_percent`).
- Distance inputs are capped at the 12 Å record cutoff with a tooltip explaining why.

Above the subsections, a **coverage banner**: "Target contacts computed for 1,240 of 8,310
designs in 3 runs" with a **Compute target contacts** button, a progress bar while
running, and a per-run breakdown on expand. Filter rows are editable but marked with a
warning badge while coverage is incomplete. If a run's `target_moves` flag is set, the
banner notes that its apo SASA was computed per design.

### 4.3 API client (`frontend/src/webapi.ts`)

`filteringApi.targetResidues(runIds)`, `filteringApi.computeTargetContacts(payload)`
and `filteringApi.targetContactProfile(payload)` (§6.3),
plus the DTOs. Compute batches default to 200 designs per request, issued sequentially
so the progress bar is meaningful and the server-side process pool is not oversubscribed.

## 5. MCP surface

In scope for this change, not deferred: the MCP server already exposes filtering, so
target contacts belong there too.

Three existing tools take a `filters` list and build their DataFrame directly rather
than through `service.py`:

| Tool | File | Change |
| --- | --- | --- |
| `query_designs` | `mcp_server/tools/designs.py` (`filters` at line 368) | New `target_contact_groups` parameter; swap `build_designs_dataframe` + `apply_hard_filters` for `build_filter_inputs` (§3.4) |
| `rank_designs` | `mcp_server/tools/selection.py` | Same |
| `select_diverse_designs` | `mcp_server/tools/selection.py` | Same; also passed through to `FilteringRunRequest` when saving a set |

Two new tools, following the existing naming and the "does not mirror REST" principle in
`docs/development/mcp.md`:

- `list_target_residues(run_ids)` -> targets in scope, their residue catalogues and
  per-run compute coverage. Without this an agent cannot discover valid residue labels,
  which makes the filter parameter unusable. Same shape as `describe_columns` serves for
  ordinary filters.
- `target_contact_profile(run_ids, design_keys?, target_key, metric, ...)` -> the
  per-residue aggregate of §3.3, i.e. "which target residues does this design set
  actually contact, and how strongly". This is the textual counterpart of the viewer
  colour map (§6) and is the natural way to ask "what epitope did these binders hit".

Deliberately **not** exposed as an MCP tool: the compute endpoint. It is a long-running
batch job with no result of its own, and an agent triggering an hour of SASA computation
implicitly is the wrong default. Instead, when a target-contact filter hits designs with
no cached record, the tools return the existing structured error style pointing at the
UI button (the same pattern `select_diverse_designs` already uses for missing sequences).

`docs/development/mcp.md` gains a section covering the new parameter, the two new tools,
and the applicability rules from §3.3. `describe_columns`' prose mentions that target
residue conditions are a separate parameter, not columns.

## 6. Target contact map in the structure viewer

A collapsible **"Target contact map"** section at the bottom of the Designs tab's
structure viewer, following the existing disclosure pattern in `DesignsView.vue`
(`advanced-options-section` + `advanced-options-disclosure`, as used by "Reference
structure" at line 489 and "Tag placement" at line 611). It colours the target chains of
the currently-displayed structure by an aggregate computed across a chosen set of
designs, so the epitope a whole run (or a filtered subset) converges on is visible at a
glance rather than one design at a time.

### 6.1 Controls

- **Design set**: `Selected designs` / `All designs passing filters` / `All designs in
  the current run`. Defaults to the filtered set, so the map reflects whatever the
  Filtering tab currently narrows to.
- **Colour by**:
  - `Mean ΔSASA on binding` (Å² or % of max, unit toggle)
  - `Contact frequency` - fraction of the design set in which the residue counts as
    contacted, using the contact definition below
  - `Mean minimum distance` (inverted gradient: closer is hotter)
- **Contact definition** (used by contact frequency, and by the boolean mode):
  `CA distance` / `CB distance` / `Heavy atoms`, with a threshold input; or
  `ΔSASA ≥ X Å²`. Defaults to heavy atoms ≤ 5 Å.
- **Gradient range**: low and high numeric inputs, an "auto" button that fits them to the
  current data's 5th/95th percentile, and a **normalise** toggle that rescales the
  observed min/max to 0-1. Narrowing the range is the sensitivity control: with a 200-600
  residue target most residues sit near zero, and a full-range gradient washes the
  interesting ones out. It is also the answer to a design set spanning several epitopes,
  where the unscaled mean flattens the differences.
- **Boolean mode** toggle: instead of a gradient, colour the union of contacted residues
  one colour and everything else neutral. Equivalent to a two-stop gradient, but worth
  its own control since "which residues are ever touched" is a distinct question.
- **Legend** with the numeric range and the residue count above the low cutoff, plus a
  hover readout naming the residue and its value.

### 6.2 Rendering

PDBe Mol* (`pdbe-molstar`, already the viewer in `MolstarViewer.vue`) colours residue
ranges through `viewerInstance.visual.select({ data: [...], nonSelectedColor })`, where
each entry is `{auth_asym_id, start_residue_number, end_residue_number, color: {r,g,b}}`.
The map is therefore one `select` call with one entry per target residue, and
`visual.clearSelection()` on teardown or when the section is collapsed.

`MolstarViewer.vue` gains `applyResidueColorMap(entries)` / `clearResidueColorMap()` in
its existing `defineExpose` block, alongside `toggleReferenceStructureVisibility` and the
other imperative handles. The colour ramp lives in a small
`frontend/src/utils/residueColorMap.ts` (value -> RGB, given range and mode) so it is
unit-testable without a viewer, and so the legend and the structure cannot disagree.

Interaction with the existing overlays: the colour map sets a selection colouring on the
primary structure only. The membrane and tag-marker screen overlays draw separately and
are unaffected; the appended reference structure (structure index 1) is not recoloured.

### 6.3 Data

`POST /api/filtering/target-contacts/profile` (§3.5), called with the current design set
and target. Results are cached in the store keyed by
`(target_key, design-key-set hash, metric, contact definition)`, so changing only the
gradient range or switching to boolean mode recolours from memory with no round trip.
Gradient range and the control state persist per run via the existing `kvSet`/`kvGet`
pattern and a new `targetContactMapKey(runId)` in `persistence/keys.ts`, matching
`tagPlacementKey`/`advRefKey`.

If the design set has uncomputed designs the section shows the same coverage banner and
Compute button as the Filtering panel, sharing the store action rather than duplicating
it, and the profile is computed from whatever is cached with an explicit "based on N of
M designs" note.

### 6.4 Why here rather than in the Filtering tab

The map is an interpretive view of the same data the filters use, and it needs a loaded
structure to draw on. Putting it beside "Tag placement" and "Reference structure" keeps
every structure-viewer overlay in one place, and lets the usual workflow run in one
direction: look at where the binders actually land, then go to the Filtering tab and
write the residue conditions that select for it.

## 7. Performance

Per design: two Shrake-Rupley passes plus a KD-tree query. As first written, against
BioPython's `ShrakeRupley`, that measured ~0.65 s for a 174-residue complex at
`n_points=100` - `Bio.PDB.SASA` builds a fresh KDTree of the point mesh for every atom.
Moving the kernel to biotite, keeping BioPython's radii and point mesh so the numbers
are unchanged, and asking only for the residues inside the record cutoff brought that to
~0.034 s (measured on the bundled ccl7 run, whose target moves, so both passes run).
With the per-run apo reference reused - the normal case - only one pass runs.

Filter evaluation itself is a dictionary lookup per design per filter, negligible next
to the existing polars pass.

Cache reads for a 10,000-design run scope are a single indexed `SELECT` returning about
70 MB of JSON in the worst case. If that proves slow in practice, the fallback is an
in-memory contacts cache hydrated alongside `designs_cache` in `cache.py`, keyed the
same way; the repository methods above are already shaped for that.

## 8. Tests

Backend (`backend/tests/`):

- `test_target_contacts.py`: a synthetic two-chain PDB (reuse the
  `synthetic_complex_pdb` fixture from `test_structural_metrics.py`) checks distances,
  bound vs apo SASA, ΔSASA sign, cutoff truncation, and `n_points`/probe-radius
  plumbing. One case pins Å² and % values against `complex_sasa.py` run on the same
  structure so the port stays faithful.
- `test_target_contacts_persistence.py`: round-trip, params-key specificity,
  chain-role specificity, `delete_run` cleanup. Mirrors
  `test_structural_metrics_persistence.py`.
- `test_target_contact_filters.py`: `augment_with_target_contacts` against a small
  DataFrame plus a fake repository, covering each scope and metric, all three
  applicability rules from §3.3 (out-of-group-scope exempt, residue-absent exempt,
  present-but-uncomputed fails), and a two-group case where each group constrains only
  its own target's runs.
- `test_target_contact_profile.py`: aggregation maths, including that residues outside
  the record cutoff contribute ΔSASA 0 rather than being dropped from the denominator.
- MCP: extend `test_mcp.py` with `list_target_residues`, `target_contact_profile`, and
  `query_designs` carrying `target_contact_groups`.
- Extend `test_filtering_engine.py`/service tests so cascade counts include contact
  stages in the right order.

Frontend: `residueColorMap.ts` gets unit tests for the value-to-colour ramp, range
clamping and boolean mode, since the legend and the structure both read from it.

E2E (`tests/`): a Playwright case adding a contact filter, computing, and confirming the
Designs table narrows and the chain summary shows the new stage; plus one opening the
"Target contact map" section and asserting the legend range and residue count render.

## 9. Implementation order

1. `util/sasa_constants.py` extraction (Tien table out of `tag_placement.py`);
   `filtering/target_contacts.py` port with tests against `complex_sasa.py` output.
2. Persistence tables, protocol/noop/sqlite methods, `delete_run` cleanup, tests.
3. `target-residues` and `target-contacts/compute` endpoints, schemas.
4. `target_contacts_service.augment_with_target_contacts` and the shared
   `build_filter_inputs`, plus the five service call sites; `FilterCascadeStage.label`;
   exclusion of `__tc_*` from the column picker.
5. Store, `webapi.ts`, `TargetContactFilters.vue` (single-target path first, target
   subsections second), panel renumbering, `filterLabel.ts`, persistence field.
6. MCP: `target_contact_groups` on the three existing tools, `list_target_residues`,
   `target_contact_profile`, `docs/development/mcp.md`.
7. Profile endpoint, `residueColorMap.ts`, `MolstarViewer.applyResidueColorMap`, and the
   "Target contact map" disclosure section in `DesignsView.vue`.
8. Playwright cases (filter narrows the table; colour map draws); `CHANGELOG.md`.

Steps 1-5 are the usable core: the feature works end to end for a single target after
step 5. Steps 6 and 7 are independent of each other and can land in either order.

## 10. Open points

- Target grouping (§3.3, §4.2) assumes a target is identified by its sequence. Two runs
  against the same protein whose constructs differ by a tag or a truncation get separate
  groups and separate residue catalogues, which is correct but means the user writes the
  equivalent-residue mapping by hand. An alignment-based "link these two targets" helper
  would remove that manual step; out of scope here, but the `target_key` indirection is
  what would make it addable later without a schema change.
- The viewer colour map (§6) aggregates over whatever design set is chosen. Mean ΔSASA
  across a heterogeneous set (several different epitopes) flattens out, which is what
  the configurable gradient min/max and the **normalise** mode (rescale the observed
  range to 0-1) are for: tighten the range and the separate epitopes separate again.
  Contact frequency is the other tool for the same situation. Response curves beyond a
  linear rescale are overkill and are not planned.
- Residue label form: `A166` (chain + number, as `complex_sasa.py` emits) is used as the
  stored key, with `E166` one-letter shown in the UI for readability. Insertion codes
  append directly (`A166A`), which is unambiguous only because chain IDs are matched
  greedily first, exactly as `parse_residue_token` already does.
- The 12 Å record cutoff and 1.4 Å / 100-point SASA parameters are part of `params_key`,
  so changing them invalidates cached records rather than mixing them. They are
  constants in v1, not user-facing settings.
