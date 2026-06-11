/**
 * Plots Store
 * Manages plotting data, chart state, and plot interactions
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { plotsApi } from '../webapi'
import { PERSISTENCE_KEYS } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'
import type { PlotSelection, PlotsState } from '../types/store'

type ScatterAxisPreferences = {
    x: string | null
    y: string | null
    color: string | null
    size: string | null
}

const emptyScatterAxisPreferences = (): ScatterAxisPreferences => ({
    x: null,
    y: null,
    color: null,
    size: null,
})

export const usePlotsStore = defineStore('plots', () => {
    // State
    const selectedRunIds = ref<string[]>([])
    const combinedData = ref<any[]>([])
    const numericColumns = ref<string[]>([])
    const plotColumns = ref<string[]>([])
    const scatterXCol = ref<string | null>(null)
    const scatterYCol = ref<string | null>(null)
    const scatterColorCol = ref<string | null>(null)
    const scatterSizeCol = ref<string | null>(null)
    const loading = ref(false)
    const chartLoading = ref(false)
    const plotSelections = ref<PlotSelection[]>([])

    const scatterAxisPreferences = ref<ScatterAxisPreferences>(emptyScatterAxisPreferences())
    const plotsPersistenceHydrated = ref(false)
    let resolvingScatterColumns = false

    // Getters
    const filteredRuns = computed(() => {
        return []
    })

    const availableColumns = computed(() => numericColumns.value)

    const hasValidData = computed(() =>
        combinedData.value.length > 0 &&
        numericColumns.value.length > 0 &&
        scatterXCol.value &&
        scatterYCol.value
    )

    const selectedDataPoints = computed(() => {
        if (plotSelections.value.length === 0) return combinedData.value

        return combinedData.value.filter(point => {
            return plotSelections.value.some(selection => {
                if (selection.type === 'point' && selection.data) {
                    return selection.data.some(selectedPoint =>
                        selectedPoint.design_id === point.design_id
                    )
                } else if (selection.type === 'range' && selection.field && selection.range) {
                    const value = point[selection.field]
                    return value >= selection.range.min && value <= selection.range.max
                }
                return false
            })
        })
    })

    const columnCoverage = (coerced: any[], col: string): number =>
        coerced.reduce((acc: number, r: any) => acc + (Number.isFinite(r[col]) ? 1 : 0), 0)

    const defaultNumericColumn = (
        coerced: any[],
        numeric: string[],
        exclude?: string | null,
    ): string | null => {
        const candidates = numeric.filter((c) => c !== exclude)
        if (candidates.length === 0) return null
        const sorted = [...candidates].sort((a, b) => columnCoverage(coerced, b) - columnCoverage(coerced, a))
        return sorted[0] ?? null
    }

    const resolveNumericColumn = (
        preference: string | null,
        numeric: string[],
        coerced: any[],
        exclude?: string | null,
    ): string | null => {
        const candidates = numeric.filter((c) => c !== exclude)
        if (preference && candidates.includes(preference)) return preference
        return defaultNumericColumn(coerced, numeric, exclude)
    }

    const resolveOptionalColumn = (
        preference: string | null,
        available: string[],
    ): string | null => {
        if (preference && available.includes(preference)) return preference
        return null
    }

    const applyScatterColumnsFromData = (coerced: any[]) => {
        const numeric = numericColumns.value
        const plotCols = plotColumns.value
        const prefs = scatterAxisPreferences.value

        resolvingScatterColumns = true
        try {
            const x = resolveNumericColumn(prefs.x, numeric, coerced)
            const y = resolveNumericColumn(prefs.y, numeric, coerced, x)
            scatterXCol.value = x
            scatterYCol.value = y
            scatterColorCol.value = resolveOptionalColumn(prefs.color, plotCols)
            scatterSizeCol.value = resolveOptionalColumn(prefs.size, numeric)
        } finally {
            resolvingScatterColumns = false
        }
    }

    const recordScatterAxisPreferences = () => {
        if (!plotsPersistenceHydrated.value || resolvingScatterColumns) return
        scatterAxisPreferences.value = {
            x: scatterXCol.value,
            y: scatterYCol.value,
            color: scatterColorCol.value,
            size: scatterSizeCol.value,
        }
        void kvSet(PERSISTENCE_KEYS.plotsScatterAxes, { ...scatterAxisPreferences.value })
    }

    const hydrateFromPersistence = async () => {
        try {
            const payload = await kvGet<Partial<ScatterAxisPreferences>>(PERSISTENCE_KEYS.plotsScatterAxes)
            if (payload) {
                scatterAxisPreferences.value = {
                    x: typeof payload.x === 'string' ? payload.x : null,
                    y: typeof payload.y === 'string' ? payload.y : null,
                    color: typeof payload.color === 'string' ? payload.color : null,
                    size: typeof payload.size === 'string' ? payload.size : null,
                }
            }
        } catch (e) {
            console.warn('Failed to hydrate plots persistence from IndexedDB', e)
        } finally {
            plotsPersistenceHydrated.value = true
        }
    }

    // Actions
    const setSelectedRuns = (runIds: string[]) => {
        selectedRunIds.value = runIds
    }

    const fetchCombinedData = async (runIds: string[]) => {
        if (runIds.length === 0) {
            combinedData.value = []
            numericColumns.value = []
            scatterXCol.value = null
            scatterYCol.value = null
            return
        }

        loading.value = true
        try {
            const [result, cols] = await Promise.all([
                plotsApi.getCombinedData(runIds),
                plotsApi.getPlotColumns(runIds).catch(() => null)
            ])

            const coerced = result.data.map((row: any) => {
                const copy: any = { ...row }
                for (const key of Object.keys(copy)) {
                    const v = copy[key]
                    if (v == null) continue
                    if (typeof v === 'number') continue
                    const n = Number(v)
                    if (Number.isFinite(n)) copy[key] = n
                }
                return copy
            })

            combinedData.value = coerced
            numericColumns.value = result.numericColumns
            const keys = new Set<string>()
            coerced.forEach((r: any) => Object.keys(r).forEach((k) => keys.add(k)))
            plotColumns.value = Array.from(keys).filter((col) =>
                coerced.some((r: any) => r[col] != null && r[col] !== '')
            ).sort()

            if (cols?.numeric_columns?.length) {
                const defX = cols.defaults?.x
                const defY = cols.defaults?.y
                if (defX && !scatterAxisPreferences.value.x) scatterAxisPreferences.value.x = defX
                if (defY && !scatterAxisPreferences.value.y) scatterAxisPreferences.value.y = defY
            }

            applyScatterColumnsFromData(coerced)
        } catch (err) {
            console.error('Error loading combined data:', err)
            throw err
        } finally {
            loading.value = false
        }
    }

    const setAxisColumns = (x: string, y: string) => {
        scatterXCol.value = x
        scatterYCol.value = y
    }

    const updatePlots = () => {
        // Triggered by components
    }

    const clearData = () => {
        selectedRunIds.value = []
        combinedData.value = []
        numericColumns.value = []
        plotColumns.value = []
        scatterXCol.value = null
        scatterYCol.value = null
        scatterColorCol.value = null
        scatterSizeCol.value = null
        plotSelections.value = []
    }

    const addPlotSelection = (selection: PlotSelection) => {
        plotSelections.value.push(selection)
    }

    const clearPlotSelections = () => {
        plotSelections.value = []
    }

    const removePlotSelection = (index: number) => {
        plotSelections.value.splice(index, 1)
    }

    const selectDataPoints = (points: any[]) => {
        const selection: PlotSelection = {
            type: 'point',
            data: points
        }
        addPlotSelection(selection)
    }

    const selectDataRange = (field: string, min: number, max: number) => {
        const selection: PlotSelection = {
            type: 'range',
            field,
            range: { min, max }
        }
        addPlotSelection(selection)
    }

    const getFilteredDataForColumn = (column: string) => {
        return combinedData.value.filter(row => {
            const v = row[column]
            if (v == null) return false
            const n = typeof v === 'number' ? v : Number(v)
            return Number.isFinite(n)
        })
    }

    const setDataFromDesigns = (rows: any[]) => {
        if (!rows || rows.length === 0) {
            combinedData.value = []
            numericColumns.value = []
            plotColumns.value = []
            return
        }

        const coerced = rows.map((row: any) => {
            const copy: any = { ...row }
            for (const key of Object.keys(copy)) {
                const v = copy[key]
                if (v == null || typeof v === 'number') continue
                const n = Number(v)
                if (Number.isFinite(n)) copy[key] = n
            }
            return copy
        })
        combinedData.value = coerced

        const keys = new Set<string>()
        coerced.forEach(r => Object.keys(r).forEach(k => keys.add(k)))
        numericColumns.value = Array.from(keys).filter(col =>
            coerced.some(r => Number.isFinite(r[col]))
        )
        plotColumns.value = Array.from(keys).filter(col =>
            coerced.some(r => r[col] != null && r[col] !== '')
        ).sort()

        applyScatterColumnsFromData(coerced)
    }

    return {
        selectedRunIds,
        combinedData,
        numericColumns,
        plotColumns,
        scatterXCol,
        scatterYCol,
        scatterColorCol,
        scatterSizeCol,
        loading,
        chartLoading,
        plotSelections,

        filteredRuns,
        availableColumns,
        hasValidData,
        selectedDataPoints,

        setSelectedRuns,
        fetchCombinedData,
        setAxisColumns,
        updatePlots,
        clearData,
        hydrateFromPersistence,
        recordScatterAxisPreferences,

        addPlotSelection,
        clearPlotSelections,
        removePlotSelection,
        selectDataPoints,
        selectDataRange,
        getFilteredDataForColumn,
        setDataFromDesigns,
    }
})
