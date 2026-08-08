<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Panel from 'primevue/panel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Slider from 'primevue/slider'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import Message from 'primevue/message'
import Checkbox from 'primevue/checkbox'
import { useToast } from 'primevue/usetoast'
import { useDesignsStore, useFilteringStore } from '../stores'
import { getMethodTagStyle } from '../config/pipelineDisplay'
import MetricColumnSelector from './MetricColumnSelector.vue'
import type { FilterSpecDto } from '../webapi'
import type { InputNumberInputEvent } from 'primevue/inputnumber'

const filteringStore = useFilteringStore()
const designsStore = useDesignsStore()
const toast = useToast()

// Operator sets mirror the backend FilterSpec superset (plan §7A.1) — numeric vs
// string vs empty-check, chosen per the selected column's dtype.
const NUMERIC_OPERATORS: { label: string; value: string }[] = [
  { label: '<  (lower is better)', value: '<' },
  { label: '≤', value: '<=' },
  { label: '>  (higher is better)', value: '>' },
  { label: '≥', value: '>=' }
]

const STRING_OPERATORS: { label: string; value: string }[] = [
  { label: 'contains', value: 'contains' },
  { label: 'does not contain', value: 'not_contains' },
  { label: 'starts with', value: 'starts_with' },
  { label: 'ends with', value: 'ends_with' },
  { label: 'equals', value: 'equals' },
  { label: 'not equals', value: 'not_equals' },
  { label: 'regex', value: 'regex' }
]

const EMPTY_OPERATORS: { label: string; value: string }[] = [
  { label: 'is empty', value: 'is_empty' },
  { label: 'is not empty', value: 'is_not_empty' }
]

function isNumericColumn(column: string): boolean {
  const info = filteringStore.availableColumns.find((c) => c.name === column)
  if (!info) return true // default to numeric (matches prior single-operator-set behaviour when column not yet resolved)
  return !info.dtype.toLowerCase().includes('str') && !info.dtype.toLowerCase().includes('utf8')
}

function operatorsForColumn(column: string): { label: string; value: string }[] {
  const base = isNumericColumn(column) ? NUMERIC_OPERATORS : STRING_OPERATORS
  return [...base, ...EMPTY_OPERATORS]
}

function isEmptyOperator(operator: string): boolean {
  return operator === 'is_empty' || operator === 'is_not_empty'
}

const savedSetName = ref('')

onMounted(async () => {
  if (filteringStore.hasSelectedRuns) {
    await filteringStore.fetchAvailableColumns()
    await filteringStore.flushApply()
  }
})

watch(
  () => filteringStore.activeRunIds.slice().sort().join(','),
  async () => {
    filteringStore.previewResult = null
    filteringStore.clearAppliedFilters()
    await filteringStore.fetchAvailableColumns()
    await filteringStore.flushApply()
  }
)

const handlePreview = async () => {
  try {
    await filteringStore.runPreview()
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Preview failed',
      detail: err instanceof Error ? err.message : 'Unknown error',
      life: 6000
    })
  }
}

const handleApplyRanking = async () => {
  try {
    await filteringStore.applyRanking()
    toast.add({ severity: 'success', summary: 'Ranking applied', life: 4000 })
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Failed to apply ranking',
      detail: err instanceof Error ? err.message : 'Unknown error',
      life: 6000
    })
  }
}

const handleApplyDiversity = async () => {
  try {
    await filteringStore.applyDiversityFilter()
    const res = filteringStore.lastDiversityResult
    toast.add({
      severity: 'success',
      summary: 'Diversity filter applied',
      detail: res
        ? `${res.diverse_set_count} diverse designs selected from ${res.passing_filters} passing filters (of ${res.total_designs} total).`
        : undefined,
      life: 8000
    })
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Failed to apply diversity filter',
      detail: err instanceof Error ? err.message : 'Unknown error',
      life: 6000
    })
  }
}

// InputNumber only emits `update:model-value` on blur/Enter, not per keystroke —
// its `input` event fires live as the user types, so use that to keep the debounced
// apply in sync without requiring the field to lose focus.
const handleThresholdInput = (filter: FilterSpecDto, event: InputNumberInputEvent) => {
  filter.threshold = typeof event.value === 'number' ? event.value : null
  filteringStore.scheduleApply()
}

const handleDisableAllFilters = () => {
  filteringStore.disableAllFilters()
  toast.add({ severity: 'info', summary: 'All filters disabled', life: 3000 })
}

const handleCreateSavedSet = async () => {
  const name = savedSetName.value.trim()
  if (!name) {
    toast.add({ severity: 'warn', summary: 'Name required', detail: 'Give the saved set a name.', life: 4000 })
    return
  }
  try {
    const res = await filteringStore.createSavedSet(name)
    toast.add({
      severity: 'success',
      summary: 'Saved set created',
      detail: `"${res.name}": ${res.diverse_set_count} designs selected from ${res.passing_filters} passing filters (of ${res.total_input} total).`,
      life: 8000
    })
    savedSetName.value = ''
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Failed to create saved set',
      detail: err instanceof Error ? err.message : 'Unknown error',
      life: 6000
    })
  }
}

const formatSampleRange = (col: { sample_values?: { min: number; max: number } | null }) => {
  if (!col.sample_values) return '—'
  return `${col.sample_values.min.toFixed(2)} – ${col.sample_values.max.toFixed(2)}`
}

const formatEquivalentColumns = (col: { raw_columns?: Record<string, string> }) => {
  if (!col.raw_columns || Object.keys(col.raw_columns).length === 0) return '—'
  return Object.entries(col.raw_columns)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([method, raw]) => `${method}: ${raw}`)
    .join(', ')
}

interface CascadeRow {
  column: string
  operator: string
  threshold: number | null
  remaining: number | null
  enabled: boolean
  isFinal: boolean
}

// Every configured filter is listed (including disabled ones, via filteringStore's
// shared filterChain — see stores/filtering.ts), each with a "remaining" count.
// Diversity selection is a separate, explicit action (not part of the hard-filter
// cascade the backend computes for /api/filtering/preview — see plan §7A.2), but it's
// conceptually the cascade's next stage, so it's appended here client-side rather than
// requiring the backend to know about it. "Final set" is always its own trailing
// summary row — no threshold, and its remaining count mirrors whichever stage above it
// last actually narrowed the set (diversity selection if applied, else the last
// enabled filter, else the unfiltered total when no filters are configured/enabled).
const cascadeRows = computed<CascadeRow[]>(() => {
  const rows: CascadeRow[] = filteringStore.filterChain.map((item) => ({
    column: item.column,
    operator: item.operator,
    threshold: item.threshold,
    remaining: item.remaining,
    enabled: item.enabled,
    isFinal: false
  }))

  const diversity = filteringStore.lastDiversityResult
  if (diversity) {
    rows.push({
      column: 'Diversity Selection',
      operator: `budget=${filteringStore.budget}, α=${filteringStore.alpha.toFixed(2)}`,
      threshold: null,
      remaining: diversity.diverse_set_count,
      enabled: true,
      isFinal: false
    })
  }

  let finalRemaining = filteringStore.initialDesignCount ?? 0
  for (let i = rows.length - 1; i >= 0; i--) {
    if (rows[i].remaining != null) {
      finalRemaining = rows[i].remaining as number
      break
    }
  }
  rows.push({
    column: 'Final set',
    operator: '',
    threshold: null,
    remaining: finalRemaining,
    enabled: true,
    isFinal: true
  })

  return rows
})

function cascadeRowClass(data: CascadeRow) {
  return { 'fsb-cascade-row--final': data.isFinal, 'fsb-cascade-row--disabled': !data.enabled }
}
</script>

<template>
  <div class="filter-set-builder">
    <Panel v-if="!filteringStore.hasSelectedRuns" header="Source Runs" class="fsb-panel">
      <p class="fsb-hint">
        No runs selected. Run scope for filtering comes from the <strong>Select
        Runs</strong> tab — pick one or more runs there, and they'll be pooled together
        here for filtering/ranking/diversity selection.
      </p>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="Available Metrics" class="fsb-panel" toggleable collapsed>
      <div v-if="filteringStore.columnsLoading" class="fsb-hint">Loading columns…</div>
      <Message v-else-if="filteringStore.columnsError" severity="error" :closable="false">
        {{ filteringStore.columnsError }}
      </Message>
      <DataTable
        v-else
        :value="filteringStore.availableColumns"
        size="small"
        data-key="name"
        class="fsb-columns-table"
      >
        <Column field="name" header="Column" sortable />
        <Column field="canonical_name" header="Canonical" sortable>
          <template #body="{ data }">
            <Tag v-if="data.canonical_name" :value="data.canonical_name" severity="info" />
            <span v-else>—</span>
          </template>
        </Column>
        <Column header="Present in runs (method)">
          <template #body="{ data }">
            <Tag
              v-for="method in data.present_in_runs"
              :key="method"
              :value="method"
              :style="getMethodTagStyle(method)"
              class="pipeline-palette-tag fsb-method-tag"
            />
          </template>
        </Column>
        <Column header="Equivalent columns">
          <template #body="{ data }">{{ formatEquivalentColumns(data) }}</template>
        </Column>
        <Column header="Range">
          <template #body="{ data }">{{ formatSampleRange(data) }}</template>
        </Column>
      </DataTable>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="1. Hard Filters" class="fsb-panel">
      <p class="fsb-hint">
        Every design must pass all filters to be counted as "passing". Filters are
        applied live to the Designs table.
      </p>
      <div
        v-for="(filter, idx) in filteringStore.filters"
        :key="idx"
        class="fsb-filter-row"
        :class="{ 'fsb-row--disabled': filter.enabled === false }"
      >
        <ToggleSwitch
          v-model="filter.enabled"
          :true-value="true"
          :false-value="false"
          aria-label="Enable filter"
          class="fsb-row__enable-toggle"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <MetricColumnSelector
          v-model="filter.column"
          :columns="filteringStore.availableColumns"
          :disabled="filter.enabled === false"
          class="fsb-filter-row__column"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <Select
          v-model="filter.operator"
          :options="operatorsForColumn(filter.column)"
          option-label="label"
          option-value="value"
          :disabled="filter.enabled === false"
          class="fsb-filter-row__operator"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <InputNumber
          v-if="!isEmptyOperator(filter.operator) && isNumericColumn(filter.column)"
          v-model="filter.threshold"
          :min-fraction-digits="0"
          :max-fraction-digits="4"
          :disabled="filter.enabled === false"
          class="fsb-filter-row__threshold"
          @input="handleThresholdInput(filter, $event)"
        />
        <InputText
          v-else-if="!isEmptyOperator(filter.operator)"
          v-model="filter.text_value"
          placeholder="Value…"
          :disabled="filter.enabled === false"
          class="fsb-filter-row__threshold"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <Button
          icon="pi pi-trash"
          severity="danger"
          text
          rounded
          aria-label="Remove filter"
          @click="filteringStore.removeFilter(idx)"
        />
      </div>
      <div class="fsb-filter-actions">
        <Button
          label="Add filter"
          icon="pi pi-plus"
          text
          size="small"
          @click="filteringStore.addFilter()"
        />
        <Button
          label="Disable all filters"
          icon="pi pi-ban"
          text
          size="small"
          severity="secondary"
          @click="handleDisableAllFilters"
        />
        <span v-if="filteringStore.applyLoading" class="fsb-apply-status">
          <i class="pi pi-spin pi-spinner" /> Applying…
        </span>
        <span v-else-if="filteringStore.passingDesignKeys" class="fsb-apply-status">
          {{ filteringStore.passingDesignKeys.size }} designs passing
        </span>
      </div>
      <Message v-if="filteringStore.applyError" severity="error" :closable="false" class="fsb-preview-error">
        {{ filteringStore.applyError }}
      </Message>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="2. Ranking Metrics" class="fsb-panel">
      <p class="fsb-hint">
        Designs are ranked by the <em>worst</em> of their scaled ranks across these
        metrics (boltzgen's "Algorithm 2" — see plan §2.2). Weight is inverse
        importance: a larger weight de-emphasises that metric.
      </p>
      <div
        v-for="(metric, idx) in filteringStore.rankingMetrics"
        :key="idx"
        class="fsb-metric-row"
        :class="{ 'fsb-row--disabled': metric.enabled === false }"
      >
        <ToggleSwitch
          v-model="metric.enabled"
          :true-value="true"
          :false-value="false"
          aria-label="Enable ranking metric"
          class="fsb-row__enable-toggle"
        />
        <MetricColumnSelector
          v-model="metric.column"
          :columns="filteringStore.availableColumns"
          :disabled="metric.enabled === false"
          class="fsb-metric-row__column"
        />
        <label class="fsb-metric-row__weight-label">
          Weight
          <InputNumber
            v-model="metric.weight"
            :min="0.01"
            :max-fraction-digits="2"
            :step="0.5"
            :disabled="metric.enabled === false"
            class="fsb-metric-row__weight"
          />
        </label>
        <label class="fsb-metric-row__toggle">
          <input type="checkbox" v-model="metric.higher_is_better" :disabled="metric.enabled === false" />
          Higher is better
        </label>
        <Button
          icon="pi pi-trash"
          severity="danger"
          text
          rounded
          aria-label="Remove ranking metric"
          @click="filteringStore.removeRankingMetric(idx)"
        />
      </div>
      <div class="fsb-filter-actions">
        <Button
          label="Add ranking metric"
          icon="pi pi-plus"
          text
          size="small"
          @click="filteringStore.addRankingMetric()"
        />
        <Button
          label="Apply Ranking"
          icon="pi pi-sort-numeric-down"
          size="small"
          :loading="filteringStore.rankLoading"
          :disabled="!filteringStore.hasSelectedRuns"
          @click="handleApplyRanking"
        />
        <span v-if="filteringStore.rankedDesigns" class="fsb-apply-status">
          Ranked {{ filteringStore.rankedDesigns.size }} designs
        </span>
      </div>
      <Message v-if="filteringStore.rankError" severity="error" :closable="false" class="fsb-preview-error">
        {{ filteringStore.rankError }}
      </Message>
      <p class="fsb-hint">
        Ranking is not applied automatically — click "Apply Ranking" after configuring
        metrics. This attaches <code>final_rank</code>/<code>quality_score</code> to the
        Designs table without narrowing which rows are shown.
      </p>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="3. Diversity Selection" class="fsb-panel">
      <div class="fsb-diversity-row">
        <label class="fsb-diversity-field">
          Budget (designs in final set)
          <InputNumber v-model="filteringStore.budget" :min="1" show-buttons />
        </label>
        <label class="fsb-diversity-field fsb-diversity-field--alpha">
          Quality ↔ Diversity (α = {{ filteringStore.alpha.toFixed(2) }})
          <Slider v-model="filteringStore.alpha" :min="0" :max="1" :step="0.05" />
          <span class="fsb-hint">0 = quality only, 1 = diversity only</span>
        </label>
      </div>

      <div class="fsb-best-mpnn-row">
        <Checkbox
          :modelValue="designsStore.bestMpnnOnly"
          @update:modelValue="designsStore.toggleBestMpnnOnly"
          :binary="true"
          inputId="fsb-best-mpnn-only"
        />
        <label for="fsb-best-mpnn-only">Only best MPNN variant per backbone</label>
      </div>

      <details class="fsb-size-buckets">
        <summary>Size buckets (optional — caps selections per sequence-length range)</summary>
        <div
          v-for="(bucket, idx) in filteringStore.sizeBuckets"
          :key="idx"
          class="fsb-bucket-row"
        >
          <label>Min <InputNumber v-model="bucket.min" :min="0" /></label>
          <label>Max <InputNumber v-model="bucket.max" :min="0" /></label>
          <label>Count <InputNumber v-model="bucket.num_designs" :min="0" /></label>
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            aria-label="Remove size bucket"
            @click="filteringStore.removeSizeBucket(idx)"
          />
        </div>
        <Button
          label="Add size bucket"
          icon="pi pi-plus"
          text
          size="small"
          @click="filteringStore.addSizeBucket()"
        />
      </details>

      <div class="fsb-filter-actions">
        <Button
          label="Apply Diversity Filter"
          icon="pi pi-sitemap"
          size="small"
          :loading="filteringStore.diversityLoading"
          :disabled="!filteringStore.hasSelectedRuns"
          @click="handleApplyDiversity"
        />
        <span v-if="filteringStore.lastDiversityResult" class="fsb-apply-status">
          {{ filteringStore.lastDiversityResult.diverse_set_count }} diverse designs selected
        </span>
      </div>
      <Message v-if="filteringStore.diversityError" severity="error" :closable="false" class="fsb-preview-error">
        {{ filteringStore.diversityError }}
      </Message>
      <p class="fsb-hint">
        Not applied automatically — this can be slow (pairwise alignment-based
        diversity selection). Narrows the Designs table to just the diverse subset.
      </p>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="4. Filter cascade" class="fsb-panel">
      <p class="fsb-hint">
        Updates automatically as hard filters change (debounced) — no need to
        re-trigger manually.
      </p>
      <span v-if="filteringStore.previewLoading" class="fsb-apply-status">
        <i class="pi pi-spin pi-spinner" /> Updating preview…
      </span>
      <Message v-if="filteringStore.previewError" severity="error" :closable="false" class="fsb-preview-error">
        {{ filteringStore.previewError }}
        <Button label="Retry" text size="small" @click="handlePreview" />
      </Message>
      <div v-if="filteringStore.previewResult" class="fsb-preview-result">
        <p>
          <strong>{{ filteringStore.previewResult.total_designs }}</strong> total designs
          across selected runs.
        </p>
        <DataTable
          v-if="cascadeRows.length > 0"
          :value="cascadeRows"
          size="small"
          :rowClass="cascadeRowClass"
        >
          <Column header="Filter">
            <template #body="{ data }">
              <Tag v-if="data.isFinal" severity="success" value="Final set" />
              <span v-else>{{ data.column }}</span>
            </template>
          </Column>
          <Column header="Threshold">
            <template #body="{ data }">{{ data.threshold !== null ? `${data.operator} ${data.threshold}` : data.operator }}</template>
          </Column>
          <Column field="remaining" header="Remaining" />
        </DataTable>
        <p v-if="!filteringStore.lastDiversityResult" class="fsb-hint">
          No diversity filter applied.
        </p>
      </div>
    </Panel>

    <Panel v-if="filteringStore.hasSelectedRuns" header="5. Create Saved Set" class="fsb-panel">
      <div class="fsb-create-row">
        <InputText
          v-model="savedSetName"
          placeholder="Saved set name…"
          class="fsb-create-row__name"
        />
        <Button
          label="Create Saved Set"
          icon="pi pi-save"
          :loading="filteringStore.creatingSavedSet"
          :disabled="!filteringStore.canCreateSavedSet"
          @click="handleCreateSavedSet"
        />
      </div>
      <Message
        v-if="filteringStore.createSavedSetError"
        severity="error"
        :closable="false"
        class="fsb-preview-error"
      >
        {{ filteringStore.createSavedSetError }}
      </Message>
      <p v-if="filteringStore.lastCreatedSavedSet" class="fsb-hint">
        Last created: <strong>{{ filteringStore.lastCreatedSavedSet.name }}</strong> —
        {{ filteringStore.lastCreatedSavedSet.diverse_set_count }} designs selected
        (budget {{ filteringStore.lastCreatedSavedSet.top_set_count }}), from
        {{ filteringStore.lastCreatedSavedSet.passing_filters }} passing filters of
        {{ filteringStore.lastCreatedSavedSet.total_input }} total. View it under Saved
        Sets.
      </p>
    </Panel>
  </div>
</template>

<style scoped>
.filter-set-builder {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.fsb-panel {
  width: 100%;
}

.fsb-hint {
  font-size: 0.85rem;
  color: #6c757d;
  margin: 0.25rem 0 0.75rem 0;
}

.fsb-columns-table {
  width: 100%;
}

.fsb-filter-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.25rem;
}

.fsb-apply-status {
  font-size: 0.85rem;
  color: #495057;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.fsb-method-tag {
  margin-right: 0.25rem;
}

.fsb-filter-row,
.fsb-metric-row,
.fsb-bucket-row {
  display: flex;
  /* flex-start, not center: MetricColumnSelector's height varies row-to-row (it grows
     when it shows a min/max/mean/median hint under the dropdown for whichever column is
     currently selected), and center-alignment against a variable-height sibling made
     the Select box visibly shift up/down between rows depending on whether its neighbour
     had a hint showing. flex-start keeps every control's top edge aligned regardless. */
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
  flex-wrap: wrap;
}

/* Controls that don't grow (toggle, operator/weight fields, delete button) still want
   to be centered on the dropdown's own control line, not glued to the row's top edge. */
.fsb-row__enable-toggle,
.fsb-filter-row__operator,
.fsb-filter-row__threshold,
.fsb-filter-row > .p-button,
.fsb-metric-row__weight-label,
.fsb-metric-row__toggle,
.fsb-metric-row > .p-button {
  margin-top: 0.3rem;
}

.fsb-row--disabled {
  opacity: 0.55;
}

.fsb-filter-row__column,
.fsb-metric-row__column {
  flex: 1 1 260px;
  min-width: 220px;
}

.fsb-filter-row__operator {
  min-width: 12rem;
}

.fsb-filter-row__threshold {
  min-width: 8rem;
}

/* Same PrimeVue InputNumber inner-<input>-overflow issue as
   .fsb-metric-row__weight below — belt and braces since this wrapper is also
   width-constrained next to a sibling (the delete button). */
.fsb-filter-row__threshold :deep(input) {
  width: 100%;
  box-sizing: border-box;
}

.fsb-metric-row__weight-label,
.fsb-metric-row__toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #495057;
}

.fsb-metric-row__weight {
  width: 9rem;
}

/* PrimeVue's InputNumber inner <input> doesn't respect the wrapper's width by
   default and overflows past it (observed: 205px inner input inside a 144px
   wrapper), visually overlapping/painting over whatever sits to its right. */
.fsb-metric-row__weight :deep(input) {
  width: 100%;
  box-sizing: border-box;
}

.fsb-diversity-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.fsb-diversity-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.fsb-diversity-field--alpha {
  min-width: 20rem;
  flex: 1;
}

.fsb-best-mpnn-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #495057;
  margin-bottom: 0.75rem;
}

.fsb-size-buckets {
  margin-top: 0.5rem;
}

.fsb-size-buckets summary {
  cursor: pointer;
  font-size: 0.85rem;
  color: #495057;
  margin-bottom: 0.5rem;
}

.fsb-bucket-row label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
}

.fsb-preview-result {
  margin-top: 1rem;
}

.fsb-cascade-row--final {
  font-weight: 600;
  background-color: #e6f4ea !important;
}

.fsb-cascade-row--disabled {
  opacity: 0.5;
  text-decoration: line-through;
}

.fsb-preview-error {
  margin-top: 0.75rem;
}

.fsb-create-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.fsb-create-row__name {
  min-width: 20rem;
  flex: 1;
}
</style>
