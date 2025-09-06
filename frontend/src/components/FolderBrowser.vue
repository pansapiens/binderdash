<template>
  <div class="folder-browser">
    <div class="browser-header">
      <h2>Folder Browser</h2>
      <div class="browser-controls">
        <Button 
          label="Scan Selected Folders" 
          icon="pi pi-search" 
          @click="scanSelectedFolders"
          :loading="folderStore.scanning"
          :disabled="selectedFolderNodes.length === 0"
        />
        <Button 
          label="Clear Selection" 
          icon="pi pi-times" 
          @click="clearSelection"
          :disabled="selectedFolderNodes.length === 0"
          severity="secondary"
        />
      </div>
    </div>

    <div class="browser-content">
      <TreeTable 
        :value="folderStore.folders" 
        :loading="folderStore.loading"
        @node-expand="onNodeExpand"
        @node-collapse="onNodeCollapse"
        v-model:expandedKeys="expandedKeys"
        dataKey="key"
        lazy
        :loadingIcon="'pi pi-spinner'"
        :loadingMode="'card'"
      >
        <Column field="name" header="Name" expander>
          <template #body="{ node }">
            <div class="folder-node">
              <input 
                type="checkbox"
                :checked="isNodeSelected(node)"
                @change="toggleNodeSelection(node)"
                @click="console.log('Checkbox clicked for node:', node.key)"
                class="folder-checkbox"
                style="pointer-events: auto; z-index: 10; position: relative; margin-right: 0.5rem;"
              />
              <i :class="getFolderIcon(node)" class="folder-icon"></i>
              <span>{{ node.name }}</span>
            </div>
          </template>
        </Column>
        <Column field="path" header="Path">
          <template #body="{ node }">
            <span class="folder-path">{{ node.path }}</span>
          </template>
        </Column>
      </TreeTable>
    </div>

    <div v-if="selectedFolderNodes.length > 0" class="selection-summary">
      <h3>Selected Folders ({{ selectedFolderNodes.length }})</h3>
      <div class="selected-folders">
        <Chip 
          v-for="folder in selectedFolderNodes" 
          :key="folder.path"
          :label="folder.name"
          :removable="true"
          @remove="removeSelectedFolder(folder)"
        />
      </div>
    </div>

    <div v-if="folderStore.scanResults.length > 0" class="scan-results">
      <div class="scan-results-header">
        <h3>Scan Results ({{ folderStore.scanResults.length }} runs found)</h3>
        <div class="scan-results-controls">
          <Button 
            label="Select All" 
            icon="pi pi-check-square" 
            @click="selectAllRuns"
            size="small"
            outlined
          />
          <Button 
            label="Deselect All" 
            icon="pi pi-square" 
            @click="deselectAllRuns"
            size="small"
            outlined
          />
          <Button 
            label="Include Selected Runs" 
            icon="pi pi-plus" 
            @click="includeSelectedRuns"
            :disabled="folderStore.selectedRuns.length === 0"
            size="small"
          />
        </div>
      </div>
      
      <DataTable 
        :value="folderStore.scanResults" 
        v-model:selection="folderStore.selectedRuns"
        selectionMode="multiple"
        dataKey="run_id"
        stripedRows
        paginator
        :rows="10"
        :rowsPerPageOptions="[5, 10, 20, 50]"
        paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
        currentPageReportTemplate="Showing {first} to {last} of {totalRecords} runs"
        :filters="filters"
        filterDisplay="menu"
        :globalFilterFields="['metadata.name', 'protocol', 'path']"
        showGridlines
        :resizableColumns="true"
        columnResizeMode="fit"
        :reorderableColumns="true"
        :rowHover="true"
      >
        <template #header>
          <div class="flex justify-content-between align-items-center">
            <span class="text-xl font-bold">Detected Runs</span>
            <span class="text-sm text-muted">
              {{ folderStore.selectedRuns.length }} of {{ folderStore.scanResults.length }} selected
            </span>
          </div>
        </template>

        <template #empty>
          <div class="text-center p-4">
            <i class="pi pi-search" style="font-size: 3rem; color: #6c757d;"></i>
            <h3>No Runs Found</h3>
            <p>No valid runs detected in selected folders</p>
          </div>
        </template>

        <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
        <Column field="metadata.name" header="Name" sortable style="min-width: 150px">
          <template #body="{ data }">
            <div class="run-name">
              <i :class="getProtocolIcon(data.protocol)" class="protocol-icon"></i>
              {{ data.metadata.name }}
            </div>
          </template>
        </Column>
        <Column field="project_id" header="Project ID" sortable style="min-width: 120px">
          <template #body="{ data }">
            <span class="project-id">{{ data.project_id || '-' }}</span>
          </template>
        </Column>
        <Column field="protocol" header="Protocol" sortable style="min-width: 100px">
          <template #body="{ data }">
            <Tag :value="data.protocol" :severity="getProtocolSeverity(data.protocol)" />
          </template>
        </Column>
        <Column field="metadata.pdb_count" header="PDB Files" sortable style="min-width: 100px">
          <template #body="{ data }">
            <Badge :value="data.metadata.pdb_count" severity="info" />
          </template>
        </Column>
        <Column field="path" header="Path" style="min-width: 200px">
          <template #body="{ data }">
            <span class="run-path">{{ data.path }}</span>
          </template>
        </Column>
        <Column field="metadata.results_file" header="Results File" style="min-width: 150px">
          <template #body="{ data }">
            <span class="results-file">{{ data.metadata.results_file }}</span>
          </template>
        </Column>
      </DataTable>
    </div>
    
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Chip from 'primevue/chip'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import Badge from 'primevue/badge'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import { useFolderStore, useRunsStore } from '../stores'

// Define emits
const emit = defineEmits(['runs-scanned'])

const toast = useToast()

// Use Pinia stores
const folderStore = useFolderStore()
const runsStore = useRunsStore()

// Local UI state (not shared across components)
const expandedKeys = ref<Record<string, any>>({})
const filters = ref<any>(null)

// Computed
const selectedFolderNodes = computed(() => {
  const selected: any[] = []
  for (const [key, value] of Object.entries(folderStore.selectedKeys)) {
    if (value !== null) {
      // Find the node in the folders tree
      const findNode = (nodes: any[], targetKey: string): any => {
        for (const node of nodes) {
          if (node.key === targetKey) {
            return node
          }
          if (node.children) {
            const found = findNode(node.children, targetKey)
            if (found) return found
          }
        }
        return null
      }
      
      const node = findNode(folderStore.folders, key)
      if (node) {
        selected.push(node)
      }
    }
  }
  return selected
})

// Methods
const loadFolders = async (path = '') => {
  try {
    await folderStore.fetchFolders(path)
  } catch (error) {
    console.error('Error loading folders:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load folders',
      life: 3000
    })
  }
}

const loadChildren = async (node: any): Promise<void> => {
  console.log('loadChildren called for node:', node.path)
  try {
    await folderStore.loadChildren(node)
  } catch (error) {
    console.error('Error loading children:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load folder children',
      life: 3000
    })
  }
}

const onNodeExpand = async (event: any): Promise<void> => {
  console.log('onNodeExpand called with event:', event)
  console.log('Event keys:', Object.keys(event))
  
  // For PrimeVue TreeTable lazy loading, the node data might be in a different property
  const node = event.node || event.data || event
  console.log('Node to expand:', node)
  
  if (!node) {
    console.error('No node data found in event')
    return
  }
  
  console.log('Node children:', node.children)
  console.log('Node has_children:', node.has_children)
  
  // For lazy loading, we need to load children when expanding
  if (node.has_children && !node.children) {
    console.log('Loading children for node:', node.path)
    await loadChildren(node)
  } else {
    console.log('Skipping load - conditions not met')
  }
}

const onNodeCollapse = (event: any): void => {
  console.log('onNodeCollapse called with event:', event)
}

const scanSelectedFolders = async () => {
  if (selectedFolderNodes.value.length === 0) return

  try {
    const runs = await folderStore.scanFolders(selectedFolderNodes.value.map(folder => folder.path))

    toast.add({
      severity: 'success',
      summary: 'Scan Complete',
      detail: `Found ${runs.length} runs in selected folders`,
      life: 3000
    })

    // Emit event to notify parent that runs have been scanned
    emit('runs-scanned', runs)
  } catch (error) {
    console.error('Error scanning folders:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to scan selected folders',
      life: 3000
    })
  }
}

const clearSelection = () => {
  folderStore.clearSelection()
}

const selectAllRuns = () => {
  folderStore.selectAllRuns()
}

const deselectAllRuns = () => {
  folderStore.deselectAllRuns()
}

const includeSelectedRuns = () => {
  if (folderStore.selectedRuns.length === 0) return
  
  toast.add({
    severity: 'success',
    summary: 'Runs Included',
    detail: `${folderStore.selectedRuns.length} runs have been included for processing`,
    life: 3000
  })
  
  // Emit event with selected runs
  emit('runs-scanned', folderStore.selectedRuns)
}

const removeSelectedFolder = (folder: any): void => {
  folderStore.removeSelectedFolder(folder.key)
}

const onNodeSelect = (event: any): void => {
  console.log('Node selected:', event.node)
  console.log('Current selectedKeys:', folderStore.selectedKeys)
}

const onNodeUnselect = (event: any): void => {
  console.log('Node unselected:', event.node)
  console.log('Current selectedKeys:', folderStore.selectedKeys)
}

const getFolderIcon = (node: any): string => {
  if (node.has_children) {
    return 'pi pi-folder-open'
  }
  return 'pi pi-folder'
}

const isNodeSelected = (node: any): boolean => {
  const result = folderStore.selectedKeys[node.key] === true
  console.log('isNodeSelected for node:', node.key, 'result:', result, 'selectedKeys:', folderStore.selectedKeys)
  return result
}

const toggleNodeSelection = (node: any): void => {
  console.log('toggleNodeSelection called for node:', node.key)
  console.log('Current selectedKeys before toggle:', folderStore.selectedKeys)
  
  folderStore.toggleNodeSelection(node.key)
  
  console.log('Selected keys after toggle:', folderStore.selectedKeys)
  console.log('isNodeSelected result:', isNodeSelected(node))
}

const getProtocolSeverity = (protocol: any): string => {
  switch (protocol) {
    case 'bindcraft':
      return 'success'
    case 'rfd':
      return 'info'
    default:
      return 'warning'
  }
}

const getProtocolIcon = (protocol: any): string => {
  switch (protocol) {
    case 'bindcraft':
      return 'pi pi-code'
    case 'rfd':
      return 'pi pi-file'
    default:
      return 'pi pi-info-circle'
  }
}

// Lifecycle
onMounted(() => {
  loadFolders()
})
</script>

<style scoped>
.folder-browser {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.browser-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.browser-header h2 {
  margin: 0;
  color: #495057;
}

.browser-controls {
  display: flex;
  gap: 0.5rem;
}

.browser-content {
  min-height: 400px;
}

.folder-node {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.folder-checkbox {
  margin-right: 0.5rem;
  pointer-events: auto !important;
  z-index: 10 !important;
  position: relative !important;
}

/* Ensure checkbox is clickable and visible */
:deep(.folder-checkbox .p-checkbox) {
  pointer-events: auto !important;
  cursor: pointer !important;
  z-index: 10 !important;
  position: relative !important;
}

:deep(.folder-checkbox .p-checkbox .p-checkbox-box) {
  pointer-events: auto !important;
  cursor: pointer !important;
  z-index: 10 !important;
  position: relative !important;
}

:deep(.folder-checkbox input[type="checkbox"]) {
  pointer-events: auto !important;
  cursor: pointer !important;
  z-index: 10 !important;
  position: relative !important;
}

.folder-icon {
  color: #6c757d;
}

.folder-path {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
}

.selection-summary {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.selection-summary h3 {
  margin: 0 0 1rem 0;
  color: #495057;
}

.selected-folders {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.scan-results {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.scan-results h3 {
  margin: 0 0 1rem 0;
  color: #495057;
}

.scan-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.scan-results-header h3 {
  margin: 0;
  color: #495057;
}

.scan-results-controls {
  display: flex;
  gap: 0.5rem;
}

.run-path {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
}

.run-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.run-type-icon {
  color: #6c757d;
}

.results-file {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
}

/* PrimeVue overrides */
:deep(.p-treetable) {
  border: 1px solid #e9ecef;
  border-radius: 8px;
}

:deep(.p-treetable .p-treetable-thead > tr > th) {
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
  font-weight: 600;
}

:deep(.p-treetable .p-treetable-tbody > tr > td) {
  border-bottom: 1px solid #f1f3f4;
}

:deep(.p-treetable .p-treetable-tbody > tr:hover > td) {
  background: #f8f9fa;
}

/* Ensure checkboxes are visible */
:deep(.p-treetable .p-checkbox) {
  margin-right: 0.5rem;
}

:deep(.p-treetable .p-checkbox .p-checkbox-box) {
  border: 1px solid #dee2e6;
  background: white;
}

:deep(.p-treetable .p-checkbox .p-checkbox-box.p-highlight) {
  background: #667eea;
  border-color: #667eea;
}


</style>
