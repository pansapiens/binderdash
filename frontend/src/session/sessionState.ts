/**
 * Capture and restore the Designs/Filtering/Plots UI state that a download bundle
 * records, so a bundle explains how its contents were selected - and, given the runs
 * still exist, can put the UI back that way.
 */

import { useDesignsStore } from '../stores/designs'
import { useFilteringStore } from '../stores/filtering'
import { usePlotsStore } from '../stores/plots'
import { useRunsStore } from '../stores/runs'
import {
    SESSION_KIND,
    SESSION_SCHEMA_VERSION,
    type RestoreOutcome,
    type SessionRunRefDto,
    type SessionStateDto
} from './types'

/** Major version we can read. A file claiming a higher major is rejected outright. */
const SUPPORTED_MAJOR = 1

function majorOf(version: string | undefined): number {
    const parsed = Number.parseInt(String(version ?? '').split('.')[0] ?? '', 10)
    return Number.isFinite(parsed) ? parsed : 0
}

function runRefs(runIds: string[]): SessionRunRefDto[] {
    const runsStore = useRunsStore()
    const byId = new Map(runsStore.runs.map((r: any) => [String(r.run_id), r]))
    return runIds.map((runId) => {
        const run: any = byId.get(runId)
        return {
            run_id: runId,
            run_name: run?.run_name ?? run?.metadata?.name ?? null,
            project_id: run?.project_id ?? null,
            method: run?.method ?? null,
            run_path: run?.path ?? run?.run_path ?? null
        }
    })
}

export function buildSessionState(): SessionStateDto {
    const designs = useDesignsStore()
    const filtering = useFilteringStore()
    const plots = usePlotsStore()

    const runIds = [...designs.selectedRunIds]

    return {
        schema_version: SESSION_SCHEMA_VERSION,
        kind: SESSION_KIND,
        captured: true,
        captured_at: new Date().toISOString(),
        runs: runRefs(runIds),
        run_ids: runIds,
        selection_mode: designs.selectAllFiltered ? 'all_filtered' : 'explicit',
        selected_design_count: designs.selectedDesigns?.length ?? 0,
        visible_columns: [...designs.visibleColumns],
        sort: (designs.tableMultiSortMeta ?? [])
            .filter((m: any) => m?.field)
            .map((m: any) => ({ field: String(m.field), order: Number(m.order ?? 1) })),
        best_mpnn_only: designs.bestMpnnOnly,
        saved_set_ids: [...(designs.selectedSavedSetIds ?? [])],
        filtering: {
            filters: JSON.parse(JSON.stringify(filtering.filters ?? [])),
            target_contact_groups: JSON.parse(
                JSON.stringify(filtering.targetContactGroups ?? [])
            ),
            metrics: JSON.parse(JSON.stringify(filtering.rankingMetrics ?? [])),
            budget: filtering.budget,
            alpha: filtering.alpha,
            size_buckets: JSON.parse(JSON.stringify(filtering.sizeBuckets ?? [])),
            diversity_enabled: filtering.diversityEnabled
        },
        plots: {
            // The live axis refs rather than the persisted preferences object: the
            // preferences are the store's private copy, and these are what is on screen.
            scatter_axes: {
                x: plots.scatterXCol,
                y: plots.scatterYCol,
                color: plots.scatterColorCol,
                size: plots.scatterSizeCol
            }
        }
    }
}

export function isSessionState(payload: any): payload is SessionStateDto {
    if (!payload || typeof payload !== 'object') return false
    if (payload.kind === SESSION_KIND) return true
    // Tolerate a file written before `kind` was stamped, or hand-edited.
    return Array.isArray(payload.run_ids) && typeof payload.schema_version === 'string'
}

export function assertReadableVersion(payload: { schema_version?: string }, label: string): void {
    const major = majorOf(payload.schema_version)
    if (major > SUPPORTED_MAJOR) {
        throw new Error(
            `This ${label} was written by a newer Binderdash (schema ${payload.schema_version}). ` +
                `This version reads schema ${SUPPORTED_MAJOR}.x.`
        )
    }
}

/**
 * Put the UI back. Per-section and defensive on purpose: a bundle is often opened
 * against a Binderdash whose runs have moved on, and restoring the filters is still
 * worth doing when two of the runs have gone.
 */
export async function applySessionState(state: SessionStateDto): Promise<RestoreOutcome[]> {
    assertReadableVersion(state, 'session file')

    const outcomes: RestoreOutcome[] = []
    const designs = useDesignsStore()
    const filtering = useFilteringStore()
    const plots = usePlotsStore()
    const runsStore = useRunsStore()

    if (state.captured === false) {
        return [
            {
                section: 'Session',
                status: 'skipped',
                detail: state.note ?? 'This file records no UI state.'
            }
        ]
    }

    const requested = Array.isArray(state.run_ids) ? state.run_ids.map(String) : []
    if (requested.length > 0) {
        if (runsStore.runs.length === 0) {
            try {
                await runsStore.fetchRuns()
            } catch {
                // Non-fatal: without the run list we simply cannot report which are missing.
            }
        }
        const known = new Set(runsStore.runs.map((r: any) => String(r.run_id)))
        const present = known.size > 0 ? requested.filter((id) => known.has(id)) : requested
        const missing = requested.filter((id) => !present.includes(id))

        if (present.length > 0) {
            designs.setSelectedRunIds(present)
            await designs.flushSelectedRunIds?.()
        }
        outcomes.push({
            section: 'Runs',
            status: missing.length === 0 ? 'applied' : present.length > 0 ? 'partial' : 'skipped',
            detail:
                missing.length > 0
                    ? `${missing.length} run(s) from the file are not on this server: ${missing
                          .slice(0, 3)
                          .join(', ')}${missing.length > 3 ? '…' : ''}`
                    : `${present.length} run(s)`
        })
    }

    if (Array.isArray(state.visible_columns) && state.visible_columns.length > 0) {
        designs.visibleColumns = [...state.visible_columns]
        outcomes.push({ section: 'Columns', status: 'applied' })
    }

    if (Array.isArray(state.sort) && state.sort.length > 0) {
        designs.tableMultiSortMeta = state.sort
            .filter((s) => s && s.field)
            .map((s) => ({ field: String(s.field), order: s.order === -1 ? -1 : 1 })) as any
        designs.tableFirst = 0
        outcomes.push({ section: 'Table sort', status: 'applied' })
    }

    if (typeof state.best_mpnn_only === 'boolean') {
        designs.bestMpnnOnly = state.best_mpnn_only
    }

    const recipe = state.filtering ?? {}
    if (recipe && (recipe.filters?.length || recipe.metrics?.length || recipe.budget != null)) {
        // loadRecipe already exists for "Reapply filters" on a Saved Set; reusing it keeps
        // one path for turning a stored recipe back into filter-builder state.
        filtering.loadRecipe({
            name: '',
            run_ids: requested,
            filters: recipe.filters ?? [],
            target_contact_groups: recipe.target_contact_groups ?? [],
            metrics: recipe.metrics ?? [],
            budget: recipe.budget ?? 24,
            alpha: recipe.alpha ?? 0.001,
            size_buckets: recipe.size_buckets ?? [],
            // loadRecipe reads the diversity toggle off the recipe and then schedules a
            // filter run, so this has to go in rather than be corrected afterwards -
            // otherwise that run fires with diversity on and the toggle visibly flips.
            // Absent (a session written before the toggle existed) means on, matching
            // loadRecipe's treatment of older saved recipes.
            apply_diversity: recipe.diversity_enabled !== false
        } as any)
        outcomes.push({
            section: 'Filters and ranking',
            status: 'applied',
            detail: `${recipe.filters?.length ?? 0} filter(s), ${recipe.metrics?.length ?? 0} ranking metric(s)`
        })
    }

    const axes = state.plots?.scatter_axes
    if (axes && typeof axes === 'object' && (axes.x || axes.y)) {
        if (axes.x) plots.scatterXCol = axes.x
        if (axes.y) plots.scatterYCol = axes.y
        if (axes.color !== undefined) plots.scatterColorCol = axes.color
        if (axes.size !== undefined) plots.scatterSizeCol = axes.size
        plots.recordScatterAxisPreferences()
        outcomes.push({ section: 'Plot axes', status: 'applied' })
    }

    return outcomes
}
