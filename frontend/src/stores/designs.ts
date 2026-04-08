/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { localeComparator, resolveFieldData, sort } from '@primeuix/utils/object'
import { designsApi } from '../webapi'
import type { Design, FilterState, ColumnConfig, StructureInfo, CustomFilter } from '../types/store'

export const useDesignsStore = defineStore('designs', () => {
    // State
    const designs = ref<Design[]>([])
    const selectedDesigns = ref<Design[]>([])
    const selectedRunIds = ref<string[]>([]) // Track selected run IDs for filtering
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
    const CUSTOM_FILTERS_STORAGE_KEY = 'binderdash:custom-filters-v1'

    const loadCustomFiltersFromStorage = () => {
        if (typeof localStorage === 'undefined') return
        try {
            const raw = localStorage.getItem(CUSTOM_FILTERS_STORAGE_KEY)
            if (!raw) return
            const parsed = JSON.parse(raw) as { filters?: unknown[] }
            if (Array.isArray(parsed.filters)) {
                customFilters.value = parsed.filters.map((f: any) => ({
                    id: typeof f?.id === 'string' ? f.id : crypto.randomUUID(),
                    column: typeof f?.column === 'string' ? f.column : '',
                    operator: typeof f?.operator === 'string' ? f.operator : 'eq',
                    value: f?.value,
                    enabled: f?.enabled !== false
                }))
            }
        } catch (e) {
            console.warn('Failed to load custom filters from localStorage', e)
        }
    }

    const persistCustomFiltersToStorage = () => {
        if (typeof localStorage === 'undefined') return
        try {
            localStorage.setItem(
                CUSTOM_FILTERS_STORAGE_KEY,
                JSON.stringify({
                    filters: customFilters.value
                })
            )
        } catch {
            /* quota / private mode */
        }
    }

    loadCustomFiltersFromStorage()

    watch(customFilters, () => persistCustomFiltersToStorage(), { deep: true })

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

    // Getters
    const filteredDesigns = computed(() => {
        let filtered = designs.value

        // Apply global filter
        if (filters.value.global.value) {
            const globalValue = filters.value.global.value.toLowerCase()
            filtered = filtered.filter(design => {
                return getGlobalFilterFields().some(field => {
                    const value = design[field]
                    return value && value.toString().toLowerCase().includes(globalValue)
                })
            })
        }

        // Apply individual column filters
        if (filters.value.design_id.value) {
            filtered = filtered.filter(design =>
                design.design_id && design.design_id.toLowerCase().includes(filters.value.design_id.value.toLowerCase())
            )
        }

        if (filters.value.project_id.value) {
            filtered = filtered.filter(design =>
                design.project_id && design.project_id.toLowerCase().includes(filters.value.project_id.value.toLowerCase())
            )
        }

        if (filters.value.run_name.value) {
            filtered = filtered.filter(design =>
                design.run_name && design.run_name.toLowerCase().includes(filters.value.run_name.value.toLowerCase())
            )
        }

        if (filters.value.method.value) {
            filtered = filtered.filter(design =>
                (design as any).method === filters.value.method.value
            )
        }

        // Apply score range filters
        if (filters.value.score_min.value !== null) {
            filtered = filtered.filter(design => {
                const scoreFields = [
                    'pae_interaction',
                    'Average_i_pTM',
                    'design_to_target_iptm',
                    'quality_score',
                    'i_pTM',
                    'ipTM',
                    'iptm',
                    'pair_pae',
                    'rf3_ipsae_min',
                    'rf3_rmsd_target_aligned_binder_rmsd_all'
                ]
                return scoreFields.some(field => {
                    const value = design[field]
                    return value !== null && value !== undefined && value >= filters.value.score_min.value
                })
            })
        }

        if (filters.value.score_max.value !== null) {
            filtered = filtered.filter(design => {
                const scoreFields = [
                    'pae_interaction',
                    'Average_i_pTM',
                    'design_to_target_iptm',
                    'quality_score',
                    'i_pTM',
                    'ipTM',
                    'iptm',
                    'pair_pae',
                    'rf3_ipsae_min',
                    'rf3_rmsd_target_aligned_binder_rmsd_all'
                ]
                return scoreFields.some(field => {
                    const value = design[field]
                    return value !== null && value !== undefined && value <= filters.value.score_max.value
                })
            })
        }

        // Apply length range filters
        if (filters.value.length_min.value !== null) {
            filtered = filtered.filter(design => {
                const length = design.Length || design.length
                return length !== null && length !== undefined && Number(length) >= filters.value.length_min.value
            })
        }

        if (filters.value.length_max.value !== null) {
            filtered = filtered.filter(design => {
                const length = design.Length || design.length
                return length !== null && length !== undefined && Number(length) <= filters.value.length_max.value
            })
        }

        // Apply target sequence filter (regex pattern matching)
        if (filters.value.target_sequence.value) {
            const targetSequencePattern = filters.value.target_sequence.value
            filtered = filtered.filter(design => {
                const targetSequence = (design as any).target_sequence
                if (!targetSequence) return false

                try {
                    // Create regex from the pattern, case-insensitive
                    const regex = new RegExp(targetSequencePattern, 'i')
                    return regex.test(targetSequence)
                } catch (error) {
                    // If regex is invalid, fall back to simple string contains
                    return targetSequence.toLowerCase().includes(targetSequencePattern.toLowerCase())
                }
            })
        }

        const activeCustomFilters = customFilters.value.filter(f => f.enabled !== false)
        if (activeCustomFilters.length > 0) {
            filtered = filtered.filter(design =>
                activeCustomFilters.every(f => passesCustomFilter(design, f))
            )
        }

        // Filter by selected run IDs - show only selected runs, or nothing if none selected
        if (selectedRunIds.value.length > 0) {
            filtered = filtered.filter(design =>
                selectedRunIds.value.includes(design.run_id)
            )
        } else {
            // If no runs are selected, show no designs
            filtered = []
        }

        // Apply best MPNN filtering if enabled
        if (bestMpnnOnly.value) {
            filtered = _filterBestMpnnDesigns(filtered)
        }

        return filtered
    })

    const orderedFilteredDesigns = computed(() => {
        const data = [...filteredDesigns.value]
        const field = tableSortField.value
        const order = tableSortOrder.value
        if (field == null || order == null || order === 0) {
            return data
        }
        const resolvedFieldData = new Map<Design, unknown>()
        for (const item of data) {
            resolvedFieldData.set(item, resolveFieldData(item, field))
        }
        const comparer = localeComparator()
        data.sort((a, b) => {
            const v1 = resolvedFieldData.get(a)
            const v2 = resolvedFieldData.get(b)
            return sort(v1 as any, v2 as any, order, comparer as any, 1)
        })
        return data
    })

    const extractFilename = (pdbFile: string | undefined): string => {
        if (!pdbFile) return ''
        return pdbFile.split('/').pop() || ''
    }

    const getStructureFilename = (design: Design): string => {
        const fromPdb = extractFilename(design.pdb_file)
        if (fromPdb) return fromPdb
        if ((design as any).method === 'boltzgen' && (design as any).file_name != null && (design as any).file_name !== '') {
            return String((design as any).file_name).trim()
        }
        return ''
    }

    const hasStructureFile = (d: Design): boolean =>
        !!(d.pdb_file || ((d as any).method === 'boltzgen' && (d as any).file_name))

    const totalDesigns = computed(() => designs.value.length)

    // Helper function to select the best design from a group using primary and secondary scores
    const _selectBestDesign = (designs: Design[]): Design => {
        if (designs.length === 0) return designs[0]
        if (designs.length === 1) return designs[0]

        // Define primary and secondary scores for each method
        const scoreConfig = {
            bindcraft: {
                primary: 'Average_i_pTM',
                secondary: ['Average_Binder_pLDDT'],
                higherIsBetter: true
            },
            rfd: {
                primary: 'pae_interaction',
                secondary: ['plddt_binder'],
                higherIsBetter: false
            },
            rfd3: {
                primary: 'iptm',
                secondary: ['rf3_ipsae_min'],
                higherIsBetter: true
            }
        }

        let bestDesign = designs[0]
        let bestScore: number | null = null

        for (const design of designs) {
            const method = (design as any).method || ''
            const config = scoreConfig[method as keyof typeof scoreConfig]

            if (!config) {
                // Unknown method, keep the first design
                continue
            }

            // Get primary score
            const primaryScore = design[config.primary as keyof Design] as number | null
            if (primaryScore === null || primaryScore === undefined) {
                continue
            }

            // Compare with current best
            let isBetter = false
            if (bestScore === null) {
                isBetter = true
            } else if (config.higherIsBetter) {
                if (primaryScore > bestScore) {
                    isBetter = true
                } else if (primaryScore === bestScore) {
                    // Primary scores are equal, check secondary scores
                    isBetter = _compareSecondaryScores(design, bestDesign, config.secondary, true)
                }
            } else {
                if (primaryScore < bestScore) {
                    isBetter = true
                } else if (primaryScore === bestScore) {
                    // Primary scores are equal, check secondary scores
                    isBetter = _compareSecondaryScores(design, bestDesign, config.secondary, false)
                }
            }

            if (isBetter) {
                bestDesign = design
                bestScore = primaryScore
            }
        }

        return bestDesign
    }

    // Helper function to compare secondary scores when primary scores are equal
    const _compareSecondaryScores = (
        design1: Design,
        design2: Design,
        secondaryFields: string[],
        higherIsBetter: boolean
    ): boolean => {
        for (const field of secondaryFields) {
            const score1 = design1[field as keyof Design] as number | null
            const score2 = design2[field as keyof Design] as number | null

            // Skip if either score is null/undefined
            if (score1 === null || score1 === undefined || score2 === null || score2 === undefined) {
                continue
            }

            // Compare scores
            if (higherIsBetter) {
                if (score1 > score2) return true
                if (score1 < score2) return false
            } else {
                if (score1 < score2) return true
                if (score1 > score2) return false
            }
        }

        // If all secondary scores are equal or missing, return false (keep current best)
        return false
    }

    // Helper function to filter best MPNN designs
    const _filterBestMpnnDesigns = (designs: Design[]): Design[] => {
        if (!designs || designs.length === 0) return designs

        // Group designs by backbone_id
        const backboneGroups: Record<string, Design[]> = {}
        for (const design of designs) {
            const backboneId = (design as any).backbone_id
            if (!backboneId) {
                // If no backbone_id, keep the design as-is
                backboneGroups['no_backbone'] = backboneGroups['no_backbone'] || []
                backboneGroups['no_backbone'].push(design)
                continue
            }

            backboneGroups[backboneId] = backboneGroups[backboneId] || []
            backboneGroups[backboneId].push(design)
        }

        // For each backbone group, select the best design
        const filteredDesigns: Design[] = []
        for (const [backboneId, groupDesigns] of Object.entries(backboneGroups)) {
            if (backboneId === 'no_backbone') {
                // Keep all designs without backbone_id
                filteredDesigns.push(...groupDesigns)
                continue
            }

            if (groupDesigns.length === 1) {
                // Only one design for this backbone, keep it
                filteredDesigns.push(groupDesigns[0])
                continue
            }

            // Find the best design using primary and secondary scores
            const bestDesign = _selectBestDesign(groupDesigns)
            filteredDesigns.push(bestDesign)
        }

        return filteredDesigns
    }

    // Helper function for global filtering
    const getGlobalFilterFields = () => {
        // Base fields that are always present
        const baseFields = ['design_id', 'project_id', 'run_name', 'method', 'Length']

        // Add score columns that are currently visible
        const scoreFields = visibleColumns.value.filter((col: string) =>
            ['pae_interaction', 'Average_i_pTM', 'i_pTM', 'ipTM', 'plddt_binder', 'Average_Binder_pLDDT'].includes(col)
        )

        return [...baseFields, ...scoreFields]
    }

    const designsWithPdbOrdered = (): Design[] =>
        orderedFilteredDesigns.value.filter(d => hasStructureFile(d))

    watch(() => filters.value, () => {
        const withPdb = designsWithPdbOrdered()
        currentNavDesignId.value = withPdb[0]?.design_id ?? null
    }, { deep: true })

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

    // Actions
    const fetchDesigns = async () => {
        loading.value = true
        try {
            const hadDesigns = designs.value.length > 0
            const prevVisible = [...visibleColumns.value]
            const data = await designsApi.listDesigns()
            designs.value = data.designs

            // Build columns dynamically from the loaded data
            columns.value = buildColumnsFromData(data.designs)

            // Update default visible columns to include score columns if they exist
            const newDefaultColumns = ['design_id', 'project_id', 'run_name', 'method']

            if (data.designs.some(d => Object.prototype.hasOwnProperty.call(d, 'good'))) {
                newDefaultColumns.push('good')
            }

            // Add Length column if it exists in the data
            if (data.designs.some(d => 'Length' in d && d['Length'] != null)) {
                newDefaultColumns.push('Length')
            }

            // Dynamically add score columns that exist in the data
            const scoreColumns = [
                'pae_interaction',
                'Average_i_pTM',
                'design_to_target_iptm',
                'quality_score',
                'i_pTM',
                'ipTM',
                'iptm',
                'pair_pae',
                'rf3_ipsae_min',
                'rf3_rmsd_target_aligned_binder_rmsd_all'
            ]
            scoreColumns.forEach(scoreCol => {
                if (data.designs.some(d => scoreCol in d && d[scoreCol] != null)) {
                    newDefaultColumns.push(scoreCol)
                }
            })

            // Note: target_sequence column is available but not shown by default
            // Users can toggle it on via the column selector if needed

            if (!hadDesigns) {
                visibleColumns.value = newDefaultColumns
            } else {
                const fieldSet = new Set(columns.value.map(c => c.field))
                visibleColumns.value = prevVisible.filter(f => fieldSet.has(f))
            }
        } catch (err) {
            console.error('Error loading designs:', err)
            throw err
        } finally {
            loading.value = false
        }
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
        // No need to reload designs - filtering is done in computed property
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
    }

    const navigateStructure = (direction: 'next' | 'previous') => {
        const withPdb = designsWithPdbOrdered()
        const idx = withPdb.findIndex(d => d.design_id === currentNavDesignId.value)
        if (idx < 0) return
        if (direction === 'next' && idx < withPdb.length - 1) {
            currentNavDesignId.value = withPdb[idx + 1].design_id
        } else if (direction === 'previous' && idx > 0) {
            currentNavDesignId.value = withPdb[idx - 1].design_id
        }
    }

    const clearDesigns = async () => {
        try {
            await designsApi.clearDesigns()
            designs.value = []
            selectedDesigns.value = []
            currentNavDesignId.value = null
        } catch (err) {
            console.error('Error clearing designs:', err)
            throw err
        }
    }

    const setSelectedRunIds = (runIds: string[]) => {
        selectedRunIds.value = runIds
        // Clear any selected designs that are no longer in the filtered list
        selectedDesigns.value = selectedDesigns.value.filter(design =>
            runIds.length === 0 || runIds.includes(design.run_id)
        )
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
        designs.value = designs.value.map(sync)
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
        designs.value = designs.value.map(sync)
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
        designs.value = designs.value.map(sync)
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

    // Helper function to build columns from data
    const buildColumnsFromData = (designs: Design[]): ColumnConfig[] => {
        if (!designs || designs.length === 0) return columns.value

        const baseColumns: ColumnConfig[] = [
            { field: 'design_id', header: 'Design ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 150px' },
            { field: 'project_id', header: 'Project ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'run_name', header: 'Run Name', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'method', header: 'Method', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 100px' }
        ]

        if (designs.some(d => Object.prototype.hasOwnProperty.call(d, 'good'))) {
            baseColumns.push({
                field: 'good',
                header: 'Good',
                sortable: true,
                filter: true,
                filterType: 'boolean',
                showFilterMenu: false,
                style: 'min-width: 90px'
            })
        }

        if (designs.some(d => Object.prototype.hasOwnProperty.call(d, 'tag'))) {
            baseColumns.push({
                field: 'tag',
                header: 'Tag',
                sortable: true,
                filter: true,
                filterType: 'text',
                showFilterMenu: false,
                style: 'min-width: 72px'
            })
        }

        // Add score columns if they exist in the data
        const scoreColumns: ColumnConfig[] = []
        const knownScoreFields = [
            { field: 'pae_interaction', header: 'PAE Interaction' },
            { field: 'Average_i_pTM', header: 'Average i_pTM' },
            { field: 'design_to_target_iptm', header: 'Design→Target ipTM' },
            { field: 'quality_score', header: 'Quality Score' },
            { field: 'pLDDT', header: 'pLDDT' },
            { field: 'i_pTM', header: 'i_pTM' },
            { field: 'ipTM', header: 'ipTM' },
            { field: 'iptm', header: 'ipTM' },
            { field: 'pair_pae', header: 'Pair PAE' },
            { field: 'rf3_ipsae_min', header: 'RF3 ipSAE Min' },
            {
                field: 'rf3_rmsd_target_aligned_binder_rmsd_all',
                header: 'RF3 RMSD (Target-aligned Binder)'
            }
        ]

        knownScoreFields.forEach(scoreField => {
            if (designs.some(d => scoreField.field in d && d[scoreField.field] != null)) {
                scoreColumns.push({
                    field: scoreField.field,
                    header: scoreField.header,
                    sortable: true,
                    filter: true,
                    filterType: 'numeric',
                    showFilterMenu: false,
                    style: 'min-width: 120px'
                })
            }
        })

        const metadataColumns: ColumnConfig[] = [
            { field: 'target_sequence', header: 'Target Sequence', sortable: false, filter: false, style: 'min-width: 200px' },
            { field: 'pdb_file', header: 'PDB File', sortable: false, filter: false, style: 'min-width: 200px' },
            { field: 'run_path', header: 'Run Path', sortable: false, filter: false, style: 'min-width: 200px' }
        ]

        // Add other columns from the data (excluding already defined ones)
        const existingFields = new Set([
            'design_id', 'project_id', 'run_name', 'method', 'good', 'tag',
            'pae_interaction', 'Average_i_pTM', 'design_to_target_iptm', 'quality_score',
            'pLDDT', 'i_pTM', 'ipTM',
            'pdb_file', 'run_path', 'run_id', 'target_sequence'
        ])

        const dynamicKeys = new Set<string>()
        for (const design of designs) {
            for (const key of Object.keys(design)) {
                if (!existingFields.has(key)) dynamicKeys.add(key)
            }
        }

        const otherColumns: ColumnConfig[] = []
        for (const key of dynamicKeys) {
            let sample: unknown
            for (const design of designs) {
                const v = design[key]
                if (v != null && v !== '') {
                    sample = v
                    break
                }
            }

            let filterType = 'text'
            let sortable = false
            if (sample === undefined) {
                filterType = 'text'
            } else if (typeof sample === 'boolean') {
                filterType = 'boolean'
                sortable = true
            } else if (typeof sample === 'number' && !Number.isNaN(sample)) {
                filterType = 'numeric'
                sortable = true
            } else if (sample instanceof Date) {
                filterType = 'date'
                sortable = true
            } else if (typeof sample === 'string' && sample.trim() !== '' && !Number.isNaN(Number(sample))) {
                filterType = 'numeric'
                sortable = true
            }

            otherColumns.push({
                field: key,
                header: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                sortable,
                filter: true,
                filterType,
                showFilterMenu: false,
                style: 'min-width: 120px'
            })
        }

        return [...baseColumns, ...scoreColumns, ...metadataColumns, ...otherColumns]
    }

    return {
        // State
        designs,
        selectedDesigns,
        selectedRunIds,
        filters,
        bestMpnnOnly,
        customFilters,
        isFieldReferencedByCustomFilter,
        allFiltersForFieldEnabled,
        setAllCustomFiltersEnabledForField,
        columns,
        visibleColumns,
        loading,
        currentNavDesignId,
        tableSortField,
        tableSortOrder,

        // Getters
        filteredDesigns,
        orderedFilteredDesigns,
        totalDesigns,
        currentStructure,
        canNavigatePrevious,
        canNavigateNext,
        totalStructures,

        // Actions
        fetchDesigns,
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
        applyTagPlacementResult
    }
})
