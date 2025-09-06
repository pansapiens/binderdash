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
    protocol: string;
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
    protocol: string;
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
 * Plots APIs - Simplified to work with raw data
 */
export const plotsApi = {
    /**
     * Get combined data from multiple runs for plotting
     * @param runIds - List of run IDs
     * @returns Promise with combined data and column information
     */
    async getCombinedData(runIds: string[]): Promise<{ data: any[], columns: string[], numericColumns: string[] }> {
        const allData: any[] = []
        const allColumns = new Set<string>()

        // Fetch data from each run
        for (const runId of runIds) {
            try {
                const runData = await runsApi.getRunTable(runId)
                if (runData && runData.data) {
                    // Add run_id to each row for identification
                    const enrichedData = runData.data.map((row: any) => ({
                        ...row,
                        run_id: runId
                    }))
                    allData.push(...enrichedData)

                    // Collect all column names
                    runData.columns.forEach((col: string) => allColumns.add(col))
                }
            } catch (error) {
                console.warn(`Failed to load data for run ${runId}:`, error)
            }
        }

        // Determine numeric columns
        const numericColumns = Array.from(allColumns).filter(col => {
            if (allData.length === 0) return false
            // Check if column has numeric values (excluding null/undefined)
            return allData.some(row =>
                row[col] != null &&
                typeof row[col] === 'number' &&
                !isNaN(row[col])
            )
        })

        return {
            data: allData,
            columns: Array.from(allColumns),
            numericColumns
        }
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
