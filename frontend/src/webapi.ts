/**
 * Centralized API client for Binderdash frontend
 * All API calls should go through this module
 */

// Basic type definitions
interface ApiRequestOptions {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
}

interface Folder {
    path: string;
    name: string;
    has_children: boolean;
}

interface TreeResponse {
    folders: Folder[];
}

interface Run {
    run_id: string;
    project_id: string;
    run_type: string;
    path: string;
    metadata: {
        name: string;
        pdb_count: number;
        results_file: string;
    };
}

interface RunsResponse {
    runs: Run[];
}

interface Design {
    design_id: string;
    project_id: string;
    run_name: string;
    run_type: string;
    pae_interaction?: number;
    Average_i_pTM?: number;
    pdb_file?: string;
    run_path: string;
    run_id: string;
    [key: string]: any; // Allow additional properties
}

interface DesignsResponse {
    designs: Design[];
}

interface PlotColumnsResponse {
    numeric_columns: string[];
    defaults: {
        x?: string;
        y?: string;
    };
    total_rows: number;
    run_count?: number;
}

interface ScatterPlotResponse {
    data: any[];
    data_points: number;
    total_rows: number;
    run_count?: number;
}

interface HistogramPlotResponse {
    data: any[];
    data_points: number;
    total_rows: number;
    run_count?: number;
}

interface MessageResponse {
    message: string;
}

const API_BASE = ''

/**
 * Generic fetch wrapper with error handling
 */
async function apiRequest<T = any>(url: string, options: ApiRequestOptions = {}): Promise<T> {
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
     * @param path - Optional path parameter to get children of a specific directory
     * @returns Promise with folder structure
     */
    async getTree(path = ''): Promise<TreeResponse> {
        const url = `${API_BASE}/api/tree${path ? `?path=${encodeURIComponent(path)}` : ''}`
        return await apiRequest<TreeResponse>(url)
    }
}

/**
 * Runs Management APIs
 */
export const runsApi = {
    /**
     * Scan selected folders for valid run directories
     * @param folders - List of folder paths to scan
     * @returns Promise with discovered runs
     */
    async scanRuns(folders: string[]): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs/scan`, {
            method: 'POST',
            body: JSON.stringify({ folders })
        })
    },

    /**
     * List all cached runs
     * @returns Promise with all cached runs
     */
    async listRuns(): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs`)
    },

    /**
     * Get results table data for a specific run
     * @param runId - Unique identifier for the run
     * @returns Promise with table data
     */
    async getRunTable(runId: string): Promise<any> {
        return await apiRequest(`${API_BASE}/api/runs/${runId}/table`)
    },

    /**
     * Get PDB file URL for a specific run and filename
     * @param runId - Unique identifier for the run
     * @param filename - Name of the PDB file
     * @returns URL to the PDB file
     */
    getPdbFileUrl(runId: string, filename: string): string {
        return `${API_BASE}/api/runs/${runId}/files/pdb/${filename}`
    },

    /**
     * Remove a run from the cache
     * @param runId - Unique identifier for the run
     * @returns Promise with success message
     */
    async deleteRun(runId: string): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/runs/${runId}`, {
            method: 'DELETE'
        })
    },

    /**
     * Clear all runs from the cache
     * @returns Promise with success message
     */
    async clearRuns(): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/runs`, {
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
     * @returns Promise with all designs
     */
    async listDesigns(): Promise<DesignsResponse> {
        return await apiRequest<DesignsResponse>(`${API_BASE}/api/designs`)
    },

    /**
     * Clear all designs from the cache
     * @returns Promise with success message
     */
    async clearDesigns(): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/designs`, {
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
     * @param runId - Unique identifier for the run
     * @returns Promise with column information
     */
    async getPlotColumns(runId: string): Promise<PlotColumnsResponse> {
        return await apiRequest<PlotColumnsResponse>(`${API_BASE}/api/runs/${runId}/plots/columns`)
    },

    /**
     * Get available columns for plotting from multiple runs
     * @param runIds - List of run IDs
     * @returns Promise with combined column information
     */
    async getPlotColumnsMultiple(runIds: string[]): Promise<PlotColumnsResponse> {
        return await apiRequest<PlotColumnsResponse>(`${API_BASE}/api/runs/plots/columns`, {
            method: 'POST',
            body: JSON.stringify({ run_ids: runIds })
        })
    },

    /**
     * Get Vega-Lite specification for a scatter plot from a single run
     * @param runId - Unique identifier for the run
     * @param xCol - Column name for X axis
     * @param yCol - Column name for Y axis
     * @returns Promise with scatter plot data
     */
    async getScatterPlot(runId: string, xCol: string, yCol: string): Promise<any> {
        const params = new URLSearchParams({ x_col: xCol, y_col: yCol })
        return await apiRequest(`${API_BASE}/api/runs/${runId}/plots/scatter?${params}`)
    },

    /**
     * Get raw data for a scatter plot from multiple runs
     * @param runIds - List of run IDs
     * @param xCol - Column name for X axis
     * @param yCol - Column name for Y axis
     * @returns Promise with scatter plot data
     */
    async getScatterPlotMultiple(runIds: string[], xCol: string, yCol: string): Promise<ScatterPlotResponse> {
        return await apiRequest<ScatterPlotResponse>(`${API_BASE}/api/runs/plots/scatter`, {
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
     * @param runId - Unique identifier for the run
     * @param col - Column name for the distribution
     * @returns Promise with histogram data
     */
    async getHistogramPlot(runId: string, col: string): Promise<any> {
        const params = new URLSearchParams({ col })
        return await apiRequest(`${API_BASE}/api/runs/${runId}/plots/histogram?${params}`)
    },

    /**
     * Get raw data for a histogram from multiple runs
     * @param runIds - List of run IDs
     * @param col - Column name for the distribution
     * @returns Promise with histogram data
     */
    async getHistogramPlotMultiple(runIds: string[], col: string): Promise<HistogramPlotResponse> {
        return await apiRequest<HistogramPlotResponse>(`${API_BASE}/api/runs/plots/histogram`, {
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
