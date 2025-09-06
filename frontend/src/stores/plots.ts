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
            const result = await plotsApi.getCombinedData(runIds)
            combinedData.value = result.data
            numericColumns.value = result.numericColumns

            // Set default columns based on available numeric columns
            if (numericColumns.value.length > 0) {
                // Look for common score columns first
                const xCol = numericColumns.value.find(col =>
                    col.toLowerCase().includes('plddt') || col.toLowerCase().includes('confidence')
                ) || numericColumns.value[0]

                const yCol = numericColumns.value.find(col =>
                    col.toLowerCase().includes('pae') ||
                    col.toLowerCase().includes('iptm') ||
                    col.toLowerCase().includes('interaction')
                ) || (numericColumns.value.length > 1 ? numericColumns.value[1] : numericColumns.value[0])

                scatterXCol.value = xCol
                scatterYCol.value = yCol
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
        return combinedData.value.filter(row =>
            row[column] != null &&
            !isNaN(row[column])
        )
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
