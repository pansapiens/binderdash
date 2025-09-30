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
              <label>Method:</label>
              <Dropdown 
                v-model="designsStore.filters.method.value" 
                :options="methodOptions" 
                placeholder="Select method"
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
            <div class="filter-row">
              <label>Length Range:</label>
              <div class="length-range">
                <div class="length-inputs">
                  <InputNumber 
                    v-model="lengthMin" 
                    :min="lengthRange[0]"
                    :max="lengthRange[1]"
                    @update:modelValue="updateLengthFromInputs"
                    placeholder="Min"
                    class="filter-input-small"
                  />
                  <span class="range-separator">to</span>
                  <InputNumber 
                    v-model="lengthMax" 
                    :min="lengthRange[0]"
                    :max="lengthRange[1]"
                    @update:modelValue="updateLengthFromInputs"
                    placeholder="Max"
                    class="filter-input-small"
                  />
                </div>
                <Slider 
                  v-model="lengthRangeValue"
                  :min="lengthRange[0]"
                  :max="lengthRange[1]"
                  range
                  class="length-slider"
                />
              </div>
            </div>
            <div class="filter-row">
              <label>Target Sequence:</label>
              <InputText 
                v-model="designsStore.filters.target_sequence.value" 
                placeholder="Search target sequences (regex)..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Best MPNN only:</label>
              <Checkbox 
                :modelValue="designsStore.bestMpnnOnly"
                @update:modelValue="designsStore.toggleBestMpnnOnly"
                :binary="true"
                inputId="best-mpnn-only"
              />
              <label for="best-mpnn-only" class="ml-2">Show only best MPNN variant per backbone</label>
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
          :selectOnClick="false"
          @row-click="onRowClick"
        >
          <template #header>
            <div class="flex justify-content-between align-items-center">
              <span class="text-xl font-bold">All Designs</span>
              <div class="flex gap-2 align-items-center">
                <Button 
                  icon="pi pi-table" 
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
                <div class="flex align-items-start gap-3">
                  <div class="flex flex-column gap-2">
                    <SplitButton 
                      :model="exportMenuItems"
                      label="Download TSV"
                      icon="pi pi-download"
                      dropdownIcon="pi pi-chevron-down"
                      @click="onDownloadTsv"
                      size="small"
                    />
                    <div class="flex align-items-center gap-1">
                      <Checkbox 
                        :modelValue="exportIncludeAllColumns"
                        @update:modelValue="val => exportIncludeAllColumns = !!val"
                        :binary="true"
                        inputId="include-all-cols"
                      />
                      <label for="include-all-cols" class="text-sm">Include all columns</label>
                    </div>
                  </div>
                  <div class="select-top-controls">
                    <label for="select-top-count" class="text-sm font-medium">Select top:</label>
                    <InputNumber 
                      v-model="selectTopCount"
                      :min="1"
                      :max="designsStore.filteredDesigns.length"
                      placeholder="N"
                      size="small"
                      inputId="select-top-count"
                      class="select-top-input"
                      @input="(event) => selectTopCount = Number(event.value)"
                    />
                    <Button 
                      label="Select"
                      @click="selectTopRows"
                      size="small"
                      :disabled="!selectTopCount || selectTopCount < 1"
                    />
                  </div>
                </div>
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

          <!-- Selection column -->
          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>

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

          <Column header="Actions" style="width: 180px" :exportable="false">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button 
                  icon="pi pi-eye" 
                  size="small"
                  @click="viewDesign(data)"
                  rounded
                  tooltip="View Structure"
                />
                <Button 
                  icon="pi pi-download" 
                  size="small"
                  @click="downloadPdb(data)"
                  rounded
                  tooltip="Download PDB"
                />
                <Button 
                  icon="pi pi-code" 
                  size="small"
                  @click="openParamsDialog(data)"
                  rounded
                  :disabled="!data?.params"
                  tooltip="View Params JSON"
                />
              </div>
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
            <div class="details-section">
              <div class="details-section-title">Design Data</div>
              <div class="details-grid">
                <div class="detail-item">
                  <div class="detail-label">Design</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.design_id }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Project</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.project_id }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Run</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.run_name }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Method</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.method }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Length</div>
                  <div class="detail-value">{{ getLengthValue(designsStore.currentStructure.design) }}</div>
                </div>
                <div class="detail-item file-item">
                  <div class="detail-label">File</div>
                  <div class="detail-value file-value">
                    <span class="file-name truncate-ellipsis" :title="designsStore.currentStructure.filename">{{ designsStore.currentStructure.filename }}</span>
                    <Button 
                      icon="pi pi-download" 
                      size="small"
                      rounded
                      @click.stop="downloadCurrentPdb"
                      :aria-label="`Download ${designsStore.currentStructure.filename}`"
                      v-tooltip.top="'Download PDB'"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div class="details-section">
              <div class="details-section-title">Scores</div>
              <div class="details-grid">
                <template v-for="scoreField in displayScores" :key="scoreField">
                  <div
                    v-if="hasValidValue(designsStore.currentStructure.design[scoreField])"
                    class="detail-item"
                  >
                    <div class="score-bar" :style="{ backgroundColor: scoreColor(scoreField, designsStore.currentStructure.design[scoreField]) }"></div>
                    <div class="detail-label">{{ formatScoreHeader(scoreField) }}</div>
                    <div class="detail-value">{{ formatScore(designsStore.currentStructure.design[scoreField]) }}</div>
                  </div>
                </template>
              </div>
            </div>
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
  
  <Dialog 
    v-model:visible="showParamsDialog" 
    modal 
    header="Run Parameters"
    :style="{ width: '60vw', maxWidth: '900px' }"
  >
    <div v-if="currentParamsJson" class="params-json-container">
      <pre class="params-pre">{{ currentParamsJson }}</pre>
    </div>
    <div v-else class="text-center p-3">No params available for this design</div>
  </Dialog>
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
import Slider from 'primevue/slider'
import SplitButton from 'primevue/splitbutton'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import Dialog from 'primevue/dialog'
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
const exportIncludeAllColumns = ref(false)
const selectTopCount = ref<number | null>(null)
const exportMenuItems = ref([
  { label: 'Download CSV', icon: 'pi pi-download', command: () => onDownloadCsv() },
  { label: 'Download PDBs', icon: 'pi pi-box', command: () => onDownloadPdbs() }
])

// Params dialog state
const showParamsDialog = ref(false)
const currentParamsJson = ref<string>('')

// Filter options
const methodOptions = ref(['bindcraft', 'rfd'])

// Length filter state
const lengthRange = ref([0, 300]) // Default range, will be updated based on data
const lengthMin = ref(0)
const lengthMax = ref(300)

// Primary scores to display in structure details
const primaryScores = ref(['Average_i_pTM', 'pae_interaction'])
const secondaryScores = ref(['Average_Binder_pLDDT', 'plddt_binder'])
// const binderRMSD = ref(['Average_Binder_RMSD', 'binder_aligned_rmsd'])

// Human-readable field name mapping
const niceFieldNames: Record<string, string> = {
  'Average_i_pTM': 'Average i-pTM',
  'pae_interaction': 'PAE Interaction',
  'Average_Binder_RMSD': 'Average Binder RMSD',
  'Average_Target_RMSD': 'Average Target RMSD',
  'Average_Binder_pLDDT': 'Average Binder pLDDT',
  'plddt_binder': 'Binder pLDDT',
  'binder_aligned_rmsd': 'Binder Aligned RMSD'
}

// Computed properties using store
const isColumnVisible = (field: string): boolean => {
  return designsStore.visibleColumns.includes(field)
}

// Computed properties for length filtering
const lengthRangeValue = computed({
  get: () => [designsStore.filters.length_min.value || lengthMin.value, designsStore.filters.length_max.value || lengthMax.value],
  set: (value: number[]) => {
    designsStore.filters.length_min.value = value[0]
    designsStore.filters.length_max.value = value[1]
    lengthMin.value = value[0]
    lengthMax.value = value[1]
  }
})


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

const onRowClick = (event: any): void => {
  // Only trigger view if the click wasn't on a button or checkbox
  const target = event.originalEvent.target as HTMLElement
  const isButton = target.closest('button') || target.closest('.p-button')
  const isCheckbox = target.closest('.p-checkbox') || target.closest('input[type="checkbox"]')
  
  // Don't trigger view if clicking on buttons or checkboxes
  if (!isButton && !isCheckbox) {
    // Prevent the default row selection behavior
    event.originalEvent.preventDefault()
    event.originalEvent.stopPropagation()
    
    // Just view the design without affecting selection
    viewDesign(event.data)
  }
}

const downloadPdb = async (design: any): Promise<void> => {
  try {
    // Use the store's helper function to extract filename
    const filename = designsStore.extractFilename(design.pdb_file)
    
    if (!filename) {
      throw new Error('No PDB file found for this design')
    }
    
    // Get the PDB URL for this design
    const pdbUrl = runsApi.getPdbFileUrl(design.run_id, filename)
    
    // Create a temporary anchor element to trigger download
    const link = document.createElement('a')
    link.href = pdbUrl
    link.download = filename
    link.target = '_blank'
    
    // Append to body, click, and remove
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    toast.add({
      severity: 'success',
      summary: 'Download Started',
      detail: `Downloading ${filename}`,
      life: 3000
    })
  } catch (error: any) {
    console.error('Error downloading PDB:', error)
    toast.add({
      severity: 'error',
      summary: 'Download Failed',
      detail: error.message || 'Failed to download PDB file',
      life: 3000
    })
  }
}

const openParamsDialog = (design: any): void => {
  try {
    const params = design?.params
    currentParamsJson.value = params ? JSON.stringify(params, null, 2) : ''
    showParamsDialog.value = true
  } catch (err) {
    currentParamsJson.value = ''
    showParamsDialog.value = true
  }
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

const selectTopRows = () => {
  if (!selectTopCount.value || selectTopCount.value < 1) {
    return
  }
  
  // Get the currently filtered and sorted designs
  const sortedDesigns = designsStore.filteredDesigns
  
  // Select the top N rows based on current sorting
  const topRows = sortedDesigns.slice(0, selectTopCount.value)
  
  // Update the store's selected designs
  designsStore.selectedDesigns = topRows
  
  toast.add({
    severity: 'success',
    summary: 'Selection Updated',
    detail: `Selected top ${selectTopCount.value} designs`,
    life: 2000
  })
}

// Export helpers
const getRowsToExport = () => {
  const selected = designsStore.selectedDesigns
  return (selected && selected.length > 0) ? selected : designsStore.filteredDesigns
}

const getColumnsToExport = () => {
  const replaceRunId = (cols: string[]) => {
    return cols.map(c => (c === 'run_id' ? 'binderdash_run_id' : c)).filter((v, i, a) => a.indexOf(v) === i)
  }

  if (exportIncludeAllColumns.value) {
    // All distinct keys across rows
    const rows = getRowsToExport()
    const keySet = new Set<string>()
    rows.forEach((r: any) => Object.keys(r).forEach(k => keySet.add(k)))
    return replaceRunId(Array.from(keySet))
  }
  return replaceRunId(designsStore.visibleColumns)
}

const toSeparatedValues = (rows: any[], cols: string[], sep: string): string => {
  const esc = (v: any) => {
    if (v == null) return ''
    const s = String(v)
    return sep === ',' && /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const header = cols.join(sep)
  const valueFor = (r: any, c: string) => {
    if (c === 'binderdash_run_id') return r['run_id']
    return r[c]
  }
  const lines = rows.map(r => cols.map(c => esc(valueFor(r, c))).join(sep))
  return [header, ...lines].join('\n')
}

const downloadBlob = (blob: Blob, filename: string) => {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const onDownloadCsv = () => {
  const rows = getRowsToExport()
  const cols = getColumnsToExport()
  const content = toSeparatedValues(rows as any[], cols as string[], ',')
  downloadBlob(new Blob([content], { type: 'text/csv;charset=utf-8' }), 'designs.csv')
}

const onDownloadTsv = () => {
  const rows = getRowsToExport()
  const cols = getColumnsToExport()
  const content = toSeparatedValues(rows as any[], cols as string[], '\t')
  downloadBlob(new Blob([content], { type: 'text/tab-separated-values;charset=utf-8' }), 'designs.tsv')
}

const onDownloadPdbs = async () => {
  try {
    const rows = getRowsToExport().filter((d: any) => d.pdb_file)
    if (rows.length === 0) {
      toast.add({ severity: 'warn', summary: 'No PDBs', detail: 'No PDB files to download', life: 2500 })
      return
    }
    const items = rows.map((d: any) => ({ run_id: d.run_id, filename: designsStore.extractFilename(d.pdb_file) }))
    const blob = await runsApi.downloadPdbsTar(items)
    downloadBlob(blob, 'designs_pdbs.tar')
  } catch (err: any) {
    console.error('Error downloading PDBs tar:', err)
    toast.add({ severity: 'error', summary: 'Download Failed', detail: err?.message || 'Failed to download PDBs', life: 3000 })
  }
}

// Length filter methods
const updateLengthFromInputs = () => {
  designsStore.filters.length_min.value = lengthMin.value
  designsStore.filters.length_max.value = lengthMax.value
}

const updateLengthRange = () => {
  // Update the length range based on available data
  if (designsStore.designs.length > 0) {
    const lengths = designsStore.designs
      .map(design => design.Length || design.length)
      .filter(length => length != null && !isNaN(Number(length)))
      .map(length => Number(length))
    
    if (lengths.length > 0) {
      const minLength = Math.min(...lengths)
      const maxLength = Math.max(...lengths)
      lengthRange.value = [minLength, maxLength]
      
      // Set initial values if not already set
      if (designsStore.filters.length_min.value == null) {
        lengthMin.value = minLength
        designsStore.filters.length_min.value = minLength
      }
      if (designsStore.filters.length_max.value == null) {
        lengthMax.value = maxLength
        designsStore.filters.length_max.value = maxLength
      }
    }
  }
}

const getPdbUrl = () => {
  if (!designsStore.currentStructure) return ''
  return runsApi.getPdbFileUrl(designsStore.currentStructure.design.run_id, designsStore.currentStructure.filename)
}

const downloadCurrentPdb = async (): Promise<void> => {
  try {
    if (!designsStore.currentStructure) return
    const filename = designsStore.currentStructure.filename
    const runId = designsStore.currentStructure.design.run_id
    if (!filename || !runId) return
    const pdbUrl = runsApi.getPdbFileUrl(runId, filename)
    const link = document.createElement('a')
    link.href = pdbUrl
    link.download = filename
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast.add({ severity: 'success', summary: 'Download Started', detail: `Downloading ${filename}` , life: 2500 })
  } catch (error: any) {
    console.error('Error downloading PDB:', error)
    toast.add({ severity: 'error', summary: 'Download Failed', detail: error?.message || 'Failed to download PDB file', life: 3000 })
  }
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

// Display scores list (order as requested plus existing primary)
const displayScores = ref([
  'Average_i_pTM',
  'Average_Binder_RMSD',
  'Average_Target_RMSD',
  'Average_Binder_pLDDT',
  'pae_interaction',
  'plddt_binder',
  'binder_aligned_rmsd'
])

const getLengthValue = (design: any): string | number => {
  const len = design?.Length ?? design?.length
  return (len != null && !isNaN(Number(len))) ? Number(len) : ''
}


// Score colour utilities
const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const colorFromT = (t: number): string => {
  // t in [0,1], map 0=red (#e74c3c), 0.5=amber (#f1c40f), 1=green (#2ecc71)
  const r1 = 231, g1 = 76, b1 = 60
  const r2 = 241, g2 = 196, b2 = 15
  const r3 = 46, g3 = 204, b3 = 113
  if (t <= 0.5) {
    const k = t / 0.5
    const r = Math.round(lerp(r1, r2, k))
    const g = Math.round(lerp(g1, g2, k))
    const b = Math.round(lerp(b1, b2, k))
    return `rgb(${r}, ${g}, ${b})`
  } else {
    const k = (t - 0.5) / 0.5
    const r = Math.round(lerp(r2, r3, k))
    const g = Math.round(lerp(g2, g3, k))
    const b = Math.round(lerp(b2, b3, k))
    return `rgb(${r}, ${g}, ${b})`
  }
}

const scoreColor = (field: string, raw: any): string => {
  const v = Number(raw)
  if (!isFinite(v)) return '#dfe6e9'

  // Field-specific ranges and whether higher is better
  const config: Record<string, { min: number, max: number, higherBetter: boolean }> = {
    'Average_i_pTM': { min: 0, max: 1, higherBetter: true },
    'Average_Binder_pLDDT': { min: 0, max: 100, higherBetter: true },
    'plddt_binder': { min: 0, max: 100, higherBetter: true },
    'pae_interaction': { min: 0, max: 20, higherBetter: false },
    'Average_Binder_RMSD': { min: 0, max: 3.5, higherBetter: false },
    'Average_Target_RMSD': { min: 0, max: 3.5, higherBetter: false },
    'binder_aligned_rmsd': { min: 0, max: 3.5, higherBetter: false }
  }

  const cfg = config[field]
  if (!cfg) return '#dfe6e9'
  const span = Math.max(1e-9, cfg.max - cfg.min)
  let t = clamp01((v - cfg.min) / span)
  if (!cfg.higherBetter) t = 1 - t
  return colorFromT(t)
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

// Update length range when designs are loaded
watch(() => designsStore.designs, () => {
  updateLengthRange()
}, { deep: true, immediate: true })

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

.length-range {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  max-width: 400px;
}

.length-inputs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.length-slider {
  width: 100%;
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

.details-section {
  margin-bottom: 0.75rem;
}

.details-section-title {
  font-weight: 600;
  color: #495057;
  margin-bottom: 0.5rem;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  background: #ffffff;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
}

.detail-item.clickable {
  cursor: pointer;
}

.score-bar {
  height: 6px;
  border-radius: 3px;
  margin-bottom: 0.25rem;
}

.detail-label {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.detail-value {
  font-size: 1rem;
  color: #343a40;
  font-weight: 600;
  word-break: break-all;
}

.file-item .file-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.truncate-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-item:hover {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  border-color: #e2e6ea;
}

/* Removed full-width spanning for file item to match other cards */

.file-value {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  /* Assume ~8px per char average for this font size; 128 chars ≈ 1024px */
  max-width: 1024px;
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

:deep(.p-datatable .p-datatable-tbody > tr) {
  cursor: pointer;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  user-select: none;
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

/* Action buttons styling */
.action-buttons {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.params-json-container {
  max-height: 70vh;
  overflow: auto;
}

.params-pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.9rem;
  margin: 0;
}

/* Select top controls styling */
.select-top-input {
  width: 60px;
  min-width: 60px;
}

.select-top-input :deep(.p-inputnumber-input) {
  text-align: center;
  width: 100%;
}

.select-top-controls {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
}
</style>
