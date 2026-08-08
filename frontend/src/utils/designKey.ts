/**
 * Shared design-key format for matching backend filtering results (`DesignKeyDto` /
 * ranked/diverse design rows) against frontend `Design` rows, and for deduping design
 * rows sourced from more than one place (live Runs vs. frozen Saved Sets — see plan
 * §7A.5 "Dedup rule").
 *
 * Both `stores/filtering.ts` (building the passing/ranked key sets from API responses)
 * and `stores/designs.ts` (looking a design up in those sets, and deduping Run vs. Set
 * rows) must agree on this format exactly — hence the shared util, so they can't drift
 * (see plan §7A).
 *
 * Uses `\x1f` (unit separator) as the join character, matching the existing
 * `designRowKey`/`binderRowKey` convention already used in `stores/designs.ts` for
 * DataTable row identity, and the backend's `design_dedupe_key` (persistence/protocol.py).
 *
 * Two equivalent entry points (both produce identical output — pick whichever reads
 * better at the call site): `buildDesignKey({...})` takes an object (handy when you
 * already have a `Design`-shaped value), `designDedupeKey(a, b, c)` takes positional
 * args (handy for ad-hoc triples).
 */

const KEY_SEP = '\x1f'

export interface DesignKeyParts {
    run_id: string | number | null | undefined
    design_id: string | number | null | undefined
    source_path?: string | number | null | undefined
}

/** Build the canonical `run_id␟design_id␟source_path` key used to look up filtering results. */
export function buildDesignKey(parts: DesignKeyParts): string {
    return designDedupeKey(parts.run_id, parts.design_id, parts.source_path)
}

/** Positional-argument variant of `buildDesignKey` — identical output format. */
export function designDedupeKey(
    runId: string | number | null | undefined,
    designId: string | number | null | undefined,
    sourcePath?: string | number | null | undefined
): string {
    const rid = String(runId ?? '')
    const did = String(designId ?? '')
    const sp = sourcePath != null && String(sourcePath).trim() ? String(sourcePath).trim() : ''
    return `${rid}${KEY_SEP}${did}${KEY_SEP}${sp}`
}
