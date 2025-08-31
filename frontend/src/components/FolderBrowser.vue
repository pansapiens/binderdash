<template>
  <div class="folder-browser">
    <div class="browser-header">
      <h2>Folder Browser</h2>
      <div class="browser-controls">
        <Button 
          label="Scan Selected Folders" 
          icon="pi pi-search" 
          @click="scanSelectedFolders"
          :loading="scanning"
          :disabled="selectedFolders.length === 0"
        />
        <Button 
          label="Clear Selection" 
          icon="pi pi-times" 
          @click="clearSelection"
          :disabled="selectedFolders.length === 0"
          severity="secondary"
        />
      </div>
    </div>

    <div class="browser-content">
      <TreeTable 
        :value="folders" 
        :loading="loading"
        @node-expand="onNodeExpand"
        :expandedKeys="expandedKeys"
        v-model:expandedKeys="expandedKeys"
        dataKey="key"
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

    <div v-if="selectedFolders.length > 0" class="selection-summary">
      <h3>Selected Folders ({{ selectedFolders.length }})</h3>
      <div class="selected-folders">
        <Chip 
          v-for="folder in selectedFolders" 
          :key="folder.path"
          :label="folder.name"
          :removable="true"
          @remove="removeSelectedFolder(folder)"
        />
      </div>
    </div>

    <div v-if="scanResults.length > 0" class="scan-results">
      <h3>Scan Results ({{ scanResults.length }} runs found)</h3>
      <DataTable :value="scanResults" stripedRows>
        <Column field="metadata.name" header="Name"></Column>
        <Column field="run_type" header="Type">
          <template #body="{ data }">
            <Tag :value="data.run_type" :severity="getRunTypeSeverity(data.run_type)" />
          </template>
        </Column>
        <Column field="metadata.pdb_count" header="PDB Files"></Column>
        <Column field="path" header="Path">
          <template #body="{ data }">
            <span class="run-path">{{ data.path }}</span>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import TreeTable from 'primevue/treetable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Chip from 'primevue/chip'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'
import Checkbox from 'primevue/checkbox'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

// State
const folders = ref([])
const selectedKeys = ref({})
const expandedKeys = ref({})
const loading = ref(false)
const scanning = ref(false)
const scanResults = ref([])

// Computed
const selectedFolders = computed(() => {
  const selected = []
  for (const [key, value] of Object.entries(selectedKeys.value)) {
    if (value !== null) {
      // Find the node in the folders tree
      const findNode = (nodes, targetKey) => {
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
      
      const node = findNode(folders.value, key)
      if (node) {
        selected.push(node)
      }
    }
  }
  return selected
})

// Methods
const loadFolders = async (path = '') => {
  loading.value = true
  try {
    const response = await fetch(`/api/tree${path ? `?path=${encodeURIComponent(path)}` : ''}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    folders.value = data.folders.map(folder => ({
      key: folder.path,
      name: folder.name,
      path: folder.path,
      has_children: folder.has_children,
      children: folder.has_children ? [] : undefined,
      leaf: !folder.has_children,
      selectable: true
    }))
    console.log('Loaded folders:', folders.value)
  } catch (error) {
    console.error('Error loading folders:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load folders',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const loadChildren = async (node) => {
  try {
    const response = await fetch(`/api/tree?path=${encodeURIComponent(node.path)}`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    node.children = data.folders.map(folder => ({
      key: folder.path,
      name: folder.name,
      path: folder.path,
      has_children: folder.has_children,
      children: folder.has_children ? [] : undefined,
      leaf: !folder.has_children,
      selectable: true
    }))
    console.log('Loaded children for node:', node.path, node.children)
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

const onNodeExpand = async (event) => {
  const node = event.node
  if (node.children && node.children.length === 0 && node.has_children) {
    await loadChildren(node)
  }
}

const scanSelectedFolders = async () => {
  if (selectedFolders.value.length === 0) return

  scanning.value = true
  try {
    const response = await fetch('/api/runs/scan', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        folders: selectedFolders.value.map(folder => folder.path)
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    scanResults.value = data.runs

    toast.add({
      severity: 'success',
      summary: 'Scan Complete',
      detail: `Found ${data.runs.length} runs in selected folders`,
      life: 3000
    })
  } catch (error) {
    console.error('Error scanning folders:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to scan selected folders',
      life: 3000
    })
  } finally {
    scanning.value = false
  }
}

const clearSelection = () => {
  selectedKeys.value = {}
}

const removeSelectedFolder = (folder) => {
  delete selectedKeys.value[folder.key]
}

const onNodeSelect = (event) => {
  console.log('Node selected:', event.node)
  console.log('Current selectedKeys:', selectedKeys.value)
}

const onNodeUnselect = (event) => {
  console.log('Node unselected:', event.node)
  console.log('Current selectedKeys:', selectedKeys.value)
}

const getFolderIcon = (node) => {
  if (node.has_children) {
    return 'pi pi-folder-open'
  }
  return 'pi pi-folder'
}

const isNodeSelected = (node) => {
  const result = selectedKeys.value[node.key] === true
  console.log('isNodeSelected for node:', node.key, 'result:', result, 'selectedKeys:', selectedKeys.value)
  return result
}

const toggleNodeSelection = (node) => {
  console.log('toggleNodeSelection called for node:', node.key)
  console.log('Current selectedKeys before toggle:', selectedKeys.value)
  
  if (selectedKeys.value[node.key]) {
    delete selectedKeys.value[node.key]
    console.log('Removed node from selection')
  } else {
    selectedKeys.value[node.key] = true
    console.log('Added node to selection')
  }
  
  console.log('Selected keys after toggle:', selectedKeys.value)
  console.log('isNodeSelected result:', isNodeSelected(node))
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

.run-path {
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
