/**
 * Plots Store
 * Manages plotting data, chart state, and plot interactions
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { plotsApi } from '../webapi'
import type { Run, PlotSelection, PlotsState } from '../types/store'

export const usePlotsStore = defineStore('plots', () => {
    // State
    const selectedRunIds = ref<string[]>([])
    const combinedData = ref<any[]>([])
    const numericColumns = ref<string[]>([])
    const scatterXCol = ref<string | null>(null)
    const scatterYCol = ref<string | null>(null)
    const loading = ref(false)
    const chartLoading = ref(false)
    const plotSelections = ref<PlotSelection[]>([])

    // Getters
    const filteredRuns = computed(() => {
        // This will be enhanced with filtering logic based on available runs
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
        // Return data points that match current plot selections
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

            // Coerce numeric-like strings to numbers for plotting
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

            // Prefer backend defaults; fallback to heuristic with max coverage
            if (cols && cols.numeric_columns?.length) {
                const defX = cols.defaults?.x
                const defY = cols.defaults?.y
                if (defX) scatterXCol.value = defX
                if (defY) scatterYCol.value = defY
            }
            if (!scatterXCol.value || !scatterYCol.value) {
                // Pick columns with most finite values
                const coverage = (col: string) => coerced.reduce((acc: number, r: any) => acc + (Number.isFinite(r[col]) ? 1 : 0), 0)
                const sorted = [...numericColumns.value].sort((a, b) => coverage(b) - coverage(a))
                if (sorted.length > 0) scatterXCol.value = scatterXCol.value || sorted[0]
                if (sorted.length > 1) scatterYCol.value = scatterYCol.value || sorted[1]
            }
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
        // This will trigger plot updates in components
        // The actual plot rendering will be handled by components
    }

    const clearData = () => {
        selectedRunIds.value = []
        combinedData.value = []
        numericColumns.value = []
        scatterXCol.value = null
        scatterYCol.value = null
        plotSelections.value = []
    }

    // Plot interaction methods
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

    return {
        // State
        selectedRunIds,
        combinedData,
        numericColumns,
        scatterXCol,
        scatterYCol,
        loading,
        chartLoading,
        plotSelections,

        // Getters
        filteredRuns,
        availableColumns,
        hasValidData,
        selectedDataPoints,

        // Actions
        setSelectedRuns,
        fetchCombinedData,
        setAxisColumns,
        updatePlots,
        clearData,

        // Plot interactions
        addPlotSelection,
        clearPlotSelections,
        removePlotSelection,
        selectDataPoints,
        selectDataRange,
        getFilteredDataForColumn
    }
})
