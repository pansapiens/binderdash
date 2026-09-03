/**
 * Type definitions for Pinia stores
 */

// Base types from webapi.ts
export interface PrimaryScoreStats {
    column: string;
    count: number;
    min: number;
    max: number;
    mean: number;
    median: number;
    stddev: number;
}

export interface Run {
    run_id: string;
    project_id: string;
    method: string;
    path: string;
    metadata: {
        name: string;
        pdb_count: number;
        trajectory_count?: number;
        target_count?: number;
        primary_score_stats?: PrimaryScoreStats;
        results_file: string;
        merged_count?: number;
        total_pdb_count?: number;
    };
}

export interface Design {
    design_id: string;
    project_id: string;
    run_name: string;
    method: string;
    pdb_file?: string;
    run_path: string;
    run_id: string;
    /** Stable DataTable selection key (set by designs store; not from pipeline files). */
    binderRowKey?: string;
    [key: string]: any; // Allow additional properties including dynamic score columns
}

export interface FolderNode {
    key: string;
    name: string;
    path: string;
    has_children: boolean;
    children?: FolderNode[];
    leaf: boolean;
    selectable: boolean;
}

// Store-specific types
export type ColumnDataType = 'text' | 'numeric' | 'boolean' | 'date'

export interface ColumnConfig {
    field: string;
    header: string;
    sortable: boolean;
    filter?: boolean;
    filterType?: string;
    showFilterMenu?: boolean;
    style: string;
    class?: string;
    template?: any;
}

export interface StructureInfo {
    design: Design;
    filename: string;
    pdbPath: string;
}

export interface PlotSelection {
    type: 'point' | 'range' | 'brush';
    data?: any[];
    field?: string;
    range?: { min: number; max: number };
}

export interface Notification {
    id: string;
    severity: 'success' | 'info' | 'warn' | 'error';
    summary: string;
    detail: string;
    life?: number;
}

// Store state interfaces
export interface RunsState {
    runs: Run[];
    loading: boolean;
    error: string | null;
    lastScanned: Date | null;
}

export interface DesignsState {
    designs: Design[];
    selectedDesigns: Design[];
    columns: ColumnConfig[];
    visibleColumns: string[];
    loading: boolean;
    currentNavDesignId: string | null;
}

export interface PlotsState {
    selectedRunIds: string[];
    combinedData: any[];
    numericColumns: string[];
    plotColumns: string[];
    scatterXCol: string | null;
    scatterYCol: string | null;
    scatterColorCol: string | null;
    scatterSizeCol: string | null;
    loading: boolean;
    chartLoading: boolean;
    plotSelections: PlotSelection[];
}

export interface FolderState {
    folders: FolderNode[];
    selectedFolders: string[];
    expandedKeys: Record<string, boolean>;
    scanResults: Run[];
    selectedRuns: Run[];
    loading: boolean;
    scanning: boolean;
}

export interface AppState {
    activeTab: string;
    notifications: Notification[];
    theme: 'light' | 'dark';
    sidebarCollapsed: boolean;
}
