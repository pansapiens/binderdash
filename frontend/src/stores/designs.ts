/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, shallowRef, computed, watch, nextTick } from 'vue'
import { localeComparator, resolveFieldData, sort } from '@primeuix/utils/object'
import { designsApi, savedSetsApi } from '../webapi'
import type { SavedSetDesignRowDto } from '../webapi'
import { PERSISTENCE_KEYS } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'
import type { Design, ColumnConfig, StructureInfo } from '../types/store'
import { buildDesignKey, designDedupeKey } from '../utils/designKey'
import { useFilteringStore } from './filtering'
import {
    scoreColumnConfigsForTable,
    DESIGN_BUILD_COLUMN_STATIC_KEYS,
    METHOD_BEST_SCORE,
    getStructureFilenameFromDesign,
    designHasStructureFile,
    defaultVisibleScoreColumnFields,
} from '../config/pipelineDisplay'

/** Cap rows scanned when inferring dynamic table columns (full data still loaded). */
const COLUMN_INFER_SAMPLE_SIZE = 400

/** Stable unique row id for PrimeVue DataTable selection (not from pipeline data). */
function designRowKey(design: Design, index: number): string {
    const sp = (design as Record<string, unknown>).source_path
    const spStr = sp != null && String(sp).trim() ? String(sp).trim() : ''
    const rid = String(design.run_id ?? '')
    const did = String(design.design_id ?? `row_${index}`)
    return spStr ? `${rid}\x1f${did}\x1f${spStr}` : `${rid}\x1f${did}`
}

function designBinderKey(d: Design): string {
    return d.binderRowKey ?? `${d.run_id}\x1f${d.design_id}`
}

/** Assign binderRowKey on each row so DataTable selection stays unique per design. */
function withRowKeys(rows: Design[]): Design[] {
    const seen = new Map<string, number>()
    return rows.map((d, index) => {
        let key = designRowKey(d, index)
        const n = seen.get(key) ?? 0
        seen.set(key, n + 1)
        if (n > 0) {
            key = `${key}\x1f${n}`
        }
        return { ...d, binderRowKey: key }
    })
}

function sampleDesignsForColumnInference(designs: Design[]): Design[] {
    if (designs.length <= COLUMN_INFER_SAMPLE_SIZE) return designs
    const out = designs.slice(0, COLUMN_INFER_SAMPLE_SIZE)
    const last = designs[designs.length - 1]
    if (last && out[out.length - 1] !== last) out.push(last)
    return out
}

export const useDesignsStore = defineStore('designs', () => {
    // State — shallowRef: large run tables are replaced wholesale, not deep-mutated.
    const designs = shallowRef<Design[]>([])
    /** Designs grouped by run_id (mirrors `designs` after each load/patch). */
    const designsByRun = ref<Map<string, Design[]>>(new Map())
    /** All filtered rows selected (O(1) select-all); use excludedKeys for unchecked rows. */
    const selectAllFiltered = ref(false)
    const excludedKeys = ref<Set<string>>(new Set())
    const includedKeys = ref<Set<string>>(new Set())
    const pendingSelectAllFiltered = ref(false)
    const selectedRunIds = ref<string[]>([]) // Track selected run IDs for filtering
    /** Sorted join of run ids last successfully loaded into `designs`. */
    const loadedRunIdsSignature = ref<string>('')
    // Saved Sets selected for inclusion alongside Runs (plan §7A.4/§7A.5) — Sets show
    // frozen-snapshot data (§7A.3), merged into the same `designs` pool, deduped against
    // any live-selected Run that also contains the same design.
    const selectedSavedSetIds = ref<string[]>([])
    /** Sorted join of saved-set ids last successfully merged into `designs`. */
    const loadedSavedSetIdsSignature = ref<string>('')
    let fetchSeq = 0
    let selectionDebounceTimer: ReturnType<typeof setTimeout> | null = null
    let savedSetSelectionDebounceTimer: ReturnType<typeof setTimeout> | null = null
    const SELECTION_DEBOUNCE_MS = 200

    function runIdsSignature(runIds: string[]): string {
        return [...runIds].sort().join('|')
    }

    function rebuildDesignsByRun(rows: Design[]): void {
        const m = new Map<string, Design[]>()
        for (const d of rows) {
            const rid = String(d.run_id)
            const arr = m.get(rid) ?? []
            arr.push(d)
            m.set(rid, arr)
        }
        designsByRun.value = m
    }
    const pendingSelectedDesignKeys = ref<Array<{ run_id: string; design_id: string }>>([])
    const pendingCurrentNavDesignId = ref<string | null>(null)
    const designsPersistenceHydrated = ref(false)
    const bestMpnnOnly = ref(false)

    const columns = ref<ColumnConfig[]>([])
    const visibleColumns = ref<string[]>(['design_id', 'project_id', 'run_name', 'method', 'Length'])
    const loading = ref(false)
    const currentNavDesignId = ref<string | null>(null)
    const tableSortField = ref<string | undefined>(undefined)
    const tableSortOrder = ref<number | undefined>(undefined)

    function buildColumnsFromData(allDesigns: Design[]): ColumnConfig[] {
        if (!allDesigns || allDesigns.length === 0) return []
        const designs = sampleDesignsForColumnInference(allDesigns)

        const baseColumns: ColumnConfig[] = [
            { field: 'design_id', header: 'Design ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 150px' },
            { field: 'project_id', header: 'Project ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'run_name', header: 'Run Name', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'method', header: 'Method', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 100px' }
        ]

        if (designs.some(d => Object.prototype.hasOwnProperty.call(d, 'good'))) {
            baseColumns.push({
                field: 'good',
                header: 'Good',
                sortable: true,
                filter: true,
                filterType: 'boolean',
                showFilterMenu: false,
                style: 'min-width: 90px'
            })
        }

        if (designs.some(d => Object.prototype.hasOwnProperty.call(d, 'tag'))) {
            baseColumns.push({
                field: 'tag',
                header: 'Tag',
                sortable: true,
                filter: true,
                filterType: 'text',
                showFilterMenu: false,
                style: 'min-width: 72px'
            })
        }

        const scoreColumns: ColumnConfig[] = []
        const knownScoreFields = scoreColumnConfigsForTable()

        knownScoreFields.forEach(scoreField => {
            if (designs.some(d => scoreField.field in d && d[scoreField.field] != null)) {
                scoreColumns.push({
                    field: scoreField.field,
                    header: scoreField.header,
                    sortable: true,
                    filter: true,
                    filterType: 'numeric',
                    showFilterMenu: false,
                    style: 'min-width: 120px'
                })
            }
        })

        const metadataColumns: ColumnConfig[] = [
            { field: 'target_sequence', header: 'Target Sequence', sortable: false, filter: false, style: 'min-width: 200px' },
            { field: 'pdb_file', header: 'PDB File', sortable: false, filter: false, style: 'min-width: 200px' },
            { field: 'run_path', header: 'Run Path', sortable: false, filter: false, style: 'min-width: 200px' }
        ]

        const existingFields = DESIGN_BUILD_COLUMN_STATIC_KEYS

        const dynamicKeys = new Set<string>()
        for (const design of designs) {
            for (const key of Object.keys(design)) {
                if (!existingFields.has(key)) dynamicKeys.add(key)
            }
        }

        const otherColumns: ColumnConfig[] = []
        for (const key of dynamicKeys) {
            let sample: unknown
            for (const design of designs) {
                const v = design[key]
                if (v != null && v !== '') {
                    sample = v
                    break
                }
            }

            let filterType = 'text'
            let sortable = false
            if (sample === undefined) {
                filterType = 'text'
            } else if (typeof sample === 'boolean') {
                filterType = 'boolean'
                sortable = true
            } else if (typeof sample === 'number' && !Number.isNaN(sample)) {
                filterType = 'numeric'
                sortable = true
            } else if (sample instanceof Date) {
                filterType = 'date'
                sortable = true
            } else if (typeof sample === 'string' && sample.trim() !== '' && !Number.isNaN(Number(sample))) {
                filterType = 'numeric'
                sortable = true
            }

            otherColumns.push({
                field: key,
                header: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                sortable,
                filter: true,
                filterType,
                showFilterMenu: false,
                style: 'min-width: 120px'
            })
        }

        return [...baseColumns, ...scoreColumns, ...metadataColumns, ...otherColumns]
    }

    const columnsForSelectedRuns = computed((): ColumnConfig[] => {
        if (selectedRunIds.value.length === 0 && selectedSavedSetIds.value.length === 0) return []
        const parts: Design[] = []
        for (const id of selectedRunIds.value) {
            const rows = designsByRun.value.get(id)
            if (rows?.length) parts.push(...rows)
        }
        // Saved-Set-sourced rows (plan §7A) aren't grouped under a selected live run_id
        // in designsByRun when their own run isn't also live-selected — pull them in via
        // their provenance marker so column inference still covers Set-only columns.
        if (selectedSavedSetIds.value.length > 0) {
            for (const d of designs.value) {
                if ((d as Record<string, unknown>).__source_saved_set_id != null) parts.push(d)
            }
        }
        if (parts.length === 0) return []
        return buildColumnsFromData(parts)
    })

    watch(
        columnsForSelectedRuns,
        (cols) => {
            const allowed = new Set(cols.map(c => c.field))
            if (allowed.size === 0) return
            visibleColumns.value = visibleColumns.value.filter(f => allowed.has(f))
        },
        { deep: true }
    )

    const hydrateFromPersistence = async () => {
        try {
            const viewPayload = await kvGet<{
                selectedRunIds?: unknown
                selectedDesigns?: unknown
                currentNavDesignId?: unknown
            }>(PERSISTENCE_KEYS.designsViewState)
            if (viewPayload) {
                if (Array.isArray(viewPayload.selectedRunIds)) {
                    selectedRunIds.value = viewPayload.selectedRunIds
                        .map((v) => String(v))
                        .filter((v) => v.length > 0)
                }
                const sel = viewPayload.selectedDesigns
                if (sel && typeof sel === 'object' && (sel as { allFiltered?: boolean }).allFiltered) {
                    pendingSelectAllFiltered.value = true
                } else if (Array.isArray(sel)) {
                    pendingSelectedDesignKeys.value = sel
                        .map((row) => {
                            const runId = (row as any)?.run_id
                            const designId = (row as any)?.design_id
                            if (runId == null || designId == null) return null
                            return { run_id: String(runId), design_id: String(designId) }
                        })
                        .filter((row): row is { run_id: string; design_id: string } => row !== null)
                } else if (
                    sel &&
                    typeof sel === 'object' &&
                    Array.isArray((sel as { designs?: unknown }).designs)
                ) {
                    pendingSelectedDesignKeys.value = (sel as { designs: unknown[] }).designs
                        .map((row) => {
                            const runId = (row as any)?.run_id
                            const designId = (row as any)?.design_id
                            if (runId == null || designId == null) return null
                            return { run_id: String(runId), design_id: String(designId) }
                        })
                        .filter((row): row is { run_id: string; design_id: string } => row !== null)
                }
                if (viewPayload.currentNavDesignId != null && viewPayload.currentNavDesignId !== '') {
                    pendingCurrentNavDesignId.value = String(viewPayload.currentNavDesignId)
                }
            }
        } catch (e) {
            console.warn('Failed to hydrate designs persistence from IndexedDB', e)
        } finally {
            designsPersistenceHydrated.value = true
        }
    }

    // Getters — `designs` holds only rows for the current selected runs after fetch.
    // Hard filtering (column/operator/threshold rules) now lives entirely on the
    // backend filtering engine (see plan §7A) — a design passes when
    // filteringStore.effectivePassingKeys is null (no active filter) or contains this
    // design's key. The legacy client-side custom-filter system (per-row
    // column/operator/value rules re-implemented in JS) has been removed in favour of
    // this single source of truth; see the Filtering tab for building filters.
    const filteredDesigns = computed(() => {
        let filtered = designs.value

        // Apply backend-driven hard filters + (if enabled) diversity selection from the
        // Filtering tab (see plan §7A) — null means no active filter (show everything);
        // otherwise keep only designs whose key is in the passing set. Lazily looked up
        // to avoid a circular store-init dependency (filteringStore.activeRunIds reads
        // this store).
        const passingKeys = useFilteringStore().effectivePassingKeys
        if (passingKeys) {
            filtered = filtered.filter(design => passingKeys.has(buildDesignKey(design)))
        }

        // Filter by selected run IDs (defensive; payload is usually already scoped).
        // Rows sourced from a selected Saved Set (plan §7A — see fetchDesignsForSelection
        // in this file) carry __source_saved_set_id and are exempt: their run_id is the
        // *originating* run, which may not itself be live-selected in Select Runs.
        if (selectedRunIds.value.length > 0 || selectedSavedSetIds.value.length > 0) {
            const idSet = new Set(selectedRunIds.value.map(String))
            filtered = filtered.filter(design =>
                idSet.has(String(design.run_id)) || (design as Record<string, unknown>).__source_saved_set_id != null
            )
        } else {
            filtered = []
        }

        // Apply best MPNN filtering if enabled
        if (bestMpnnOnly.value) {
            filtered = _filterBestMpnnDesigns(filtered)
        }

        // Attach final_rank/quality_score from an "Apply Ranking"/"Apply Diversity
        // Filter" result (see plan §7A.2), for display/sorting in the Designs table.
        const rankedDesigns = useFilteringStore().rankedDesigns
        if (rankedDesigns) {
            filtered = filtered.map(design => {
                const info = rankedDesigns.get(buildDesignKey(design))
                if (!info) return design
                return { ...design, final_rank: info.final_rank, quality_score: info.quality_score }
            })
        }

        return filtered
    })

    const clearDesignSelection = () => {
        selectAllFiltered.value = false
        excludedKeys.value = new Set()
        includedKeys.value = new Set()
    }

    const resolveSelectedDesigns = (): Design[] => {
        const rows = filteredDesigns.value
        if (selectAllFiltered.value) {
            if (excludedKeys.value.size === 0) return rows
            return rows.filter((d) => !excludedKeys.value.has(designBinderKey(d)))
        }
        if (includedKeys.value.size === 0) return []
        return rows.filter((d) => includedKeys.value.has(designBinderKey(d)))
    }

    const selectedDesigns = computed(() => resolveSelectedDesigns())

    const selectedDesignCount = computed(() => {
        const total = filteredDesigns.value.length
        if (selectAllFiltered.value) return Math.max(0, total - excludedKeys.value.size)
        return includedKeys.value.size
    })

    const isDesignSelected = (design: Design): boolean => {
        const key = designBinderKey(design)
        if (selectAllFiltered.value) return !excludedKeys.value.has(key)
        return includedKeys.value.has(key)
    }

    const toggleDesignSelected = (design: Design, checked: boolean) => {
        const key = designBinderKey(design)
        if (selectAllFiltered.value) {
            const next = new Set(excludedKeys.value)
            if (checked) next.delete(key)
            else next.add(key)
            excludedKeys.value = next
        } else {
            const next = new Set(includedKeys.value)
            if (checked) next.add(key)
            else next.delete(key)
            includedKeys.value = next
        }
    }

    const toggleSelectAllFiltered = (checked: boolean) => {
        if (checked) {
            selectAllFiltered.value = true
            excludedKeys.value = new Set()
            includedKeys.value = new Set()
        } else {
            clearDesignSelection()
        }
    }

    const tableHeaderSelectionChecked = computed(
        () =>
            filteredDesigns.value.length > 0 &&
            selectedDesignCount.value === filteredDesigns.value.length
    )

    const tableHeaderSelectionIndeterminate = computed(() => {
        const count = selectedDesignCount.value
        return count > 0 && count < filteredDesigns.value.length
    })

    const setSelectionFromDesigns = (designsToSelect: Design[]) => {
        selectAllFiltered.value = false
        excludedKeys.value = new Set()
        includedKeys.value = new Set(designsToSelect.map(designBinderKey))
    }

    const restoreSelectionAfterLoad = (rows: Design[]) => {
        if (pendingSelectAllFiltered.value) {
            selectAllFiltered.value = true
            excludedKeys.value = new Set()
            includedKeys.value = new Set()
            pendingSelectAllFiltered.value = false
            return
        }
        if (pendingSelectedDesignKeys.value.length > 0) {
            const keySet = new Set(
                pendingSelectedDesignKeys.value.map((k) => `${k.run_id}::${k.design_id}`)
            )
            setSelectionFromDesigns(rows.filter((d) => keySet.has(`${d.run_id}::${d.design_id}`)))
            pendingSelectedDesignKeys.value = []
            return
        }
        if (selectAllFiltered.value) {
            return
        }
        if (includedKeys.value.size > 0) {
            const byBinder = new Map(rows.map((d) => [designBinderKey(d), d]))
            const next = new Set<string>()
            for (const key of includedKeys.value) {
                if (byBinder.has(key)) next.add(key)
            }
            includedKeys.value = next
        }
    }

    const persistViewStateToStorage = () => {
        if (!designsPersistenceHydrated.value) return
        const selectionPayload =
            selectAllFiltered.value && excludedKeys.value.size === 0
                ? { allFiltered: true as const }
                : {
                      designs: resolveSelectedDesigns().map((d) => ({
                          run_id: d.run_id,
                          design_id: d.design_id
                      }))
                  }
        void kvSet(PERSISTENCE_KEYS.designsViewState, {
            selectedRunIds: selectedRunIds.value,
            selectedDesigns: selectionPayload,
            currentNavDesignId: currentNavDesignId.value
        })
    }

    const selectedDesignKeysSignature = computed(() => {
        if (selectAllFiltered.value && excludedKeys.value.size === 0) {
            return `__all__:${filteredDesigns.value.length}`
        }
        return [...includedKeys.value].sort().join('|')
    })

    const orderedFilteredDesigns = computed(() => {
        const data = [...filteredDesigns.value]
        const field = tableSortField.value
        const order = tableSortOrder.value
        if (field == null || order == null || order === 0) {
            return data
        }
        const resolvedFieldData = new Map<Design, unknown>()
        for (const item of data) {
            resolvedFieldData.set(item, resolveFieldData(item, field))
        }
        const comparer = localeComparator()
        data.sort((a, b) => {
            const v1 = resolvedFieldData.get(a)
            const v2 = resolvedFieldData.get(b)
            return sort(v1 as any, v2 as any, order, comparer as any, 1)
        })
        return data
    })

    const extractFilename = (pdbFile: string | undefined): string => {
        if (!pdbFile) return ''
        return pdbFile.split('/').pop() || ''
    }

    const getStructureFilename = (design: Design): string => getStructureFilenameFromDesign(design)

    const hasStructureFile = (d: Design): boolean => designHasStructureFile(d)

    const totalDesigns = computed(() => designs.value.length)

    // Helper function to select the best design from a group using primary and secondary scores
    const _selectBestDesign = (designs: Design[]): Design => {
        if (designs.length === 0) return designs[0]
        if (designs.length === 1) return designs[0]

        let bestDesign = designs[0]
        let bestScore: number | null = null

        for (const design of designs) {
            const method = (design as any).method || ''
            const config = METHOD_BEST_SCORE[method]

            if (!config) {
                // Unknown method, keep the first design
                continue
            }

            // Get primary score
            const primaryScore = design[config.primary as keyof Design] as number | null
            if (primaryScore === null || primaryScore === undefined) {
                continue
            }

            // Compare with current best
            let isBetter = false
            if (bestScore === null) {
                isBetter = true
            } else if (config.higherIsBetter) {
                if (primaryScore > bestScore) {
                    isBetter = true
                } else if (primaryScore === bestScore) {
                    // Primary scores are equal, check secondary scores
                    isBetter = _compareSecondaryScores(design, bestDesign, config.secondary, true)
                }
            } else {
                if (primaryScore < bestScore) {
                    isBetter = true
                } else if (primaryScore === bestScore) {
                    // Primary scores are equal, check secondary scores
                    isBetter = _compareSecondaryScores(design, bestDesign, config.secondary, false)
                }
            }

            if (isBetter) {
                bestDesign = design
                bestScore = primaryScore
            }
        }

        return bestDesign
    }

    // Helper function to compare secondary scores when primary scores are equal
    const _compareSecondaryScores = (
        design1: Design,
        design2: Design,
        secondaryFields: string[],
        higherIsBetter: boolean
    ): boolean => {
        for (const field of secondaryFields) {
            const score1 = design1[field as keyof Design] as number | null
            const score2 = design2[field as keyof Design] as number | null

            // Skip if either score is null/undefined
            if (score1 === null || score1 === undefined || score2 === null || score2 === undefined) {
                continue
            }

            // Compare scores
            if (higherIsBetter) {
                if (score1 > score2) return true
                if (score1 < score2) return false
            } else {
                if (score1 < score2) return true
                if (score1 > score2) return false
            }
        }

        // If all secondary scores are equal or missing, return false (keep current best)
        return false
    }

    // Helper function to filter best MPNN designs
    const _filterBestMpnnDesigns = (designs: Design[]): Design[] => {
        if (!designs || designs.length === 0) return designs

        // Group designs by backbone_id
        const backboneGroups: Record<string, Design[]> = {}
        for (const design of designs) {
            const backboneId = (design as any).backbone_id
            if (!backboneId) {
                // If no backbone_id, keep the design as-is
                backboneGroups['no_backbone'] = backboneGroups['no_backbone'] || []
                backboneGroups['no_backbone'].push(design)
                continue
            }

            backboneGroups[backboneId] = backboneGroups[backboneId] || []
            backboneGroups[backboneId].push(design)
        }

        // For each backbone group, select the best design
        const filteredDesigns: Design[] = []
        for (const [backboneId, groupDesigns] of Object.entries(backboneGroups)) {
            if (backboneId === 'no_backbone') {
                // Keep all designs without backbone_id
                filteredDesigns.push(...groupDesigns)
                continue
            }

            if (groupDesigns.length === 1) {
                // Only one design for this backbone, keep it
                filteredDesigns.push(groupDesigns[0])
                continue
            }

            // Find the best design using primary and secondary scores
            const bestDesign = _selectBestDesign(groupDesigns)
            filteredDesigns.push(bestDesign)
        }

        return filteredDesigns
    }

    const designsWithPdbOrdered = (): Design[] =>
        orderedFilteredDesigns.value.filter(d => hasStructureFile(d))

    watch(orderedFilteredDesigns, () => {
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) {
            currentNavDesignId.value = null
            return
        }
        if (!currentNavDesignId.value || !withPdb.some(d => d.design_id === currentNavDesignId.value)) {
            currentNavDesignId.value = withPdb[0].design_id
        }
    }, { deep: true, immediate: true })

    const currentStructure = computed((): StructureInfo | null => {
        if (selectedDesignCount.value === 0) {
            return null
        }

        const withPdb = designsWithPdbOrdered()

        if (withPdb.length === 0) {
            return null
        }

        const id = currentNavDesignId.value
        const design = id ? withPdb.find(d => d.design_id === id) : undefined
        const chosen = design ?? withPdb[0]
        const filename = getStructureFilename(chosen)
        if (!filename) {
            return null
        }

        return {
            design: chosen,
            filename,
            pdbPath: chosen.pdb_file || ''
        }
    })

    const canNavigatePrevious = computed(() => {
        if (selectedDesignCount.value === 0) return false
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) return false
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        return idx > 0
    })

    const canNavigateNext = computed(() => {
        if (selectedDesignCount.value === 0) return false
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) return false
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        return idx >= 0 && idx < withPdb.length - 1
    })

    const totalStructures = computed(() => {
        return designsWithPdbOrdered().length
    })

    // Actions
    const fetchDesignsForRuns = async (runIds: string[]) => {
        const seq = ++fetchSeq
        if (runIds.length === 0) {
            designs.value = []
            rebuildDesignsByRun([])
            loadedRunIdsSignature.value = ''
            clearDesignSelection()
            currentNavDesignId.value = null
            loading.value = false
            return
        }

        loading.value = true
        try {
            const hadDesigns = designs.value.length > 0
            const prevVisible = [...visibleColumns.value]
            const data = await designsApi.listDesigns(runIds)
            if (seq !== fetchSeq) return

            const rows = withRowKeys(data.designs)
            designs.value = rows
            rebuildDesignsByRun(rows)
            loadedRunIdsSignature.value = runIdsSignature(runIds)

            restoreSelectionAfterLoad(rows)

            if (pendingCurrentNavDesignId.value != null) {
                currentNavDesignId.value = pendingCurrentNavDesignId.value
                pendingCurrentNavDesignId.value = null
            }
            const withPdb = designsWithPdbOrdered()
            if (!withPdb.some((d) => d.design_id === currentNavDesignId.value)) {
                currentNavDesignId.value = withPdb[0]?.design_id ?? null
            }

            if (seq === fetchSeq) {
                loading.value = false
            }

            // Defer column metadata so the table can render rows before a large scan.
            await nextTick()
            if (seq !== fetchSeq) return

            const sample = sampleDesignsForColumnInference(rows)
            columns.value = buildColumnsFromData(rows)

            const newDefaultColumns = ['design_id', 'project_id', 'run_name', 'method']

            if (sample.some(d => Object.prototype.hasOwnProperty.call(d, 'good'))) {
                newDefaultColumns.push('good')
            }

            if (sample.some(d => 'Length' in d && d['Length'] != null)) {
                newDefaultColumns.push('Length')
            }

            const scoreColumns = defaultVisibleScoreColumnFields()
            scoreColumns.forEach(scoreCol => {
                if (sample.some(d => scoreCol in d && d[scoreCol] != null)) {
                    newDefaultColumns.push(scoreCol)
                }
            })

            if (!hadDesigns) {
                visibleColumns.value = newDefaultColumns
            } else {
                const fieldSet = new Set(columns.value.map(c => c.field))
                visibleColumns.value = prevVisible.filter(f => fieldSet.has(f))
            }
        } catch (err) {
            console.error('Error loading designs:', err)
            throw err
        } finally {
            if (seq === fetchSeq) {
                loading.value = false
            }
        }
    }

    /** Refresh designs for the current `selectedRunIds` (e.g. after cache refresh). */
    const fetchDesigns = async () => {
        await fetchDesignsForRuns(selectedRunIds.value)
    }

    /**
     * Convert one Saved Set's frozen design rows (see plan §7A.3 — snapshot data,
     * not rejoined against live run data) into Design-shaped rows, tagged with
     * provenance markers so the UI can show which Set a row came from.
     */
    function savedSetRowsToDesigns(rows: SavedSetDesignRowDto[], savedSetId: string, savedSetName: string): Design[] {
        return rows.map((row) => ({
            ...row.metrics,
            run_id: row.run_id,
            design_id: row.design_id,
            source_path: row.source_path ?? undefined,
            final_rank: row.final_rank ?? undefined,
            quality_score: row.quality_score ?? undefined,
            in_diverse_set: row.in_diverse_set,
            __source_saved_set_id: savedSetId,
            __source_saved_set_name: savedSetName,
        } as unknown as Design))
    }

    /**
     * Load the raw design pool from the union of selected Runs + selected Saved Sets
     * (plan §7A "Redesign: Unifying Designs-Tab Filters With the Filtering Tab").
     *
     * Runs go through the existing `fetchDesignsForRuns` (untouched — that function
     * already owns row/column setup for the live-run path). Saved Sets are fetched
     * separately and merged in afterwards, deduped per §7A.5: a design present via
     * both a live-selected Run and a selected Set keeps the live Run's version.
     */
    const fetchDesignsForSelection = async (runIds: string[], savedSetIds: string[]) => {
        await fetchDesignsForRuns(runIds)

        if (savedSetIds.length === 0) {
            loadedSavedSetIdsSignature.value = ''
            return
        }

        const filteringStore = useFilteringStore()
        const liveKeys = new Set(
            designs.value.map((d) => designDedupeKey(d.run_id, d.design_id, (d as Record<string, unknown>).source_path as string | undefined))
        )

        // First-seen-in-selection-order wins between two Sets with no live Run in
        // view for that key (plan §7A.5 — explicitly left as a low-stakes, undecided
        // tiebreak; this is the accepted default).
        const seenSetKeys = new Set<string>()
        const setRows: Design[] = []
        for (const savedSetId of savedSetIds) {
            let savedSetName = filteringStore.savedSets.find((s) => s.id === savedSetId)?.name
            if (savedSetName == null) {
                try {
                    const detail = await savedSetsApi.get(savedSetId)
                    savedSetName = detail.name
                } catch (err) {
                    console.error(`Error fetching saved set ${savedSetId} details:`, err)
                    savedSetName = savedSetId
                }
            }
            try {
                const { designs: rows } = await savedSetsApi.getDesigns(savedSetId)
                for (const design of savedSetRowsToDesigns(rows, savedSetId, savedSetName)) {
                    const key = designDedupeKey(design.run_id, design.design_id, (design as Record<string, unknown>).source_path as string | undefined)
                    if (liveKeys.has(key) || seenSetKeys.has(key)) continue
                    seenSetKeys.add(key)
                    setRows.push(design)
                }
            } catch (err) {
                console.error(`Error fetching designs for saved set ${savedSetId}:`, err)
            }
        }

        if (setRows.length === 0) {
            loadedSavedSetIdsSignature.value = [...savedSetIds].sort().join('|')
            return
        }

        const hadVisibleColumns = visibleColumns.value.length > 0
        const merged = withRowKeys([...designs.value, ...setRows])
        designs.value = merged
        rebuildDesignsByRun(merged)
        loadedSavedSetIdsSignature.value = [...savedSetIds].sort().join('|')

        // Re-run column inference over the merged pool so Set-only columns show up.
        await nextTick()
        columns.value = buildColumnsFromData(merged)

        // Mirrors fetchDesignsForRuns' first-load defaulting: if nothing was visible yet
        // (e.g. a Set was selected with zero live Runs, so fetchDesignsForRuns([]) never
        // set defaults), pick the same sensible default column set.
        if (!hadVisibleColumns) {
            const sample = sampleDesignsForColumnInference(merged)
            const defaultColumns = ['design_id', 'project_id', 'run_name', 'method']
            if (sample.some(d => Object.prototype.hasOwnProperty.call(d, 'good'))) {
                defaultColumns.push('good')
            }
            if (sample.some(d => 'Length' in d && d['Length'] != null)) {
                defaultColumns.push('Length')
            }
            defaultVisibleScoreColumnFields().forEach(scoreCol => {
                if (sample.some(d => scoreCol in d && d[scoreCol] != null)) {
                    defaultColumns.push(scoreCol)
                }
            })
            visibleColumns.value = defaultColumns
        }
    }

    const flushSelectedRunIds = async (): Promise<void> => {
        if (selectionDebounceTimer) {
            clearTimeout(selectionDebounceTimer)
            selectionDebounceTimer = null
        }
        await fetchDesignsForSelection(selectedRunIds.value, selectedSavedSetIds.value)
    }

    const ensureDesignsForCurrentSelection = async (): Promise<void> => {
        if (selectedRunIds.value.length === 0) return
        const sig = runIdsSignature(selectedRunIds.value)
        if (sig === loadedRunIdsSignature.value && designs.value.length > 0) return
        await fetchDesignsForRuns(selectedRunIds.value)
    }

    const toggleBestMpnnOnly = () => {
        bestMpnnOnly.value = !bestMpnnOnly.value
        // No need to reload designs - filtering is done in computed property
    }

    const selectDesigns = (designsToSelect: Design[]) => {
        setSelectionFromDesigns(designsToSelect)
        const withPdb = designsWithPdbOrdered()
        currentNavDesignId.value = withPdb[0]?.design_id ?? null
    }

    const toggleColumn = (field: string) => {
        const index = visibleColumns.value.indexOf(field)
        if (index > -1) {
            visibleColumns.value.splice(index, 1)
        } else {
            visibleColumns.value.push(field)
        }
    }

    const navigateStructure = (direction: 'next' | 'previous') => {
        const withPdb = designsWithPdbOrdered()
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        if (idx < 0) return
        if (direction === 'next' && idx < withPdb.length - 1) {
            currentNavDesignId.value = withPdb[idx + 1].design_id
        } else if (direction === 'previous' && idx > 0) {
            currentNavDesignId.value = withPdb[idx - 1].design_id
        }
    }

    const clearDesigns = async () => {
        try {
            await designsApi.clearDesigns()
            designs.value = []
            rebuildDesignsByRun([])
            loadedRunIdsSignature.value = ''
            clearDesignSelection()
            currentNavDesignId.value = null
        } catch (err) {
            console.error('Error clearing designs:', err)
            throw err
        }
    }

    const setSelectedRunIds = (runIds: string[]) => {
        const previousRunIdsSignature = runIdsSignature(selectedRunIds.value)
        const nextRunIdsSignature = runIdsSignature(runIds)
        selectedRunIds.value = runIds
        if (runIds.length === 0) {
            clearDesignSelection()
        } else if (selectAllFiltered.value) {
            excludedKeys.value = new Set(
                [...excludedKeys.value].filter((key) => {
                    const row = designs.value.find((d) => designBinderKey(d) === key)
                    return row != null && runIds.includes(String(row.run_id))
                })
            )
        } else {
            includedKeys.value = new Set(
                [...includedKeys.value].filter((key) => {
                    const row = designs.value.find((d) => designBinderKey(d) === key)
                    return row != null && runIds.includes(String(row.run_id))
                })
            )
        }

        if (
            nextRunIdsSignature === previousRunIdsSignature &&
            nextRunIdsSignature === loadedRunIdsSignature.value &&
            designs.value.length > 0
        ) {
            return
        }

        if (selectionDebounceTimer) {
            clearTimeout(selectionDebounceTimer)
            selectionDebounceTimer = null
        }

        if (runIds.length === 0) {
            void fetchDesignsForSelection([], selectedSavedSetIds.value)
            return
        }

        selectionDebounceTimer = setTimeout(() => {
            selectionDebounceTimer = null
            void fetchDesignsForSelection(runIds, selectedSavedSetIds.value)
        }, SELECTION_DEBOUNCE_MS)
    }

    /**
     * Setter for `selectedSavedSetIds`, mirroring `setSelectedRunIds`'s debounce
     * convention (own timer, so a Sets-only change doesn't cancel an in-flight
     * Runs-selection debounce or vice versa). Triggers the combined Runs+Sets
     * reload (see plan §7A.4 — Select Runs handles inclusion of both).
     */
    const setSelectedSavedSetIds = (savedSetIds: string[]) => {
        const previousSignature = [...selectedSavedSetIds.value].sort().join('|')
        const nextSignature = [...savedSetIds].sort().join('|')
        selectedSavedSetIds.value = savedSetIds

        if (
            nextSignature === previousSignature &&
            nextSignature === loadedSavedSetIdsSignature.value
        ) {
            return
        }

        if (savedSetSelectionDebounceTimer) {
            clearTimeout(savedSetSelectionDebounceTimer)
            savedSetSelectionDebounceTimer = null
        }

        if (savedSetIds.length === 0) {
            void fetchDesignsForSelection(selectedRunIds.value, [])
            return
        }

        savedSetSelectionDebounceTimer = setTimeout(() => {
            savedSetSelectionDebounceTimer = null
            void fetchDesignsForSelection(selectedRunIds.value, savedSetIds)
        }, SELECTION_DEBOUNCE_MS)
    }

    const viewDesign = (design: Design) => {
        setSelectionFromDesigns([design])

        const withPdb = designsWithPdbOrdered()
        const index = withPdb.findIndex(d => d.design_id === design.design_id)
        if (index >= 0) {
            currentNavDesignId.value = withPdb[index].design_id
        } else if (withPdb.length > 0) {
            currentNavDesignId.value = withPdb[0].design_id
        } else {
            currentNavDesignId.value = null
        }
    }

    const patchDesignGood = async (design: Design, good: boolean | null) => {
        const sourcePath = (design as any).source_path as string | undefined
        await designsApi.patchDesignGood({
            run_id: design.run_id,
            design_id: design.design_id,
            good,
            ...(sourcePath ? { source_path: sourcePath } : {})
        })
        const sync = (d: Design): Design => {
            if (d.run_id !== design.run_id || d.design_id !== design.design_id) return d
            if (good === null) {
                const next = { ...d } as Record<string, unknown>
                delete next.good
                return next as Design
            }
            return { ...d, good }
        }
        designs.value = designs.value.map(sync)
        rebuildDesignsByRun(designs.value)

        if (!columns.value.some(c => c.field === 'good')) {
            const methodIdx = columns.value.findIndex(c => c.field === 'method')
            const goodCol: ColumnConfig = {
                field: 'good',
                header: 'Good',
                sortable: true,
                filter: true,
                filterType: 'boolean',
                showFilterMenu: false,
                style: 'min-width: 90px'
            }
            if (methodIdx >= 0) {
                columns.value.splice(methodIdx + 1, 0, goodCol)
            } else {
                columns.value.push(goodCol)
            }
        }
        if (!visibleColumns.value.includes('good')) {
            const mi = visibleColumns.value.indexOf('method')
            if (mi >= 0) {
                visibleColumns.value.splice(mi + 1, 0, 'good')
            } else {
                visibleColumns.value.push('good')
            }
        }
    }

    const ensureColumnsVisible = (fields: string[]) => {
        const allowed = new Set(columns.value.map((c) => c.field))
        for (const raw of fields) {
            const field = raw.trim()
            if (!field || !allowed.has(field)) continue
            if (!visibleColumns.value.includes(field)) {
                visibleColumns.value.push(field)
            }
        }
    }

    const ensureTagColumnVisible = () => {
        if (!columns.value.some(c => c.field === 'tag')) {
            const goodIdx = columns.value.findIndex(c => c.field === 'good')
            const methodIdx = columns.value.findIndex(c => c.field === 'method')
            const tagCol: ColumnConfig = {
                field: 'tag',
                header: 'Tag',
                sortable: true,
                filter: true,
                filterType: 'text',
                showFilterMenu: false,
                style: 'min-width: 72px'
            }
            if (goodIdx >= 0) {
                columns.value.splice(goodIdx + 1, 0, tagCol)
            } else if (methodIdx >= 0) {
                columns.value.splice(methodIdx + 1, 0, tagCol)
            } else {
                columns.value.push(tagCol)
            }
        }
        if (!visibleColumns.value.includes('tag')) {
            const gi = visibleColumns.value.indexOf('good')
            const mi = visibleColumns.value.indexOf('method')
            if (gi >= 0) {
                visibleColumns.value.splice(gi + 1, 0, 'tag')
            } else if (mi >= 0) {
                visibleColumns.value.splice(mi + 1, 0, 'tag')
            } else {
                visibleColumns.value.push('tag')
            }
        }
    }

    const patchDesignTag = async (design: Design, tag: 'N' | 'C' | null) => {
        const sourcePath = (design as any).source_path as string | undefined
        await designsApi.patchDesignTag({
            run_id: design.run_id,
            design_id: design.design_id,
            tag,
            ...(sourcePath ? { source_path: sourcePath } : {})
        })
        const sync = (d: Design): Design => {
            if (d.run_id !== design.run_id || d.design_id !== design.design_id) return d
            if (tag === null) {
                const next = { ...d } as Record<string, unknown>
                delete next.tag
                return next as Design
            }
            return { ...d, tag }
        }
        designs.value = designs.value.map(sync)
        rebuildDesignsByRun(designs.value)
        ensureTagColumnVisible()
    }

    const applyTagPlacementResult = (row: {
        run_id: string
        design_id: string
        tag?: string | null
        error?: string | null
    }) => {
        if (row.error) return
        const sync = (d: Design): Design => {
            if (String(d.run_id) !== String(row.run_id) || String(d.design_id) !== String(row.design_id)) {
                return d
            }
            if (row.tag == null || String(row.tag).trim() === '') {
                const next = { ...d } as Record<string, unknown>
                delete next.tag
                return next as Design
            }
            return { ...d, tag: row.tag }
        }
        designs.value = designs.value.map(sync)
        rebuildDesignsByRun(designs.value)
        ensureTagColumnVisible()
    }

    const getCurrentRowPosition = () => {
        if (selectedDesignCount.value === 0) return '0 / 0'

        const withPdb = designsWithPdbOrdered()

        if (withPdb.length === 0) return '0 / 0'

        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        if (idx < 0) return '0 / 0'

        return `${idx + 1} / ${withPdb.length}`
    }

    watch([selectedRunIds, selectedDesignKeysSignature, currentNavDesignId], () => persistViewStateToStorage())

    return {
        // State
        designs,
        designsByRun,
        selectedDesigns,
        selectedDesignCount,
        selectAllFiltered,
        isDesignSelected,
        toggleDesignSelected,
        toggleSelectAllFiltered,
        tableHeaderSelectionChecked,
        tableHeaderSelectionIndeterminate,
        clearDesignSelection,
        setSelectionFromDesigns,
        resolveSelectedDesigns,
        selectedRunIds,
        selectedSavedSetIds,
        bestMpnnOnly,
        columns,
        columnsForSelectedRuns,
        visibleColumns,
        loading,
        currentNavDesignId,
        tableSortField,
        tableSortOrder,

        // Getters
        filteredDesigns,
        orderedFilteredDesigns,
        totalDesigns,
        currentStructure,
        canNavigatePrevious,
        canNavigateNext,
        totalStructures,

        // Actions
        fetchDesigns,
        fetchDesignsForRuns,
        fetchDesignsForSelection,
        flushSelectedRunIds,
        ensureDesignsForCurrentSelection,
        toggleBestMpnnOnly,
        selectDesigns,
        toggleColumn,
        ensureColumnsVisible,
        navigateStructure,
        clearDesigns,
        setSelectedRunIds,
        setSelectedSavedSetIds,
        viewDesign,
        getCurrentRowPosition,
        extractFilename,
        getStructureFilename,
        patchDesignGood,
        patchDesignTag,
        applyTagPlacementResult,
        hydrateFromPersistence
    }
})
