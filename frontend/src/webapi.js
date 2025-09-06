/**
 * Centralized API client for Binderdash frontend
 * All API calls should go through this module
 */

const API_BASE = ''

/**
 * Generic fetch wrapper with error handling
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        return await response.json()
    } catch (error) {
        console.error(`API request failed for ${url}:`, error)
        throw error
    }
}

/**
 * Tree/Folder Browser APIs
 */
export const treeApi = {
    /**
     * Get folder structure for the file browser
     * @param {string} path - Optional path parameter to get children of a specific directory
     * @returns {Promise<{folders: Array}>}
     */
    async getTree(path = '') {
        const url = `${API_BASE}/api/tree${path ? `?path=${encodeURIComponent(path)}` : ''}`
        return await apiRequest(url)
    }
}

/**
 * Runs Management APIs
 */
export const runsApi = {
    /**
     * Scan selected folders for valid run directories
     * @param {Array<string>} folders - List of folder paths to scan
     * @returns {Promise<{runs: Array}>}
     */
    async scanRuns(folders) {
        return await apiRequest(`${API_BASE}/api/runs/scan`, {
            method: 'POST',
            body: JSON.stringify({ folders })
        })
    },

    /**
     * List all cached runs
     * @returns {Promise<{runs: Array}>}
     */
    async listRuns() {
        return await apiRequest(`${API_BASE}/api/runs`)
    },

    /**
     * Get results table data for a specific run
     * @param {string} runId - Unique identifier for the run
     * @returns {Promise<{columns: Array, data: Array, total_rows: number}>}
     */
    async getRunTable(runId) {
        return await apiRequest(`${API_BASE}/api/runs/${runId}/table`)
    },

    /**
     * Get PDB file URL for a specific run and filename
     * @param {string} runId - Unique identifier for the run
     * @param {string} filename - Name of the PDB file
     * @returns {string} - URL to the PDB file
     */
    getPdbFileUrl(runId, filename) {
        return `${API_BASE}/api/runs/${runId}/files/pdb/${filename}`
    },

    /**
     * Remove a run from the cache
     * @param {string} runId - Unique identifier for the run
     * @returns {Promise<{message: string}>}
     */
    async deleteRun(runId) {
        return await apiRequest(`${API_BASE}/api/runs/${runId}`, {
            method: 'DELETE'
        })
    },

    /**
     * Clear all runs from the cache
     * @returns {Promise<{message: string}>}
     */
    async clearRuns() {
        return await apiRequest(`${API_BASE}/api/runs`, {
            method: 'DELETE'
        })
    }
}

/**
 * Designs Management APIs
 */
export const designsApi = {
    /**
     * List all designs from all cached runs
     * @returns {Promise<{designs: Array}>}
     */
    async listDesigns() {
        return await apiRequest(`${API_BASE}/api/designs`)
    },

    /**
     * Clear all designs from the cache
     * @returns {Promise<{message: string}>}
     */
    async clearDesigns() {
        return await apiRequest(`${API_BASE}/api/designs`, {
            method: 'DELETE'
        })
    }
}

/**
 * Plots APIs
 */
export const plotsApi = {
    /**
     * Get available columns for plotting from a specific run
     * @param {string} runId - Unique identifier for the run
     * @returns {Promise<{numeric_columns: Array, defaults: Object, total_rows: number}>}
     */
    async getPlotColumns(runId) {
        return await apiRequest(`${API_BASE}/api/runs/${runId}/plots/columns`)
    },

    /**
     * Get available columns for plotting from multiple runs
     * @param {Array<string>} runIds - List of run IDs
     * @returns {Promise<{numeric_columns: Array, defaults: Object, total_rows: number, run_count: number}>}
     */
    async getPlotColumnsMultiple(runIds) {
        return await apiRequest(`${API_BASE}/api/runs/plots/columns`, {
            method: 'POST',
            body: JSON.stringify({ run_ids: runIds })
        })
    },

    /**
     * Get Vega-Lite specification for a scatter plot from a single run
     * @param {string} runId - Unique identifier for the run
     * @param {string} xCol - Column name for X axis
     * @param {string} yCol - Column name for Y axis
     * @returns {Promise<{spec: Object, data_points: number, total_rows: number}>}
     */
    async getScatterPlot(runId, xCol, yCol) {
        const params = new URLSearchParams({ x_col: xCol, y_col: yCol })
        return await apiRequest(`${API_BASE}/api/runs/${runId}/plots/scatter?${params}`)
    },

    /**
     * Get raw data for a scatter plot from multiple runs
     * @param {Array<string>} runIds - List of run IDs
     * @param {string} xCol - Column name for X axis
     * @param {string} yCol - Column name for Y axis
     * @returns {Promise<{data: Array, data_points: number, total_rows: number, run_count: number}>}
     */
    async getScatterPlotMultiple(runIds, xCol, yCol) {
        return await apiRequest(`${API_BASE}/api/runs/plots/scatter`, {
            method: 'POST',
            body: JSON.stringify({
                run_ids: runIds,
                x_col: xCol,
                y_col: yCol
            })
        })
    },

    /**
     * Get Vega-Lite specification for a histogram from a single run
     * @param {string} runId - Unique identifier for the run
     * @param {string} col - Column name for the distribution
     * @returns {Promise<{spec: Object, data_points: number, total_rows: number}>}
     */
    async getHistogramPlot(runId, col) {
        const params = new URLSearchParams({ col })
        return await apiRequest(`${API_BASE}/api/runs/${runId}/plots/histogram?${params}`)
    },

    /**
     * Get raw data for a histogram from multiple runs
     * @param {Array<string>} runIds - List of run IDs
     * @param {string} col - Column name for the distribution
     * @returns {Promise<{data: Array, data_points: number, total_rows: number, run_count: number}>}
     */
    async getHistogramPlotMultiple(runIds, col) {
        return await apiRequest(`${API_BASE}/api/runs/plots/histogram`, {
            method: 'POST',
            body: JSON.stringify({
                run_ids: runIds,
                col
            })
        })
    }
}

/**
 * Default export with all API modules
 */
export default {
    tree: treeApi,
    runs: runsApi,
    designs: designsApi,
    plots: plotsApi
}
