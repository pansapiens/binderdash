/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { designsApi } from '../webapi'
import type { Design, FilterState, ColumnConfig, StructureInfo, DesignsState } from '../types/store'

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
        protocol: { value: null, matchMode: 'equals' },
        score_min: { value: null, matchMode: 'gte' },
        score_max: { value: null, matchMode: 'lte' }
    })
    const columns = ref<ColumnConfig[]>([])
    const visibleColumns = ref<string[]>(['design_id', 'project_id', 'run_name', 'protocol'])
    const loading = ref(false)
    const currentStructureIndex = ref(0)

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

        if (filters.value.protocol.value) {
            filtered = filtered.filter(design =>
                design.protocol === filters.value.protocol.value
            )
        }

        // Apply score range filters
        if (filters.value.score_min.value !== null) {
            filtered = filtered.filter(design => {
                // Check all possible score fields
                const scoreFields = ['pae_interaction', 'Average_i_pTM', 'pLDDT', 'i_pTM', 'ipTM']
                return scoreFields.some(field => {
                    const value = design[field]
                    return value !== null && value !== undefined && value >= filters.value.score_min.value
                })
            })
        }

        if (filters.value.score_max.value !== null) {
            filtered = filtered.filter(design => {
                // Check all possible score fields
                const scoreFields = ['pae_interaction', 'Average_i_pTM', 'pLDDT', 'i_pTM', 'ipTM']
                return scoreFields.some(field => {
                    const value = design[field]
                    return value !== null && value !== undefined && value <= filters.value.score_max.value
                })
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

        return filtered
    })

    const totalDesigns = computed(() => designs.value.length)

    // Helper function for global filtering
    const getGlobalFilterFields = () => {
        // Base fields that are always present
        const baseFields = ['design_id', 'project_id', 'run_name', 'protocol']

        // Add score columns that are currently visible
        const scoreFields = visibleColumns.value.filter((col: string) =>
            ['pae_interaction', 'Average_i_pTM', 'pLDDT', 'i_pTM', 'ipTM'].includes(col)
        )

        return [...baseFields, ...scoreFields]
    }

    // Watch for filter changes and reset navigation index
    watch(() => filters.value, () => {
        // Reset to first structure when filters change
        currentStructureIndex.value = 0
    }, { deep: true })

    const currentStructure = computed((): StructureInfo | null => {
        if (selectedDesigns.value.length === 0) {
            return null
        }

        // Get all designs with PDB files from the filtered designs
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)

        if (designsWithPdb.length === 0 || currentStructureIndex.value >= designsWithPdb.length) {
            return null
        }

        const design = designsWithPdb[currentStructureIndex.value]
        if (!design.pdb_file) {
            return null
        }

        return {
            design,
            filename: design.pdb_file.split('/').pop() || '',
            pdbPath: design.pdb_file
        }
    })

    const canNavigatePrevious = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)
        return currentStructureIndex.value > 0 && designsWithPdb.length > 0
    })

    const canNavigateNext = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)
        return currentStructureIndex.value < designsWithPdb.length - 1 && designsWithPdb.length > 0
    })

    const totalStructures = computed(() => {
        return filteredDesigns.value.filter(d => d.pdb_file).length
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
            const newDefaultColumns = ['design_id', 'project_id', 'run_name', 'protocol']

            // Dynamically add score columns that exist in the data
            const scoreColumns = ['pae_interaction', 'Average_i_pTM', 'pLDDT', 'i_pTM', 'ipTM']
            scoreColumns.forEach(scoreCol => {
                if (data.designs.some(d => scoreCol in d && d[scoreCol] != null)) {
                    newDefaultColumns.push(scoreCol)
                }
            })

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
            protocol: { value: null, matchMode: 'equals' },
            score_min: { value: null, matchMode: 'gte' },
            score_max: { value: null, matchMode: 'lte' }
        }
    }

    const selectDesigns = (designsToSelect: Design[]) => {
        selectedDesigns.value = designsToSelect
        currentStructureIndex.value = 0
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
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)

        if (direction === 'next' && currentStructureIndex.value < designsWithPdb.length - 1) {
            currentStructureIndex.value++
        } else if (direction === 'previous' && currentStructureIndex.value > 0) {
            currentStructureIndex.value--
        }
    }

    const clearDesigns = async () => {
        try {
            await designsApi.clearDesigns()
            designs.value = []
            selectedDesigns.value = []
            currentStructureIndex.value = 0
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

        // Find the position of this design among filtered designs with PDB files
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)
        const index = designsWithPdb.findIndex(d => d.design_id === design.design_id)
        currentStructureIndex.value = index >= 0 ? index : 0
    }

    const getCurrentRowPosition = () => {
        if (selectedDesigns.value.length === 0) return '0 / 0'

        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)

        if (designsWithPdb.length === 0) return '0 / 0'

        return `${currentStructureIndex.value + 1} / ${designsWithPdb.length}`
    }

    // Helper function to build columns from data
    const buildColumnsFromData = (designs: Design[]): ColumnConfig[] => {
        if (!designs || designs.length === 0) return columns.value

        const baseColumns: ColumnConfig[] = [
            { field: 'design_id', header: 'Design ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 150px' },
            { field: 'project_id', header: 'Project ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'run_name', header: 'Run Name', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
            { field: 'protocol', header: 'Protocol', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 100px' }
        ]

        // Add score columns if they exist in the data
        const scoreColumns: ColumnConfig[] = []
        const knownScoreFields = [
            { field: 'pae_interaction', header: 'PAE Interaction' },
            { field: 'Average_i_pTM', header: 'Average i_pTM' },
            { field: 'pLDDT', header: 'pLDDT' },
            { field: 'i_pTM', header: 'i_pTM' },
            { field: 'ipTM', header: 'ipTM' }
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
            { field: 'pdb_file', header: 'PDB File', sortable: false, filter: false, style: 'min-width: 200px' },
            { field: 'run_path', header: 'Run Path', sortable: false, filter: false, style: 'min-width: 200px' }
        ]

        // Add other columns from the data (excluding already defined ones)
        const existingFields = new Set([
            'design_id', 'project_id', 'run_name', 'protocol',
            'pae_interaction', 'Average_i_pTM', 'pLDDT', 'i_pTM', 'ipTM',
            'pdb_file', 'run_path', 'run_id'
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
        columns,
        visibleColumns,
        loading,
        currentStructureIndex,

        // Getters
        filteredDesigns,
        totalDesigns,
        currentStructure,
        canNavigatePrevious,
        canNavigateNext,
        totalStructures,

        // Actions
        fetchDesigns,
        setFilters,
        clearFilters,
        selectDesigns,
        toggleColumn,
        navigateStructure,
        clearDesigns,
        setSelectedRunIds,
        viewDesign,
        getCurrentRowPosition
    }
})
