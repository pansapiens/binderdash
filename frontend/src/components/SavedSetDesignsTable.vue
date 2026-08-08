<template>
  <div class="saved-set-designs-table">
    <div class="designs-table-header">
      <Button
        label="Back"
        icon="pi pi-arrow-left"
        severity="secondary"
        outlined
        @click="emit('back')"
      />
      <h3 v-if="savedSet">{{ savedSet.name }}</h3>
    </div>

    <DataTable
      :value="rows"
      data-key="rowKey"
      stripedRows
      paginator
      :rows="20"
      :rowsPerPageOptions="[10, 20, 50, 100]"
      showGridlines
      :resizableColumns="true"
      columnResizeMode="fit"
      :rowHover="true"
      :loading="loading"
    >
      <template #empty>
        <div class="empty-msg">
          <i class="pi pi-inbox empty-icon" aria-hidden="true" />
          <p v-if="loading">Loading designs…</p>
          <p v-else>No designs in this saved set.</p>
        </div>
      </template>
      <Column field="design_id" header="Design ID" sortable style="min-width: 12rem" />
      <Column field="run_id" header="Run ID" sortable style="min-width: 10rem" />
      <Column field="final_rank" header="Final Rank" sortable style="min-width: 8rem" />
      <Column field="quality_score" header="Quality Score" sortable style="min-width: 8rem">
        <template #body="{ data }">
          {{ formatNumber(data.quality_score) }}
        </template>
      </Column>
      <Column field="in_diverse_set" header="In Diverse Set" sortable style="min-width: 8rem">
        <template #body="{ data }">
          <i
            :class="data.in_diverse_set ? 'pi pi-check-circle diverse-yes' : 'pi pi-minus-circle diverse-no'"
            aria-hidden="true"
          />
        </template>
      </Column>
      <Column
        v-for="field in extraMetricFields"
        :key="field"
        :field="field"
        :header="field"
        sortable
        style="min-width: 10rem"
      >
        <template #body="{ data }">
          {{ formatCell(data[field]) }}
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import { savedSetsApi } from '../webapi'
import type { SavedSetDesignRowDto, SavedSetDto } from '../webapi'

const props = defineProps<{
  savedSetId: string
}>()

const emit = defineEmits<{
  back: []
}>()

// Mol* / 3D structure viewing is explicitly out of scope for this table
// (plan task description) — this is a plain metrics table only.

const loading = ref(false)
const savedSet = ref<SavedSetDto | null>(null)
const rows = ref<Array<SavedSetDesignRowDto & { rowKey: string }>>([])

/** A small, readable subset of flattened `metrics` columns worth surfacing by default. */
const PREFERRED_METRIC_FIELDS = ['Sequence', 'sequence', 'designed_sequence', 'Length', 'iptm', 'ptm', 'rmsd']

const extraMetricFields = computed<string[]>(() => {
  const present = new Set<string>()
  for (const row of rows.value) {
    for (const key of Object.keys(row.metrics ?? {})) {
      if (PREFERRED_METRIC_FIELDS.includes(key)) present.add(key)
    }
  }
  return PREFERRED_METRIC_FIELDS.filter((f) => present.has(f))
})

function formatNumber(value: number | null | undefined): string {
  if (value == null) return '—'
  return Number(value).toFixed(4)
}

function formatCell(value: unknown): string {
  if (value == null) return '—'
  return String(value)
}

async function load() {
  loading.value = true
  try {
    const [details, designsResponse] = await Promise.all([
      savedSetsApi.get(props.savedSetId),
      savedSetsApi.getDesigns(props.savedSetId)
    ])
    savedSet.value = details
    rows.value = designsResponse.designs.map((row, index) => ({
      ...row,
      // Flatten a handful of metrics fields onto the row for column access below.
      ...Object.fromEntries(
        PREFERRED_METRIC_FIELDS.filter((f) => f in (row.metrics ?? {})).map((f) => [f, row.metrics[f]])
      ),
      rowKey: `${row.run_id}\x1f${row.design_id}\x1f${row.source_path ?? ''}\x1f${index}`
    }))
  } catch (err) {
    console.error('Error loading saved set designs:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.savedSetId, () => load())
onMounted(() => load())
</script>

<style scoped>
.saved-set-designs-table {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.designs-table-header {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.designs-table-header h3 {
  margin: 0;
  color: #495057;
}

.diverse-yes {
  color: #22863a;
}

.diverse-no {
  color: #6c757d;
}

.empty-msg {
  padding: 1.5rem;
  text-align: center;
  color: #6c757d;
}

.empty-icon {
  font-size: 3rem;
  color: #6c757d;
}
</style>
