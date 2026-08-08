# Adding a pipeline method type

Binderdash recognises design pipelines by **method** string (e.g. `bindcraft`, `rfd`, `boltzgen`, `rfd3`). When you add a new one, keep the backend detection/metadata and the frontend display config in sync.

## Backend

| Location | What to change |
| -------- | -------------- |
| `backend/config/run_signatures.py` | **`run_folder_signatures`** — declarative entries: `method`, `submethod`, paths (`required_files`, `results_table`, `pdb_pattern`, …), **`primary_score_columns`**, design id columns, trajectory hints. New methods usually mean a **new signature dict** (and priority ordering). |
| `backend/config/method_paths.py` | **`PIPELINE_METHOD_IDS`** — add the new id. Update **`_RUN_NAME_SEGMENT_BLOCKLIST`** / **`_PROJECT_ID_SEGMENT_BLOCKLIST`** if path segments for the new layout should be ignored when inferring run/project names. |
| `backend/run_discovery.py` | Search for **`method ==`** / **`get("method")`** — branches for target sequence, backbone id, dataframe standardisation, structure resolution, etc. Extend only where the new pipeline differs from the generic path. |
| `backend/config/score_labels.py` | Optional: **`SCORE_FIELD_LABELS`** for human-readable names of new score columns in API/UI. |

`run_signatures` docstrings note alignment with the frontend primary-score config; **`primary_score_columns`** in each signature should match how you resolve “primary” scores for that method on the client.

## Frontend

`frontend/src/config/pipelineDisplay.ts` is the main file. Touch the pieces that apply to your method:

| Piece | Role |
| ----- | ---- |
| **`PIPELINE_METHOD_IDS`** / **`PipelineMethodId`** | Register the method id for filters, tags, and typing. |
| **`METHOD_TAG_PALETTE`**, **`METHOD_TAG_DISPLAY`** | Chip colour and icon for **Select Runs** method tags. |
| **`SCORE_FIELD_DEFS`** | Declares score columns (table, filters, colouring); add entries for new CSV/TSV fields. |
| **`METHOD_BEST_SCORE`** | Primary/secondary columns and direction for “best design” grouping within MPNN variants. |
| **`PRIMARY_SCORE_CHIP_RULES`** | Which column(s) drive the **primary score** chip on Select Runs (align with backend **`primary_score_columns`**). |
| **`getStructureFilenameFromDesign`** / **`designHasStructureFile`** | Only if structure path resolution is special-cased (see existing **`boltzgen`** handling). |

Other modules may import these exports; after changing method ids or score fields, run a quick search for the old method name or column names across `frontend/src`.
