<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import Slider from 'primevue/slider'
import { filteringApi } from '../webapi'
import type {
  DesignKeyDto,
  TargetContactCoverageDto,
  TargetContactProfileRequestDto,
  TargetContactProfileRowDto,
  TargetInfoDto
} from '../webapi'
import { PALETTE_OPTIONS, buildColorMap, gradientCss } from '../utils/residueColorMap'
import { targetContactMapKey } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'
import type { PaletteName, ResidueColor, ResidueValue } from '../utils/residueColorMap'

const props = defineProps<{
  /** The run whose target is coloured; the viewer shows one design from it. */
  runId: string | null
  /** Designs currently selected in the table, for the "selected designs" scope. */
  selectedDesignKeys: DesignKeyDto[]
}>()

const emit = defineEmits<{
  (e: 'apply', colors: ResidueColor[]): void
  (e: 'clear'): void
}>()

const METRICS = [
  { label: 'ΔSASA on binding', value: 'delta_sasa' as const },
  { label: 'Contact frequency', value: 'contact_frequency' as const },
  { label: 'Closest approach', value: 'distance' as const }
]

const DISTANCE_TYPES = [
  { label: 'Heavy atoms', value: 'heavy' as const },
  { label: 'CA distance', value: 'ca' as const },
  { label: 'CB distance', value: 'cb' as const }
]

const UNITS = [
  { label: 'Å²', value: 'angstrom' as const },
  { label: '% of max', value: 'percent' as const }
]

const SCOPES = [
  { label: 'All designs in this run', value: 'run' },
  { label: 'Selected designs', value: 'selected' }
]

const enabled = ref(false)
const scope = ref<'run' | 'selected'>('run')
const metric = ref<TargetContactProfileRequestDto['metric']>('delta_sasa')
const unit = ref<'angstrom' | 'percent'>('angstrom')
const distanceType = ref<'ca' | 'cb' | 'heavy'>('heavy')
const contactThreshold = ref(5)
const targetKey = ref<string>('')

const palette = ref<PaletteName>('heat')
const gradientMin = ref<number | null>(null)
const gradientMax = ref<number | null>(null)
const booleanMode = ref(false)
const booleanThreshold = ref(10)

/** Teleport only once the slot exists in the DOM, else Vue warns and drops the node. */
const legendSlotReady = ref(false)
onMounted(() => {
  legendSlotReady.value = !!document.getElementById('contact-map-legend-slot')
})

const targets = ref<TargetInfoDto[]>([])
const coverage = ref<TargetContactCoverageDto[]>([])
const rows = ref<TargetContactProfileRowDto[]>([])
const nDesigns = ref(0)
const loading = ref(false)
const computing = ref(false)
const errorMessage = ref<string | null>(null)
const warning = ref<string | null>(null)

const targetOptions = computed(() =>
  targets.value.map((t) => ({ label: t.label, value: t.target_key }))
)

/** Low values are the interesting end for a distance, so the ramp runs the other way. */
const invert = computed(() => metric.value === 'distance')

const missingDesigns = computed(() =>
  coverage.value.reduce((sum, c) => sum + Math.max(0, c.total_designs - c.computed_designs), 0)
)

const valueUnitLabel = computed(() => {
  if (metric.value === 'contact_frequency') return 'fraction of designs'
  if (metric.value === 'distance') return 'Å'
  return unit.value === 'percent' ? '% of max' : 'Å²'
})

const residueValues = computed<ResidueValue[]>(() =>
  rows.value.map((row) => ({
    chain: row.chain,
    resseq: row.resseq,
    // Contact frequency is a mean over 1/0 per design, so `mean` is the fraction.
    value: row.n ? row.mean ?? null : null
  }))
)

const colorMap = computed(() =>
  buildColorMap(residueValues.value, {
    palette: palette.value,
    min: gradientMin.value,
    max: gradientMax.value,
    invert: invert.value,
    boolean: booleanMode.value,
    threshold: booleanThreshold.value
  })
)

const legendGradient = computed(() =>
  booleanMode.value ? '' : gradientCss(palette.value)
)

/** What the data actually spans, which is what the slider runs between. */
const observedRange = computed<[number, number]>(() => {
  const present = residueValues.value
    .map((r) => r.value)
    .filter((v): v is number => v != null && Number.isFinite(v))
  if (!present.length) return [0, 1]
  const low = Math.min(...present)
  const high = Math.max(...present)
  return high > low ? [low, high] : [low, low + 1]
})

/** ~100 steps across the observed range, snapped to a 1/2/5 ladder so the handles
 * land on round numbers whatever the metric's scale. */
const sliderStep = computed(() => {
  const [low, high] = observedRange.value
  const raw = (high - low) / 100
  if (!(raw > 0)) return 0.01
  const magnitude = Math.pow(10, Math.floor(Math.log10(raw)))
  const normalised = raw / magnitude
  const rounded = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10
  return Math.max(rounded * magnitude, 0.01)
})

/**
 * Handles at the ends mean "follow the data": the bound is stored as null so the
 * gradient keeps rescaling as the design set or metric changes, rather than freezing
 * at whatever the range happened to be when the slider was last touched.
 */
const sliderRange = computed<number[]>({
  get() {
    const [low, high] = observedRange.value
    return [gradientMin.value ?? low, gradientMax.value ?? high]
  },
  set([low, high]) {
    const [observedLow, observedHigh] = observedRange.value
    gradientMin.value = low <= observedLow ? null : low
    gradientMax.value = high >= observedHigh ? null : high
  }
})

const clampedBelow = computed(() => gradientMin.value != null)
const clampedAbove = computed(() => gradientMax.value != null)

// The legend's ends are the domain's ends; which one is drawn on the left depends on
// whether the ramp is inverted. Values outside the domain are painted the end colour,
// so a pulled-in bound reads as "≤ x" / "≥ x" rather than an exact value.
const domainLowLabel = computed(() =>
  `${clampedBelow.value ? '≤ ' : ''}${formatValue(colorMap.value.domain[0])}`
)
const domainHighLabel = computed(() =>
  `${clampedAbove.value ? '≥ ' : ''}${formatValue(colorMap.value.domain[1])}`
)
const legendLow = computed(() =>
  invert.value ? domainHighLabel.value : domainLowLabel.value
)
const legendHigh = computed(() =>
  invert.value ? domainLowLabel.value : domainHighLabel.value
)

function formatValue(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(2)
}

const TOP_RESIDUE_COUNT = 6

/**
 * The residues worth naming in the summary: the strongest few by the metric on show,
 * out of those the binders actually reach. Contacts are only recorded within 12 A of
 * the binder, so a residue with contact_fraction 0 was never near one; for ΔSASA and
 * contact frequency a mean of 0 means it was near but never buried, which is not worth
 * naming either.
 */
const topResidues = computed(() => {
  const candidates = rows.value.filter(
    (r) =>
      r.n &&
      r.mean != null &&
      r.contact_fraction > 0 &&
      (invert.value || r.mean > 0)
  )
  return [...candidates]
    .sort((a, b) => (invert.value ? (a.mean ?? 0) - (b.mean ?? 0) : (b.mean ?? 0) - (a.mean ?? 0)))
    .slice(0, TOP_RESIDUE_COUNT)
})

/**
 * "R12, E15, Y20 (chain A); I200 (chain B)" - residue type and number, grouped by
 * chain. Chains are ordered by their strongest residue and read in sequence order
 * within a chain, which is how an epitope is usually described.
 */
const topResiduesSummary = computed(() => {
  const byChain = new Map<string, typeof topResidues.value>()
  for (const residue of topResidues.value) {
    const group = byChain.get(residue.chain)
    if (group) group.push(residue)
    else byChain.set(residue.chain, [residue])
  }
  const parts = [...byChain.entries()].map(([chain, residues]) => {
    const names = [...residues]
      .sort((a, b) => a.resseq - b.resseq)
      .map((r) => `${r.aa1 || r.resname}${r.resseq}`)
      .join(', ')
    return `${names} (chain ${chain})`
  })
  return parts.join('; ')
})

interface PersistedSettings {
  enabled: boolean
  scope: 'run' | 'selected'
  metric: TargetContactProfileRequestDto['metric']
  unit: 'angstrom' | 'percent'
  distanceType: 'ca' | 'cb' | 'heavy'
  contactThreshold: number
  palette: PaletteName
  gradientMin: number | null
  gradientMax: number | null
  booleanMode: boolean
  booleanThreshold: number
}

/** Per run: the gradient range that makes one target legible is wrong for another. */
let restoring = false

async function restoreSettings(runId: string) {
  restoring = true
  try {
    const saved = await kvGet<PersistedSettings>(targetContactMapKey(runId))
    if (!saved) return
    enabled.value = !!saved.enabled
    scope.value = saved.scope ?? 'run'
    metric.value = saved.metric ?? 'delta_sasa'
    unit.value = saved.unit ?? 'angstrom'
    distanceType.value = saved.distanceType ?? 'heavy'
    contactThreshold.value = saved.contactThreshold ?? 5
    palette.value = saved.palette ?? 'heat'
    gradientMin.value = saved.gradientMin ?? null
    gradientMax.value = saved.gradientMax ?? null
    booleanMode.value = !!saved.booleanMode
    booleanThreshold.value = saved.booleanThreshold ?? 10
  } catch (err) {
    console.warn('Contact map settings restore failed', err)
  } finally {
    restoring = false
  }
}

async function persistSettings() {
  if (restoring || !props.runId) return
  try {
    await kvSet(targetContactMapKey(props.runId), {
      enabled: enabled.value,
      scope: scope.value,
      metric: metric.value,
      unit: unit.value,
      distanceType: distanceType.value,
      contactThreshold: contactThreshold.value,
      palette: palette.value,
      gradientMin: gradientMin.value,
      gradientMax: gradientMax.value,
      booleanMode: booleanMode.value,
      booleanThreshold: booleanThreshold.value
    })
  } catch (err) {
    console.warn('Contact map settings persist failed', err)
  }
}

async function loadTargets() {
  if (!props.runId) return
  errorMessage.value = null
  try {
    const res = await filteringApi.targetResidues([props.runId])
    targets.value = res.targets
    coverage.value = res.coverage
    warning.value = res.warnings.length ? res.warnings.join('; ') : null
    if (!targets.value.some((t) => t.target_key === targetKey.value)) {
      targetKey.value = targets.value[0]?.target_key ?? ''
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to resolve the target'
  }
}

async function loadProfile() {
  if (!props.runId || !targetKey.value) return
  loading.value = true
  errorMessage.value = null
  try {
    const res = await filteringApi.targetContactProfile({
      run_ids: [props.runId],
      design_keys: scope.value === 'selected' ? props.selectedDesignKeys : [],
      target_key: targetKey.value,
      metric: metric.value,
      unit: unit.value,
      distance_type: distanceType.value,
      contact_metric: 'distance',
      contact_threshold: contactThreshold.value
    })
    rows.value = res.residues
    nDesigns.value = res.n_designs
    warning.value = res.warnings.length ? res.warnings.join('; ') : null
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load the contact profile'
    rows.value = []
    nDesigns.value = 0
  } finally {
    loading.value = false
  }
}

async function computeContacts() {
  if (!props.runId) return
  computing.value = true
  errorMessage.value = null
  try {
    const res = await filteringApi.computeTargetContacts({ run_ids: [props.runId] })
    coverage.value = res.coverage
    if (res.errors.length) errorMessage.value = res.errors.slice(0, 3).join('; ')
    await loadProfile()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to compute target contacts'
  } finally {
    computing.value = false
  }
}

function resetGradientRange() {
  gradientMin.value = null
  gradientMax.value = null
}

function paint() {
  if (!enabled.value) return
  if (!colorMap.value.colors.length) {
    emit('clear')
    return
  }
  // Every target residue is in the map (residues with no data get the no-data colour),
  // so the rest of the structure - the binder - keeps its own colouring.
  emit('apply', colorMap.value.colors)
}

/** Reapply after the viewer reloads a structure, which discards any painted colours. */
defineExpose({ repaint: paint, enabled })

watch(
  () => props.runId,
  async (runId) => {
    rows.value = []
    targets.value = []
    if (!runId) return
    await restoreSettings(runId)
    if (enabled.value) {
      await loadTargets()
      await loadProfile()
      paint()
    } else {
      emit('clear')
    }
  },
  { immediate: true }
)

watch(enabled, async (on) => {
  void persistSettings()
  if (!on) {
    emit('clear')
    return
  }
  if (!targets.value.length) await loadTargets()
  if (!rows.value.length) await loadProfile()
  paint()
})

// Refetch when the question changes; repaint when only the presentation changes.
watch([metric, unit], () => {
  // A range in A^2 means nothing for a 0-1 contact frequency, so start from the data.
  resetGradientRange()
})

watch([metric, unit, distanceType, contactThreshold, scope, targetKey], async () => {
  void persistSettings()
  if (!enabled.value) return
  await loadProfile()
  paint()
})
watch(
  [palette, gradientMin, gradientMax, booleanMode, booleanThreshold],
  () => {
    void persistSettings()
    paint()
  }
)
watch(
  () => props.selectedDesignKeys,
  async () => {
    if (!enabled.value || scope.value !== 'selected') return
    await loadProfile()
    paint()
  }
)
</script>

<template>
  <div class="contact-map-body">
    <div class="advanced-row">
      <Checkbox v-model="enabled" :binary="true" input-id="contact-map-enabled" />
      <label for="contact-map-enabled" class="advanced-checkbox-label">
        Colour the target by contact map
      </label>
    </div>

    <template v-if="enabled">
      <Message v-if="errorMessage" severity="error" :closable="false" class="contact-map-message">
        {{ errorMessage }}
      </Message>
      <Message v-else-if="warning" severity="warn" :closable="false" class="contact-map-message">
        {{ warning }}
      </Message>

      <div v-if="missingDesigns > 0" class="contact-map-compute">
        <span class="contact-map-compute-text">
          {{ missingDesigns }} design{{ missingDesigns === 1 ? '' : 's' }} in this run
          {{ missingDesigns === 1 ? 'has' : 'have' }} no computed contacts.
        </span>
        <Button
          label="Compute"
          size="small"
          :loading="computing"
          @click="computeContacts"
        />
      </div>
      <ProgressBar v-if="computing" mode="indeterminate" class="contact-map-progress" />

      <div v-if="targetOptions.length > 1" class="advanced-row advanced-row--full">
        <label class="advanced-label">Target</label>
        <Select
          v-model="targetKey"
          :options="targetOptions"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <div class="advanced-row advanced-row--full">
        <label class="advanced-label">Colour by</label>
        <Select
          v-model="metric"
          :options="METRICS"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <div class="advanced-row advanced-row--full">
        <label class="advanced-label">Over</label>
        <Select
          v-model="scope"
          :options="SCOPES"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <div v-if="metric === 'delta_sasa'" class="advanced-row advanced-row--full">
        <label class="advanced-label">Units</label>
        <Select
          v-model="unit"
          :options="UNITS"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <div v-if="metric !== 'delta_sasa'" class="advanced-row advanced-row--full">
        <label class="advanced-label">Contact type</label>
        <Select
          v-model="distanceType"
          :options="DISTANCE_TYPES"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <div v-if="metric === 'contact_frequency'" class="advanced-row advanced-row--full">
        <label class="advanced-label">Contact within (Å)</label>
        <InputNumber
          v-model="contactThreshold"
          :min="1"
          :max="12"
          :step="0.5"
          :max-fraction-digits="1"
          show-buttons
          class="contact-map-number"
        />
      </div>

      <div class="advanced-row">
        <Checkbox v-model="booleanMode" :binary="true" input-id="contact-map-boolean" />
        <label for="contact-map-boolean" class="advanced-checkbox-label">
          Contact / no contact only
        </label>
      </div>

      <div v-if="booleanMode" class="advanced-row advanced-row--full">
        <label class="advanced-label">
          Contact when {{ invert ? '≤' : '≥' }} ({{ valueUnitLabel }})
        </label>
        <InputNumber
          v-model="booleanThreshold"
          :min="0"
          :step="1"
          :max-fraction-digits="2"
          class="contact-map-number"
        />
      </div>

      <div v-else class="advanced-row advanced-row--full">
        <label class="advanced-label">Palette</label>
        <Select
          v-model="palette"
          :options="PALETTE_OPTIONS"
          option-label="label"
          option-value="value"
          class="advanced-dropdown"
        />
      </div>

      <!-- The key and its range slider belong against the structure, not several
           sections below it, so they are teleported to a slot under the viewer. The
           fallback keeps them in place if that slot is ever absent. -->
      <Teleport to="#contact-map-legend-slot" :disabled="!legendSlotReady">
        <div class="contact-map-key">
          <div class="contact-map-legend">
            <template v-if="booleanMode">
              <span class="contact-map-swatch contact-map-swatch--contact" />
              <span class="contact-map-legend-label">contact</span>
              <span class="contact-map-swatch contact-map-swatch--none" />
              <span class="contact-map-legend-label">no contact</span>
            </template>
            <template v-else>
              <span class="contact-map-legend-label">{{ legendLow }}</span>
              <span class="contact-map-legend-bar" :style="{ background: legendGradient }" />
              <span class="contact-map-legend-label">{{ legendHigh }}</span>
              <span class="contact-map-legend-unit">{{ valueUnitLabel }}</span>
            </template>
          </div>

          <div v-if="!booleanMode" class="contact-map-slider">
            <Slider
              v-model="sliderRange"
              range
              :min="observedRange[0]"
              :max="observedRange[1]"
              :step="sliderStep"
              :disabled="!rows.length"
              aria-label="Gradient range"
            />
            <div class="contact-map-slider-ends">
              <span>{{ formatValue(observedRange[0]) }}</span>
              <button
                v-if="gradientMin !== null || gradientMax !== null"
                type="button"
                class="contact-map-slider-reset"
                @click="resetGradientRange"
              >
                Reset range
              </button>
              <span>{{ formatValue(observedRange[1]) }}</span>
            </div>
          </div>
        </div>
      </Teleport>

      <p class="advanced-hint">
        <span v-if="loading">Loading profile…</span>
        <span v-else-if="!nDesigns">No design in scope has computed contacts yet.</span>
        <span v-else>
          {{ nDesigns }} design{{ nDesigns === 1 ? '' : 's' }};
          strongest: {{ topResiduesSummary || '—' }}
        </span>
      </p>
    </template>
  </div>
</template>

<style scoped>
.contact-map-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.contact-map-message {
  margin: 0;
}

.contact-map-compute {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.8rem;
}

.contact-map-compute-text {
  color: #6c757d;
}

.contact-map-progress {
  height: 4px;
}

.contact-map-number {
  width: 100%;
}

.contact-map-key {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.contact-map-slider {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0 0.15rem;
}

.contact-map-slider-ends {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.7rem;
  color: #6c757d;
}

.contact-map-slider-reset {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: #4361aa;
  cursor: pointer;
  text-decoration: underline;
}

.contact-map-legend {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #495057;
}

.contact-map-legend-bar {
  flex: 1;
  height: 10px;
  border-radius: 2px;
  border: 1px solid #dee2e6;
}

.contact-map-legend-unit {
  color: #6c757d;
}

.contact-map-swatch {
  width: 14px;
  height: 10px;
  border-radius: 2px;
  border: 1px solid #dee2e6;
}

.contact-map-swatch--contact {
  background: rgb(189, 42, 36);
}

.contact-map-swatch--none {
  background: rgb(220, 224, 230);
}
</style>
