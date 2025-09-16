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
    async scanRuns(folders: string[]): Promise<RunsResponse> {
        return await apiRequest<RunsResponse>(`${API_BASE}/api/runs/scan`, {
            method: 'POST',
            body: JSON.stringify({ folders }),
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
     * Get PDB file URL for a specific run and filename
     * @param runId - Unique identifier for the run
     * @param filename - Name of the PDB file
     * @returns URL to the PDB file (authentication via cookies)
     */
    getPdbFileUrl(runId: string, filename: string): string {
        return `${API_BASE}/api/runs/${runId}/files/pdb/${filename}`
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
