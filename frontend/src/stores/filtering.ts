/**
 * Filtering Store
 * Boltzgen-style filter/rank/diversity-selection state and Saved Sets management.
 * See .cursor/plans/boltzgen_filtering_ui.plan.md §7A for the redesign this
 * implements: run scope comes from `useDesignsStore().selectedRunIds` (no separate
 * run picker here — see plan §7A.2), hard filters are debounced and live-narrow the
 * Designs table via `passingDesignKeys`, and ranking/diversity are explicit actions
 * that populate `rankedDesigns`.
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { filteringApi, savedSetsApi } from '../webapi'
import type {
    ColumnInfoDto,
    FilterSpecDto,
    FilteringPreviewResponseDto,
    FilteringRunRequestDto,
    FilteringRunResponseDto,
    RankingMetricDto,
    SavedSetDto,
    SizeBucketDto
} from '../webapi'
import { buildDesignKey } from '../utils/designKey'
import { useDesignsStore } from './designs'
import { PERSISTENCE_KEYS } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'

/** Debounce window for hard-filter round-trips (see plan §7A.2 — cheap, ~0.16s/60k rows). */
const APPLY_DEBOUNCE_MS = 300

/** Debounce window for persisting filter/ranking/diversity config to IndexedDB. */
const PERSIST_DEBOUNCE_MS = 400

export interface RankedDesignInfo {
    final_rank: number | null
    quality_score: number | null
}

export const useFilteringStore = defineStore('filtering', () => {
    // Available columns (union across the active Designs-tab run scope)
    const availableColumns = ref<ColumnInfoDto[]>([])
    const columnsLoading = ref(false)
    const columnsError = ref<string | null>(null)

    // Filter set configuration
    const filters = ref<FilterSpecDto[]>([])
    const rankingMetrics = ref<RankingMetricDto[]>([])
    const budget = ref<number>(24)
    const alpha = ref<number>(0.1)
    const sizeBuckets = ref<SizeBucketDto[]>([])

    // Live-filter result: null = no active filter (show everything); otherwise the set
    // of design keys (see utils/designKey.ts) that pass the current hard filters.
    // Kept as plain reactive state (not fused into a single fetch-and-filter action) so
    // a future client-side-only path could populate it without a network round-trip —
    // see plan §7A.2's "keep the door open" constraint.
    const passingDesignKeys = ref<Set<string> | null>(null)
    const applyLoading = ref(false)
    const applyError = ref<string | null>(null)
    let applyDebounceTimer: ReturnType<typeof setTimeout> | null = null
    let applySeq = 0

    // Ranking result (from "Apply Ranking" or "Apply Diversity Filter"), keyed the same way.
    const rankedDesigns = ref<Map<string, RankedDesignInfo> | null>(null)
    const rankLoading = ref(false)
    const rankError = ref<string | null>(null)

    const diversityLoading = ref(false)
    const diversityError = ref<string | null>(null)
    const lastDiversityResult = ref<{ passing_filters: number; diverse_set_count: number; total_designs: number } | null>(null)

    // Preview (filter cascade) — unchanged behaviour, now against designsStore.selectedRunIds
    const previewResult = ref<FilteringPreviewResponseDto | null>(null)
    const previewLoading = ref(false)
    const previewError = ref<string | null>(null)

    // Create Saved Set
    const creatingSavedSet = ref(false)
    const createSavedSetError = ref<string | null>(null)
    const lastCreatedSavedSet = ref<FilteringRunResponseDto | null>(null)

    // Saved Sets list
    const savedSets = ref<SavedSetDto[]>([])
    const savedSetsLoading = ref(false)
    const savedSetsError = ref<string | null>(null)

    // Looked up lazily (not at store-setup time) to avoid a circular-init issue: this
    // store's activeRunIds reads designsStore.selectedRunIds, and designsStore in turn
    // needs to consult this store's passingDesignKeys/rankedDesigns when computing
    // filteredDesigns — see stores/designs.ts.
    const activeRunIds = computed(() => useDesignsStore().selectedRunIds)
    const hasSelectedRuns = computed(() => activeRunIds.value.length > 0)

    // `enabled` (default true) is a local UI-only toggle so a row can be turned off
    // without deleting it — never sent to the backend. These computed views strip it
    // and drop disabled rows, and are what every outgoing request body is built from.
    const activeFilters = computed<FilterSpecDto[]>(() =>
        filters.value
            .filter((f) => f.enabled !== false)
            .map(({ column, operator, threshold, text_value }) => ({ column, operator, threshold, text_value }))
    )
    const activeRankingMetrics = computed<RankingMetricDto[]>(() =>
        rankingMetrics.value
            .filter((m) => m.enabled !== false)
            .map(({ column, weight, higher_is_better }) => ({ column, weight, higher_is_better }))
    )

    const hasActiveFilters = computed(() => activeFilters.value.length > 0)

    const canCreateSavedSet = computed(
        () => hasSelectedRuns.value && budget.value > 0 && !creatingSavedSet.value
    )

    // Total designs before any hard filter — same DataFrame the cascade counts below
    // derive from (previewResult always covers the full active run scope, even with
    // zero filters configured — see runPreview).
    const initialDesignCount = computed<number | null>(() => previewResult.value?.total_designs ?? null)

    // Per-filter cascade, positioned for UI consumers that render the filter list as a
    // chain (FilterChainSummary.vue). Each row pairs a configured filter (including
    // disabled ones) with the "designs
    // remaining" count after that stage — per_filter_counts is computed server-side
    // from activeFilters (enabled-only, same relative order), so it's zipped
    // positionally against just the enabled rows here. Guarded by a length check so a
    // stale (pre-debounce) preview doesn't get paired with the wrong filter while an
    // edit is in flight.
    const filterChain = computed(() => {
        const stages = previewResult.value?.per_filter_counts ?? []
        const enabledCount = filters.value.filter((f) => f.enabled !== false).length
        const stagesMatch = stages.length === enabledCount
        let stageIdx = 0
        return filters.value.map((filter, index) => {
            const enabled = filter.enabled !== false
            let remaining: number | null = null
            if (enabled) {
                remaining = stagesMatch ? stages[stageIdx].remaining : null
                stageIdx += 1
            }
            return {
                index,
                column: filter.column,
                operator: filter.operator,
                threshold: filter.threshold ?? null,
                text_value: filter.text_value ?? null,
                enabled,
                remaining
            }
        })
    })

    // --- Available columns ---

    const fetchAvailableColumns = async () => {
        if (!hasSelectedRuns.value) {
            availableColumns.value = []
            return
        }
        columnsLoading.value = true
        columnsError.value = null
        try {
            const res = await filteringApi.columns(activeRunIds.value)
            availableColumns.value = res.columns
        } catch (err) {
            columnsError.value = err instanceof Error ? err.message : 'Failed to load available columns'
            console.error('Error fetching filtering columns:', err)
        } finally {
            columnsLoading.value = false
        }
    }

    // --- Hard filters: debounced live-apply (see plan §7A.2) ---

    const runApplyNow = async () => {
        const seq = ++applySeq
        if (!hasSelectedRuns.value || !hasActiveFilters.value) {
            // No runs, or no filters configured — nothing to narrow by; show everything.
            passingDesignKeys.value = null
            applyLoading.value = false
            return
        }
        applyLoading.value = true
        applyError.value = null
        try {
            const res = await filteringApi.apply({
                run_ids: activeRunIds.value,
                filters: activeFilters.value
            })
            if (seq !== applySeq) return
            passingDesignKeys.value = new Set(
                res.passing_keys.map((k) => buildDesignKey(k))
            )
        } catch (err) {
            if (seq !== applySeq) return
            applyError.value = err instanceof Error ? err.message : 'Failed to apply filters'
            console.error('Error applying filters:', err)
        } finally {
            if (seq === applySeq) applyLoading.value = false
        }
    }

    /**
     * Debounced entry point — call whenever a filter row (or its enabled toggle)
     * changes. Also re-runs the filter-cascade preview on the same debounce, so the
     * "Preview filter cascade" table stays in sync with live hard-filter edits instead
     * of needing a manual re-click.
     */
    const scheduleApply = () => {
        if (applyDebounceTimer) clearTimeout(applyDebounceTimer)
        applyDebounceTimer = setTimeout(() => {
            applyDebounceTimer = null
            void runApplyNow()
            void runPreview().catch(() => {
                /* surfaced via previewError; don't let it break the apply flow */
            })
        }, APPLY_DEBOUNCE_MS)
    }

    const flushApply = async () => {
        if (applyDebounceTimer) {
            clearTimeout(applyDebounceTimer)
            applyDebounceTimer = null
        }
        await Promise.all([
            runApplyNow(),
            runPreview().catch(() => {
                /* surfaced via previewError; don't let it break the apply flow */
            })
        ])
    }

    // --- Ranking / diversity: explicit actions, not debounced (see plan §7A.2) ---

    const applyRanking = async () => {
        if (!hasSelectedRuns.value) return
        rankLoading.value = true
        rankError.value = null
        try {
            const res = await filteringApi.rank({
                run_ids: activeRunIds.value,
                filters: activeFilters.value,
                metrics: activeRankingMetrics.value
            })
            const map = new Map<string, RankedDesignInfo>()
            for (const d of res.designs) {
                map.set(buildDesignKey(d), {
                    final_rank: d.final_rank ?? null,
                    quality_score: d.quality_score ?? null
                })
            }
            rankedDesigns.value = map
        } catch (err) {
            rankError.value = err instanceof Error ? err.message : 'Failed to apply ranking'
            console.error('Error applying ranking:', err)
            throw err
        } finally {
            rankLoading.value = false
        }
    }

    const applyDiversityFilter = async () => {
        if (!hasSelectedRuns.value) return
        diversityLoading.value = true
        diversityError.value = null
        try {
            const res = await filteringApi.diversity({
                run_ids: activeRunIds.value,
                filters: activeFilters.value,
                metrics: activeRankingMetrics.value,
                budget: budget.value,
                alpha: alpha.value,
                size_buckets: sizeBuckets.value
            })
            const rankMap = new Map<string, RankedDesignInfo>()
            const diverseKeys = new Set<string>()
            for (const d of res.designs) {
                const key = buildDesignKey(d)
                rankMap.set(key, {
                    final_rank: d.final_rank ?? null,
                    quality_score: d.quality_score ?? null
                })
                if (d.in_diverse_set) diverseKeys.add(key)
            }
            rankedDesigns.value = rankMap
            // Narrow passingDesignKeys to just the diverse subset.
            passingDesignKeys.value = diverseKeys
            lastDiversityResult.value = {
                passing_filters: res.passing_filters,
                diverse_set_count: res.diverse_set_count,
                total_designs: res.total_designs
            }
        } catch (err) {
            diversityError.value = err instanceof Error ? err.message : 'Failed to apply diversity filter'
            console.error('Error applying diversity filter:', err)
            throw err
        } finally {
            diversityLoading.value = false
        }
    }

    // --- Reset / clear ---

    const clearAppliedFilters = () => {
        passingDesignKeys.value = null
        rankedDesigns.value = null
        applyError.value = null
        rankError.value = null
        diversityError.value = null
        lastDiversityResult.value = null
    }

    const disableAllFilters = () => {
        filters.value.forEach((filter) => {
            filter.enabled = false
        })
        scheduleApply()
    }

    const toggleFilterEnabled = (index: number) => {
        const filter = filters.value[index]
        if (!filter) return
        filter.enabled = filter.enabled === false ? true : false
        scheduleApply()
    }

    // --- Preview (cascade) ---

    const runPreview = async () => {
        if (!hasSelectedRuns.value) {
            previewResult.value = null
            return
        }
        previewLoading.value = true
        previewError.value = null
        try {
            previewResult.value = await filteringApi.preview({
                run_ids: activeRunIds.value,
                filters: activeFilters.value,
                metrics: activeRankingMetrics.value
            })
        } catch (err) {
            previewError.value = err instanceof Error ? err.message : 'Failed to run filter preview'
            console.error('Error running filtering preview:', err)
            throw err
        } finally {
            previewLoading.value = false
        }
    }

    // --- Filter/metric/bucket row editing ---

    const addFilter = () => {
        const firstColumn = availableColumns.value[0]?.name ?? ''
        filters.value.push({ column: firstColumn, operator: '<', threshold: 0, enabled: true })
        scheduleApply()
    }

    const removeFilter = (index: number) => {
        filters.value.splice(index, 1)
        scheduleApply()
    }

    const addRankingMetric = () => {
        const firstColumn = availableColumns.value[0]?.name ?? ''
        rankingMetrics.value.push({ column: firstColumn, weight: 1, higher_is_better: true, enabled: true })
    }

    const removeRankingMetric = (index: number) => {
        rankingMetrics.value.splice(index, 1)
    }

    const addSizeBucket = () => {
        sizeBuckets.value.push({ min: 0, max: 100, num_designs: 5 })
    }

    const removeSizeBucket = (index: number) => {
        sizeBuckets.value.splice(index, 1)
    }

    // --- Saved Sets ---

    const fetchSavedSets = async () => {
        savedSetsLoading.value = true
        savedSetsError.value = null
        try {
            const res = await savedSetsApi.list()
            savedSets.value = res.saved_sets
        } catch (err) {
            savedSetsError.value = err instanceof Error ? err.message : 'Failed to load saved sets'
            console.error('Error fetching saved sets:', err)
        } finally {
            savedSetsLoading.value = false
        }
    }

    const createSavedSet = async (name: string): Promise<FilteringRunResponseDto> => {
        creatingSavedSet.value = true
        createSavedSetError.value = null
        try {
            const res = await filteringApi.run({
                name,
                run_ids: activeRunIds.value,
                filters: activeFilters.value,
                metrics: activeRankingMetrics.value,
                budget: budget.value,
                alpha: alpha.value,
                size_buckets: sizeBuckets.value
            })
            lastCreatedSavedSet.value = res
            await fetchSavedSets()
            return res
        } catch (err) {
            createSavedSetError.value =
                err instanceof Error ? err.message : 'Failed to create saved set'
            console.error('Error creating saved set:', err)
            throw err
        } finally {
            creatingSavedSet.value = false
        }
    }

    const deleteSavedSet = async (savedSetId: string) => {
        try {
            await savedSetsApi.delete(savedSetId)
            savedSets.value = savedSets.value.filter((s) => s.id !== savedSetId)
        } catch (err) {
            savedSetsError.value = err instanceof Error ? err.message : 'Failed to delete saved set'
            console.error('Error deleting saved set:', err)
            throw err
        }
    }

    const resetFilterSet = () => {
        filters.value = []
        rankingMetrics.value = []
        budget.value = 24
        alpha.value = 0.1
        sizeBuckets.value = []
        previewResult.value = null
        previewError.value = null
        lastCreatedSavedSet.value = null
        createSavedSetError.value = null
        clearAppliedFilters()
    }

    /**
     * Populate `filters`/`rankingMetrics`/`budget`/`alpha`/`sizeBuckets` from a
     * previously-saved filter recipe (a `SavedSet.filter_params`, which is a
     * serialized `FilteringRunRequest`). Deliberately does NOT touch `run_ids`/`name`
     * — run scope comes from `designsStore.selectedRunIds`, not the recipe (see plan
     * §7A.4 — called by the in-progress "reapply filters" button elsewhere).
     */
    const loadRecipe = (recipe: FilteringRunRequestDto): void => {
        // A saved recipe's filters/metrics never carry `enabled` (it's UI-only, never
        // sent to or stored by the backend — see activeFilters/activeRankingMetrics
        // above) — every loaded row starts enabled.
        filters.value = recipe.filters ? recipe.filters.map((f) => ({ ...f, enabled: true })) : []
        rankingMetrics.value = recipe.metrics ? recipe.metrics.map((m) => ({ ...m, enabled: true })) : []
        budget.value = recipe.budget ?? 24
        alpha.value = recipe.alpha ?? 0.1
        sizeBuckets.value = recipe.size_buckets ? [...recipe.size_buckets] : []
        clearAppliedFilters()
        scheduleApply()
    }

    // --- Persistence (IndexedDB) — survive browser refresh; mirrors the pattern used
    // by the Designs tab's own view-state persistence (stores/designs.ts) and Plots'
    // scatter-axis preferences (stores/plots.ts). ---

    const filteringPersistenceHydrated = ref(false)
    let persistDebounceTimer: ReturnType<typeof setTimeout> | null = null

    const persistFilteringViewState = () => {
        if (!filteringPersistenceHydrated.value) return
        if (persistDebounceTimer) clearTimeout(persistDebounceTimer)
        persistDebounceTimer = setTimeout(() => {
            persistDebounceTimer = null
            void kvSet(PERSISTENCE_KEYS.filteringViewState, {
                filters: filters.value,
                rankingMetrics: rankingMetrics.value,
                budget: budget.value,
                alpha: alpha.value,
                sizeBuckets: sizeBuckets.value
            })
        }, PERSIST_DEBOUNCE_MS)
    }

    watch([filters, rankingMetrics, budget, alpha, sizeBuckets], persistFilteringViewState, { deep: true })

    const hydrateFromPersistence = async () => {
        try {
            const payload = await kvGet<{
                filters?: unknown
                rankingMetrics?: unknown
                budget?: unknown
                alpha?: unknown
                sizeBuckets?: unknown
            }>(PERSISTENCE_KEYS.filteringViewState)
            if (payload) {
                if (Array.isArray(payload.filters)) {
                    filters.value = payload.filters as FilterSpecDto[]
                }
                if (Array.isArray(payload.rankingMetrics)) {
                    rankingMetrics.value = payload.rankingMetrics as RankingMetricDto[]
                }
                if (typeof payload.budget === 'number') {
                    budget.value = payload.budget
                }
                if (typeof payload.alpha === 'number') {
                    alpha.value = payload.alpha
                }
                if (Array.isArray(payload.sizeBuckets)) {
                    sizeBuckets.value = payload.sizeBuckets as SizeBucketDto[]
                }
            }
        } catch (e) {
            console.warn('Failed to hydrate filtering persistence from IndexedDB', e)
        } finally {
            filteringPersistenceHydrated.value = true
        }
    }

    return {
        // State
        availableColumns,
        columnsLoading,
        columnsError,
        filters,
        rankingMetrics,
        budget,
        alpha,
        sizeBuckets,
        passingDesignKeys,
        applyLoading,
        applyError,
        rankedDesigns,
        rankLoading,
        rankError,
        diversityLoading,
        diversityError,
        lastDiversityResult,
        previewResult,
        previewLoading,
        previewError,
        creatingSavedSet,
        createSavedSetError,
        lastCreatedSavedSet,
        savedSets,
        savedSetsLoading,
        savedSetsError,

        // Getters
        activeRunIds,
        hasSelectedRuns,
        hasActiveFilters,
        canCreateSavedSet,
        initialDesignCount,
        filterChain,

        // Actions
        fetchAvailableColumns,
        scheduleApply,
        flushApply,
        applyRanking,
        applyDiversityFilter,
        clearAppliedFilters,
        disableAllFilters,
        toggleFilterEnabled,
        runPreview,
        addFilter,
        removeFilter,
        addRankingMetric,
        removeRankingMetric,
        addSizeBucket,
        removeSizeBucket,
        fetchSavedSets,
        createSavedSet,
        deleteSavedSet,
        resetFilterSet,
        loadRecipe,
        hydrateFromPersistence
    }
})
