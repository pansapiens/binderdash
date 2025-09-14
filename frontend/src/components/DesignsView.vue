<template>
  <div class="designs-view">
    <div class="designs-header">
      <h2>Designs</h2>
      <div class="designs-controls">
        <!-- Controls removed - designs now auto-sync with selected runs -->
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
            <div v-for="col in designsStore.columns" :key="col.field" class="column-toggle">
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
                v-model="designsStore.filters.global.value" 
                placeholder="Search all columns..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Design ID:</label>
              <InputText 
                v-model="designsStore.filters.design_id.value" 
                placeholder="Filter by design ID..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Project ID:</label>
              <InputText 
                v-model="designsStore.filters.project_id.value" 
                placeholder="Filter by project ID..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Run Name:</label>
              <InputText 
                v-model="designsStore.filters.run_name.value" 
                placeholder="Filter by run name..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Protocol:</label>
              <Dropdown 
                v-model="designsStore.filters.protocol.value" 
                :options="protocolOptions" 
                placeholder="Select protocol"
                class="filter-input"
                showClear
              />
            </div>
            <div class="filter-row">
              <label>Score Range:</label>
              <div class="score-range">
                <InputNumber 
                  v-model="designsStore.filters.score_min.value" 
                  placeholder="Min"
                  class="filter-input-small"
                />
                <span class="range-separator">to</span>
                <InputNumber 
                  v-model="designsStore.filters.score_max.value" 
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
          :key="`designs-table-${designsStore.selectedRunIds.length}-${designsStore.filteredDesigns.length}`"
          :value="designsStore.filteredDesigns" 
          :loading="designsStore.loading"
          v-model:selection="designsStore.selectedDesigns"
          selectionMode="multiple"
          dataKey="design_id"
          stripedRows
          paginator
          :rows="10"
          :rowsPerPageOptions="[10, 20, 50, 100]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="Showing {first} to {last} of {totalRecords} designs"
          showGridlines
          :resizableColumns="true"
          columnResizeMode="fit"
          :reorderableColumns="true"
          :reorderableRows="true"
          :rowHover="true"
          :scrollable="true"
          scrollHeight="800px"
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
              <p>Scan some folders and select runs to see designs here</p>
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
            v-for="col in getVisibleColumns()" 
            :key="col.field"
            :field="col.field" 
            :header="col.header"
            :sortable="col.sortable"
            :filter="col.filter"
            :filterType="col.filterType || 'text'"
            :showFilterMenu="col.showFilterMenu"
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
      <div v-if="designsStore.selectedDesigns.length > 0" class="structure-viewer-section">
        <div class="viewer-header">
          <h3>Structure Viewer</h3>
          <div class="viewer-controls">
            <Button 
              icon="pi pi-chevron-left" 
              @click="navigateToPreviousRow"
              :disabled="!designsStore.canNavigatePrevious"
              text
              rounded
            />
            <span class="structure-counter">
              {{ getCurrentRowPosition() }}
            </span>
            <Button 
              icon="pi pi-chevron-right" 
              @click="navigateToNextRow"
              :disabled="!designsStore.canNavigateNext"
              text
              rounded
            />
            <Button 
              :icon="isSpinning ? 'pi pi-pause' : 'pi pi-play'" 
              @click="toggleSpin"
              text
              rounded
              :tooltip="isSpinning ? 'Pause Rotation' : 'Start Rotation'"
            />
          </div>
        </div>

        <div class="structure-info">
          <div v-if="designsStore.currentStructure" class="structure-details">
            <table class="structure-details-table">
              <tbody>
                <tr>
                  <th>Design</th>
                  <td>{{ designsStore.currentStructure.design.design_id }}</td>
                </tr>
                <tr>
                  <th>Project</th>
                  <td>{{ designsStore.currentStructure.design.project_id }}</td>
                </tr>
                <tr>
                  <th>Run</th>
                  <td>{{ designsStore.currentStructure.design.run_name }}</td>
                </tr>
                <tr>
                  <th>Protocol</th>
                  <td>{{ designsStore.currentStructure.design.protocol }}</td>
                </tr>
                <template 
                  v-for="scoreField in primaryScores" 
                  :key="scoreField"
                >
                  <tr v-if="hasValidValue(designsStore.currentStructure.design[scoreField])">
                    <th>{{ formatScoreHeader(scoreField) }}</th>
                    <td>{{ formatScore(designsStore.currentStructure.design[scoreField]) }}</td>
                  </tr>
                </template>
                <tr>
                  <th>File</th>
                  <td>{{ designsStore.currentStructure.filename }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <MolstarViewer 
          v-if="designsStore.currentStructure"
          :pdb-url="getPdbUrl()"
          :structure-info="designsStore.currentStructure"
          :auto-focus="true"
          :show-controls="true"
          ref="molstarViewerRef"
        />
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

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import MolstarViewer from './MolstarViewer.vue'
import { runsApi } from '../webapi'
import { useDesignsStore, useAppStore, useAuthStore, useFolderStore } from '../stores'

const toast = useToast()

// Use Pinia stores
const designsStore = useDesignsStore()
const appStore = useAppStore()
const authStore = useAuthStore()
const folderStore = useFolderStore()

// Local UI state (not shared across components)
const showColumnSelector = ref(false)
const showFilterPanel = ref(false)
const molstarViewerRef = ref<any>(null)
const isSpinning = ref(false)

// Filter options
const protocolOptions = ref(['bindcraft', 'rfd'])

// Primary scores to display in structure details
const primaryScores = ref(['Average_i_pTM', 'pae_interaction'])

// Human-readable field name mapping
const niceFieldNames: Record<string, string> = {
  'Average_i_pTM': 'Average i-pTM',
  'pae_interaction': 'PAE Interaction'
}

// Computed properties using store
const isColumnVisible = (field: string): boolean => {
  return designsStore.visibleColumns.includes(field)
}


// Methods

const loadDesigns = async () => {
  // Only load designs if authentication allows it
  if (!authStore.canLoadData) {
    console.log('Authentication required - skipping designs load')
    return
  }

  try {
    await designsStore.fetchDesigns()
  } catch (error: any) {
    console.error('Error loading designs:', error)
    // Don't show toast for authentication errors - user will be redirected to login
    if (error?.message !== 'Authentication required') {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Failed to load designs',
        life: 3000
      })
    }
  }
}

const viewDesign = (design: any): void => {
  designsStore.viewDesign(design)
}

const navigateToNextRow = () => {
  designsStore.navigateStructure('next')
}

const navigateToPreviousRow = () => {
  designsStore.navigateStructure('previous')
}

const getCurrentRowPosition = () => {
  return designsStore.getCurrentRowPosition()
}

const toggleSpin = async () => {
  if (molstarViewerRef.value) {
    await molstarViewerRef.value.toggleSpin()
    // Update local state to reflect the change
    isSpinning.value = molstarViewerRef.value.isSpinning
  }
}

const toggleColumnSelector = () => {
  showColumnSelector.value = !showColumnSelector.value
}

const toggleFilterPanel = () => {
  showFilterPanel.value = !showFilterPanel.value
}

// Removed duplicate function - using the one defined above

const toggleColumn = (field: string): void => {
  designsStore.toggleColumn(field)
}

const clearFilters = () => {
  designsStore.clearFilters()
}

const applyFilters = () => {
  // Filters are automatically applied through the DataTable's filter system
  // This method can be used for additional custom filtering logic if needed
  console.log('Filters applied:', designsStore.filters)
}

const getPdbUrl = () => {
  if (!designsStore.currentStructure) return ''
  return runsApi.getPdbFileUrl(designsStore.currentStructure.design.run_id, designsStore.currentStructure.filename)
}

const hasValidValue = (value: any): boolean => {
  return value !== null && value !== undefined && value !== '' && !isNaN(Number(value))
}

const formatScore = (value: any): string => {
  if (!hasValidValue(value)) return ''
  const num = Number(value)
  return num.toFixed(3)
}

const formatScoreHeader = (fieldName: string): string => {
  // Convert field names to user-friendly headers
  return niceFieldNames[fieldName] || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}


const getVisibleColumns = () => {
  // If columns haven't been loaded yet, return empty array
  if (designsStore.columns.length === 0) {
    return []
  }
  
  // Filter the full column configuration to only show visible columns
  return designsStore.columns.filter((col: any) => 
    designsStore.visibleColumns.includes(col.field)
  )
}


// Watchers
watch(() => authStore.canLoadData, (canLoad) => {
  if (canLoad && designsStore.designs.length === 0) {
    loadDesigns()
  }
}, { immediate: true })

// Watch for changes in selected runs and update designs store
watch(() => folderStore.selectedRuns, (newSelectedRuns) => {
  if (newSelectedRuns && newSelectedRuns.length > 0) {
    // Update the designs store with the selected run IDs
    const runIds = newSelectedRuns.map(run => run.run_id)
    designsStore.setSelectedRunIds(runIds)
  } else {
    // Clear the run filter if no runs are selected
    designsStore.setSelectedRunIds([])
  }
}, { deep: true, immediate: true })

// Sync spinning state when viewer changes
watch(() => molstarViewerRef.value?.isSpinning, (newSpinningState) => {
  if (newSpinningState !== undefined) {
    isSpinning.value = newSpinningState
  }
}, { immediate: true })

// Lifecycle
onMounted(() => {
  // Only load if authentication allows it
  if (authStore.canLoadData) {
    loadDesigns()
  }
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

.structure-details-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.structure-details-table th {
  text-align: left;
  font-weight: 600;
  color: #495057;
  padding: 0.25rem 0.5rem 0.25rem 0;
  min-width: 80px;
}

.structure-details-table td {
  color: #6c757d;
  padding: 0.25rem 0;
  word-break: break-all;
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
