/**
 * Runs Store
 * Manages run discovery, caching, and metadata
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { runsApi } from '../webapi'
import type { Run, RunsState } from '../types/store'

export const useRunsStore = defineStore('runs', () => {
    // State
    const runs = ref<Run[]>([])
    const loading = ref(false)
    const error = ref<string | null>(null)
    const lastScanned = ref<Date | null>(null)

    // Getters
    const availableRuns = computed(() => runs.value)

    const runsByProject = computed(() => (projectId: string) =>
        runs.value.filter(run => run.project_id === projectId)
    )

    const runsByProtocol = computed(() => (protocol: string) =>
        runs.value.filter(run => run.protocol === protocol)
    )

    const totalRuns = computed(() => runs.value.length)

    // Actions
    const fetchRuns = async () => {
        loading.value = true
        error.value = null
        try {
            const data = await runsApi.listRuns()
            runs.value = data.runs
        } catch (err) {
            error.value = err instanceof Error ? err.message : 'Failed to fetch runs'
            console.error('Error fetching runs:', err)
        } finally {
            loading.value = false
        }
    }

    const scanFolders = async (folders: string[]) => {
        loading.value = true
        error.value = null
        try {
            const data = await runsApi.scanRuns(folders)
            // Add new runs to existing ones (avoid duplicates)
            const existingRunIds = new Set(runs.value.map(run => run.run_id))
            const newRuns = data.runs.filter(run => !existingRunIds.has(run.run_id))
            runs.value.push(...newRuns)
            lastScanned.value = new Date()
            return data.runs
        } catch (err) {
            error.value = err instanceof Error ? err.message : 'Failed to scan folders'
            console.error('Error scanning folders:', err)
            throw err
        } finally {
            loading.value = false
        }
    }

    const deleteRun = async (runId: string) => {
        try {
            await runsApi.deleteRun(runId)
            runs.value = runs.value.filter(run => run.run_id !== runId)
        } catch (err) {
            error.value = err instanceof Error ? err.message : 'Failed to delete run'
            console.error('Error deleting run:', err)
            throw err
        }
    }

    const clearRuns = async () => {
        try {
            await runsApi.clearRuns()
            runs.value = []
            lastScanned.value = null
        } catch (err) {
            error.value = err instanceof Error ? err.message : 'Failed to clear runs'
            console.error('Error clearing runs:', err)
            throw err
        }
    }

    const refreshRuns = async () => {
        await fetchRuns()
    }

    const getRunById = (runId: string) => {
        return runs.value.find(run => run.run_id === runId)
    }

    return {
        // State
        runs,
        loading,
        error,
        lastScanned,

        // Getters
        availableRuns,
        runsByProject,
        runsByProtocol,
        totalRuns,

        // Actions
        fetchRuns,
        scanFolders,
        deleteRun,
        clearRuns,
        refreshRuns,
        getRunById
    }
})
