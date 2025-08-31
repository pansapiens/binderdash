<template>
  <div class="runs-view">
    <div class="runs-header">
      <h2>Runs & Structure Viewer</h2>
      <div class="runs-controls">
        <Button 
          label="Refresh Runs" 
          icon="pi pi-refresh" 
          @click="loadRuns"
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

    <div class="runs-content">
      <div class="runs-table-section">
        <DataTable 
          :value="runs" 
          :loading="loading"
          v-model:selection="selectedRuns"
          selectionMode="multiple"
          dataKey="run_id"
          stripedRows
          paginator
          :rows="10"
          :rowsPerPageOptions="[5, 10, 20, 50]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="Showing {first} to {last} of {totalRecords} runs"
        >
          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
          <Column field="metadata.name" header="Name" sortable></Column>
          <Column field="run_type" header="Type" sortable>
            <template #body="{ data }">
              <Tag :value="data.run_type" :severity="getRunTypeSeverity(data.run_type)" />
            </template>
          </Column>
          <Column field="metadata.pdb_count" header="PDB Files" sortable>
            <template #body="{ data }">
              <Badge :value="data.metadata.pdb_count" severity="info" />
            </template>
          </Column>
          <Column field="path" header="Path">
            <template #body="{ data }">
              <span class="run-path">{{ data.path }}</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <Button 
                icon="pi pi-eye" 
                size="small"
                @click="viewRun(data)"
                text
                rounded
              />
            </template>
          </Column>
        </DataTable>
      </div>

      <div v-if="selectedRuns.length > 0" class="structure-viewer-section">
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
            <p><strong>Run:</strong> {{ currentStructure.run.metadata.name }}</p>
            <p><strong>Type:</strong> {{ currentStructure.run.run_type }}</p>
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
          <p>Select one or more runs from the table above to view structures</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

// State
const runs = ref([])
const selectedRuns = ref([])
const loading = ref(false)
const currentStructureIndex = ref(0)
const molstarContainer = ref(null)

// Computed
const totalStructures = computed(() => {
  return selectedRuns.value.reduce((total, run) => total + run.pdb_files.length, 0)
})

const currentStructure = computed(() => {
  if (selectedRuns.value.length === 0 || totalStructures.value === 0) {
    return null
  }

  let structureIndex = 0
  for (const run of selectedRuns.value) {
    for (const pdbFile of run.pdb_files) {
      if (structureIndex === currentStructureIndex.value) {
        return {
          run,
          filename: pdbFile.split('/').pop(),
          pdbPath: pdbFile
        }
      }
      structureIndex++
    }
  }
  return null
})

// Methods
const loadRuns = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/runs')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    runs.value = data.runs
  } catch (error) {
    console.error('Error loading runs:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load runs',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const clearCache = async () => {
  try {
    const response = await fetch('/api/runs', {
      method: 'DELETE'
    })
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    runs.value = []
    selectedRuns.value = []
    currentStructureIndex.value = 0
    
    toast.add({
      severity: 'success',
      summary: 'Cache Cleared',
      detail: 'All runs have been removed from cache',
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

const viewRun = (run) => {
  // Select the run and show its first structure
  selectedRuns.value = [run]
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

const getRunTypeSeverity = (runType) => {
  switch (runType) {
    case 'bindcraft':
      return 'success'
    case 'rfd':
      return 'info'
    default:
      return 'warning'
  }
}

const loadMolstarViewer = async () => {
  if (!currentStructure.value || !molstarContainer.value) {
    return
  }

  try {
    // Clear previous viewer
    molstarContainer.value.innerHTML = ''

    // Create a simple placeholder for now
    // In a real implementation, you would load Molstar here
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
    // This would involve:
    // 1. Loading Molstar library
    // 2. Creating viewer instance
    // 3. Loading PDB file from /api/runs/{run_id}/files/pdb/{filename}
    
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
  loadRuns()
})
</script>

<style scoped>
.runs-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.runs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.runs-header h2 {
  margin: 0;
  color: #495057;
}

.runs-controls {
  display: flex;
  gap: 0.5rem;
}

.runs-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.runs-table-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
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

.run-path {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
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
</style>
