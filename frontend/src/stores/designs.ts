/**
 * Designs Store
 * Manages design data, filtering, and selection
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { designsApi } from '../webapi'
import type { Design, FilterState, ColumnConfig, StructureInfo, DesignsState } from '../types/store'

export const useDesignsStore = defineStore('designs', () => {
    // State
    const designs = ref<Design[]>([])
    const selectedDesigns = ref<Design[]>([])
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
        // This will be enhanced with actual filtering logic
        return designs.value
    })

    const totalDesigns = computed(() => designs.value.length)

    const currentStructure = computed((): StructureInfo | null => {
        if (selectedDesigns.value.length === 0) {
            return null
        }

        let structureIndex = 0
        for (const design of selectedDesigns.value) {
            if (design.pdb_file) {
                if (structureIndex === currentStructureIndex.value) {
                    return {
                        design,
                        filename: design.pdb_file.split('/').pop() || '',
                        pdbPath: design.pdb_file
                    }
                }
                structureIndex++
            }
        }
        return null
    })

    const canNavigatePrevious = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const currentDesign = selectedDesigns.value[currentStructureIndex.value]
        const currentIndex = filteredDesigns.value.findIndex(d => d.design_id === currentDesign.design_id)
        return currentIndex > 0
    })

    const canNavigateNext = computed(() => {
        if (selectedDesigns.value.length === 0) return false
        const currentDesign = selectedDesigns.value[currentStructureIndex.value]
        const currentIndex = filteredDesigns.value.findIndex(d => d.design_id === currentDesign.design_id)
        return currentIndex < filteredDesigns.value.length - 1
    })

    const totalStructures = computed(() => {
        return selectedDesigns.value.reduce((total, design) => {
            return total + (design.pdb_file ? 1 : 0)
        }, 0)
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
        if (direction === 'next' && currentStructureIndex.value < totalStructures.value - 1) {
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

    const viewDesign = (design: Design) => {
        selectedDesigns.value = [design]
        currentStructureIndex.value = 0
    }

    const getCurrentRowPosition = () => {
        if (selectedDesigns.value.length === 0) return '0 / 0'

        const currentDesign = selectedDesigns.value[currentStructureIndex.value]
        const currentIndex = filteredDesigns.value.findIndex(d => d.design_id === currentDesign.design_id)

        if (currentIndex === -1) return '0 / 0'

        // Find the position among designs with PDB files
        const designsWithPdb = filteredDesigns.value.filter(d => d.pdb_file)
        const pdbIndex = designsWithPdb.findIndex(d => d.design_id === currentDesign.design_id)

        return `${pdbIndex + 1} / ${designsWithPdb.length}`
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
        viewDesign,
        getCurrentRowPosition
    }
})
