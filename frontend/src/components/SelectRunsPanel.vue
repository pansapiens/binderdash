<template>
  <div class="select-runs-panel">
    <div class="panel-header">
      <h2>Select Runs</h2>
      <p class="hint">
        Choose ingested runs to drive the Designs table and (by default) plots. Run name filter applies after you type at least three characters.
      </p>
      <div class="filters">
        <div class="filter-field">
          <label for="sr-project">Project</label>
          <Dropdown
            id="sr-project"
            v-model="projectFilter"
            :options="projectOptions"
            option-label="label"
            option-value="value"
            placeholder="All projects"
            filter
            filter-placeholder="Search projects..."
            show-clear
            class="filter-dropdown"
          />
        </div>
        <div class="filter-field">
          <label for="sr-method">Method</label>
          <Dropdown
            id="sr-method"
            v-model="methodFilter"
            :options="methodOptions"
            option-label="label"
            option-value="value"
            placeholder="All methods"
            filter
            filter-placeholder="Search methods..."
            show-clear
            class="filter-dropdown"
          />
        </div>
        <div class="filter-field grow">
          <label for="sr-name">Run name</label>
          <InputText
            id="sr-name"
            v-model="nameInput"
            placeholder="Type 3+ characters to filter"
            class="filter-input"
          />
        </div>
        <Button
          label="Refresh list"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          :loading="runsStore.loading"
          @click="runsStore.fetchRuns()"
        />
      </div>
    </div>

    <DataTable
      v-model:selection="tableSelection"
      :value="filteredRuns"
      data-key="run_id"
      stripedRows
      paginator
      :rows="10"
      :rowsPerPageOptions="[5, 10, 20, 50]"
      paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
      currentPageReportTemplate="Showing {first} to {last} of {totalRecords} runs"
      showGridlines
      :resizableColumns="true"
      columnResizeMode="fit"
      :reorderableColumns="true"
      :rowHover="true"
      :loading="runsStore.loading"
    >
      <template #empty>
        <div class="empty-msg">
          <i class="pi pi-inbox empty-icon" aria-hidden="true" />
          <p v-if="runsStore.loading">Loading runs…</p>
          <template v-else>
            <h3>No ingested runs</h3>
            <p>Use <strong>Ingest Runs</strong> to add runs from disk.</p>
          </template>
        </div>
      </template>
      <Column selectionMode="multiple" headerStyle="width: 3rem" />
      <Column field="metadata.name" header="Name" sortable style="min-width: 150px">
        <template #body="{ data }">
          <div class="run-name">
            <i :class="getMethodIconClass(data.method)" class="protocol-icon" aria-hidden="true" />
            {{ data.metadata?.name ?? '—' }}
          </div>
        </template>
      </Column>
      <Column field="project_id" header="Project ID" sortable style="min-width: 120px">
        <template #body="{ data }">
          <span class="project-id">{{ data.project_id || '—' }}</span>
        </template>
      </Column>
      <Column field="method" header="Method" sortable style="min-width: 100px">
        <template #body="{ data }">
          <Tag
            :value="data.method"
            :style="getMethodTagStyle(data.method)"
            class="pipeline-palette-tag"
          />
        </template>
      </Column>
      <Column field="metadata.pdb_count" sortable style="min-width: 110px">
        <template #header>
          <span v-tooltip.top="'Accepted or filtered designs / pre-filter trajectories or designs'">Accepted / total</span>
        </template>
        <template #body="{ data }">
          {{ formatAcceptedTotalText(data) }}
        </template>
      </Column>
      <Column field="metadata.primary_score_stats.median" sortable style="min-width: 300px">
        <template #header>
          <span
            v-tooltip.top="'Mean ± σ over accepted/filtered designs, range [min - max]; chip shows the score column.'"
          >Primary score</span>
        </template>
        <template #body="{ data }">
          <template v-for="w in [primaryScoreDisplay(data)]" :key="data.run_id">
            <div v-if="w" class="primary-score-row">
              <span v-tooltip.top="w.title" class="primary-score-numbers">{{ w.numbersLine }}</span>
              <Tag
                :value="w.chipLabel"
                :style="w.tagStyle"
                class="primary-score-type-tag pipeline-palette-tag"
              />
            </div>
            <span v-else class="muted-cell">—</span>
          </template>
        </template>
      </Column>
      <Column field="path" header="Path" style="min-width: 200px">
        <template #body="{ data }">
          <span class="run-path">{{ data.path }}</span>
        </template>
      </Column>
      <Column field="metadata.results_file" header="Results File" style="min-width: 150px">
        <template #body="{ data }">
          <span class="results-file">{{ data.metadata?.results_file ?? '—' }}</span>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useRunsStore, useDesignsStore, usePlotsStore } from '../stores'
import type { Run } from '../types/store'
import { formatAcceptedTotalText, primaryScoreDisplay } from '../utils/runDisplay'
import { getMethodTagStyle, getMethodIconClass } from '../config/pipelineDisplay'

const runsStore = useRunsStore()
const designsStore = useDesignsStore()
const plotsStore = usePlotsStore()

const projectFilter = ref<string | null>(null)
const methodFilter = ref<string | null>(null)
const nameInput = ref('')
const nameDebounced = ref('')
let nameTimer: ReturnType<typeof setTimeout> | null = null

watch(nameInput, (v) => {
  if (nameTimer) clearTimeout(nameTimer)
  nameTimer = setTimeout(() => {
    nameDebounced.value = v
  }, 300)
})

const projectOptions = computed(() => {
  const set = new Set<string>()
  for (const r of runsStore.runs) {
    if (r.project_id) set.add(r.project_id)
  }
  return [...set].sort().map((value) => ({ label: value, value }))
})

const methodOptions = computed(() => {
  const set = new Set<string>()
  for (const r of runsStore.runs) {
    if (r.method) set.add(r.method)
  }
  return [...set].sort().map((value) => ({ label: value, value }))
})

const filteredRuns = computed(() => {
  let rows = [...runsStore.runs]
  if (projectFilter.value) {
    rows = rows.filter((r) => r.project_id === projectFilter.value)
  }
  if (methodFilter.value) {
    rows = rows.filter((r) => r.method === methodFilter.value)
  }
  const q = nameDebounced.value.trim().toLowerCase()
  if (q.length >= 3) {
    rows = rows.filter((r) => (r.metadata?.name || '').toLowerCase().includes(q))
  }
  return rows
})

const tableSelection = ref<Run[]>([])

const sameIdSet = (a: string[], b: string[]): boolean => {
  if (a.length !== b.length) return false
  const bs = new Set(b)
  return a.every((id) => bs.has(id))
}

watch(
  tableSelection,
  (sel) => {
    const ids = sel.map((r) => r.run_id)
    if (!sameIdSet(ids, designsStore.selectedRunIds)) {
      designsStore.setSelectedRunIds(ids)
    }
    if (!sameIdSet(ids, plotsStore.selectedRunIds)) {
      plotsStore.setSelectedRuns(ids)
    }
  },
  { deep: true }
)

watch(
  [() => runsStore.runs, () => designsStore.selectedRunIds],
  ([runs, selectedIds]) => {
    const ids = new Set(selectedIds)
    const nextSelection = ids.size === 0 ? [] : runs.filter((r) => ids.has(r.run_id))
    const currentIds = tableSelection.value.map((r) => r.run_id)
    const nextIds = nextSelection.map((r) => r.run_id)
    if (sameIdSet(currentIds, nextIds)) {
      return
    }
    tableSelection.value = nextSelection
  },
  { deep: true, immediate: true }
)

onMounted(() => {
  runsStore.fetchRuns()
})
</script>

<style scoped>
.select-runs-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-header h2 {
  margin: 0 0 0.5rem 0;
  color: #495057;
}

.hint {
  margin: 0 0 1rem 0;
  color: #6c757d;
  font-size: 0.95rem;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 0.5rem;
}

.filter-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 10rem;
}

.filter-field.grow {
  flex: 1 1 14rem;
  min-width: 14rem;
}

.filter-field label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #495057;
}

.filter-dropdown,
.filter-input {
  width: 100%;
}

.run-path {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
}

.project-id {
  color: #495057;
}

.run-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.protocol-icon {
  color: #6c757d;
}

.muted-cell {
  color: #6c757d;
}

.primary-score-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.primary-score-numbers {
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
  color: #495057;
  word-break: break-word;
}

.primary-score-type-tag {
  flex-shrink: 0;
  max-width: 100%;
}

.primary-score-type-tag :deep(.p-tag-label) {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.results-file {
  font-family: monospace;
  font-size: 0.9rem;
  color: #6c757d;
  word-break: break-all;
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
