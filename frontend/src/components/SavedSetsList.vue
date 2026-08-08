<template>
  <div class="saved-sets-list">
    <DataTable
      :value="filteringStore.savedSets"
      data-key="id"
      stripedRows
      paginator
      :rows="10"
      :rowsPerPageOptions="[5, 10, 20, 50]"
      showGridlines
      :resizableColumns="true"
      columnResizeMode="fit"
      :rowHover="true"
      :loading="filteringStore.savedSetsLoading"
    >
      <template #empty>
        <div class="empty-msg">
          <i class="pi pi-bookmark empty-icon" aria-hidden="true" />
          <p v-if="filteringStore.savedSetsLoading">Loading saved sets…</p>
          <template v-else>
            <h3>No saved sets</h3>
            <p>Create one from the <strong>Filtering</strong> tab.</p>
          </template>
        </div>
      </template>
      <Column field="name" header="Name" sortable style="min-width: 12rem" />
      <Column field="created_at" header="Created" sortable style="min-width: 10rem">
        <template #body="{ data }">
          {{ formatDate(data.created_at) }}
        </template>
      </Column>
      <Column header="Source Runs" style="min-width: 10rem">
        <template #body="{ data }">
          {{ formatSourceRuns(data.source_run_ids) }}
        </template>
      </Column>
      <Column field="design_count" header="Design Count" sortable style="min-width: 8rem">
        <template #body="{ data }">
          {{ data.design_count }} / {{ data.total_input }}
        </template>
      </Column>
      <Column header="Actions" style="min-width: 18rem">
        <template #body="{ data }">
          <div class="saved-set-actions">
            <Button
              icon="pi pi-eye"
              severity="secondary"
              text
              v-tooltip.top="'View designs'"
              @click="emit('view-designs', data.id)"
            />
            <Button
              icon="pi pi-pencil"
              severity="secondary"
              text
              v-tooltip.top="'Rename'"
              @click="openRenameDialog(data)"
            />
            <Button
              icon="pi pi-download"
              severity="secondary"
              text
              v-tooltip.top="'Download ZIP'"
              @click="downloadSavedSet(data.id)"
            />
            <Button
              icon="pi pi-filter"
              severity="secondary"
              text
              v-tooltip.top="'Reapply filters (load recipe into Filtering tab)'"
              @click="reapplyFilters(data)"
            />
            <Button
              icon="pi pi-trash"
              severity="danger"
              text
              v-tooltip.top="'Delete'"
              :loading="deletingId === data.id"
              @click="confirmDelete(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <Dialog
      v-model:visible="renameDialogVisible"
      modal
      header="Rename saved set"
      :style="{ width: 'min(28rem, 95vw)' }"
      :closable="true"
      @hide="onRenameDialogHide"
    >
      <div class="rename-field">
        <label for="saved-set-rename-input">Name</label>
        <InputText
          id="saved-set-rename-input"
          v-model="renameValue"
          class="rename-input"
          @keyup.enter="confirmRename"
        />
      </div>
      <template #footer>
        <Button
          label="Cancel"
          severity="secondary"
          outlined
          @click="renameDialogVisible = false"
        />
        <Button
          label="Rename"
          icon="pi pi-check"
          :loading="renaming"
          :disabled="!renameValue.trim()"
          @click="confirmRename"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import { useToast } from 'primevue/usetoast'
import { useFilteringStore, useRunsStore } from '../stores'
import { savedSetsApi } from '../webapi'
import type { FilteringRunRequestDto, SavedSetDto } from '../webapi'
import { formatSourceRunNames } from '../utils/runDisplay'

const emit = defineEmits<{
  'view-designs': [id: string]
  'reapply-filters': []
}>()

const filteringStore = useFilteringStore()
const runsStore = useRunsStore()
const toast = useToast()

function formatDate(createdAt: string): string {
  const d = new Date(createdAt)
  if (Number.isNaN(d.getTime())) return createdAt
  return d.toLocaleString()
}

function formatSourceRuns(sourceRunIds: string[] | undefined): string {
  return formatSourceRunNames(sourceRunIds, runsStore.availableRuns)
}

// --- Rename ---

const renameDialogVisible = ref(false)
const renameValue = ref('')
const renaming = ref(false)
const pendingRenameSet = ref<SavedSetDto | null>(null)

function openRenameDialog(set: SavedSetDto) {
  pendingRenameSet.value = set
  renameValue.value = set.name
  renameDialogVisible.value = true
}

function onRenameDialogHide() {
  pendingRenameSet.value = null
  renameValue.value = ''
}

async function confirmRename() {
  const set = pendingRenameSet.value
  const name = renameValue.value.trim()
  if (!set || !name) return
  renaming.value = true
  try {
    const updated = await savedSetsApi.rename(set.id, name)
    const idx = filteringStore.savedSets.findIndex((s) => s.id === set.id)
    if (idx >= 0) {
      filteringStore.savedSets.splice(idx, 1, updated)
    }
    toast.add({
      severity: 'success',
      summary: 'Renamed',
      detail: `Saved set renamed to "${updated.name}".`,
      life: 4000
    })
    renameDialogVisible.value = false
  } catch (error) {
    console.error('Rename saved set failed:', error)
    toast.add({
      severity: 'error',
      summary: 'Rename failed',
      detail: error instanceof Error ? error.message : 'Request failed',
      life: 5000
    })
  } finally {
    renaming.value = false
  }
}

// --- Delete ---

const deletingId = ref<string | null>(null)

async function confirmDelete(set: SavedSetDto) {
  // No useConfirm/ConfirmDialog pattern exists elsewhere in the frontend yet —
  // a plain window.confirm matches the rest of the codebase for this one action.
  if (!window.confirm(`Delete saved set "${set.name}"? This cannot be undone.`)) return
  deletingId.value = set.id
  try {
    await filteringStore.deleteSavedSet(set.id)
    toast.add({
      severity: 'success',
      summary: 'Deleted',
      detail: `Saved set "${set.name}" deleted.`,
      life: 4000
    })
  } catch (error) {
    console.error('Delete saved set failed:', error)
    toast.add({
      severity: 'error',
      summary: 'Delete failed',
      detail: error instanceof Error ? error.message : 'Request failed',
      life: 5000
    })
  } finally {
    deletingId.value = null
  }
}

// --- Download ---

function downloadSavedSet(id: string) {
  window.open(savedSetsApi.getDownloadUrl(id), '_blank')
}

// --- Reapply filters ---

function reapplyFilters(set: SavedSetDto) {
  filteringStore.loadRecipe(set.filter_params as FilteringRunRequestDto)
  emit('reapply-filters')
}
</script>

<style scoped>
.saved-sets-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.saved-set-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.rename-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.rename-field label {
  font-weight: 600;
  color: #495057;
}

.rename-input {
  width: 100%;
}

.empty-msg {
  padding: 1.5rem;
  text-align: center;
  color: #6c757d;
}

.empty-msg h3 {
  margin: 0.5rem 0 0.25rem 0;
  color: #495057;
  font-size: 1.1rem;
}

.empty-icon {
  font-size: 3rem;
  color: #6c757d;
}
</style>
