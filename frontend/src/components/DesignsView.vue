<template>
  <div class="designs-view">
    <div class="designs-header">
      <h2>Designs</h2>
      <div class="designs-controls">
        <Button 
          label="Refresh Designs" 
          icon="pi pi-refresh" 
          @click="loadDesigns"
          :loading="loading"
        />
        <Button 
          label="Clear Cache" 
          icon="pi pi-trash" 
          @click="clearCache"
          severity="danger"
        />
      </div>
    </div>

          <div class="designs-content">
        <!-- Column Selector Panel moved to top -->
        <div v-if="showColumnSelector" class="column-selector-panel">
          <div class="column-selector-header">
            <h3>Toggle Columns</h3>
            <Button 
              icon="pi pi-times" 
              @click="toggleColumnSelector"
              rounded
              variant="outlined"
              aria-label="Close column selector"
              class="close-button"
            />
          </div>
          <div class="column-toggles">
            <div v-for="col in allColumns" :key="col.field" class="column-toggle">
              <Checkbox 
                :modelValue="isColumnVisible(col.field)"
                @update:modelValue="toggleColumn(col.field)"
                :binary="true"
                :inputId="'col-' + col.field"
              />
              <label :for="'col-' + col.field" class="ml-2">{{ col.header }}</label>
            </div>
          </div>
        </div>

        <!-- Filter Panel -->
        <div v-if="showFilterPanel" class="filter-panel">
          <div class="filter-panel-header">
            <h3>Filters</h3>
            <Button 
              icon="pi pi-times" 
              @click="toggleFilterPanel"
              rounded
              variant="outlined"
              aria-label="Close filter panel"
              class="close-button"
            />
          </div>
          <div class="filter-controls">
            <div class="filter-row">
              <label>Global Search:</label>
              <InputText 
                v-model="filters.global.value" 
                placeholder="Search all columns..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Design ID:</label>
              <InputText 
                v-model="filters.design_id.value" 
                placeholder="Filter by design ID..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Run Type:</label>
              <Dropdown 
                v-model="filters.run_type.value" 
                :options="runTypeOptions" 
                placeholder="Select run type"
                class="filter-input"
                showClear
              />
            </div>
            <div class="filter-row">
              <label>Score Range:</label>
              <div class="score-range">
                <InputNumber 
                  v-model="filters.score_min.value" 
                  placeholder="Min"
                  class="filter-input-small"
                />
                <span class="range-separator">to</span>
                <InputNumber 
                  v-model="filters.score_max.value" 
                  placeholder="Max"
                  class="filter-input-small"
                />
              </div>
            </div>
            <div class="filter-actions">
              <Button 
                label="Clear Filters" 
                @click="clearFilters"
                outlined
                size="small"
              />
              <Button 
                label="Apply Filters" 
                @click="applyFilters"
                size="small"
              />
            </div>
          </div>
        </div>

        <div class="designs-table-section">
          <DataTable 
          :value="designs" 
          :loading="loading"
          v-model:selection="selectedDesigns"
          selectionMode="multiple"
          dataKey="design_id"
          stripedRows
          paginator
          :rows="20"
          :rowsPerPageOptions="[10, 20, 50, 100]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="Showing {first} to {last} of {totalRecords} designs"
          :filters="filters"
          filterDisplay="row"
          :globalFilterFields="['design_id', 'run_name', 'run_type', 'pae_interaction', 'Average_i_pTM']"
          showGridlines
          :resizableColumns="true"
          columnResizeMode="fit"
          :reorderableColumns="true"
          :reorderableRows="true"
          :rowHover="true"
          :scrollable="true"
          scrollHeight="400px"
        >
          <template #header>
            <div class="flex justify-content-between align-items-center">
              <span class="text-xl font-bold">All Designs</span>
              <div class="flex gap-2">
                <Button 
                  icon="pi pi-columns" 
                  @click="toggleColumnSelector"
                  text
                  rounded
                  :class="{ 'p-button-outlined': showColumnSelector }"
                />
                <Button 
                  icon="pi pi-filter" 
                  @click="toggleFilterPanel"
                  text
                  rounded
                  :class="{ 'p-button-outlined': showFilterPanel }"
                />
              </div>
            </div>
          </template>

          <template #empty>
            <div class="text-center p-4">
              <i class="pi pi-table" style="font-size: 3rem; color: #6c757d;"></i>
              <h3>No Designs Found</h3>
              <p>Scan some folders to discover designs</p>
            </div>
          </template>

          <template #loading>
            <div class="text-center p-4">
              <i class="pi pi-spinner pi-spin" style="font-size: 2rem; color: #667eea;"></i>
              <p>Loading designs...</p>
            </div>
          </template>

          <!-- Dynamic columns based on available data -->
          <Column 
            v-for="col in visibleColumns" 
            :key="col.field"
            :field="col.field" 
            :header="col.header"
            :sortable="col.sortable"
            :filter="true"
            :filterType="col.filterType || 'text'"
            :showFilterMenu="false"
            :style="col.style"
            :class="col.class"
          >
            <template #body="{ data }" v-if="col.template">
              <component :is="col.template" :data="data" :field="col.field" />
            </template>
          </Column>

          <Column header="Actions" style="width: 120px" :exportable="false">
            <template #body="{ data }">
              <Button 
                icon="pi pi-eye" 
                size="small"
                @click="viewDesign(data)"
                text
                rounded
                tooltip="View Structure"
              />
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Structure Viewer Section -->
      <div v-if="selectedDesigns.length > 0" class="structure-viewer-section">
        <div class="viewer-header">
          <h3>Structure Viewer</h3>
          <div class="viewer-controls">
            <Button 
              icon="pi pi-chevron-left" 
              @click="previousStructure"
              :disabled="currentStructureIndex <= 0"
              text
              rounded
            />
            <span class="structure-counter">
              {{ currentStructureIndex + 1 }} / {{ totalStructures }}
            </span>
            <Button 
              icon="pi pi-chevron-right" 
              @click="nextStructure"
              :disabled="currentStructureIndex >= totalStructures - 1"
              text
              rounded
            />
          </div>
        </div>

        <div class="structure-info">
          <div v-if="currentStructure" class="structure-details">
            <p><strong>Design:</strong> {{ currentStructure.design.design_id }}</p>
            <p><strong>Run:</strong> {{ currentStructure.design.run_name }}</p>
            <p><strong>Type:</strong> {{ currentStructure.design.run_type }}</p>
            <p><strong>File:</strong> {{ currentStructure.filename }}</p>
          </div>
        </div>

        <div class="molstar-container">
          <div ref="molstarContainer" class="molstar-viewer"></div>
        </div>
      </div>

      <div v-else class="no-selection">
        <div class="no-selection-content">
          <i class="pi pi-cube" style="font-size: 3rem; color: #6c757d;"></i>
          <h3>No Structures Selected</h3>
          <p>Select one or more designs from the table above to view structures</p>
        </div>
      </div>
    </div>
    
    <Toast />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'

const toast = useToast()

// State
const designs = ref([])
const selectedDesigns = ref([])
const loading = ref(false)
const currentStructureIndex = ref(0)
const molstarContainer = ref(null)
const showColumnSelector = ref(false)
const showFilterPanel = ref(false)

// Filter state
const filters = ref({
  global: { value: null, matchMode: 'contains' },
  design_id: { value: null, matchMode: 'contains' },
  run_type: { value: null, matchMode: 'equals' },
  score_min: { value: null, matchMode: 'gte' },
  score_max: { value: null, matchMode: 'lte' }
})

// Filter options
const runTypeOptions = ref(['bindcraft', 'rfd'])

// Column configuration
const allColumns = ref([
  { field: 'design_id', header: 'Design ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 150px' },
  { field: 'run_name', header: 'Run Name', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
  { field: 'run_type', header: 'Run Type', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 100px' },
  { field: 'pae_interaction', header: 'PAE Interaction', sortable: true, filter: true, filterType: 'numeric', showFilterMenu: false, style: 'min-width: 120px' },
  { field: 'Average_i_pTM', header: 'Average i_pTM', sortable: true, filter: true, filterType: 'numeric', showFilterMenu: false, style: 'min-width: 120px' },
  { field: 'pdb_file', header: 'PDB File', sortable: false, filter: false, style: 'min-width: 200px' },
  { field: 'run_path', header: 'Run Path', sortable: false, filter: false, style: 'min-width: 200px' }
])

// Function to build columns dynamically from data
const buildColumnsFromData = (designs) => {
  if (!designs || designs.length === 0) return allColumns.value
  
  const baseColumns = [
    { field: 'design_id', header: 'Design ID', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 150px' },
    { field: 'run_name', header: 'Run Name', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 120px' },
    { field: 'run_type', header: 'Run Type', sortable: true, filter: true, filterType: 'text', showFilterMenu: false, style: 'min-width: 100px' }
  ]
  
  // Add score columns if they exist in the data
  const scoreColumns = []
  if (designs.some(d => 'pae_interaction' in d)) {
    scoreColumns.push({ field: 'pae_interaction', header: 'PAE Interaction', sortable: true, filter: true, filterType: 'numeric', showFilterMenu: false, style: 'min-width: 120px' })
  }
  if (designs.some(d => 'Average_i_pTM' in d)) {
    scoreColumns.push({ field: 'Average_i_pTM', header: 'Average i_pTM', sortable: true, filter: true, filterType: 'numeric', showFilterMenu: false, style: 'min-width: 120px' })
  }
  
  const metadataColumns = [
    { field: 'pdb_file', header: 'PDB File', sortable: false, filter: false, style: 'min-width: 200px' },
    { field: 'run_path', header: 'Run Path', sortable: false, filter: false, style: 'min-width: 200px' }
  ]
  
  // Add other columns from the data (excluding already defined ones)
  const existingFields = new Set([
    'design_id', 'run_name', 'run_type', 'pae_interaction', 'Average_i_pTM', 
    'pdb_file', 'run_path', 'run_id', 'project_id'
  ])
  
  const otherColumns = []
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

// Default visible columns
const defaultVisibleColumns = ref(['design_id', 'run_name', 'run_type', 'pae_interaction', 'Average_i_pTM'])

// Computed
const visibleColumns = computed(() => {
  return allColumns.value.filter(col => isColumnVisible(col.field))
})

const isColumnVisible = (field) => {
  return defaultVisibleColumns.value.includes(field)
}

const totalStructures = computed(() => {
  return selectedDesigns.value.reduce((total, design) => {
    return total + (design.pdb_file ? 1 : 0)
  }, 0)
})

const currentStructure = computed(() => {
  if (selectedDesigns.value.length === 0 || totalStructures.value === 0) {
    return null
  }

  let structureIndex = 0
  for (const design of selectedDesigns.value) {
    if (design.pdb_file) {
      if (structureIndex === currentStructureIndex.value) {
        return {
          design,
          filename: design.pdb_file.split('/').pop(),
          pdbPath: design.pdb_file
        }
      }
      structureIndex++
    }
  }
  return null
})

// Methods
const loadDesigns = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/designs')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    designs.value = data.designs
    
    // Build columns dynamically from the loaded data
    allColumns.value = buildColumnsFromData(data.designs)
    
    // Update default visible columns to include score columns if they exist
    const newDefaultColumns = ['design_id', 'run_name', 'run_type']
    if (data.designs.some(d => 'pae_interaction' in d)) {
      newDefaultColumns.push('pae_interaction')
    }
    if (data.designs.some(d => 'Average_i_pTM' in d)) {
      newDefaultColumns.push('Average_i_pTM')
    }
    defaultVisibleColumns.value = newDefaultColumns
  } catch (error) {
    console.error('Error loading designs:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load designs',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const clearCache = async () => {
  try {
    const response = await fetch('/api/designs', {
      method: 'DELETE'
    })
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    designs.value = []
    selectedDesigns.value = []
    currentStructureIndex.value = 0
    
    toast.add({
      severity: 'success',
      summary: 'Cache Cleared',
      detail: 'All designs have been removed from cache',
      life: 3000
    })
  } catch (error) {
    console.error('Error clearing cache:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to clear cache',
      life: 3000
    })
  }
}

const viewDesign = (design) => {
  // Select the design and show its structure
  selectedDesigns.value = [design]
  currentStructureIndex.value = 0
}

const previousStructure = () => {
  if (currentStructureIndex.value > 0) {
    currentStructureIndex.value--
  }
}

const nextStructure = () => {
  if (currentStructureIndex.value < totalStructures.value - 1) {
    currentStructureIndex.value++
  }
}

const toggleColumnSelector = () => {
  showColumnSelector.value = !showColumnSelector.value
}

const toggleFilterPanel = () => {
  showFilterPanel.value = !showFilterPanel.value
}

// Removed duplicate function - using the one defined above

const toggleColumn = (field) => {
  const index = defaultVisibleColumns.value.indexOf(field)
  if (index > -1) {
    // Remove column from visible columns
    defaultVisibleColumns.value.splice(index, 1)
  } else {
    // Add column to visible columns
    defaultVisibleColumns.value.push(field)
  }
}

const clearFilters = () => {
  filters.value = {
    global: { value: null, matchMode: 'contains' },
    design_id: { value: null, matchMode: 'contains' },
    run_type: { value: null, matchMode: 'equals' },
    score_min: { value: null, matchMode: 'gte' },
    score_max: { value: null, matchMode: 'lte' }
  }
}

const applyFilters = () => {
  // Filters are automatically applied through the DataTable's filter system
  // This method can be used for additional custom filtering logic if needed
  console.log('Filters applied:', filters.value)
}

const loadMolstarViewer = async () => {
  if (!currentStructure.value || !molstarContainer.value) {
    return
  }

  try {
    // Clear previous viewer
    molstarContainer.value.innerHTML = ''

    // Create a simple placeholder for now
    const placeholder = document.createElement('div')
    placeholder.style.cssText = `
      width: 100%;
      height: 400px;
      background: #f8f9fa;
      border: 2px dashed #dee2e6;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #6c757d;
      font-size: 1.1rem;
    `
    placeholder.innerHTML = `
      <div style="text-align: center;">
        <i class="pi pi-cube" style="font-size: 2rem; margin-bottom: 1rem; display: block;"></i>
        <div>Molstar Viewer</div>
        <div style="font-size: 0.9rem; margin-top: 0.5rem;">
          Loading: ${currentStructure.value.filename}
        </div>
      </div>
    `
    
    molstarContainer.value.appendChild(placeholder)

    // TODO: Implement actual Molstar viewer
    
  } catch (error) {
    console.error('Error loading Molstar viewer:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load structure viewer',
      life: 3000
    })
  }
}

// Watchers
watch(currentStructure, () => {
  nextTick(() => {
    loadMolstarViewer()
  })
})

// Lifecycle
onMounted(() => {
  loadDesigns()
})

// Expose methods to parent component
defineExpose({
  loadDesigns
})
</script>

<style scoped>
.designs-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.designs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.designs-header h2 {
  margin: 0;
  color: #495057;
}

.designs-controls {
  display: flex;
  gap: 0.5rem;
}

.designs-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.designs-table-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
}

.column-selector-panel {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
  border: 1px solid #e9ecef;
  margin-bottom: 1.5rem;
}

.column-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.column-selector-header h3 {
  margin: 0;
  color: #495057;
}

/*
.close-button {
  padding: 0.5rem;
  min-width: auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button .p-button-icon {
  margin-left: 0.125rem;
}
*/

.filter-panel {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
  border: 1px solid #e9ecef;
  margin-bottom: 1.5rem;
}

.filter-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.filter-panel-header h3 {
  margin: 0;
  color: #495057;
}

.filter-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.filter-row label {
  min-width: 120px;
  font-weight: 500;
  color: #495057;
}

.filter-input {
  flex: 1;
  max-width: 300px;
}

.filter-input-small {
  width: 120px;
}

.score-range {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.range-separator {
  color: #6c757d;
  font-weight: 500;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e9ecef;
}

/* Removed duplicate rule - using .column-selector-header h3 above */

.column-toggles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}

.column-toggle {
  display: flex;
  align-items: center;
  padding: 0.5rem;
  border-radius: 4px;
  background: #f8f9fa;
}

.structure-viewer-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.viewer-header h3 {
  margin: 0;
  color: #495057;
}

.viewer-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.structure-counter {
  font-weight: 500;
  color: #495057;
  min-width: 60px;
  text-align: center;
}

.structure-info {
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.structure-details p {
  margin: 0.25rem 0;
  color: #495057;
}

.molstar-container {
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
}

.molstar-viewer {
  width: 100%;
  height: 400px;
}

.no-selection {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 3rem;
}

.no-selection-content {
  text-align: center;
  color: #6c757d;
}

.no-selection-content h3 {
  margin: 1rem 0 0.5rem 0;
  color: #495057;
}

.no-selection-content p {
  margin: 0;
  font-size: 1rem;
}

/* PrimeVue overrides */
:deep(.p-datatable) {
  border: none;
}

:deep(.p-datatable .p-datatable-thead > tr > th) {
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
  font-weight: 600;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  border-bottom: 1px solid #f1f3f4;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover > td) {
  background: #f8f9fa;
}

/* Pagination spacing improvements */
:deep(.p-datatable .p-paginator) {
  padding: 1rem 0;
  gap: 0.5rem;
}

:deep(.p-datatable .p-paginator .p-paginator-pages) {
  gap: 0.25rem;
}

:deep(.p-datatable .p-paginator .p-paginator-pages .p-paginator-page) {
  margin: 0 0.125rem;
}

:deep(.p-datatable .p-paginator .p-paginator-first,
       .p-datatable .p-paginator .p-paginator-prev,
       .p-datatable .p-paginator .p-paginator-next,
       .p-datatable .p-paginator .p-paginator-last) {
  margin: 0 0.25rem;
}

:deep(.p-datatable .p-paginator .p-paginator-current) {
  margin: 0 1rem;
}

:deep(.p-datatable .p-paginator .p-dropdown) {
  margin-left: 0.5rem;
}
</style>
