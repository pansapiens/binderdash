<template>
  <div class="prepare-sequences-view">
    <div class="ps-header">
      <h2>Prepare sequences</h2>
    </div>

    <div class="ps-intro-box">
      <p class="ps-intro">
        <strong>Tagging:</strong> Tags you place in the <strong>N-tagged</strong> and <strong>C-tagged</strong> areas are only added to designs whose
        <strong>tag</strong> column is <code>N</code> or <code>C</code> respectively. Designs with another tag value get
        only the core sequence plus the global N/C terminal additions and optional stop.
      </p>
      <p class="ps-case-help">
        <strong>Entering amino acid and nucleotides:</strong> Sequences entered in uppercase are interpreted as amino acids, lowercase are nucleotides. You can mix and match
        upper and lowercase (eg <code>atgGS</code> translates to <code>MGS</code>).
      </p>
    </div>

    <div class="ps-order-name">
      <label for="ps-export-order-name">Order name:</label>
      <InputText
        id="ps-export-order-name"
        v-model="seqPrep.exportOrderName"
        placeholder="Optional; used in download filenames instead of prepared_sequences"
        class="w-full"
      />
    </div>

    <div class="ps-builder card-like">
      <div class="ps-builder-row">
        <div class="ps-zone">
          <span class="ps-zone-label">N-tagged</span>
          <div class="ps-chips">
            <Chip
              v-for="(t, i) in seqPrep.nTags"
              :key="t.id"
              :label="`${t.label} ${t.sequence}`"
              removable
              class="ps-tag-chip"
              :style="tagPresetChipCssVars(t.kind)"
              @remove="seqPrep.removeTag('n', i)"
            >
              <div class="ps-tag-chip-body">
                <span class="ps-tag-chip-name">{{ t.label }}</span>
                <span class="ps-tag-chip-seq">{{ t.sequence }}</span>
              </div>
            </Chip>
            <span v-if="seqPrep.nTags.length === 0" class="ps-placeholder">Add tags below</span>
          </div>
        </div>
        <span class="ps-binder-label">-{design}-</span>
        <div class="ps-zone">
          <span class="ps-zone-label">C-tagged</span>
          <div class="ps-chips">
            <Chip
              v-for="(t, i) in seqPrep.cTags"
              :key="t.id"
              :label="`${t.label} ${t.sequence}`"
              removable
              class="ps-tag-chip"
              :style="tagPresetChipCssVars(t.kind)"
              @remove="seqPrep.removeTag('c', i)"
            >
              <div class="ps-tag-chip-body">
                <span class="ps-tag-chip-name">{{ t.label }}</span>
                <span class="ps-tag-chip-seq">{{ t.sequence }}</span>
              </div>
            </Chip>
            <span v-if="seqPrep.cTags.length === 0" class="ps-placeholder">Add tags below</span>
          </div>
        </div>
      </div>

      <div class="ps-palette">
        <span class="ps-palette-label">Add to N side:</span>
        <Button
          v-for="p in seqPrep.presetOptionsN"
          :key="'n-' + p.kind"
          size="small"
          severity="secondary"
          outlined
          :label="p.tag_name"
          class="ps-preset-btn"
          :style="tagPresetChromeStyle(p.kind)"
          @click="seqPrep.addPreset('n', p)"
        />
        <span class="ps-palette-label ps-ml">Add to C side:</span>
        <Button
          v-for="p in seqPrep.presetOptionsC"
          :key="'c-' + p.kind"
          size="small"
          severity="secondary"
          outlined
          :label="p.tag_name"
          class="ps-preset-btn"
          :style="tagPresetChromeStyle(p.kind)"
          @click="seqPrep.addPreset('c', p)"
        />
      </div>
      <div class="ps-custom-row">
        <InputText
          v-model="seqPrep.customTagInput"
          placeholder="Custom sequence (UPPERCASE=AA, lowercase=nuc)"
          class="ps-custom-input"
          @keyup.enter="addCustomBoth"
        />
        <Button size="small" label="Add custom → N" @click="seqPrep.addCustomTag('n')" />
        <Button size="small" label="Add custom → C" @click="seqPrep.addCustomTag('c')" />
      </div>
    </div>

    <div class="ps-form grid card-like">
      <div class="ps-field">
        <label for="ps-npre">Add sequence to all N-terminal</label>
        <InputText
          id="ps-npre"
          v-model="seqPrep.nTerminalPrefix"
          class="w-full ps-terminal-input ps-terminal-input--n"
        />
      </div>
      <div class="ps-field">
        <label for="ps-csuf">Add sequence to all C-terminal</label>
        <InputText
          id="ps-csuf"
          v-model="seqPrep.cTerminalSuffix"
          class="w-full ps-terminal-input ps-terminal-input--c"
        />
      </div>
      <div class="ps-field ps-checks">
        <Checkbox v-model="seqPrep.includeStop" input-id="ps-stop" binary />
        <label for="ps-stop">Include stop *</label>
      </div>
      <div class="ps-field">
        <label for="ps-chain">Chain to extract (PDB/mmCIF)</label>
        <Select
          id="ps-chain"
          v-model="seqPrep.extractChain"
          :options="chainOptions"
          class="w-full"
        />
      </div>
      <div class="ps-field-row ps-field-row--padding">
        <div class="ps-field">
          <label for="ps-pad">Post-stop padding</label>
          <InputText
            id="ps-pad"
            v-model="seqPrep.postStopPadding"
            class="w-full"
            placeholder="UPPERCASE=AA, lowercase=nuc (a,c,g,t)"
          />
        </div>
        <div class="ps-field">
          <label for="ps-pad-up-to">Pad up to nucleotide length (bp)</label>
          <InputNumber
            id="ps-pad-up-to"
            v-model="seqPrep.postStopPadUpToNucleotideLength"
            class="w-full"
            :min="0"
            :allow-empty="true"
            placeholder="Leave empty to omit padding"
          />
        </div>
      </div>
      <div v-if="seqPrep.dnaMode" class="ps-field">
        <label for="ps-minlen">Minimum DNA fragment length (bp)</label>
        <InputNumber
          id="ps-minlen"
          v-model="seqPrep.minDnaFragmentLength"
          :min="0"
          :max="100000"
          class="w-full"
        />
      </div>
    </div>

    <div class="ps-optimization-toolbar card-like mt-3">
      <div class="ps-opt-header">
        <div class="ps-codon-field">
          <label for="ps-codon-table" class="ps-codon-label">Target organism (Codon table)</label>
          <Select
            id="ps-codon-table"
            v-model="seqPrep.selectedCodonTable"
            :options="seqPrep.codonTableOptions"
            option-label="label"
            option-value="value"
            :loading="seqPrep.codonTablesListLoading || seqPrep.codonTablesDetailLoading"
            class="ps-codon-select w-full md:w-20rem"
          />
        </div>
        <div class="ps-opt-actions">
          <Button
            label="Optimize DNA"
            icon="pi pi-bolt"
            severity="primary"
            :loading="seqPrep.optimizing"
            :disabled="seqPrep.preparedRows.length === 0"
            @click="seqPrep.runOptimization()"
          />
        </div>
      </div>
    </div>

    <Panel
      header="DNA Optimization Constraints"
      :toggleable="true"
      :collapsed="true"
      class="ps-optimization-panel card-like mb-4"
    >
      <div class="ps-opt-content">
        <Message v-if="seqPrep.optimizationGlobalError" severity="error" :closable="false" class="ps-opt-msg mb-4">{{ seqPrep.optimizationGlobalError }}</Message>
        <Message v-if="seqPrep.optimizationStale && seqPrep.optimizationEverSucceeded" severity="warn" :closable="false" class="ps-opt-msg mb-4">Inputs changed. Run optimization to update sequence DNA.</Message>

        <div class="ps-opt-panel-actions">
          <Button
            label="Defaults"
            icon="pi pi-refresh"
            severity="secondary"
            size="small"
            @click="seqPrep.resetConstraintsToDefaults()"
          />
          <Button
            label="Add Constraint"
            icon="pi pi-plus"
            severity="secondary"
            size="small"
            @click="seqPrep.addConstraint()"
          />
        </div>

        <DataTable :value="seqPrep.optimizationConstraints" class="p-datatable-sm" responsiveLayout="scroll">
          <Column field="enabled" header="Active" style="width: 5rem">
            <template #body="{ data }">
              <Checkbox v-model="data.enabled" :binary="true" />
            </template>
          </Column>
          <Column field="type" header="Constraint Type">
            <template #body="{ data }">
              <Select v-model="data.type" :options="['EnforceGCContent', 'AvoidHairpins', 'AvoidPattern', 'AvoidRareCodons', 'UniquifyAllKmers']" class="w-full" />
            </template>
          </Column>
          <Column field="params" header="Parameters (JSON)">
            <template #body="{ data }">
               <InputText :value="JSON.stringify(data.params)" @change="updateConstraintParams(data, $event.target.value)" class="w-full" placeholder='{"mini": 0.25}' />
            </template>
          </Column>
          <Column headerStyle="width: 4rem">
            <template #body="{ index }">
               <Button icon="pi pi-trash" severity="danger" text @click="seqPrep.removeConstraint(index)" />
            </template>
          </Column>
        </DataTable>
      </div>
    </Panel>

    <div class="ps-actions">
      <Button
        label="Extract missing sequences from structures"
        icon="pi pi-download"
        severity="help"
        :loading="seqPrep.extracting"
        :disabled="seqPrep.inputDesigns.length === 0"
        @click="onExtractMissing"
      />
      <span class="ps-hint">{{ inputSummary }}</span>
    </div>

    <div class="ps-view-bar">
      <div class="ps-view-toggle">
        <span :class="{ 'ps-toggle-active': !seqPrep.dnaMode }">Amino acid</span>
        <ToggleSwitch
          id="ps-view-mode"
          v-model="seqPrep.dnaMode"
          aria-label='Show as "Amino acid / Nucleotide"'
        />
        <span :class="{ 'ps-toggle-active': seqPrep.dnaMode }">Nucleotide</span>
      </div>
      <div class="ps-view-toggle">
        <span :class="{ 'ps-toggle-active': !seqPrep.goodOnly }">All</span>
        <ToggleSwitch
          id="ps-good-only"
          v-model="seqPrep.goodOnly"
          aria-label="Scope: all in scope or good designs only"
        />
        <span :class="{ 'ps-toggle-active': seqPrep.goodOnly }">Good only</span>
      </div>
    </div>

    <div class="ps-table-toolbar">
      <div class="ps-show-pad-toggle">
        <ToggleSwitch
          id="ps-show-post-pad"
          v-model="seqPrep.showPostStopPadding"
          :disabled="seqPrep.dnaMode"
          aria-label="Show post-stop padding (amino acid view)"
        />
        <label
          for="ps-show-post-pad"
          class="ps-show-pad-label"
          :class="{ 'ps-show-pad-label--disabled': seqPrep.dnaMode }"
        >
          Show post-stop padding
        </label>
      </div>
      <label for="ps-column-toggle" class="ps-column-toggle-label">Columns</label>
      <MultiSelect
        id="ps-column-toggle"
        v-model="selectedColumnKeys"
        :options="columnOptions"
        option-label="label"
        option-value="key"
        placeholder="Columns"
        class="ps-column-multiselect"
        display="chip"
        :max-selected-labels="3"
      />
    </div>

    <DataTable
      v-model:filters="tableFilters"
      :value="preparedRowsForTable"
      striped-rows
      paginator
      resizable-columns
      show-gridlines
      filter-display="row"
      :rows="5"
      :rowsPerPageOptions="[5, 10, 24, 48, 96]"
      data-key="row_key"
      class="ps-table"
    >
      <Column
        v-if="selectedColumnKeys.includes('design')"
        field="design_id"
        filter-field="design_filter_text"
        header="Design"
        sortable
        :show-filter-menu="false"
        style="min-width: 11rem"
      >
        <template #body="{ data }">
          <span class="ps-design-meta">
            <span class="ps-design-meta-label">Design ID:</span> {{ data.design_id }}<br />
            <span class="ps-design-meta-label">Project:</span> {{ data.project_id }}<br />
            <span class="ps-design-meta-label">Run:</span> {{ data.run_name }}
          </span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            type="text"
            placeholder="Filter"
            class="p-column-filter w-full"
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('sequence')"
        header="Sequence"
        bodyClass="ps-sequence-cell"
        style="width: 24rem"
      >
        <template #body="{ data }">
          <span class="seq-wrap">
            <template v-if="seqPrep.dnaMode && data.prepared_dna">
              <span
                v-for="(seg, i) in data.segments_dna || [{ text: data.prepared_dna, cssClass: 'seq-seg-dna-body' }]"
                :key="i"
                :class="seg.cssClass"
                :style="seg.style"
              >{{ seg.text }}</span>
            </template>
            <template v-else>
              <span
                v-for="(seg, i) in aaSegmentsForView(data)"
                :key="i"
                :class="seg.cssClass"
                :style="seg.style"
              >{{ seg.text }}</span>
            </template>
          </span>
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('tag')"
        field="tag"
        header="Tag End"
        sortable
        :show-filter-menu="false"
        style="width: 1%; white-space: nowrap"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            type="text"
            placeholder="N/C"
            class="p-column-filter ps-tag-filter-input"
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('length')"
        field="sort_tagged_length"
        :header="lengthColumnHeader"
        sortable
        style="width: 8rem"
      >
        <template #body="{ data }">
          {{ taggedLength(data) }}
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('warnings')"
        field="sort_warnings"
        header="Warnings"
        sortable
        style="width: 10rem"
      >
        <template #body="{ data }">
          <span v-if="data.warnings.length > 0" class="ps-warn-cell">
            <i class="pi pi-exclamation-triangle ps-warn-icon" aria-hidden="true" />
            <span class="ps-warn-text">{{ data.warnings.join(', ') }}</span>
          </span>
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('extinction')"
        field="sort_extinction_coeff_reduced"
        header="ε₂₈₀"
        sortable
        style="width: 7.5rem"
      >
        <template #body="{ data }">
          <span class="ps-ext-stack">
            <span class="ps-ext-main">{{ data.extinction_coeff_reduced }}</span>
            <span
              v-if="data.extinction_coeff_reduced !== data.extinction_coeff_oxidized"
              class="ps-ext-ox"
            >
              (ox: {{ data.extinction_coeff_oxidized }})
            </span>
          </span>
        </template>
      </Column>
      <Column
        v-if="selectedColumnKeys.includes('pi')"
        field="isoelectric_point"
        header="pI"
        sortable
        style="width: 5rem"
      >
        <template #body="{ data }">
          {{ formatPi(data.isoelectric_point) }}
        </template>
      </Column>
    </DataTable>

    <p v-if="preparedLengthStats.count > 0" class="ps-length-summary">
      Tagged lengths ({{ preparedLengthStats.unit }}):
      <strong>min</strong> {{ preparedLengthStats.min }},
      <strong>max</strong> {{ preparedLengthStats.max }}
      <span class="ps-length-n">({{ preparedLengthStats.count }} sequence(s))</span>
      <template
        v-if="
          seqPrep.dnaMode &&
          seqPrep.optimizationEverSucceeded &&
          !seqPrep.optimizationStale
        "
      >
        <span class="ps-length-codon-meta">
          Codon optimized for {{ seqPrep.activeCodonTable.label }}, with
          {{ enabledOptimizationConstraintCount }} additional DNA optimization constraints.
        </span>
      </template>
    </p>
    <p v-else class="ps-length-summary ps-length-summary--empty">No sequences in scope.</p>

    <Message
      v-if="seqPrep.validationErrors.length > 0"
      severity="error"
      class="ps-validation-msg"
      :closable="false"
    >
      <ul class="ps-validation-list">
        <li v-for="(err, i) in seqPrep.validationErrors" :key="i">{{ err }}</li>
      </ul>
    </Message>

    <Message
      v-if="rowsWithWarnings.length > 0"
      severity="warn"
      class="ps-warnings-banner"
      :closable="false"
    >
      <div class="ps-warnings-banner-inner">
        <i class="pi pi-exclamation-triangle ps-warn-banner-icon" aria-hidden="true" />
        <div class="ps-warnings-banner-body">
          <p class="ps-warnings-banner-lead">
            <strong>Warning:</strong> Some designs are less than ideal.
          </p>
          <ul class="ps-warnings-summary-list">
            <li v-for="(line, i) in warningsSummaryLines" :key="i">{{ line }}</li>
          </ul>
          <div class="ps-warnings-ack">
            <Checkbox v-model="warningsAcknowledged" input-id="ps-warn-ack" binary />
            <label for="ps-warn-ack">Acknowledged, continue anyway</label>
          </div>
        </div>
      </div>
    </Message>

    <Message
      v-if="dnaWarningActive"
      severity="warn"
      class="ps-warnings-banner"
      :closable="false"
    >
      <div class="ps-warnings-banner-inner">
        <i class="pi pi-exclamation-triangle ps-warn-banner-icon" aria-hidden="true" />
        <div class="ps-warnings-banner-body">
          <p class="ps-warnings-banner-lead">
            <strong>Warning:</strong> DNA has not been optimized with current settings.
          </p>
          <div class="ps-warnings-ack">
            <Checkbox v-model="dnaStalenessAcknowledged" input-id="ps-dna-stale-ack" binary />
            <label for="ps-dna-stale-ack">Acknowledged, continue anyway</label>
          </div>
        </div>
      </div>
    </Message>

    <div class="ps-download">
      <SplitButton
        label="Download FASTA"
        icon="pi pi-download"
        severity="secondary"
        :disabled="!downloadAllowed"
        @click="downloadFasta"
        :model="downloadMenuItems"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import SplitButton from 'primevue/splitbutton'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import Chip from 'primevue/chip'
import Message from 'primevue/message'
import Panel from 'primevue/panel'
import {
  preparedExportBasename,
  tagPresetChipCssVars,
  tagPresetChromeStyle,
  useSeqPrepStore,
  type PreparedRow
} from '../stores/seqPrep'

const seqPrep = useSeqPrepStore()
const toast = useToast()

const updateConstraintParams = (data: any, val: string) => {
  try {
    data.params = JSON.parse(val)
  } catch (e) {
    // Ignore invalid JSON format on change
  }
}

const chainOptions = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

const columnOptions: Array<{ key: string; label: string }> = [
  { key: 'design', label: 'Design' },
  { key: 'sequence', label: 'Sequence' },
  { key: 'tag', label: 'Tag End' },
  { key: 'length', label: 'Length' },
  { key: 'warnings', label: 'Warnings' },
  { key: 'extinction', label: 'ε₂₈₀' },
  { key: 'pi', label: 'pI' },
]

const selectedColumnKeys = ref<string[]>(
  columnOptions
    .map((o) => o.key)
    .filter((key) => key !== 'extinction' && key !== 'pi')
)

const lengthColumnHeader = computed(() =>
  seqPrep.dnaMode ? 'Length (nt)' : 'Length (aa)'
)

type PreparedRowWithSort = PreparedRow & {
  sort_tagged_length: number
  sort_warnings: string
  sort_extinction_coeff_reduced: number
}

const preparedRowsForTable = computed<PreparedRowWithSort[]>(() =>
  seqPrep.preparedRows.map((row) => ({
    ...row,
    sort_tagged_length: taggedLength(row),
    sort_warnings: row.warnings.join(', '),
    sort_extinction_coeff_reduced: row.extinction_coeff_reduced
  }))
)

const tableFilters = ref({
  design_filter_text: { value: null as string | null, matchMode: 'contains' as const },
  tag: { value: null as string | null, matchMode: 'contains' as const }
})

const warningsAcknowledged = ref(false)

const preparedRowsFingerprint = computed(() =>
  seqPrep.preparedRows.map((r) => `${r.row_key}:${r.prepared_aa}`).join('|')
)

watch(preparedRowsFingerprint, () => {
  warningsAcknowledged.value = false
})

const dnaStalenessAcknowledged = ref(false)

watch(
  () =>
    [seqPrep.dnaMode, seqPrep.optimizationStale, seqPrep.optimizationEverSucceeded] as const,
  () => {
    dnaStalenessAcknowledged.value = false
  }
)

const rowsWithWarnings = computed(() => seqPrep.preparedRows.filter((r) => r.warnings.length > 0))

const enabledOptimizationConstraintCount = computed(
  () => seqPrep.optimizationConstraints.filter((c) => c.enabled).length
)

/** Shown until a successful Optimize DNA run; also while results are stale (matches panel "Inputs changed"). */
const dnaWarningActive = computed(
  () => !seqPrep.optimizationEverSucceeded || seqPrep.optimizationStale
)

const warningsSummaryLines = computed(() => {
  const map = new Map<string, string[]>()
  for (const r of rowsWithWarnings.value) {
    for (const w of r.warnings) {
      if (!map.has(w)) map.set(w, [])
      map.get(w)!.push(r.design_id)
    }
  }
  const lines: string[] = []
  const maxShow = 5
  for (const [warn, ids] of map) {
    const uniq = [...new Set(ids)]
    const shown = uniq.slice(0, maxShow)
    const more = uniq.length > maxShow ? ' …' : ''
    lines.push(`Designs ${shown.join(', ')}${more}: ${warn}`)
  }
  return lines
})

const downloadAllowed = computed(() => {
  if (!seqPrep.canDownload) return false
  if (rowsWithWarnings.value.length > 0 && !warningsAcknowledged.value) return false
  if (dnaWarningActive.value && !dnaStalenessAcknowledged.value) return false
  return true
})

onMounted(() => {
  void seqPrep.ensureCodonTablesLoaded()
})

const inputSummary = computed(() => {
  const n = seqPrep.inputDesigns.length
  if (n === 0) return 'No designs in scope (select rows on Designs or use Good only).'
  return `${n} design(s)`
})

function aaSegmentsForView(data: PreparedRow): PreparedRow['segments_aa_display'] {
  return seqPrep.showPostStopPadding ? data.segments_aa : data.segments_aa_display
}

function aaSequenceForExport(r: PreparedRow): string {
  if (seqPrep.dnaMode && r.prepared_dna) return r.prepared_dna
  if (!seqPrep.dnaMode) return seqPrep.showPostStopPadding ? r.prepared_aa : r.prepared_aa_display
  return r.prepared_aa
}

function taggedLength(data: PreparedRow): number {
  if (seqPrep.dnaMode) return (data.prepared_dna ?? '').length
  return seqPrep.showPostStopPadding ? data.prepared_aa.length : data.prepared_aa_display.length
}

function formatPi(v: number): string {
  if (!Number.isFinite(v)) return '—'
  return v.toFixed(2)
}

function exportPiRaw(v: number): string {
  if (!Number.isFinite(v)) return ''
  return String(v)
}

const preparedLengthStats = computed(() => {
  const rows = seqPrep.preparedRows
  const dna = seqPrep.dnaMode
  const unit = dna ? 'nt' : 'aa'
  if (rows.length === 0) {
    return { count: 0, min: 0, max: 0, unit }
  }
  const lens = rows.map((r) =>
    dna ? (r.prepared_dna ?? '').length : (seqPrep.showPostStopPadding ? r.prepared_aa.length : r.prepared_aa_display.length)
  )
  return {
    count: rows.length,
    min: Math.min(...lens),
    max: Math.max(...lens),
    unit
  }
})

function addCustomBoth() {
  seqPrep.addCustomTag('n')
}

function onExtractMissing() {
  void (async () => {
    const { ok, errors } = await seqPrep.fetchMissingSequences()
    if (ok > 0) {
      toast.add({
        severity: 'success',
        summary: 'Sequences extracted',
        detail: `Updated ${ok} design(s).`,
        life: 4000
      })
    }
    if (errors.length > 0) {
      toast.add({
        severity: 'warn',
        summary: 'Some rows skipped',
        detail: errors.slice(0, 5).join('; ') + (errors.length > 5 ? '…' : ''),
        life: 6000
      })
    }
    if (ok === 0 && errors.length === 0) {
      toast.add({
        severity: 'info',
        summary: 'Nothing to extract',
        detail: 'All designs in scope already have a sequence.',
        life: 3000
      })
    }
  })()
}

function downloadBlob(blob: Blob, filename: string) {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function exportDownloadStem(): string {
  return preparedExportBasename(seqPrep.exportOrderName)
}

function guardDownload(): boolean {
  if (!seqPrep.canDownload) {
    toast.add({
      severity: 'error',
      summary: 'Invalid sequence input',
      detail: seqPrep.validationErrors[0] ?? 'Fix validation errors before downloading.',
      life: 5000
    })
    return false
  }
  if (rowsWithWarnings.value.length > 0 && !warningsAcknowledged.value) {
    toast.add({
      severity: 'warn',
      summary: 'Acknowledge warnings',
      detail: 'Check the warning box above or adjust sequences before downloading.',
      life: 5000
    })
    return false
  }
  if (dnaWarningActive.value && !dnaStalenessAcknowledged.value) {
    toast.add({
      severity: 'warn',
      summary: 'Acknowledge DNA not optimised',
      detail: 'Run Optimize DNA or tick the DNA acknowledgement before downloading.',
      life: 5000
    })
    return false
  }
  return true
}

function downloadFasta() {
  if (!guardDownload()) return
  const rows = seqPrep.preparedRows
  if (rows.length === 0) {
    toast.add({ severity: 'warn', summary: 'No data', detail: 'No sequences to export', life: 2500 })
    return
  }
  const lines: string[] = []
  for (const r of rows) {
    const body = aaSequenceForExport(r)
    lines.push(`>${r.design_id}`)
    lines.push(body)
  }
  downloadBlob(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }), `${exportDownloadStem()}.fasta`)
  toast.add({ severity: 'success', summary: 'FASTA', detail: `${rows.length} record(s)`, life: 2500 })
}

function toTsv(): void {
  if (!guardDownload()) return
  const rows = seqPrep.preparedRows
  if (rows.length === 0) return
  const dna = seqPrep.dnaMode
  const cols = dna
    ? [
        'design_id',
        'project_id',
        'run_name',
        'tag',
        'original_sequence',
        'prepared_aa',
        'prepared_dna',
        'dna_length',
        'extinction_coeff_reduced',
        'extinction_coeff_oxidized',
        'isoelectric_point',
        'warnings'
      ]
    : [
        'design_id',
        'project_id',
        'run_name',
        'tag',
        'original_sequence',
        'prepared_sequence',
        'length',
        'extinction_coeff_reduced',
        'extinction_coeff_oxidized',
        'isoelectric_point',
        'warnings'
      ]
  const esc = (v: string | number) => {
    const s = String(v ?? '')
    if (s.includes('\t') || s.includes('\n') || s.includes('"')) return `"${s.replace(/"/g, '""')}"`
    return s
  }
  const lines = [cols.join('\t')]
  for (const r of rows) {
    if (dna) {
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(r.prepared_aa),
          esc(r.prepared_dna || ''),
          esc((r.prepared_dna || '').length),
          esc(r.extinction_coeff_reduced),
          esc(r.extinction_coeff_oxidized),
          esc(exportPiRaw(r.isoelectric_point)),
          esc(r.warnings.join('; '))
        ].join('\t')
      )
    } else {
      const aa = aaSequenceForExport(r)
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(aa),
          esc(aa.length),
          esc(r.extinction_coeff_reduced),
          esc(r.extinction_coeff_oxidized),
          esc(exportPiRaw(r.isoelectric_point)),
          esc(r.warnings.join('; '))
        ].join('\t')
      )
    }
  }
  downloadBlob(
    new Blob([lines.join('\n')], { type: 'text/tab-separated-values;charset=utf-8' }),
    `${exportDownloadStem()}.tsv`
  )
  toast.add({ severity: 'success', summary: 'TSV', detail: `${rows.length} row(s)`, life: 2500 })
}

function toCsv(): void {
  if (!guardDownload()) return
  const rows = seqPrep.preparedRows
  if (rows.length === 0) return
  const dna = seqPrep.dnaMode
  const cols = dna
    ? [
        'design_id',
        'project_id',
        'run_name',
        'tag',
        'original_sequence',
        'prepared_aa',
        'prepared_dna',
        'dna_length',
        'extinction_coeff_reduced',
        'extinction_coeff_oxidized',
        'isoelectric_point',
        'warnings'
      ]
    : [
        'design_id',
        'project_id',
        'run_name',
        'tag',
        'original_sequence',
        'prepared_sequence',
        'length',
        'extinction_coeff_reduced',
        'extinction_coeff_oxidized',
        'isoelectric_point',
        'warnings'
      ]
  const esc = (v: string | number) => {
    const s = String(v ?? '')
    if (s.includes(',') || s.includes('\n') || s.includes('"')) return `"${s.replace(/"/g, '""')}"`
    return s
  }
  const lines = [cols.join(',')]
  for (const r of rows) {
    if (dna) {
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(r.prepared_aa),
          esc(r.prepared_dna || ''),
          esc((r.prepared_dna || '').length),
          esc(r.extinction_coeff_reduced),
          esc(r.extinction_coeff_oxidized),
          esc(exportPiRaw(r.isoelectric_point)),
          esc(r.warnings.join('; '))
        ].join(',')
      )
    } else {
      const aa = aaSequenceForExport(r)
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(aa),
          esc(aa.length),
          esc(r.extinction_coeff_reduced),
          esc(r.extinction_coeff_oxidized),
          esc(exportPiRaw(r.isoelectric_point)),
          esc(r.warnings.join('; '))
        ].join(',')
      )
    }
  }
  downloadBlob(new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' }), `${exportDownloadStem()}.csv`)
  toast.add({ severity: 'success', summary: 'CSV', detail: `${rows.length} row(s)`, life: 2500 })
}

function toCsvTwist(): void {
  if (!guardDownload()) return
  const rows = seqPrep.preparedRows
  if (rows.length === 0) {
    toast.add({ severity: 'warn', summary: 'No data', detail: 'No sequences to export', life: 2500 })
    return
  }
  const dna = seqPrep.dnaMode
  const cols = ['design_id', 'sequence'] as const
  const esc = (v: string | number) => {
    const s = String(v ?? '')
    if (s.includes(',') || s.includes('\n') || s.includes('"')) return `"${s.replace(/"/g, '""')}"`
    return s
  }
  const lines = [cols.join(',')]
  for (const r of rows) {
    const sequence = aaSequenceForExport(r)
    lines.push([esc(r.design_id), esc(sequence)].join(','))
  }
  downloadBlob(
    new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' }),
    `${exportDownloadStem()}_twist.csv`
  )
  toast.add({ severity: 'success', summary: 'CSV (Twist)', detail: `${rows.length} row(s)`, life: 2500 })
}

const downloadMenuItems = [
  { label: 'Download TSV', icon: 'pi pi-download', command: () => toTsv() },
  { label: 'Download CSV', icon: 'pi pi-download', command: () => toCsv() },
  { label: 'CSV (Twist)', icon: 'pi pi-download', command: () => toCsvTwist() }
]
</script>

<style scoped>
.prepare-sequences-view {
  max-width: 100%;
}

.ps-header h2 {
  margin-top: 0;
}

.ps-intro-box {
  max-width: 52rem;
  margin-bottom: 1.25rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--p-content-border-color, #d7dde3);
  border-radius: 6px;
  background: var(--p-content-background, #fff);
}

.ps-intro {
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0 0 0.5rem 0;
}

.ps-case-help {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.45;
}

.ps-intro-box strong {
  font-weight: 700;
}

.ps-order-name {
  max-width: 32rem;
  margin-bottom: 1rem;
}

.ps-order-name label {
  display: block;
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.card-like {
  border: 1px solid var(--p-content-border-color, #dee2e6);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  background: var(--p-content-background, #fff);
}

.ps-optimization-toolbar.card-like {
  margin-bottom: 0.75rem;
}

.ps-opt-header {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-end;
}

.ps-codon-label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.ps-opt-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ps-opt-panel-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.ps-builder-row {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.ps-zone {
  flex: 1;
  min-width: 12rem;
  border: 1px dashed var(--p-content-border-color, #ced4da);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.ps-zone-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.35rem;
  color: var(--p-text-muted-color, #6c757d);
}

.ps-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
  min-height: 2rem;
}

.ps-placeholder {
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #adb5bd);
}

.ps-binder-label {
  align-self: center;
  font-weight: 600;
  color: var(--p-primary-color, #667eea);
  padding: 0 0.25rem;
}

.ps-palette {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.ps-palette-label {
  font-size: 0.85rem;
  font-weight: 500;
}

.ps-ml {
  margin-left: 0.75rem;
}

.ps-preset-btn {
  margin-right: 0.15rem;
}

/* Palette buttons + chips: colours from `TAG_PRESET_DEFS` in seqPrep store.
   Chips need !important + CSS vars so they beat global App.vue `.p-chip` / `.p-component *` rules. */

.prepare-sequences-view :deep(.ps-tag-chip.p-chip) {
  font-size: var(--p-button-sm-font-size, 0.875rem);
  border-color: var(--ps-chip-border) !important;
  border-width: 1px !important;
  border-style: solid !important;
  background-color: var(--ps-chip-bg) !important;
  color: var(--ps-chip-fg) !important;
}

.prepare-sequences-view :deep(.ps-tag-chip.p-chip .p-chip-label) {
  color: var(--ps-chip-fg) !important;
}

.ps-tag-chip-body {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15em;
  line-height: 1.25;
  text-align: left;
  min-width: 0;
}

.ps-tag-chip-name {
  font-weight: 600;
}

.ps-tag-chip-seq {
  font-size: 0.72em;
  font-weight: 500;
  letter-spacing: 0.02em;
  word-break: break-all;
}

.prepare-sequences-view :deep(.ps-tag-chip .p-chip-remove-icon) {
  color: var(--ps-chip-fg) !important;
  opacity: 0.75;
}

.prepare-sequences-view :deep(.ps-tag-chip .p-chip-remove-icon:hover) {
  opacity: 1;
}

.ps-custom-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.ps-custom-input {
  flex: 1;
  min-width: 12rem;
}

.ps-form {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1rem;
}

.ps-form.card-like {
  margin-top: 0.75rem;
  margin-bottom: 1rem;
}

.ps-field-row {
  display: grid;
  gap: 1rem;
}

.ps-field-row--padding {
  grid-column: 1 / -1;
  grid-template-columns: repeat(2, minmax(14rem, 1fr));
  gap: 0.5rem;
  width: fit-content;
  max-width: 100%;
  justify-self: start;
  padding: 0.75rem 0.75rem 0.75rem 0;
  border: 1px solid var(--p-content-border-color, #dee2e6);
  border-radius: 6px;
  background: color-mix(in srgb, var(--p-content-background, #fff) 88%, #eef3ff 12%);
}

.ps-field-row--padding > .ps-field {
  margin: 0;
}

.ps-field-row--padding > .ps-field:first-child {
  margin-left: 0;
  padding-left: 0;
}

.ps-length-summary {
  margin: 0.75rem 0 0;
  font-size: 0.9rem;
  color: var(--p-text-color);
}

.ps-length-summary--empty {
  color: var(--p-text-muted-color, #6c757d);
}

.ps-length-summary .ps-length-n {
  color: var(--p-text-muted-color, #6c757d);
  font-size: 0.85rem;
}

.ps-length-summary .ps-length-codon-meta {
  display: block;
  margin-top: 0.35rem;
  color: var(--p-text-muted-color, #6c757d);
  font-size: 0.85rem;
}

.ps-field label {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}

.ps-checks {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-top: 1.4rem;
}

.ps-checks label {
  margin-bottom: 0;
}

.ps-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.ps-hint {
  font-size: 0.9rem;
  color: var(--p-text-muted-color, #6c757d);
}

.ps-download {
  margin-top: 1rem;
}

.ps-design-meta {
  display: block;
  font-size: 0.85rem;
  line-height: 1.45;
  word-break: break-word;
}

.prepare-sequences-view :deep(.p-datatable-tbody > tr > td .ps-design-meta-label) {
  font-weight: 600;
  color: var(--p-text-color);
  margin-right: 0.2em;
}

.seq-wrap {
  display: block;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.4;
}

.prepare-sequences-view :deep(.ps-sequence-cell) {
  white-space: normal;
  vertical-align: top;
}

:deep(.seq-seg-core) {
  color: #212529;
}

/* Preset tag segments: inline :style from store (same JSON as chips). */

.prepare-sequences-view :deep(.ps-terminal-input--n.p-inputtext) {
  border-left: 3px solid #00897b;
  background: rgba(0, 137, 123, 0.06);
}

.prepare-sequences-view :deep(.ps-terminal-input--c.p-inputtext) {
  border-left: 3px solid #c2185b;
  background: rgba(194, 24, 91, 0.06);
}

:deep(.seq-seg-stop) {
  display: inline-block;
  padding: 0.04em 0.2em;
  border-radius: 3px;
  border: 1px solid #b23a3a;
  background: #d66868;
  color: #ffffff !important;
  font-weight: 700;
}

:deep(.seq-seg-nuc-remainder) {
  color: #6a1b9a;
  font-style: italic;
  text-decoration: underline;
  text-decoration-color: #ce93d8;
  font-size: 0.75em;
}

.ps-view-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1.25rem;
  margin-bottom: 0.75rem;
}

.ps-view-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}

.ps-toggle-active {
  font-weight: 700;
  color: var(--p-primary-color);
}

.ps-codon-field {
  min-width: 12rem;
}

.ps-codon-field label {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 0.25rem;
}

.ps-table-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
  margin-bottom: 0.5rem;
}

.ps-column-toggle-label {
  font-size: 0.85rem;
  font-weight: 500;
}

.ps-column-multiselect {
  min-width: 14rem;
  max-width: min(100%, 36rem);
}

.prepare-sequences-view :deep(.ps-tag-filter-input.p-inputtext) {
  width: 7ch;
  min-width: 7ch;
}

.ps-warn-icon {
  color: #f59e0b;
  font-size: 2rem;
  margin-right: 0.35rem;
  flex-shrink: 0;
}

.ps-warn-cell {
  display: inline-flex;
  align-items: flex-start;
  gap: 0;
  padding: 0.25rem 0.4rem;
  border-radius: 4px;
  background: var(--p-message-warn-background, #fff3cd);
  border: 1px solid var(--p-message-warn-border-color, #ffeaa7);
  font-size: 0.8rem;
  line-height: 1.35;
}

.ps-warn-text {
  color: var(--p-text-color);
}

.ps-ext-stack {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.85rem;
  line-height: 1.25;
}

.ps-ext-main {
  font-variant-numeric: tabular-nums;
}

.ps-ext-ox {
  font-size: 0.72rem;
  color: var(--p-text-muted-color, #6c757d);
}

.ps-warnings-banner {
  margin: 0.75rem 0;
  font-size: 0.9rem;
}

.ps-warnings-banner-inner {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
}

.ps-warn-banner-icon {
  color: #f59e0b;
  font-size: 1.15rem;
  margin-top: 0.1rem;
  flex-shrink: 0;
  font-size: 2rem;
}

.ps-warnings-banner-body {
  flex: 1;
  min-width: 0;
}

.ps-warnings-banner-lead {
  margin: 0 0 0.35rem 0;
}

.ps-warnings-summary-list {
  margin: 0 0 0.6rem 0;
  padding-left: 1.25rem;
}

.ps-warnings-ack {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.ps-warnings-ack label {
  margin: 0;
  font-size: 0.88rem;
  cursor: pointer;
}

.ps-validation-msg {
  margin: 0.75rem 0;
}

.ps-validation-list {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
}

:deep(.seq-seg-padding) {
  color: #78909c;
  background: rgba(120, 144, 156, 0.12);
  border-radius: 2px;
  font-style: italic;
}

:deep(.seq-seg-dna-body) {
  color: #1565c0;
}
</style>
