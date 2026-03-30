/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { localeComparator, resolveFieldData, sort } from '@primeuix/utils/object'
import { designsApi } from '../webapi'
import type { Design, FilterState, ColumnConfig, StructureInfo } from '../types/store'

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
    const columns = ref<ColumnConfig[]>([])
    const visibleColumns = ref<string[]>(['design_id', 'project_id', 'run_name', 'method', 'Length'])
    const loading = ref(false)
    const currentNavDesignId = ref<string | null>(null)
    const tableSortField = ref<string | undefined>(undefined)
    const tableSortOrder = ref<number | undefined>(undefined)

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

            visibleColumns.value = newDefaultColumns
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
            'design_id', 'project_id', 'run_name', 'method', 'good',
            'pae_interaction', 'Average_i_pTM', 'design_to_target_iptm', 'quality_score',
            'pLDDT', 'i_pTM', 'ipTM',
            'pdb_file', 'run_path', 'run_id', 'target_sequence'
        ])

        const otherColumns: ColumnConfig[] = []
        designs.forEach(design => {
            Object.keys(design).forEach(key => {
                if (!existingFields.has(key) && !otherColumns.some(col => col.field === key)) {
                    // Determine column type and properties
                    const value = design[key]
                    const isNumeric = typeof value === 'number' && !isNaN(value)
                    const isDate = value instanceof Date || (typeof value === 'string' && !isNaN(Date.parse(value)))

                    let filterType = 'text'
                    if (isNumeric) filterType = 'numeric'
                    else if (isDate) filterType = 'date'

                    otherColumns.push({
                        field: key,
                        header: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                        sortable: isNumeric || isDate,
                        filter: true,
                        filterType,
                        showFilterMenu: false,
                        style: 'min-width: 120px'
                    })
                }
            })
        })

        return [...baseColumns, ...scoreColumns, ...metadataColumns, ...otherColumns]
    }

    return {
        // State
        designs,
        selectedDesigns,
        selectedRunIds,
        filters,
        bestMpnnOnly,
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
        patchDesignGood
    }
})
