<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import MultiSelect from 'primevue/multiselect'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import { useToast } from 'primevue/usetoast'
import { useFilteringStore } from '../stores'
import type { TargetContactFilterSpecDto } from '../webapi'
import type { InputNumberInputEvent } from 'primevue/inputnumber'

const filteringStore = useFilteringStore()
const toast = useToast()

/**
 * Records are only stored for residues within this distance of the binder (see the
 * backend's DEFAULT_RECORD_CUTOFF), so a larger threshold cannot be answered.
 */
const RECORD_CUTOFF = 12

// Conditions are worded rather than exposed as raw (metric, operator) pairs, so the
// direction of each comparison is unambiguous.
const CONDITIONS: {
  label: string
  metric: TargetContactFilterSpecDto['metric']
  operator: TargetContactFilterSpecDto['operator']
}[] = [
  { label: 'within X of binder', metric: 'distance', operator: '<=' },
  { label: 'further than X from binder', metric: 'distance', operator: '>' },
  { label: 'SASA when bound ≤', metric: 'sasa_bound', operator: '<=' },
  { label: 'SASA when bound ≥', metric: 'sasa_bound', operator: '>=' },
  { label: 'ΔSASA on binding ≥', metric: 'delta_sasa', operator: '>=' },
  { label: 'ΔSASA on binding ≤', metric: 'delta_sasa', operator: '<=' }
]

const DISTANCE_TYPES = [
  { label: 'Heavy atoms', value: 'heavy' },
  { label: 'CA distance', value: 'ca' },
  { label: 'CB distance', value: 'cb' }
]

const UNITS = [
  { label: 'Å²', value: 'angstrom' },
  { label: '% of max', value: 'percent' }
]

const SCOPES = [
  { label: 'any residue', value: 'any' },
  { label: 'all residues', value: 'all' },
  { label: 'at least N', value: 'count' },
  { label: 'site total', value: 'site_percent' }
]

const conditionKey = (filter: TargetContactFilterSpecDto) => `${filter.metric}|${filter.operator}`

function setCondition(filter: TargetContactFilterSpecDto, key: string) {
  const condition = CONDITIONS.find((c) => `${c.metric}|${c.operator}` === key)
  if (!condition) return
  filter.metric = condition.metric
  filter.operator = condition.operator
  // Site totals are a percentage of the residues' combined maximum surface, so the
  // unit toggle does not apply and distance has no meaningful sum.
  if (filter.scope === 'site_percent' && filter.metric === 'distance') {
    filter.scope = 'any'
  }
  filteringStore.scheduleApply()
}

const conditionOptions = computed(() =>
  CONDITIONS.map((c) => ({ label: c.label, value: `${c.metric}|${c.operator}` }))
)

function residueOptions(targetKey: string) {
  return filteringStore.residuesForTarget(targetKey).map((r) => ({
    label: `${r.aa1}${r.resseq}`,
    sublabel: `${r.chain} · ${r.resname}`,
    value: r.label
  }))
}

const coverage = computed(() => filteringStore.contactCoverageTotals)
const computeRunning = computed(() => filteringStore.contactsComputeProgress.running)
const computeProgress = computed(() => {
  const { done, total } = filteringStore.contactsComputeProgress
  return total > 0 ? Math.round((done / total) * 100) : 0
})

const handleValueInput = (filter: TargetContactFilterSpecDto, event: InputNumberInputEvent) => {
  filter.value = typeof event.value === 'number' ? event.value : 0
  filteringStore.scheduleApply()
}

const handleCompute = async () => {
  try {
    await filteringStore.computeTargetContacts()
    toast.add({
      severity: filteringStore.contactsComputeError ? 'warn' : 'success',
      summary: 'Target contacts computed',
      detail: filteringStore.contactsComputeError ?? undefined,
      life: filteringStore.contactsComputeError ? 10000 : 5000
    })
  } catch (err) {
    toast.add({
      severity: 'error',
      summary: 'Failed to compute target contacts',
      detail: err instanceof Error ? err.message : 'Unknown error',
      life: 8000
    })
  }
}

onMounted(() => {
  if (filteringStore.hasSelectedRuns) void filteringStore.fetchTargets()
})

watch(
  () => filteringStore.activeRunIds.slice().sort().join(','),
  () => {
    void filteringStore.fetchTargets()
  }
)
</script>

<template>
  <div class="tcf">
    <p class="tcf-hint">
      Require designs to contact (or avoid) specific target residues. These apply
      alongside the hard filters above.
    </p>

    <div class="tcf-coverage">
      <span>
        Target contacts computed for
        <strong>{{ coverage.computed.toLocaleString() }}</strong> of
        <strong>{{ coverage.total.toLocaleString() }}</strong> designs
      </span>
      <Button
        label="Compute target contacts"
        icon="pi pi-calculator"
        size="small"
        :loading="computeRunning"
        :disabled="computeRunning || !filteringStore.hasSelectedRuns"
        @click="handleCompute"
      />
      <ProgressBar v-if="computeRunning" :value="computeProgress" class="tcf-progress" />
    </div>

    <Message
      v-if="filteringStore.hasUncomputedContacts && !computeRunning"
      severity="warn"
      :closable="false"
      class="tcf-message"
    >
      {{ filteringStore.runsMissingContacts.length }} run(s) have designs without computed
      contacts. Those designs fail every condition below until you compute them.
    </Message>

    <Message v-if="filteringStore.targetsError" severity="error" :closable="false" class="tcf-message">
      {{ filteringStore.targetsError }}
    </Message>

    <Message
      v-for="run in filteringStore.targetCoverage.filter((c) => c.target_moves)"
      :key="`moves-${run.run_id}`"
      severity="info"
      :closable="false"
      class="tcf-message"
    >
      {{ run.run_name }}: the target moves between designs, so unbound SASA is computed
      per design rather than once per run.
    </Message>

    <div
      v-for="(group, groupIndex) in filteringStore.targetContactGroups"
      :key="`group-${groupIndex}`"
      class="tcf-group"
    >
      <div class="tcf-group__header">
        <template v-if="filteringStore.hasMultipleTargets">
          <label class="tcf-group__label">Target</label>
          <Select
            :model-value="group.target_key"
            :options="filteringStore.targets"
            option-label="label"
            option-value="target_key"
            class="tcf-group__target"
            @update:model-value="filteringStore.setTargetContactGroupTarget(groupIndex, $event)"
          />
          <span class="tcf-group__runs">
            {{ filteringStore.targets.find((t) => t.target_key === group.target_key)?.run_ids.length ?? 0 }}
            run(s)
          </span>
          <Button
            icon="pi pi-trash"
            severity="danger"
            text
            rounded
            aria-label="Remove target section"
            @click="filteringStore.removeTargetContactGroup(groupIndex)"
          />
        </template>
        <span v-else class="tcf-group__label">Target residues</span>
      </div>

      <div
        v-for="(filter, filterIndex) in group.filters"
        :key="`filter-${groupIndex}-${filterIndex}`"
        class="tcf-row"
        :class="{ 'tcf-row--disabled': filter.enabled === false }"
      >
        <ToggleSwitch
          v-model="filter.enabled"
          :true-value="true"
          :false-value="false"
          aria-label="Enable condition"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <MultiSelect
          v-model="filter.residues"
          :options="residueOptions(group.target_key)"
          option-label="label"
          option-value="value"
          filter
          display="chip"
          placeholder="Select residues…"
          :disabled="filter.enabled === false"
          class="tcf-row__residues"
          @update:model-value="filteringStore.scheduleApply()"
        >
          <template #option="{ option }">
            <span class="tcf-option">
              <strong>{{ option.label }}</strong>
              <span class="tcf-option__sub">{{ option.sublabel }}</span>
            </span>
          </template>
        </MultiSelect>
        <Select
          :model-value="conditionKey(filter)"
          :options="conditionOptions"
          option-label="label"
          option-value="value"
          :disabled="filter.enabled === false"
          class="tcf-row__condition"
          @update:model-value="setCondition(filter, $event)"
        />
        <InputNumber
          v-model="filter.value"
          :min="0"
          :max="filter.metric === 'distance' ? RECORD_CUTOFF : undefined"
          :min-fraction-digits="0"
          :max-fraction-digits="2"
          :disabled="filter.enabled === false"
          class="tcf-row__value"
          @input="handleValueInput(filter, $event)"
        />
        <Select
          v-if="filter.metric === 'distance'"
          v-model="filter.distance_type"
          :options="DISTANCE_TYPES"
          option-label="label"
          option-value="value"
          :disabled="filter.enabled === false"
          class="tcf-row__qualifier"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <Select
          v-else-if="filter.scope !== 'site_percent'"
          v-model="filter.unit"
          :options="UNITS"
          option-label="label"
          option-value="value"
          :disabled="filter.enabled === false"
          class="tcf-row__qualifier"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <span v-else class="tcf-row__qualifier tcf-row__qualifier--fixed">% of max</span>
        <Select
          v-model="filter.scope"
          :options="filter.metric === 'distance' ? SCOPES.filter((s) => s.value !== 'site_percent') : SCOPES"
          option-label="label"
          option-value="value"
          :disabled="filter.enabled === false"
          class="tcf-row__scope"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <InputNumber
          v-if="filter.scope === 'count'"
          v-model="filter.min_count"
          :min="1"
          :max="filter.residues.length || 1"
          :disabled="filter.enabled === false"
          class="tcf-row__count"
          @update:model-value="filteringStore.scheduleApply()"
        />
        <Button
          icon="pi pi-trash"
          severity="danger"
          text
          rounded
          aria-label="Remove condition"
          @click="filteringStore.removeTargetContactFilter(groupIndex, filterIndex)"
        />
      </div>

      <div class="tcf-group__actions">
        <Button
          label="Add condition"
          icon="pi pi-plus"
          text
          size="small"
          :disabled="!group.target_key"
          @click="filteringStore.addTargetContactFilter(groupIndex)"
        />
      </div>
    </div>

    <div class="tcf-actions">
      <Button
        v-if="filteringStore.hasMultipleTargets || filteringStore.targetContactGroups.length === 0"
        label="Add target"
        icon="pi pi-plus"
        text
        size="small"
        :disabled="filteringStore.targets.length === 0"
        @click="filteringStore.addTargetContactGroup()"
      />
      <span v-if="filteringStore.targetsLoading" class="tcf-status">
        <i class="pi pi-spin pi-spinner" /> Loading target residues…
      </span>
      <span v-else-if="filteringStore.targets.length === 0" class="tcf-status">
        No target could be resolved for the selected runs.
      </span>
    </div>
  </div>
</template>

<style scoped>
.tcf {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tcf-hint {
  margin: 0;
  font-size: 0.85rem;
  color: #6c757d;
}

.tcf-coverage {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  font-size: 0.85rem;
  background: #f1f3f5;
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.tcf-progress {
  flex: 1 1 200px;
  height: 0.5rem;
}

.tcf-message {
  margin: 0;
}

.tcf-group {
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tcf-group__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tcf-group__label {
  font-weight: 600;
  font-size: 0.85rem;
}

.tcf-group__target {
  min-width: 260px;
}

.tcf-group__runs {
  font-size: 0.8rem;
  color: #6c757d;
}

.tcf-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tcf-row--disabled {
  opacity: 0.55;
}

.tcf-row__residues {
  min-width: 260px;
  max-width: 420px;
}

.tcf-row__condition {
  min-width: 190px;
}

.tcf-row__value {
  width: 110px;
}

.tcf-row__qualifier {
  min-width: 120px;
}

.tcf-row__qualifier--fixed {
  font-size: 0.85rem;
  color: #6c757d;
}

.tcf-row__scope {
  min-width: 130px;
}

.tcf-row__count {
  width: 80px;
}

.tcf-option {
  display: flex;
  flex-direction: column;
}

.tcf-option__sub {
  font-size: 0.75rem;
  color: #6c757d;
}

.tcf-group__actions,
.tcf-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.tcf-status {
  font-size: 0.85rem;
  color: #6c757d;
}
</style>
