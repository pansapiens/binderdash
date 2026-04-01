<template>
  <div class="folder-browser">
    <div class="browser-header">
      <h2>Folder Browser</h2>
      <div class="browser-controls">
        <Button 
          label="Refresh" 
          icon="pi pi-refresh" 
          @click="refreshTree"
          :loading="folderStore.loading"
          severity="secondary"
          outlined
        />
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
        v-model:expandedKeys="folderStore.expandedKeys"
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


    <div v-if="folderStore.scanResults.length > 0" class="scan-results">
      <h3>Scan Results ({{ folderStore.scanResults.length }} runs found)</h3>

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
        :globalFilterFields="['metadata.name', 'method', 'path']"
        showGridlines
        :resizableColumns="true"
        columnResizeMode="fit"
        :reorderableColumns="true"
        :rowHover="true"
      >
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
              <i :class="getMethodIcon(data.method)" class="protocol-icon"></i>
              {{ data.metadata.name }}
            </div>
          </template>
        </Column>
        <Column field="project_id" header="Project ID" sortable style="min-width: 120px">
          <template #body="{ data }">
            <span class="project-id">{{ data.project_id || '-' }}</span>
          </template>
        </Column>
        <Column field="method" header="Method" sortable style="min-width: 100px">
          <template #body="{ data }">
            <Tag :value="data.method" :severity="getMethodSeverity(data.method)" />
          </template>
        </Column>
        <Column field="metadata.pdb_count" header="Designs" sortable style="min-width: 100px">
          <template #body="{ data }">
            {{ data.metadata.pdb_count ?? '-' }}
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
import { ref, onMounted, computed, watch } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Chip from 'primevue/chip'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
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

const refreshTree = async () => {
  try {
    // Clear current selection and expanded state to start fresh
    folderStore.clearSelection()
    folderStore.expandedKeys = {}
    
    // Reload the root folders
    await folderStore.fetchFolders()
    
    toast.add({
      severity: 'success',
      summary: 'Tree Refreshed',
      detail: 'File tree has been refreshed',
      life: 2000
    })
  } catch (error) {
    console.error('Error refreshing tree:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to refresh file tree',
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

// Auto-sync selected runs - no need for manual include button
// Watch for changes in selected runs and automatically emit the event
watch(() => folderStore.selectedRuns, (newSelectedRuns, oldSelectedRuns) => {
  // Only emit if there are actually selected runs and the selection has changed
  if (newSelectedRuns.length > 0 && newSelectedRuns !== oldSelectedRuns) {
    emit('runs-scanned', newSelectedRuns)
  }
}, { deep: true })


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

const getMethodSeverity = (method: any): string => {
  switch (method) {
    case 'bindcraft':
      return 'success'
    case 'rfd':
      return 'info'
    case 'rfd3':
      return 'info'
    default:
      return 'warning'
  }
}

const getMethodIcon = (method: any): string => {
  switch (method) {
    case 'bindcraft':
      return 'pi pi-code'
    case 'rfd':
      return 'pi pi-file'
    case 'rfd3':
      return 'pi pi-box'
    default:
      return 'pi pi-info-circle'
  }
}

// Lifecycle
onMounted(async () => {
  await loadFolders()
  // After loading folders, check if any nodes should be expanded based on persisted state
  await restoreExpandedState()
})

// Restore expanded state for nodes that were previously expanded
const restoreExpandedState = async () => {
  const expandedKeys = folderStore.expandedKeys
  const keysToExpand = Object.keys(expandedKeys).filter(key => expandedKeys[key] === true)
  
  if (keysToExpand.length === 0) return
  
  // Sort keys by depth (shallowest first) to ensure parent nodes are loaded before children
  const sortedKeys = keysToExpand.sort((a, b) => {
    const depthA = (a.match(/\//g) || []).length
    const depthB = (b.match(/\//g) || []).length
    return depthA - depthB
  })
  
  // Load children for each expanded node, starting with the shallowest
  for (const key of sortedKeys) {
    const node = findNodeByKey(folderStore.folders, key)
    if (node && node.has_children && !node.children) {
      try {
        await loadChildren(node)
        // After loading children, recursively check if any of the children also need to be expanded
        await restoreExpandedStateRecursive(node.children, expandedKeys)
      } catch (error) {
        console.error('Error restoring expanded state for node:', key, error)
      }
    }
  }
}

// Recursively restore expanded state for nested nodes
const restoreExpandedStateRecursive = async (nodes: any[], expandedKeys: Record<string, boolean>) => {
  if (!nodes) return
  
  for (const node of nodes) {
    if (expandedKeys[node.key] === true && node.has_children && !node.children) {
      try {
        await loadChildren(node)
        // Continue recursively for any children that were also expanded
        if (node.children) {
          await restoreExpandedStateRecursive(node.children, expandedKeys)
        }
      } catch (error) {
        console.error('Error restoring expanded state for nested node:', node.key, error)
      }
    }
  }
}

// Helper function to find a node by its key
const findNodeByKey = (nodes: any[], targetKey: string): any => {
  for (const node of nodes) {
    if (node.key === targetKey) {
      return node
    }
    if (node.children) {
      const found = findNodeByKey(node.children, targetKey)
      if (found) return found
    }
  }
  return null
}
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
  min-height: 100px;
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
