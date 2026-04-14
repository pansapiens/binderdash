/**
 * Centralized API client for Binderdash frontend
 * All API calls should go through this module
 */

// Basic type definitions
interface ApiRequestOptions {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    requireAuth?: boolean;
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
    method: string;
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

export interface IngestPreviewReingestItem {
    run_group_key: string
    display_name: string
}

export interface IngestPreviewResponse {
    reingest: IngestPreviewReingestItem[]
}

interface Design {
    design_id: string;
    project_id: string;
    run_name: string;
    method: string;
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

export interface TagPlacementItem {
    run_id: string
    design_id: string
    pdb_file?: string | null
    source_path?: string | null
}

export interface TagPlacementRequest {
    designs: TagPlacementItem[]
    binder_chain?: string
    /** Comma- or space-separated chain IDs for target distance / contact calcs. */
    target_chains?: string | null
    distant_from?: string | null
    sasa_probe_radius?: number
    sasa_n_points?: number
    sasa_threshold?: number
    more_distant_threshold?: number
    /** When false, server skips rebuilding designs cache (use refreshDesignsCache once after a batch). */
    refresh_cache_after?: boolean
    /** When true, only return rows found in SQLite tag-metrics cache (no heavy compute). */
    cache_only?: boolean
    /** When true, skip cache reads and recompute metrics (still writes cache when persistence enabled). */
    ignore_cache?: boolean
}

export interface TagPlacementResultRow {
    run_id: string
    design_id: string
    tag?: string | null
    error?: string | null
}

export interface TagPlacementResponse {
    results: TagPlacementResultRow[]
}

export interface TagMetricsRow {
    run_id: string
    design_id: string
    pdb_file?: string | null
    sequence?: string | null
    n_aa_type?: string | null
    c_aa_type?: string | null
    n_sasa?: number | null
    c_sasa?: number | null
    n_percent_sasa?: number | null
    c_percent_sasa?: number | null
    n_percent_buried?: number | null
    c_percent_buried?: number | null
    n_c_dist?: number | null
    n_dist_target?: number | null
    c_dist_target?: number | null
    n_target_contacts?: boolean | null
    c_target_contacts?: boolean | null
    predicted_tag?: string | null
    error?: string | null
}

export interface TagMetricsResponse {
    results: TagMetricsRow[]
}

export interface SequenceExtractItem {
    run_id: string
    design_id: string
    pdb_file: string
    chain?: string
    source_path?: string | null
}

export interface SequenceExtractResultRow {
    run_id: string
    design_id: string
    sequence?: string | null
    error?: string | null
}

export interface SequenceExtractResponse {
    results: SequenceExtractResultRow[]
}

interface MessageResponse {
    message: string;
}

const API_BASE = ''

// CSRF token management
let csrfToken: string | null = null

export const setCsrfToken = (token: string | null) => {
    csrfToken = token
}

export const getCsrfToken = (): string | null => {
    return csrfToken
}

/**
 * Generic fetch wrapper with error handling and CSRF protection
 */
async function apiRequest<T = any>(url: string, options: ApiRequestOptions = {}): Promise<T> {
    try {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...options.headers
        }

        // Add CSRF token for state-changing operations
        if (options.requireAuth !== false && csrfToken && options.method && options.method !== 'GET') {
            headers['X-CSRF-Token'] = csrfToken
        }

        const response = await fetch(url, {
            headers,
            credentials: 'include', // Include cookies for authentication
            ...options
        })

        if (!response.ok) {
            // Handle authentication errors
            if (response.status === 401) {
                // Clear auth store state if available
                try {
                    const { useAuthStore } = await import('./stores/auth')
                    const authStore = useAuthStore()
                    authStore.clearAuth()
                } catch (error) {
                    // Auth store might not be available yet, ignore
                }
                throw new Error('Authentication required')
            }

            // Handle forbidden errors (403) - check if user is authenticated
            if (response.status === 403) {
                try {
                    const { useAuthStore } = await import('./stores/auth')
                    const authStore = useAuthStore()

                    // If auth is enabled and user is not authenticated, logout and show login page
                    if (authStore.isAuthEnabled && !authStore.isAuthenticated) {
                        // User is not authenticated, logout and show login page
                        await authStore.logout()
                        throw new Error('Authentication required')
                    }
                } catch (error) {
                    // If we can't check auth status or logout fails, just throw the original error
                    if (error instanceof Error && error.message === 'Authentication required') {
                        throw error
                    }
                }
                throw new Error(`Access forbidden: ${response.status}`)
            }

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
    async scanRuns(
        folders: string[],
        options?: { forceRescanOfIngested?: boolean }
    ): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs/scan`, {
            method: 'POST',
            body: JSON.stringify({
                folders,
                force_rescan_of_ingested: options?.forceRescanOfIngested ?? false
            }),
            requireAuth: true
        })
    },

    /**
     * List runs in the payload that already exist in the database (re-ingest will reset tag/good).
     */
    async ingestPreview(
        runs: Array<Record<string, unknown>>
    ): Promise<IngestPreviewResponse> {
        return await apiRequest<IngestPreviewResponse>(
            `${API_BASE}/api/runs/ingest-preview`,
            {
                method: 'POST',
                body: JSON.stringify({ runs }),
                requireAuth: true
            }
        )
    },

    /**
     * Persist discovered runs to the database (stable run_id per run_group_key).
     */
    async ingestRuns(runs: Array<Record<string, unknown>>): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs/ingest`, {
            method: 'POST',
            body: JSON.stringify({ runs }),
            requireAuth: true
        })
    },

    /**
     * List all cached runs
     * @returns Promise with all cached runs
     */
    async listRuns(): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs`, { requireAuth: true })
    },

    /**
     * Get results table data for a specific run
     * @param runId - Unique identifier for the run
     * @returns Promise with table data
     */
    async getRunTable(runId: string): Promise<any> {
        return await apiRequest(`${API_BASE}/api/runs/${runId}/table`, { requireAuth: true })
    },

    /**
     * Get structure file URL for a specific run and filename.
     * Supports both PDB (.pdb) and mmCIF (.cif) files.
     * @param runId - Unique identifier for the run
     * @param filename - Name of the structure file
     * @returns URL to the structure file (authentication via cookies)
     */
    getStructureFileUrl(runId: string, filename: string): string {
        const enc = encodeURIComponent(filename)
        return `${API_BASE}/api/runs/${runId}/files/structure/${enc}`
    },
    /**
     * Backwards-compatible alias for structure URLs.
     */
    getPdbFileUrl(runId: string, filename: string): string {
        return this.getStructureFileUrl(runId, filename)
    },

    /**
     * List input / target structure files discovered from run params.
     */
    async getInputTargets(runId: string): Promise<{ targets: Array<{ id: string; label: string }> }> {
        return await apiRequest(`${API_BASE}/api/runs/${runId}/input-targets`, { requireAuth: true })
    },

    /**
     * Build URL for TM-aligned reference structure (PDB) overlaid on a design file.
     */
    getAlignedReferenceUrl(
        runId: string,
        alignFilename: string,
        options: {
            mode: 'manual' | 'input_target'
            source?: string
            inputTargetId?: string
            referenceChains?: string
        }
    ): string {
        const params = new URLSearchParams()
        params.set('align_filename', alignFilename)
        params.set('mode', options.mode)
        if (options.mode === 'manual' && options.source != null && options.source !== '') {
            params.set('source', options.source)
        }
        if (options.mode === 'input_target' && options.inputTargetId != null) {
            params.set('input_target_id', options.inputTargetId)
        }
        const rc = options.referenceChains?.trim()
        if (rc) params.set('reference_chains', rc)
        return `${API_BASE}/api/runs/${runId}/files/reference?${params.toString()}`
    },

    /**
     * Download a tar archive of multiple PDB files.
     * @param items - Array of { run_id, filename }
     * @returns Blob of the tar file
     */
    async downloadPdbsTar(items: Array<{ run_id: string; filename: string }>): Promise<Blob> {
        const url = `${API_BASE}/api/pdbs/tar`
        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        }
        // Attach CSRF for POST requests if available
        try {
            const { getCsrfToken } = await import('./webapi')
            const token = getCsrfToken()
            if (token) headers['X-CSRF-Token'] = token
        } catch (_) {
            // ignore
        }

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify({ items }),
            credentials: 'include'
        })

        if (!response.ok) {
            if (response.status === 401) throw new Error('Authentication required')
            throw new Error(`HTTP error! status: ${response.status}`)
        }

        return await response.blob()
    },

    /**
     * Remove a run from the cache
     * @param runId - Unique identifier for the run
     * @returns Promise with success message
     */
    async deleteRun(runId: string): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/runs/${runId}`, {
            method: 'DELETE',
            requireAuth: true
        })
    },

    /**
     * Clear all runs from the cache
     * @returns Promise with success message
     */
    async clearRuns(): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/runs`, {
            method: 'DELETE',
            requireAuth: true
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
        return await apiRequest<DesignsResponse>(`${API_BASE}/api/designs`, { requireAuth: true })
    },

    /**
     * Clear all designs from the cache
     * @returns Promise with success message
     */
    async clearDesigns(): Promise<MessageResponse> {
        return await apiRequest<MessageResponse>(`${API_BASE}/api/designs`, {
            method: 'DELETE',
            requireAuth: true
        })
    },

    async patchDesignGood(payload: {
        run_id: string
        design_id: string
        good: boolean | null
        source_path?: string
    }): Promise<{ ok: boolean }> {
        return await apiRequest<{ ok: boolean }>(`${API_BASE}/api/designs/good`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
            requireAuth: true
        })
    },

    async patchDesignTag(payload: {
        run_id: string
        design_id: string
        tag: 'N' | 'C' | null
        source_path?: string
    }): Promise<{ ok: boolean }> {
        return await apiRequest<{ ok: boolean }>(`${API_BASE}/api/designs/tag`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
            requireAuth: true
        })
    },

    async postTagPlacement(payload: TagPlacementRequest): Promise<TagPlacementResponse> {
        return await apiRequest<TagPlacementResponse>(`${API_BASE}/api/designs/tag-placement`, {
            method: 'POST',
            body: JSON.stringify(payload),
            requireAuth: true
        })
    },

    async postTagMetrics(payload: TagPlacementRequest): Promise<TagMetricsResponse> {
        return await apiRequest<TagMetricsResponse>(`${API_BASE}/api/designs/tag-metrics`, {
            method: 'POST',
            body: JSON.stringify({ ...payload, refresh_cache_after: false }),
            requireAuth: true
        })
    },

    async refreshDesignsCache(): Promise<{ ok: boolean }> {
        return await apiRequest<{ ok: boolean }>(`${API_BASE}/api/designs/refresh-cache`, {
            method: 'POST',
            body: '{}',
            requireAuth: true
        })
    },

    async extractSequences(payload: {
        designs: SequenceExtractItem[]
        refresh_cache_after?: boolean
    }): Promise<SequenceExtractResponse> {
        return await apiRequest<SequenceExtractResponse>(`${API_BASE}/api/designs/sequences`, {
            method: 'POST',
            body: JSON.stringify(payload),
            requireAuth: true
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
                    // TODO: Should this be done in the backend instead ?
                    const enrichedData = runData.data.map((row: any, idx: number) => {
                        // Derive a stable design identifier for selections/tooltips
                        const possibleId =
                            row.Design ?? row.design ?? row.description ?? row.name ?? row.id ?? null
                        const design_id = possibleId != null && String(possibleId).length > 0
                            ? String(possibleId)
                            : `${runId}__row_${idx}`
                        return {
                            ...row,
                            run_id: runId,
                            design_id
                        }
                    })
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
            return allData.some(row => {
                const v = row[col]
                if (v == null) return false
                const n = typeof v === 'number' ? v : Number(v)
                return Number.isFinite(n)
            })
        })

        return {
            data: allData,
            columns: Array.from(allColumns),
            numericColumns
        }
    }

    ,
    /**
     * Ask backend for numeric columns and sensible defaults across runs
     */
    async getPlotColumns(runIds: string[]): Promise<{ numeric_columns: string[], defaults: { x: string, y: string } }> {
        const url = `${API_BASE}/api/runs/plots/columns`
        return await apiRequest<{ numeric_columns: string[], defaults: { x: string, y: string } }>(url, {
            method: 'POST',
            body: JSON.stringify({ run_ids: runIds }),
            requireAuth: true
        })
    }
}

/**
 * Authentication APIs
 */
export const authApi = {
    /**
     * Login with username and password
     * @param username - Username
     * @param password - Password
     * @returns Promise with login response including CSRF token
     */
    async login(username: string, password: string): Promise<{ message: string, user: { username: string }, csrf_token: string }> {
        const response = await apiRequest<{ message: string, user: { username: string }, csrf_token: string }>(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            body: JSON.stringify({ username, password }),
            requireAuth: false
        })

        // Store CSRF token for future requests
        setCsrfToken(response.csrf_token)

        return response
    },

    /**
     * Logout user
     * @returns Promise with logout message
     */
    async logout(): Promise<{ message: string }> {
        const response = await apiRequest<{ message: string }>(`${API_BASE}/api/auth/logout`, {
            method: 'POST',
            requireAuth: true
        })

        // Clear CSRF token
        setCsrfToken(null)

        return response
    },

    /**
     * Get current user information
     * @returns Promise with user data
     */
    async getMe(): Promise<{ username: string }> {
        return await apiRequest<{ username: string }>(`${API_BASE}/api/auth/me`, { requireAuth: true })
    },

    /**
     * Check authentication status
     * @returns Promise with auth status
     */
    async getStatus(): Promise<{
        auth_disabled: boolean
    }> {
        return await apiRequest<{
            auth_disabled: boolean
        }>(`${API_BASE}/api/auth/status`, { requireAuth: false })
    }
}

/**
 * Default export with all API modules
 */
export default {
    tree: treeApi,
    runs: runsApi,
    designs: designsApi,
    plots: plotsApi,
    auth: authApi
}
