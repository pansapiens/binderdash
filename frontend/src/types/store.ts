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
export interface FilterState {
    global: { value: any; matchMode: string };
    design_id: { value: any; matchMode: string };
    project_id: { value: any; matchMode: string };
    run_name: { value: any; matchMode: string };
    method: { value: any; matchMode: string };
    score_min: { value: any; matchMode: string };
    score_max: { value: any; matchMode: string };
    length_min: { value: any; matchMode: string };
    length_max: { value: any; matchMode: string };
    target_sequence: { value: any; matchMode: string };
}

export type ColumnDataType = 'text' | 'numeric' | 'boolean' | 'date'

export interface CustomFilter {
    id: string
    column: string
    operator: string
    value: any
    /** When false, the rule does not filter the table and structure cards for this column are greyed out (synced with sidebar toggles). */
    enabled?: boolean
}

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
    filters: FilterState;
    columns: ColumnConfig[];
    visibleColumns: string[];
    loading: boolean;
    currentNavDesignId: string | null;
}

export interface PlotsState {
    selectedRunIds: string[];
    combinedData: any[];
    numericColumns: string[];
    scatterXCol: string | null;
    scatterYCol: string | null;
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
