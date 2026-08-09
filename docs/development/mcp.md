# MCP server

Binderdash exposes a [Model Context Protocol](https://modelcontextprotocol.io) server so
an AI agent can analyse binder design campaigns directly — filter and rank designs,
select diverse panels, inspect interfaces, and hand curated Saved Sets back to a human in
the web UI.

The server is **stateless streamable-HTTP**, mounted into the same FastAPI process as the
REST API at **`/api/mcp/`** (note the trailing slash; `POST /api/mcp` 307-redirects to
it). Because it runs in-process it shares the same in-memory design cache as the REST
API — one cache, no drift.

## Installing

`fastmcp` is an **optional extra**. Without it the app runs exactly as before and the
endpoint is simply not mounted (an INFO line says so at startup).

```bash
uv pip install -r backend/requirements.txt
uv pip install "fastmcp>=3.4,<4"     # or: uv pip install -e "backend[mcp]"
```

There is **no env var** to turn it on or off — the mount is gated purely on whether
`fastmcp` imports. A flag would be untestable (the mount happens at module import,
before tests can patch settings) and would add a second way for the endpoint to be
silently missing.

It is optional rather than required because it pulls roughly thirty transitive
distributions (`keyring`, `jeepney`/`SecretStorage`, `aiofile`/`caio`, …) that resolve
backends through entry points and D-Bus and are not declared in
`desktop/binderdash.spec`'s `hiddenimports`. Keeping it out of the default set leaves the
PyInstaller desktop bundle and the production image resolution unchanged.

## Authenticating

MCP uses the same **per-user API keys** as scripted REST access (see
[Authentication](../setup/authentication.md)). Mint one with:

```bash
python -m backend.cli key create alice --name mcp
```

Send it as `Authorization: Bearer bd_…` (canonical) or `X-Binderdash-Api-Key: bd_…`.
Keys are validated through the same TTL cache as REST, so revoking a key takes effect
for both at the same moment.

Requires `DATABASE`; without persistence there is no key store and every request is
rejected with 401 (the startup log warns about this explicitly). With
`DISABLE_AUTHENTICATION=true` the server mounts with no auth at all and logs a warning.

### Client configuration

The web UI does this for you: **account menu → API keys → Create**, then expand
*"Use with Claude Code or another AI agent (MCP)"* on the new-key panel for a ready-made
command and JSON snippet with the key and this server's URL already filled in. The
section only appears when the server actually has MCP mounted (`GET /api/auth/status`
reports `mcp.enabled`).

Claude Code, in one command:

```bash
claude mcp add --transport http --scope user binderdash \
  https://binderdash.example.org/api/mcp/ \
  --header "Authorization: Bearer bd_your_key_here"
```

Or edit `~/.claude.json` (all projects) or `.mcp.json` (one project) directly — this is
exactly what the command above writes, and other MCP clients take the same shape:

```json
{
  "mcpServers": {
    "binderdash": {
      "type": "http",
      "url": "https://binderdash.example.org/api/mcp/",
      "headers": { "Authorization": "Bearer bd_your_key_here" }
    }
  }
}
```

The key is stored in that file in plain text, so prefer a dedicated expiring key per
agent and revoke it from the UI when finished. A project-scoped `.mcp.json` is shared
with anyone who clones the repo, and Claude Code asks each of them to approve the server
before first use.

## Tools

| Tool | Purpose |
|---|---|
| `list_runs` | Projects, runs, methods, design counts, merge groups |
| `describe_methods` | Canonical metrics, **sort directions**, ranking presets |
| `describe_columns` | Columns for a selection, per-method coverage and ranges |
| `query_designs` | Filter, sort, page and project the design table |
| `summarize_designs` | Quantiles and histograms without returning rows |
| `rank_designs` | Multi-metric rank-based scoring with a filter cascade |
| `select_diverse_designs` | Filter → rank → de-duplicate by sequence; optional Saved Set |
| `saved_sets` | List, read, rename Saved Sets |
| `extract_sequences` | Extract sequences from structures into the derived cache |
| `inspect_structures` | Chains, roles, sequences, `binderdash_*` interface metrics |
| `read_structure_file` | Raw structure text, size-capped |
| `export_structures` | Manifest plus the tar endpoint to fetch many structures |

There is deliberately **no plotting tool**: `query_designs` returns column-selected
tabular data and an agent charts it itself.

**Write scope** is read + analysis + Saved Sets, plus the compute-and-cache writes
(sequence extraction, structural metrics) that only populate derived caches. Scanning,
ingesting, deleting, cache refresh and merge-table upload are not exposed.

## How the tool surface differs from REST

The MCP layer deliberately does not mirror the REST API — it is where the problems
catalogued in `BINDERDASH_API_OVERHAUL.md` get fixed without changing existing REST
consumers.

- **Sort direction is never guessed.** `iptm`/`ptm` are higher-is-better;
  `pae_interaction`/`rmsd` are lower-is-better. `order="auto"` applies the known
  direction, and asking for the opposite produces a `SORT_DIRECTION_OVERRIDE` warning
  rather than a confidently reversed leaderboard.
- **Canonical column names resolve per method.** `iptm` is `Average_i_pTM` for
  bindcraft and `design_to_target_iptm` for boltzgen. Canonical resolution takes
  precedence over a same-named raw column — `pae_interaction` is *also* rfd's own column
  name, and preferring the literal would null out every other method.
- **Server paths never leave the server.** `pdb_file` is replaced by
  `structure_filename` / `structure_format` / `structure_url`; `params`,
  `target_sequence`, `run_path` and per-replicate `^\d+_` columns are never returned.
- **Server-side sort, limit, offset and column selection**, which REST does not have.
- **Silent failures become loud.** A ranking metric that resolves for no design is an
  error, not a skipped term. A diverse set short of its budget always says why.
- **Oversized responses are refused, not truncated** (`RESPONSE_TOO_LARGE`), because
  silent truncation reads as a complete answer.

## Response shape

Data-returning tools share one envelope. Rows are arrays rather than objects (40–55%
fewer tokens on a wide table) and floats are rounded to four significant figures:

```json
{
  "columns": ["run_id", "design_id", "method", "iptm", "structure_filename"],
  "rows": [["bc", "d1", "bindcraft", 0.9123, "d1.pdb"]],
  "total_matching": 1240, "returned": 25, "offset": 0, "truncated": true,
  "methods": {"bindcraft": {"columns": ["Average_i_pTM"], "higher_is_better": true}},
  "warnings": [{"code": "MERGED_RUN", "message": "..."}]
}
```

Errors are raised as `[CODE] message`, always ending in a concrete next call —
`UNKNOWN_COLUMN` (with the nearest names), `AMBIGUOUS_DESIGN_REF`,
`NO_RANKABLE_METRICS`, `RESPONSE_TOO_LARGE`, `EMPTY_SELECTION`, `SEQUENCES_REQUIRED`.

## Implementation notes

`backend/mcp_server/` — named `mcp_server`, not `mcp`, because pytest puts `backend/` on
`sys.path` where a package called `mcp` shadows the SDK that fastmcp imports.

- `server.py` — FastMCP instance, `TokenVerifier`, the ASGI app, the
  `X-Binderdash-Api-Key` header shim, and `run_blocking` (service-layer calls go through
  `asyncio.to_thread`, with a semaphore for the heavy ones so an agent's tool loop cannot
  starve the interactive web UI sharing the process).
- `vocab.py` — canonical metrics, directions, ranking presets (moved server-side from
  `frontend/src/config/rankingPresets.ts`).
- `columns.py`, `refs.py`, `tables.py`, `errors.py`, `descriptions.py` — the shared spine.
- `tools/` — `discovery.py`, `designs.py`, `selection.py`, `structures.py`.

Two integration points in `backend/main.py` are load-bearing:

1. **CSRF exemption** for the mount path. The MCP sub-app authenticates only via
   `Authorization` and never reads a cookie, so there is no ambient credential to abuse;
   without the exemption a missing key yields a `text/plain` 403 "CSRF token missing"
   that no MCP client can interpret.
2. **Lifespan chaining.** Mounting does not start the streamable-HTTP session manager —
   that happens in the sub-app's own lifespan, which Starlette does not run for mounted
   apps. Without it every tool call fails at runtime with "Task group is not
   initialized", never at import.

Tool descriptions in `descriptions.py` are the agent's only documentation; treat edits to
them as behaviour changes.
