<template>
  <div class="prepare-sequences-view">
    <div class="ps-header">
      <h2>Prepare sequences</h2>
    </div>

    <p class="ps-intro">
      Tags you place in the <strong>N-tagged</strong> and <strong>C-tagged</strong> areas are only added to designs whose
      <strong>tag</strong> column is <code>N</code> or <code>C</code> respectively. Designs with another tag value get
      only the core sequence plus the global N/C terminal additions and optional stop.
    </p>

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
              :label="`${t.label}: ${t.sequence}`"
              removable
              class="ps-tag-chip"
              :pt="tagPresetChipPt(t.kind)"
              @remove="seqPrep.removeTag('n', i)"
            />
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
              :label="`${t.label}: ${t.sequence}`"
              removable
              class="ps-tag-chip"
              :pt="tagPresetChipPt(t.kind)"
              @remove="seqPrep.removeTag('c', i)"
            />
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
          placeholder="Custom AA sequence"
          class="ps-custom-input"
          @keyup.enter="addCustomBoth"
        />
        <Button size="small" label="Add custom → N" @click="seqPrep.addCustomTag('n')" />
        <Button size="small" label="Add custom → C" @click="seqPrep.addCustomTag('c')" />
      </div>
    </div>

    <div class="ps-form grid">
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
      <div class="ps-field ps-checks">
        <Checkbox v-model="seqPrep.goodOnly" input-id="ps-good" binary />
        <label for="ps-good">Good only</label>
      </div>
      <div class="ps-field ps-checks">
        <Checkbox v-model="seqPrep.dnaMode" input-id="ps-dna" binary />
        <label for="ps-dna">Reverse translate (E. coli codons)</label>
      </div>
      <div class="ps-field">
        <label for="ps-pad">Post-stop padding</label>
        <InputText
          id="ps-pad"
          v-model="seqPrep.postStopPadding"
          class="w-full"
          :placeholder="seqPrep.dnaMode ? 'DNA (ACGT…)' : 'Amino acids'"
        />
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

    <DataTable
      :value="seqPrep.preparedRows"
      striped-rows
      paginator
      :rows="10"
      data-key="row_key"
      class="ps-table"
    >
      <Column field="design_id" header="Design ID" sortable style="min-width: 8rem" />
      <Column field="project_id" header="Project" sortable style="min-width: 6rem" />
      <Column field="run_name" header="Run" sortable style="min-width: 8rem" />
      <Column field="tag" header="Tag" sortable style="width: 5rem" />
      <Column header="Prepared sequence" style="min-width: 20rem">
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
                v-for="(seg, i) in data.segments_aa"
                :key="i"
                :class="seg.cssClass"
                :style="seg.style"
              >{{ seg.text }}</span>
            </template>
          </span>
        </template>
      </Column>
    </DataTable>

    <div class="ps-download">
      <SplitButton
        label="Download FASTA"
        icon="pi pi-download"
        severity="secondary"
        @click="downloadFasta"
        :model="downloadMenuItems"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import SplitButton from 'primevue/splitbutton'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Chip from 'primevue/chip'
import {
  preparedExportBasename,
  tagPresetChipPt,
  tagPresetChromeStyle,
  useSeqPrepStore
} from '../stores/seqPrep'

const seqPrep = useSeqPrepStore()
const toast = useToast()

const chainOptions = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

const inputSummary = computed(() => {
  const n = seqPrep.inputDesigns.length
  if (n === 0) return 'No designs in scope (select rows on Designs or use Good only).'
  return `${n} design(s)`
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

function downloadFasta() {
  const rows = seqPrep.preparedRows
  if (rows.length === 0) {
    toast.add({ severity: 'warn', summary: 'No data', detail: 'No sequences to export', life: 2500 })
    return
  }
  const lines: string[] = []
  for (const r of rows) {
    const body = seqPrep.dnaMode && r.prepared_dna ? r.prepared_dna : r.prepared_aa.replace(/\*/g, '')
    lines.push(`>${r.design_id}`)
    lines.push(body)
  }
  downloadBlob(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }), `${exportDownloadStem()}.fasta`)
  toast.add({ severity: 'success', summary: 'FASTA', detail: `${rows.length} record(s)`, life: 2500 })
}

function toTsv(): void {
  const rows = seqPrep.preparedRows
  if (rows.length === 0) return
  const dna = seqPrep.dnaMode
  const cols = dna
    ? ['design_id', 'project_id', 'run_name', 'tag', 'original_sequence', 'prepared_aa', 'prepared_dna', 'dna_length']
    : ['design_id', 'project_id', 'run_name', 'tag', 'original_sequence', 'prepared_sequence', 'length']
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
          esc((r.prepared_dna || '').length)
        ].join('\t')
      )
    } else {
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(r.prepared_aa),
          esc(r.prepared_aa.length)
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
  const rows = seqPrep.preparedRows
  if (rows.length === 0) return
  const dna = seqPrep.dnaMode
  const cols = dna
    ? ['design_id', 'project_id', 'run_name', 'tag', 'original_sequence', 'prepared_aa', 'prepared_dna', 'dna_length']
    : ['design_id', 'project_id', 'run_name', 'tag', 'original_sequence', 'prepared_sequence', 'length']
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
          esc((r.prepared_dna || '').length)
        ].join(',')
      )
    } else {
      lines.push(
        [
          esc(r.design_id),
          esc(r.project_id),
          esc(r.run_name),
          esc(r.tag),
          esc(r.original_sequence),
          esc(r.prepared_aa),
          esc(r.prepared_aa.length)
        ].join(',')
      )
    }
  }
  downloadBlob(new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' }), `${exportDownloadStem()}.csv`)
  toast.add({ severity: 'success', summary: 'CSV', detail: `${rows.length} row(s)`, life: 2500 })
}

function toCsvTwist(): void {
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
    const sequence = dna && r.prepared_dna ? r.prepared_dna : r.prepared_aa
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

.ps-intro {
  max-width: 52rem;
  line-height: 1.5;
  margin-bottom: 1.25rem;
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

/* Palette buttons + chips: colours from `TAG_PRESET_DEFS` in seqPrep store */

.prepare-sequences-view :deep(.ps-tag-chip) {
  font-size: var(--p-button-sm-font-size, 0.875rem);
}

.prepare-sequences-view :deep(.ps-tag-chip .p-chip-remove-icon) {
  color: inherit;
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
  margin-bottom: 1rem;
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

.seq-wrap {
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  word-break: break-all;
  line-height: 1.4;
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
  color: #c62828;
  font-weight: 700;
}

:deep(.seq-seg-padding) {
  color: #78909c;
  background: rgba(120, 144, 156, 0.12);
  border-radius: 2px;
}

:deep(.seq-seg-dna-body) {
  color: #1565c0;
}
</style>
