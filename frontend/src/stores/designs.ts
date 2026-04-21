/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { DesignsListQueryDTO } from '../webapi'
import { designsApi } from '../webapi'
import { PERSISTENCE_KEYS } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'
import type { Design, FilterState, ColumnConfig, StructureInfo, CustomFilter } from '../types/store'
import {
    scoreFieldsForGlobalFilter,
    getStructureFilenameFromDesign,
    designHasStructureFile,
    defaultVisibleScoreColumnFields,
} from '../config/pipelineDisplay'

const GLOBAL_FILTER_SCORE_FIELDS = new Set(scoreFieldsForGlobalFilter())

export const useDesignsStore = defineStore('designs', () => {
    // State
    const pageRows = ref<Design[]>([])
    const totalRows = ref(0)
    const pageIndex = ref(0)
    const pageSize = ref(10)
    const allMatching = ref<Design[] | null>(null)
    const allMatchingLoading = ref(false)
    const selectedDesigns = ref<Design[]>([])
    const selectedRunIds = ref<string[]>([])
    const loadedRunIdsSignature = ref<string>('')
    let fetchSeq = 0
    let selectionDebounceTimer: ReturnType<typeof setTimeout> | null = null
    let queryDebounceTimer: ReturnType<typeof setTimeout> | null = null
    const SELECTION_DEBOUNCE_MS = 200
    const QUERY_DEBOUNCE_MS = 250

    function runIdsSignature(runIds: string[]): string {
        return [...runIds].sort().join('|')
    }
    const pendingSelectedDesignKeys = ref<Array<{ run_id: string; design_id: string }>>([])
    const pendingCurrentNavDesignId = ref<string | null>(null)
    const designsPersistenceHydrated = ref(false)
    const filters = ref<FilterState>({
        global: { value: null, matchMode: 'contains' },
        design_id: { value: null, matchMode: 'contains' },
        project_id: { value: null, matchMode: 'contains' },
        run_name: { value: null, matchMode: 'contains' },
        method: { value: null, matchMode: 'equals' },
        score_min: { value: null, matchMode: 'gte' },
        score_max: { value: null, matchMode: 'lte' },
        length_min: { value: null, matchMode: 'gte' },
        length_max: { value: null, matchMode: 'lte' },
        target_sequence: { value: null, matchMode: 'regex' }
    })
    const bestMpnnOnly = ref(false)
    const customFilters = ref<CustomFilter[]>([])

    const persistCustomFiltersToStorage = () => {
        if (!designsPersistenceHydrated.value) return
        void kvSet(PERSISTENCE_KEYS.designsCustomFilters, { filters: customFilters.value })
    }

    watch(customFilters, () => persistCustomFiltersToStorage(), { deep: true })

    watch(
        [filters, customFilters, bestMpnnOnly],
        () => scheduleQueryRefresh(),
        { deep: true }
    )

    const isFieldReferencedByCustomFilter = (field: string): boolean => {
        const t = field.trim()
        if (!t) return false
        return customFilters.value.some(f => f.column?.trim() === t)
    }

    /** True when every custom filter row targeting this column is enabled (undefined counts as enabled). */
    const allFiltersForFieldEnabled = (field: string): boolean => {
        const t = field.trim()
        if (!t) return true
        const relevant = customFilters.value.filter(f => f.column?.trim() === t)
        if (relevant.length === 0) return true
        return relevant.every(f => f.enabled !== false)
    }

    const setAllCustomFiltersEnabledForField = (field: string, enabled: boolean) => {
        const t = field.trim()
        if (!t) return
        customFilters.value = customFilters.value.map(f =>
            f.column?.trim() === t ? { ...f, enabled } : f
        )
    }

    const columns = ref<ColumnConfig[]>([])
    const visibleColumns = ref<string[]>(['design_id', 'project_id', 'run_name', 'method', 'Length'])
    const loading = ref(false)
    const currentNavDesignId = ref<string | null>(null)
    const tableSortField = ref<string | undefined>(undefined)
    const tableSortOrder = ref<number | undefined>(undefined)

    const columnsForSelectedRuns = computed((): ColumnConfig[] =>
        selectedRunIds.value.length === 0 ? [] : columns.value
    )

    watch(
        columnsForSelectedRuns,
        (cols) => {
            const allowed = new Set(cols.map(c => c.field))
            if (allowed.size === 0) return
            visibleColumns.value = visibleColumns.value.filter(f => allowed.has(f))
        },
        { deep: true }
    )

    const persistViewStateToStorage = () => {
        if (!designsPersistenceHydrated.value) return
        void kvSet(PERSISTENCE_KEYS.designsViewState, {
            selectedRunIds: selectedRunIds.value,
            selectedDesigns: selectedDesigns.value.map((d) => ({
                run_id: d.run_id,
                design_id: d.design_id
            })),
            currentNavDesignId: currentNavDesignId.value
        })
    }

    const hydrateFromPersistence = async () => {
        try {
            const filtersPayload = await kvGet<{ filters?: unknown[] }>(PERSISTENCE_KEYS.designsCustomFilters)
            if (filtersPayload && Array.isArray(filtersPayload.filters)) {
                customFilters.value = filtersPayload.filters.map((f: any) => ({
                    id: typeof f?.id === 'string' ? f.id : crypto.randomUUID(),
                    column: typeof f?.column === 'string' ? f.column : '',
                    operator: typeof f?.operator === 'string' ? f.operator : 'eq',
                    value: f?.value,
                    enabled: f?.enabled !== false
                }))
            }

            const viewPayload = await kvGet<{
                selectedRunIds?: unknown
                selectedDesigns?: unknown
                currentNavDesignId?: unknown
            }>(PERSISTENCE_KEYS.designsViewState)
            if (viewPayload) {
                if (Array.isArray(viewPayload.selectedRunIds)) {
                    selectedRunIds.value = viewPayload.selectedRunIds
                        .map((v) => String(v))
                        .filter((v) => v.length > 0)
                }
                if (Array.isArray(viewPayload.selectedDesigns)) {
                    pendingSelectedDesignKeys.value = viewPayload.selectedDesigns
                        .map((row) => {
                            const runId = (row as any)?.run_id
                            const designId = (row as any)?.design_id
                            if (runId == null || designId == null) return null
                            return { run_id: String(runId), design_id: String(designId) }
                        })
                        .filter((row): row is { run_id: string; design_id: string } => row !== null)
                }
                if (viewPayload.currentNavDesignId != null && viewPayload.currentNavDesignId !== '') {
                    pendingCurrentNavDesignId.value = String(viewPayload.currentNavDesignId)
                }
            }
        } catch (e) {
            console.warn('Failed to hydrate designs persistence from IndexedDB', e)
        } finally {
            designsPersistenceHydrated.value = true
        }
    }

    const selectedDesignKeysSignature = computed(() =>
        selectedDesigns.value
            .map((d) => `${d.run_id}::${d.design_id}`)
            .sort()
            .join('|')
    )

    const operatorOptionsNumeric = [
        { label: '<=', value: 'lte' },
        { label: '>=', value: 'gte' },
        { label: '==', value: 'eq' },
        { label: '!=', value: 'ne' },
        { label: '>', value: 'gt' },
        { label: '<', value: 'lt' },
        { label: 'is empty', value: 'is_empty' },
        { label: 'is not empty', value: 'is_not_empty' }
    ]

    const operatorOptionsText = [
        { label: '==', value: 'eq' },
        { label: '!=', value: 'ne' },
        { label: 'contains', value: 'contains' },
        { label: 'does not contain', value: 'not_contains' },
        { label: 'starts with', value: 'starts_with' },
        { label: 'ends with', value: 'ends_with' },
        { label: 'is empty', value: 'is_empty' },
        { label: 'is not empty', value: 'is_not_empty' }
    ]

    const operatorOptionsBoolean = [
        { label: '==', value: 'eq' },
        { label: 'is empty', value: 'is_empty' },
        { label: 'is not empty', value: 'is_not_empty' }
    ]

    function getColumnFilterType(field: string): string {
        const fromSelected = columnsForSelectedRuns.value.find(c => c.field === field)
        if (fromSelected) return fromSelected.filterType ?? 'text'
        return columns.value.find(c => c.field === field)?.filterType ?? 'text'
    }

    function getOperatorsForColumn(field: string) {
        if (!field) return operatorOptionsText
        const t = getColumnFilterType(field)
        if (t === 'numeric') return operatorOptionsNumeric
        if (t === 'boolean') return operatorOptionsBoolean
        return operatorOptionsText
    }

    function cellIsEmptyForFilter(raw: unknown): boolean {
        return raw == null || raw === ''
    }

    function toNumericForFilter(raw: unknown): number | null {
        if (raw == null || raw === '') return null
        if (typeof raw === 'number' && !Number.isNaN(raw)) return raw
        const n = Number(raw)
        return Number.isNaN(n) ? null : n
    }

    function normalizeBooleanCell(raw: unknown): 'true' | 'false' | 'empty' {
        if (raw == null || raw === '') return 'empty'
        if (raw === true || raw === 1 || raw === '1') return 'true'
        if (typeof raw === 'string' && raw.toLowerCase() === 'true') return 'true'
        if (raw === false || raw === 0 || raw === '0') return 'false'
        if (typeof raw === 'string' && raw.toLowerCase() === 'false') return 'false'
        return 'empty'
    }

    function passesCustomFilter(design: Design, filter: CustomFilter): boolean {
        if (!filter.column) return true
        const colType = getColumnFilterType(filter.column)
        const op = filter.operator
        const raw = (design as Record<string, unknown>)[filter.column]

        if (op === 'is_empty') return cellIsEmptyForFilter(raw)
        if (op === 'is_not_empty') return !cellIsEmptyForFilter(raw)

        if (colType === 'boolean') {
            if (op !== 'eq') return true
            if (filter.value === undefined) return true
            const cell = normalizeBooleanCell(raw)
            if (filter.value === null) return cell === 'empty'
            if (filter.value === true) return cell === 'true'
            if (filter.value === false) return cell === 'false'
            return true
        }

        if (colType === 'numeric') {
            const nRow = toNumericForFilter(raw)
            if (nRow === null) return false
            if (filter.value === null || filter.value === undefined) return true
            const nFilter = toNumericForFilter(filter.value)
            if (nFilter === null) return true
            switch (op) {
                case 'eq':
                    return nRow === nFilter
                case 'ne':
                    return nRow !== nFilter
                case 'gt':
                    return nRow > nFilter
                case 'gte':
                    return nRow >= nFilter
                case 'lt':
                    return nRow < nFilter
                case 'lte':
                    return nRow <= nFilter
                default:
                    return true
            }
        }

        const rowStr = raw == null ? '' : String(raw)
        if (op === 'eq') {
            if (filter.value === null || filter.value === undefined) return true
            return rowStr === String(filter.value)
        }
        if (op === 'ne') {
            if (filter.value === null || filter.value === undefined) return true
            return rowStr !== String(filter.value)
        }
        if (cellIsEmptyForFilter(raw)) return false
        if (filter.value === null || filter.value === undefined) return true
        const fv = String(filter.value)
        switch (op) {
            case 'contains':
                return rowStr.toLowerCase().includes(fv.toLowerCase())
            case 'not_contains':
                return !rowStr.toLowerCase().includes(fv.toLowerCase())
            case 'starts_with':
                return rowStr.toLowerCase().startsWith(fv.toLowerCase())
            case 'ends_with':
                return rowStr.toLowerCase().endsWith(fv.toLowerCase())
            default:
                return true
        }
    }

    const addCustomFilter = () => {
        customFilters.value.push({
            id: crypto.randomUUID(),
            column: '',
            operator: 'eq',
            value: null,
            enabled: true
        })
    }

    const removeCustomFilter = (id: string) => {
        customFilters.value = customFilters.value.filter(f => f.id !== id)
    }

    const updateCustomFilter = (id: string, patch: Partial<Omit<CustomFilter, 'id'>>) => {
        const idx = customFilters.value.findIndex(f => f.id === id)
        if (idx < 0) return
        customFilters.value[idx] = { ...customFilters.value[idx], ...patch }
    }

    /** Current table page (server-filtered). Kept as `filteredDesigns` for template compatibility. */
    const filteredDesigns = computed(() => pageRows.value)

    /** Full matching row set when loaded; else current page. Sorting is applied server-side. */
    const orderedFilteredDesigns = computed(() => allMatching.value ?? pageRows.value)

    const extractFilename = (pdbFile: string | undefined): string => {
        if (!pdbFile) return ''
        return pdbFile.split('/').pop() || ''
    }

    const getStructureFilename = (design: Design): string => getStructureFilenameFromDesign(design)

    const hasStructureFile = (d: Design): boolean => designHasStructureFile(d)

    const totalDesigns = computed(() => totalRows.value)

    const designsWithPdbOrdered = (): Design[] =>
        orderedFilteredDesigns.value.filter(d => hasStructureFile(d))

    watch(orderedFilteredDesigns, () => {
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) {
            currentNavDesignId.value = null
            return
        }
        if (!currentNavDesignId.value || !withPdb.some(d => d.design_id === currentNavDesignId.value)) {
            currentNavDesignId.value = withPdb[0].design_id
        }
    }, { deep: true, immediate: true })

    const currentStructure = computed((): StructureInfo | null => {
        if (selectedDesigns.value.length === 0) {
            return null
        }

        const withPdb = designsWithPdbOrdered()

        if (withPdb.length === 0) {
            return null
        }

        const id = currentNavDesignId.value
        const design = id ? withPdb.find(d => d.design_id === id) : undefined
        const chosen = design ?? withPdb[0]
        const filename = getStructureFilename(chosen)
        if (!filename) {
            return null
        }

        return {
            design: chosen,
            filename,
            pdbPath: chosen.pdb_file || ''
        }
    })

    const canNavigatePrevious = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) return false
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        return idx > 0
    })

    const canNavigateNext = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const withPdb = designsWithPdbOrdered()
        if (withPdb.length === 0) return false
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        return idx >= 0 && idx < withPdb.length - 1
    })

    const totalStructures = computed(() => {
        return designsWithPdbOrdered().length
    })

    function buildListQuery(extra: Partial<DesignsListQueryDTO> = {}): DesignsListQueryDTO {
        const f = filters.value
        const runIds = selectedRunIds.value
        const filterColumns = {
            design_id: f.design_id,
            project_id: f.project_id,
            run_name: f.run_name,
            method: f.method
        }
        const range = {
            score_min: f.score_min.value ?? undefined,
            score_max: f.score_max.value ?? undefined,
            length_min: f.length_min.value ?? undefined,
            length_max: f.length_max.value ?? undefined,
            target_sequence: f.target_sequence.value ?? undefined
        }
        const globalScoreFields = visibleColumns.value.filter((c) => GLOBAL_FILTER_SCORE_FIELDS.has(c))
        const g = f.global.value
        return {
            runIds,
            sortField: tableSortField.value ?? undefined,
            sortOrder: tableSortOrder.value ?? undefined,
            global: g != null && g !== '' ? String(g) : null,
            globalScoreFields,
            filterColumns,
            customFilters: customFilters.value,
            range,
            bestMpnnOnly: bestMpnnOnly.value,
            ...extra
        }
    }

    function defaultVisibleFromColumns(cols: ColumnConfig[]): string[] {
        const fields = new Set(cols.map((c) => c.field))
        const out = ['design_id', 'project_id', 'run_name', 'method']
        if (fields.has('good')) out.push('good')
        if (fields.has('Length')) out.push('Length')
        for (const sc of defaultVisibleScoreColumnFields()) {
            if (fields.has(sc)) out.push(sc)
        }
        return out
    }

    async function syncAllMatchingRows(seq: number): Promise<void> {
        if (selectedRunIds.value.length === 0) {
            allMatching.value = null
            return
        }
        if (totalRows.value <= pageSize.value && pageIndex.value === 0) {
            allMatching.value = [...pageRows.value]
            return
        }
        allMatchingLoading.value = true
        try {
            const data = await designsApi.listDesigns(buildListQuery())
            if (seq !== fetchSeq) return
            allMatching.value = data.designs
        } finally {
            if (seq === fetchSeq) {
                allMatchingLoading.value = false
            }
        }
    }

    const ensureAllMatching = async (): Promise<Design[]> => {
        if (selectedRunIds.value.length === 0) return []
        if (allMatching.value && totalRows.value <= pageSize.value && pageIndex.value === 0) {
            return allMatching.value
        }
        allMatchingLoading.value = true
        try {
            const data = await designsApi.listDesigns(buildListQuery())
            allMatching.value = data.designs
            return allMatching.value
        } finally {
            allMatchingLoading.value = false
        }
    }

    async function runFetchPage(): Promise<void> {
        const seq = ++fetchSeq
        if (selectedRunIds.value.length === 0) return
        loading.value = true
        try {
            const data = await designsApi.listDesigns({
                ...buildListQuery(),
                page: pageIndex.value,
                pageSize: pageSize.value
            })
            if (seq !== fetchSeq) return
            pageRows.value = data.designs
            totalRows.value = data.total ?? data.designs.length
            allMatching.value = null
            await syncAllMatchingRows(seq)

            if (pendingSelectedDesignKeys.value.length > 0) {
                const keySet = new Set(pendingSelectedDesignKeys.value.map((k) => `${k.run_id}::${k.design_id}`))
                selectedDesigns.value = (allMatching.value ?? pageRows.value).filter((d) =>
                    keySet.has(`${d.run_id}::${d.design_id}`)
                )
                pendingSelectedDesignKeys.value = []
            } else {
                const keySet = new Set(selectedDesigns.value.map((d) => `${d.run_id}::${d.design_id}`))
                selectedDesigns.value = (allMatching.value ?? pageRows.value).filter((d) =>
                    keySet.has(`${d.run_id}::${d.design_id}`)
                )
            }

            if (pendingCurrentNavDesignId.value != null) {
                currentNavDesignId.value = pendingCurrentNavDesignId.value
                pendingCurrentNavDesignId.value = null
            }
            const withPdb = designsWithPdbOrdered()
            if (!withPdb.some((d) => d.design_id === currentNavDesignId.value)) {
                currentNavDesignId.value = withPdb[0]?.design_id ?? null
            }
        } catch (err) {
            console.error('Error loading designs page:', err)
            throw err
        } finally {
            if (seq === fetchSeq) {
                loading.value = false
            }
        }
    }

    function scheduleQueryRefresh(): void {
        if (selectedRunIds.value.length === 0) return
        if (queryDebounceTimer) clearTimeout(queryDebounceTimer)
        queryDebounceTimer = setTimeout(() => {
            queryDebounceTimer = null
            pageIndex.value = 0
            void runFetchPage()
        }, QUERY_DEBOUNCE_MS)
    }

    const onDataTablePage = (event: { page: number; first: number; rows: number }): void => {
        pageIndex.value = event.page
        pageSize.value = event.rows
        void runFetchPage()
    }

    const onDataTableSort = (): void => {
        pageIndex.value = 0
        void runFetchPage()
    }

    // Actions
    const fetchDesignsForRuns = async (runIds: string[]) => {
        const seq = ++fetchSeq
        if (runIds.length === 0) {
            pageRows.value = []
            totalRows.value = 0
            allMatching.value = null
            columns.value = []
            loadedRunIdsSignature.value = ''
            selectedDesigns.value = []
            currentNavDesignId.value = null
            loading.value = false
            return
        }

        loading.value = true
        try {
            const prevVisible = [...visibleColumns.value]
            const colRes = await designsApi.listDesignColumns(runIds)
            if (seq !== fetchSeq) return
            columns.value = colRes.columns as ColumnConfig[]

            if (prevVisible.length === 0 || !loadedRunIdsSignature.value) {
                visibleColumns.value = defaultVisibleFromColumns(columns.value)
            } else {
                const fieldSet = new Set(columns.value.map((c) => c.field))
                visibleColumns.value = prevVisible.filter((f) => fieldSet.has(f))
            }

            loadedRunIdsSignature.value = runIdsSignature(runIds)
            pageIndex.value = 0
            const data = await designsApi.listDesigns({
                ...buildListQuery(),
                page: 0,
                pageSize: pageSize.value
            })
            if (seq !== fetchSeq) return
            pageRows.value = data.designs
            totalRows.value = data.total ?? data.designs.length
            allMatching.value = null
            await syncAllMatchingRows(seq)

            if (pendingSelectedDesignKeys.value.length > 0) {
                const keySet = new Set(pendingSelectedDesignKeys.value.map((k) => `${k.run_id}::${k.design_id}`))
                selectedDesigns.value = (allMatching.value ?? pageRows.value).filter((d) =>
                    keySet.has(`${d.run_id}::${d.design_id}`)
                )
                pendingSelectedDesignKeys.value = []
            } else {
                const keySet = new Set(selectedDesigns.value.map((d) => `${d.run_id}::${d.design_id}`))
                selectedDesigns.value = (allMatching.value ?? pageRows.value).filter((d) =>
                    keySet.has(`${d.run_id}::${d.design_id}`)
                )
            }

            if (pendingCurrentNavDesignId.value != null) {
                currentNavDesignId.value = pendingCurrentNavDesignId.value
                pendingCurrentNavDesignId.value = null
            }
            const withPdb = designsWithPdbOrdered()
            if (!withPdb.some((d) => d.design_id === currentNavDesignId.value)) {
                currentNavDesignId.value = withPdb[0]?.design_id ?? null
            }
        } catch (err) {
            console.error('Error loading designs:', err)
            throw err
        } finally {
            if (seq === fetchSeq) {
                loading.value = false
            }
        }
    }

    /** Refresh designs for the current `selectedRunIds` (e.g. after cache refresh). */
    const fetchDesigns = async () => {
        await fetchDesignsForRuns(selectedRunIds.value)
    }

    const flushSelectedRunIds = async (): Promise<void> => {
        if (selectionDebounceTimer) {
            clearTimeout(selectionDebounceTimer)
            selectionDebounceTimer = null
        }
        await fetchDesignsForRuns(selectedRunIds.value)
    }

    const ensureDesignsForCurrentSelection = async (): Promise<void> => {
        if (selectedRunIds.value.length === 0) return
        const sig = runIdsSignature(selectedRunIds.value)
        if (sig === loadedRunIdsSignature.value && (totalRows.value > 0 || pageRows.value.length > 0)) return
        await fetchDesignsForRuns(selectedRunIds.value)
    }

    const setFilters = (newFilters: Partial<FilterState>) => {
        filters.value = { ...filters.value, ...newFilters }
    }

    const clearFilters = () => {
        filters.value = {
            global: { value: null, matchMode: 'contains' },
            design_id: { value: null, matchMode: 'contains' },
            project_id: { value: null, matchMode: 'contains' },
            run_name: { value: null, matchMode: 'contains' },
            method: { value: null, matchMode: 'equals' },
            score_min: { value: null, matchMode: 'gte' },
            score_max: { value: null, matchMode: 'lte' },
            length_min: { value: null, matchMode: 'gte' },
            length_max: { value: null, matchMode: 'lte' },
            target_sequence: { value: null, matchMode: 'regex' }
        }
        customFilters.value = []
    }

    const toggleBestMpnnOnly = () => {
        bestMpnnOnly.value = !bestMpnnOnly.value
    }

    const selectDesigns = (designsToSelect: Design[]) => {
        selectedDesigns.value = designsToSelect
        const withPdb = designsWithPdbOrdered()
        currentNavDesignId.value = withPdb[0]?.design_id ?? null
    }

    const toggleColumn = (field: string) => {
        const index = visibleColumns.value.indexOf(field)
        if (index > -1) {
            visibleColumns.value.splice(index, 1)
        } else {
            visibleColumns.value.push(field)
        }
        scheduleQueryRefresh()
    }

    const navigateStructure = async (direction: 'next' | 'previous') => {
        await ensureAllMatching()
        const withPdb = designsWithPdbOrdered()
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        if (idx < 0) return
        if (direction === 'next' && idx < withPdb.length - 1) {
            currentNavDesignId.value = withPdb[idx + 1].design_id
        } else if (direction === 'previous' && idx > 0) {
            currentNavDesignId.value = withPdb[idx - 1].design_id
        }
    }

    const patchDesignRows = (sync: (d: Design) => Design) => {
        pageRows.value = pageRows.value.map(sync)
        if (allMatching.value) {
            allMatching.value = allMatching.value.map(sync)
        }
    }

    const clearDesigns = async () => {
        try {
            await designsApi.clearDesigns()
            pageRows.value = []
            totalRows.value = 0
            allMatching.value = null
            loadedRunIdsSignature.value = ''
            selectedDesigns.value = []
            currentNavDesignId.value = null
        } catch (err) {
            console.error('Error clearing designs:', err)
            throw err
        }
    }

    const setSelectedRunIds = (runIds: string[]) => {
        selectedRunIds.value = runIds
        selectedDesigns.value = selectedDesigns.value.filter(design =>
            runIds.length === 0 || runIds.includes(design.run_id)
        )

        if (selectionDebounceTimer) {
            clearTimeout(selectionDebounceTimer)
            selectionDebounceTimer = null
        }

        if (runIds.length === 0) {
            void fetchDesignsForRuns([])
            return
        }

        selectionDebounceTimer = setTimeout(() => {
            selectionDebounceTimer = null
            void fetchDesignsForRuns(runIds)
        }, SELECTION_DEBOUNCE_MS)
    }

    const viewDesign = (design: Design) => {
        selectedDesigns.value = [design]

        const withPdb = designsWithPdbOrdered()
        const index = withPdb.findIndex(d => d.design_id === design.design_id)
        if (index >= 0) {
            currentNavDesignId.value = withPdb[index].design_id
        } else if (withPdb.length > 0) {
            currentNavDesignId.value = withPdb[0].design_id
        } else {
            currentNavDesignId.value = null
        }
    }

    const patchDesignGood = async (design: Design, good: boolean | null) => {
        const sourcePath = (design as any).source_path as string | undefined
        await designsApi.patchDesignGood({
            run_id: design.run_id,
            design_id: design.design_id,
            good,
            ...(sourcePath ? { source_path: sourcePath } : {})
        })
        const sync = (d: Design): Design => {
            if (d.run_id !== design.run_id || d.design_id !== design.design_id) return d
            if (good === null) {
                const next = { ...d } as Record<string, unknown>
                delete next.good
                return next as Design
            }
            return { ...d, good }
        }
        patchDesignRows(sync)
        selectedDesigns.value = selectedDesigns.value.map(sync)

        if (!columns.value.some(c => c.field === 'good')) {
            const methodIdx = columns.value.findIndex(c => c.field === 'method')
            const goodCol: ColumnConfig = {
                field: 'good',
                header: 'Good',
                sortable: true,
                filter: true,
                filterType: 'boolean',
                showFilterMenu: false,
                style: 'min-width: 90px'
            }
            if (methodIdx >= 0) {
                columns.value.splice(methodIdx + 1, 0, goodCol)
            } else {
                columns.value.push(goodCol)
            }
        }
        if (!visibleColumns.value.includes('good')) {
            const mi = visibleColumns.value.indexOf('method')
            if (mi >= 0) {
                visibleColumns.value.splice(mi + 1, 0, 'good')
            } else {
                visibleColumns.value.push('good')
            }
        }
    }

    const ensureTagColumnVisible = () => {
        if (!columns.value.some(c => c.field === 'tag')) {
            const goodIdx = columns.value.findIndex(c => c.field === 'good')
            const methodIdx = columns.value.findIndex(c => c.field === 'method')
            const tagCol: ColumnConfig = {
                field: 'tag',
                header: 'Tag',
                sortable: true,
                filter: true,
                filterType: 'text',
                showFilterMenu: false,
                style: 'min-width: 72px'
            }
            if (goodIdx >= 0) {
                columns.value.splice(goodIdx + 1, 0, tagCol)
            } else if (methodIdx >= 0) {
                columns.value.splice(methodIdx + 1, 0, tagCol)
            } else {
                columns.value.push(tagCol)
            }
        }
        if (!visibleColumns.value.includes('tag')) {
            const gi = visibleColumns.value.indexOf('good')
            const mi = visibleColumns.value.indexOf('method')
            if (gi >= 0) {
                visibleColumns.value.splice(gi + 1, 0, 'tag')
            } else if (mi >= 0) {
                visibleColumns.value.splice(mi + 1, 0, 'tag')
            } else {
                visibleColumns.value.push('tag')
            }
        }
    }

    const patchDesignTag = async (design: Design, tag: 'N' | 'C' | null) => {
        const sourcePath = (design as any).source_path as string | undefined
        await designsApi.patchDesignTag({
            run_id: design.run_id,
            design_id: design.design_id,
            tag,
            ...(sourcePath ? { source_path: sourcePath } : {})
        })
        const sync = (d: Design): Design => {
            if (d.run_id !== design.run_id || d.design_id !== design.design_id) return d
            if (tag === null) {
                const next = { ...d } as Record<string, unknown>
                delete next.tag
                return next as Design
            }
            return { ...d, tag }
        }
        patchDesignRows(sync)
        selectedDesigns.value = selectedDesigns.value.map(sync)
        ensureTagColumnVisible()
    }

    const applyTagPlacementResult = (row: {
        run_id: string
        design_id: string
        tag?: string | null
        error?: string | null
    }) => {
        if (row.error) return
        const sync = (d: Design): Design => {
            if (String(d.run_id) !== String(row.run_id) || String(d.design_id) !== String(row.design_id)) {
                return d
            }
            if (row.tag == null || String(row.tag).trim() === '') {
                const next = { ...d } as Record<string, unknown>
                delete next.tag
                return next as Design
            }
            return { ...d, tag: row.tag }
        }
        patchDesignRows(sync)
        selectedDesigns.value = selectedDesigns.value.map(sync)
        ensureTagColumnVisible()
    }

    const getCurrentRowPosition = () => {
        if (selectedDesigns.value.length === 0) return '0 / 0'

        const withPdb = designsWithPdbOrdered()

        if (withPdb.length === 0) return '0 / 0'

        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        if (idx < 0) return '0 / 0'

        return `${idx + 1} / ${withPdb.length}`
    }

    watch([selectedRunIds, selectedDesignKeysSignature, currentNavDesignId], () => persistViewStateToStorage())

    return {
        pageRows,
        totalRows,
        pageIndex,
        pageSize,
        allMatching,
        allMatchingLoading,
        selectedDesigns,
        selectedRunIds,
        filters,
        bestMpnnOnly,
        customFilters,
        isFieldReferencedByCustomFilter,
        allFiltersForFieldEnabled,
        setAllCustomFiltersEnabledForField,
        columns,
        columnsForSelectedRuns,
        visibleColumns,
        loading,
        currentNavDesignId,
        tableSortField,
        tableSortOrder,

        filteredDesigns,
        orderedFilteredDesigns,
        totalDesigns,
        currentStructure,
        canNavigatePrevious,
        canNavigateNext,
        totalStructures,

        fetchDesigns,
        fetchDesignsForRuns,
        flushSelectedRunIds,
        ensureDesignsForCurrentSelection,
        ensureAllMatching,
        onDataTablePage,
        onDataTableSort,
        setFilters,
        clearFilters,
        addCustomFilter,
        removeCustomFilter,
        updateCustomFilter,
        getOperatorsForColumn,
        toggleBestMpnnOnly,
        selectDesigns,
        toggleColumn,
        navigateStructure,
        clearDesigns,
        setSelectedRunIds,
        viewDesign,
        getCurrentRowPosition,
        extractFilename,
        getStructureFilename,
        patchDesignGood,
        patchDesignTag,
        applyTagPlacementResult,
        hydrateFromPersistence
    }
})
