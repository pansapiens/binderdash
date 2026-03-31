<template>
  <div class="designs-view">
    <div class="designs-header">
      <h2>Designs</h2>
      <div class="designs-controls">
        <!-- Controls removed - designs now auto-sync with selected runs -->
      </div>
    </div>

          <div class="designs-content">
        <!-- Column Selector Panel moved to top -->
        <div v-if="showColumnSelector" class="column-selector-panel">
          <div class="column-selector-header">
            <h3>Toggle Columns</h3>
            <Button 
              icon="pi pi-times" 
              @click="toggleColumnSelector"
              rounded
              variant="outlined"
              severity="danger"
              aria-label="Close column selector"
              class="close-button"
            />
          </div>
          <div class="column-toggles">
            <div v-for="col in designsStore.columns" :key="col.field" class="column-toggle">
              <Checkbox 
                :modelValue="isColumnVisible(col.field)"
                @update:modelValue="toggleColumn(col.field)"
                :binary="true"
                :inputId="'col-' + col.field"
              />
              <label :for="'col-' + col.field" class="ml-2">{{ col.header }}</label>
            </div>
          </div>
        </div>

        <!-- Filter Panel -->
        <div v-if="showFilterPanel" class="filter-panel">
          <div class="filter-panel-header">
            <h3>Filters</h3>
            <Button 
              icon="pi pi-times" 
              @click="toggleFilterPanel"
              rounded
              variant="outlined"
              severity="danger"
              aria-label="Close filter panel"
              class="close-button"
            />
          </div>
          <div class="filter-controls">
            <div class="filter-row">
              <label>Global Search:</label>
              <InputText 
                v-model="designsStore.filters.global.value" 
                placeholder="Search all columns..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Design ID:</label>
              <InputText 
                v-model="designsStore.filters.design_id.value" 
                placeholder="Filter by design ID..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Project ID:</label>
              <InputText 
                v-model="designsStore.filters.project_id.value" 
                placeholder="Filter by project ID..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Run Name:</label>
              <InputText 
                v-model="designsStore.filters.run_name.value" 
                placeholder="Filter by run name..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Method:</label>
              <Dropdown 
                v-model="designsStore.filters.method.value" 
                :options="methodOptions" 
                placeholder="Select method"
                class="filter-input"
                showClear
              />
            </div>
            <div class="filter-row">
              <label>Score Range:</label>
              <div class="score-range">
                <InputNumber 
                  v-model="designsStore.filters.score_min.value" 
                  placeholder="Min"
                  class="filter-input-small"
                />
                <span class="range-separator">to</span>
                <InputNumber 
                  v-model="designsStore.filters.score_max.value" 
                  placeholder="Max"
                  class="filter-input-small"
                />
              </div>
            </div>
            <div class="filter-row">
              <label>Length Range:</label>
              <div class="length-range">
                <div class="length-inputs">
                  <InputNumber 
                    v-model="lengthMin" 
                    :min="lengthRange[0]"
                    :max="lengthRange[1]"
                    @update:modelValue="updateLengthFromInputs"
                    placeholder="Min"
                    class="filter-input-small"
                  />
                  <span class="range-separator">to</span>
                  <InputNumber 
                    v-model="lengthMax" 
                    :min="lengthRange[0]"
                    :max="lengthRange[1]"
                    @update:modelValue="updateLengthFromInputs"
                    placeholder="Max"
                    class="filter-input-small"
                  />
                </div>
                <Slider 
                  v-model="lengthRangeValue"
                  :min="lengthRange[0]"
                  :max="lengthRange[1]"
                  range
                  class="length-slider"
                />
              </div>
            </div>
            <div class="filter-row">
              <label>Target Sequence:</label>
              <InputText 
                v-model="designsStore.filters.target_sequence.value" 
                placeholder="Search target sequences (regex)..."
                class="filter-input"
              />
            </div>
            <div class="filter-row">
              <label>Best MPNN only:</label>
              <Checkbox 
                :modelValue="designsStore.bestMpnnOnly"
                @update:modelValue="designsStore.toggleBestMpnnOnly"
                :binary="true"
                inputId="best-mpnn-only"
              />
              <label for="best-mpnn-only" class="ml-2">Show only best MPNN variant per backbone</label>
            </div>
            <div class="filter-actions">
              <Button 
                label="Clear Filters" 
                @click="clearFilters"
                outlined
                size="small"
              />
              <Button 
                label="Apply Filters" 
                @click="applyFilters"
                size="small"
              />
            </div>
          </div>
        </div>

        <div class="designs-table-section">
          <DataTable 
          :key="`designs-table-${designsStore.selectedRunIds.length}-${designsStore.filteredDesigns.length}`"
          :value="designsStore.filteredDesigns" 
          :loading="designsStore.loading"
          v-model:sortField="designsStore.tableSortField"
          v-model:sortOrder="designsStore.tableSortOrder"
          v-model:selection="designsStore.selectedDesigns"
          dataKey="design_id"
          stripedRows
          paginator
          :rows="10"
          :rowsPerPageOptions="[10, 20, 50, 100]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="Showing {first} to {last} of {totalRecords} designs"
          showGridlines
          :resizableColumns="true"
          columnResizeMode="fit"
          :reorderableColumns="true"
          :reorderableRows="true"
          :rowHover="true"
          :scrollable="true"
          scrollHeight="800px"
          :selectOnClick="false"
          @row-click="onRowClick"
        >
          <template #header>
            <div class="flex justify-content-between align-items-center">
              <span class="text-xl font-bold">All Designs</span>
              <div class="flex gap-2 align-items-center">
                <Button 
                  icon="pi pi-table" 
                  @click="toggleColumnSelector"
                  text
                  rounded
                  severity="secondary"
                  variant="outlined"
                  :class="{ 'p-button-outlined': showColumnSelector }"
                />
                <Button 
                  icon="pi pi-filter" 
                  @click="toggleFilterPanel"
                  text
                  rounded
                  severity="secondary"
                  variant="outlined"
                  :class="{ 'p-button-outlined': showFilterPanel }"
                />
                <div class="flex align-items-start gap-3">
                  <div class="flex flex-column gap-2">
                    <SplitButton 
                      :model="exportMenuItems"
                      label="Download TSV"
                      icon="pi pi-download"
                      severity="secondary"
                      dropdownIcon="pi pi-chevron-down"
                      @click="onDownloadTsv"
                      size="small"
                    />
                    <div class="flex align-items-center gap-1">
                      <Checkbox 
                        :modelValue="exportIncludeAllColumns"
                        @update:modelValue="val => exportIncludeAllColumns = !!val"
                        :binary="true"
                        inputId="include-all-cols"
                      />
                      <label for="include-all-cols" class="text-sm">Include all columns</label>
                    </div>
                  </div>
                  <div class="select-top-controls">
                    <label for="select-top-count" class="text-sm font-medium">Select top:</label>
                    <InputNumber 
                      v-model="selectTopCount"
                      :min="1"
                      :max="Math.max(1, designsStore.filteredDesigns.length)"
                      placeholder="N"
                      size="small"
                      inputId="select-top-count"
                      class="select-top-input"
                      @input="(event) => selectTopCount = Number(event.value)"
                    />
                    <Button 
                      label="Select"
                      severity="secondary"
                      @click="selectTopRows"
                      size="small"
                      :disabled="!selectTopCount || selectTopCount < 1"
                    />
                  </div>
                </div>
              </div>
            </div>
          </template>

          <template #empty>
            <div class="text-center p-4">
              <i class="pi pi-table" style="font-size: 3rem; color: #6c757d;"></i>
              <h3>No Designs Found</h3>
              <p>Scan some folders and select runs to see designs here</p>
            </div>
          </template>

          <template #loading>
            <div class="text-center p-4">
              <i class="pi pi-spinner pi-spin" style="font-size: 2rem; color: #667eea;"></i>
              <p>Loading designs...</p>
            </div>
          </template>

          <!-- Selection column -->
          <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>

          <!-- Dynamic columns based on available data -->
          <Column 
            v-for="col in getVisibleColumns()" 
            :key="col.field"
            :field="col.field" 
            :header="col.header"
            :sortable="col.sortable"
            :filter="col.filter"
            :filterType="col.filterType || 'text'"
            :showFilterMenu="col.showFilterMenu"
            :style="col.style"
            :class="col.class"
          >
            <template #body="{ data }" v-if="col.field === 'good'">
              <span :class="['good-cell', goodCellModifier(data.good)]">
                <span
                  v-if="normalizeGood(data.good) === true"
                  class="good-cell-symbol"
                  title="Good"
                  aria-label="Good"
                >✓</span>
                <span
                  v-else-if="normalizeGood(data.good) === false"
                  class="good-cell-symbol"
                  title="Not good"
                  aria-label="Not good"
                >✗</span>
                <span v-else class="good-cell-dash" aria-label="Not rated">—</span>
              </span>
            </template>
            <template #body="{ data }" v-else-if="col.template">
              <component :is="col.template" :data="data" :field="col.field" />
            </template>
          </Column>

          <Column header="Actions" style="width: 180px" :exportable="false" :frozen="true" alignFrozen="right">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button 
                  icon="pi pi-eye" 
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  @click="viewDesign(data)"
                  rounded
                  tooltip="View Structure"
                />
                <Button 
                  icon="pi pi-download" 
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  @click="downloadPdb(data)"
                  rounded
                  tooltip="Download PDB"
                />
                <Button 
                  icon="pi pi-code" 
                  size="small"
                  severity="secondary"
                  variant="outlined"
                  @click="openParamsDialog(data)"
                  rounded
                  :disabled="!data?.params"
                  tooltip="View Params JSON"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Structure Viewer Section -->
      <div v-if="designsStore.selectedDesigns.length > 0" class="structure-viewer-section">
        <div class="viewer-header">
          <h3>Structure Viewer</h3>
        </div>

        <div class="structure-info">
          <div v-if="designsStore.currentStructure" class="structure-details">
            <div class="details-section">
              <div class="details-section-title">Design Data</div>
              <div class="details-grid">
                <div class="detail-item">
                  <div class="detail-label">Design</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.design_id }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Project</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.project_id }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Run</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.run_name }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Method</div>
                  <div class="detail-value">{{ designsStore.currentStructure.design.method }}</div>
                </div>
                <div class="detail-item">
                  <div class="detail-label">Length</div>
                  <div class="detail-value">{{ getLengthValue(designsStore.currentStructure.design) }}</div>
                </div>
                <div class="detail-item file-item">
                  <div class="detail-label">File</div>
                  <div class="detail-value file-value">
                    <span class="file-name truncate-ellipsis" :title="designsStore.currentStructure.filename">{{ designsStore.currentStructure.filename }}</span>
                    <Button 
                      icon="pi pi-download" 
                      size="small"
                      rounded
                      @click.stop="downloadCurrentPdb"
                      :aria-label="`Download ${designsStore.currentStructure.filename}`"
                      v-tooltip.top="'Download PDB'"
                    />
                  </div>
                </div>
                <template
                  v-for="field in extraVisibleDesignDataFields"
                  :key="'dd-extra-' + field"
                >
                  <div class="detail-item">
                    <div class="detail-label">{{ columnHeaderForDetail(field) }}</div>
                    <div
                      class="detail-value truncate-ellipsis"
                      :title="String(getDetailFieldValue(designsStore.currentStructure.design, field) ?? '')"
                    >
                      {{ getDetailFieldValue(designsStore.currentStructure.design, field) }}
                    </div>
                  </div>
                </template>
              </div>
            </div>

            <div class="details-section">
              <div class="details-section-title">Scores</div>
              <div class="details-grid">
                <template v-for="scoreField in displayScores" :key="scoreField">
                  <div
                    v-if="hasValidValue(getScoreValue(designsStore.currentStructure.design, scoreField))"
                    class="detail-item"
                  >
                    <div class="score-bar" :style="{ backgroundColor: scoreColor(scoreField, getScoreValue(designsStore.currentStructure.design, scoreField)) }"></div>
                    <div class="detail-label">{{ formatScoreHeader(scoreField) }}</div>
                    <div class="detail-value">{{ formatScore(getScoreValue(designsStore.currentStructure.design, scoreField)) }}</div>
                  </div>
                </template>
                <template
                  v-for="scoreField in extraVisibleScoreFields"
                  :key="'sc-extra-' + scoreField"
                >
                  <div class="detail-item">
                    <div
                      class="score-bar"
                      :style="{
                        backgroundColor: extraScoreBarColor(
                          scoreField,
                          getDetailFieldValue(designsStore.currentStructure.design, scoreField)
                        )
                      }"
                    ></div>
                    <div class="detail-label">{{ columnHeaderForDetail(scoreField) }}</div>
                    <div class="detail-value">
                      {{ formatExtraScoreValue(getDetailFieldValue(designsStore.currentStructure.design, scoreField)) }}
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <div class="viewer-container" ref="viewerContainerRef" v-if="designsStore.currentStructure">
          <MolstarViewer 
            :pdb-url="getPdbUrl()"
            :reference-url="referenceViewerUrl"
            reference-data-format="mmcif"
            :membrane-data="referenceMembraneData"
            :structure-info="designsStore.currentStructure"
            :auto-focus="true"
            :show-controls="false"
            ref="molstarViewerRef"
          />
          <div
            ref="viewerControlsRef"
            class="viewer-controls"
            :style="viewerControlsStyle"
          >
            <div
              class="viewer-controls-drag"
              @pointerdown="onViewerControlsPointerDown"
              @dblclick.stop="resetViewerControlsPosition"
              role="button"
              tabindex="0"
              aria-label="Drag to reposition toolbar. Double-click to reset position."
              v-tooltip.top="viewerControlsDragTooltip"
            >
              <i class="pi pi-ellipsis-v" aria-hidden="true" />
            </div>
            <Button 
              icon="pi pi-chevron-left" 
              @click="navigateToPreviousRow"
              :disabled="!designsStore.canNavigatePrevious"
              text
              rounded
            />
            <span class="structure-counter">
              {{ getCurrentRowPosition() }}
            </span>
            <Button 
              icon="pi pi-chevron-right" 
              @click="navigateToNextRow"
              :disabled="!designsStore.canNavigateNext"
              text
              rounded
            />
            <Button 
              :icon="structureGood === true ? 'pi pi-thumbs-up-fill' : 'pi pi-thumbs-up'"
              @click="setStructureGood(true)"
              rounded
              severity="secondary"
              class="viewer-thumb-btn viewer-thumb-btn--good"
              :class="{ 'viewer-thumb-btn--selected': structureGood === true }"
              :disabled="!designsStore.currentStructure || goodRatingPending"
              v-tooltip.top="'Mark good (click again to clear)'"
              aria-label="Mark design good"
            />
            <Button 
              :icon="structureGood === false ? 'pi pi-thumbs-down-fill' : 'pi pi-thumbs-down'"
              @click="setStructureGood(false)"
              rounded
              severity="secondary"
              class="viewer-thumb-btn viewer-thumb-btn--bad"
              :class="{ 'viewer-thumb-btn--selected': structureGood === false }"
              :disabled="!designsStore.currentStructure || goodRatingPending"
              v-tooltip.top="'Not good (click again to clear)'"
              aria-label="Mark design not good"
            />
            <Button 
              :icon="isSpinning ? 'pi pi-pause' : 'pi pi-play'" 
              @click="toggleSpin"
              text
              rounded
              :tooltip="isSpinning ? 'Pause Rotation' : 'Start Rotation'"
            />
            <Button 
              label="pLDDT" 
              @click="toggleAlphaFoldView"
              text
              rounded
              :class="{ 'p-button-outlined': alphafoldViewEnabled, 'plddt-disabled': !alphafoldViewEnabled }"
              tooltip="Toggle AlphaFold pLDDT coloring"
            />
          </div>
        </div>

        <div v-if="designsStore.currentStructure" class="advanced-options-section">
          <button
            type="button"
            class="advanced-options-disclosure"
            @click="toggleAdvancedOptions"
            :aria-expanded="showAdvancedOptions"
            aria-controls="advanced-options-content"
            id="advanced-options-disclosure"
          >
            <i
              class="pi advanced-options-chevron"
              :class="showAdvancedOptions ? 'pi-chevron-down' : 'pi-chevron-right'"
              aria-hidden="true"
            />
            <span class="advanced-options-disclosure-label">Advanced options</span>
          </button>
          <div
            v-show="showAdvancedOptions"
            id="advanced-options-content"
            role="region"
            aria-labelledby="advanced-options-disclosure"
            class="advanced-options-expanded"
          >
            <div class="advanced-options-body">
            <div class="advanced-row">
              <Checkbox
                v-model="showInputTargetStructure"
                :binary="true"
                input-id="adv-input-target"
              />
              <label for="adv-input-target" class="advanced-checkbox-label">
                Show input target structure (from run params)
              </label>
            </div>
            <div
              v-if="showInputTargetStructure && inputTargetsList.length > 1"
              class="advanced-row advanced-row--full"
            >
              <label class="advanced-label">Input target</label>
              <Dropdown
                v-model="selectedInputTargetId"
                :options="inputTargetDropdownOptions"
                option-label="label"
                option-value="value"
                placeholder="Select structure"
                class="advanced-dropdown"
              />
            </div>
            <p
              v-if="showInputTargetStructure && inputTargetsList.length === 0 && !inputTargetsLoading"
              class="advanced-hint advanced-hint--warn"
            >
              No input target structure found in run params.
            </p>
            <template v-if="!showInputTargetStructure">
              <div class="advanced-row advanced-row--full">
                <div class="advanced-label advanced-label-with-info">
                  <label for="adv-reference-source">Reference structure</label>
                  <i
                    class="pi pi-info-circle advanced-reference-info-icon"
                    v-tooltip.top="referenceStructureTooltipOptions"
                    tabindex="0"
                    aria-label="Reference structure help"
                  />
                </div>
                <InputText
                  v-model="referenceManualSource"
                  id="adv-reference-source"
                  placeholder="PDB ID, https://… .pdb/.cif (.gz), or PDBTM entry/JSON URL"
                  class="advanced-input"
                  @keydown.enter="onReferenceManualEnter"
                />
              </div>
            </template>
            <div class="advanced-row advanced-row--full">
              <label for="adv-reference-chains" class="advanced-label">Chains</label>
              <InputText
                v-model="referenceChainIdsInput"
                id="adv-reference-chains"
                placeholder="Optional — comma or space separated (e.g. A, B); TM-align and overlay use only these reference chains"
                class="advanced-input"
              />
            </div>
            <div class="advanced-actions">
              <Button
                label="Load reference"
                icon="pi pi-sync"
                @click="() => loadReferenceOverlay()"
                :loading="referenceLoading"
                :disabled="!canLoadReferenceOverlay"
              />
              <Button
                label="Clear"
                icon="pi pi-times"
                severity="secondary"
                variant="outlined"
                @click="clearReferenceOverlay"
                :disabled="!referenceOverlayActive && !referenceViewerUrl"
              />
            </div>
            <div v-if="referenceMetrics" class="reference-metrics">
              <span>TM-score (design norm): {{ referenceMetrics.tmNormDesign.toFixed(3) }}</span>
              <span>TM-score (reference norm): {{ referenceMetrics.tmNormReference.toFixed(3) }}</span>
              <span>RMSD: {{ referenceMetrics.rmsd.toFixed(3) }} Å</span>
              <span>Aligned length: {{ referenceMetrics.alignedLength }}</span>
            </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="no-selection">
        <div class="no-selection-content">
          <i class="pi pi-cube" style="font-size: 3rem; color: #6c757d;"></i>
          <h3>No Structures Selected</h3>
          <p>Select one or more designs from the table above to view structures</p>
        </div>
      </div>
    </div>
    
    <Toast />
  
  <Dialog 
    v-model:visible="showParamsDialog" 
    modal 
    header="Run Parameters"
    :style="{ width: '60vw', maxWidth: '900px' }"
  >
    <div v-if="currentParamsJson" class="params-json-container">
      <pre class="params-pre">{{ currentParamsJson }}</pre>
    </div>
    <div v-else class="text-center p-3">No params available for this design</div>
  </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import Slider from 'primevue/slider'
import SplitButton from 'primevue/splitbutton'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import Dialog from 'primevue/dialog'
import MolstarViewer from './MolstarViewer.vue'
import type { MembraneData } from '../membraneOverlay'
import { runsApi } from '../webapi'
import { useDesignsStore, useAppStore, useAuthStore, useFolderStore } from '../stores'

const toast = useToast()

// Use Pinia stores
const designsStore = useDesignsStore()
const appStore = useAppStore()
const authStore = useAuthStore()
const folderStore = useFolderStore()

// Local UI state (not shared across components)
const showColumnSelector = ref(false)
const showFilterPanel = ref(false)
const showAdvancedOptions = ref(false)
const molstarViewerRef = ref<any>(null)

const VIEWER_CONTROLS_POS_KEY = 'binderdash-viewer-controls-pos'

const viewerContainerRef = ref<HTMLElement | null>(null)
const viewerControlsRef = ref<HTMLElement | null>(null)
const viewerControlsPos = ref<{ left: number; top: number } | null>(null)

const viewerControlsDragTooltip =
  'Drag to move toolbar. Double-click here to snap back to the default position.'

let viewerDragActive = false
let viewerDragPointerId: number | null = null
let viewerDragStart = { clientX: 0, clientY: 0, left: 0, top: 0 }

const viewerControlsStyle = computed(() => {
  if (!viewerControlsPos.value) return {}
  const { left, top } = viewerControlsPos.value
  return {
    left: `${Math.round(left)}px`,
    top: `${Math.round(top)}px`,
    transform: 'none',
  } as Record<string, string>
})

function persistViewerControlsPos() {
  try {
    if (viewerControlsPos.value) {
      localStorage.setItem(VIEWER_CONTROLS_POS_KEY, JSON.stringify(viewerControlsPos.value))
    } else {
      localStorage.removeItem(VIEWER_CONTROLS_POS_KEY)
    }
  } catch {
    /* ignore */
  }
}

function loadViewerControlsPos() {
  try {
    const raw = localStorage.getItem(VIEWER_CONTROLS_POS_KEY)
    if (!raw) return
    const o = JSON.parse(raw) as { left?: unknown; top?: unknown }
    if (typeof o.left === 'number' && typeof o.top === 'number' && Number.isFinite(o.left) && Number.isFinite(o.top)) {
      viewerControlsPos.value = { left: o.left, top: o.top }
    }
  } catch {
    /* ignore */
  }
}

function clampViewerControlsPosition(left: number, top: number): { left: number; top: number } {
  const c = viewerContainerRef.value
  const el = viewerControlsRef.value
  if (!c || !el) return { left, top }
  const cw = c.clientWidth
  const ch = c.clientHeight
  const ew = el.offsetWidth
  const eh = el.offsetHeight
  return {
    left: Math.max(0, Math.min(left, Math.max(0, cw - ew))),
    top: Math.max(0, Math.min(top, Math.max(0, ch - eh))),
  }
}

function clampViewerControlsIfNeeded() {
  if (!viewerControlsPos.value) return
  const next = clampViewerControlsPosition(viewerControlsPos.value.left, viewerControlsPos.value.top)
  viewerControlsPos.value = next
}

function onViewerControlsPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  const container = viewerContainerRef.value
  const controls = viewerControlsRef.value
  if (!container || !controls) return
  e.preventDefault()
  e.stopPropagation()
  const cr = container.getBoundingClientRect()
  const er = controls.getBoundingClientRect()
  const left = er.left - cr.left
  const top = er.top - cr.top
  viewerDragActive = true
  viewerDragPointerId = e.pointerId
  viewerDragStart = { clientX: e.clientX, clientY: e.clientY, left, top }
  try {
    controls.setPointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
  window.addEventListener('pointermove', onViewerControlsPointerMove)
  window.addEventListener('pointerup', onViewerControlsPointerUp)
  window.addEventListener('pointercancel', onViewerControlsPointerUp)
}

function onViewerControlsPointerMove(e: PointerEvent) {
  if (!viewerDragActive || e.pointerId !== viewerDragPointerId) return
  const dx = e.clientX - viewerDragStart.clientX
  const dy = e.clientY - viewerDragStart.clientY
  viewerControlsPos.value = clampViewerControlsPosition(
    viewerDragStart.left + dx,
    viewerDragStart.top + dy
  )
}

function onViewerControlsPointerUp(e: PointerEvent) {
  if (!viewerDragActive) return
  if (viewerDragPointerId != null && e.pointerId !== viewerDragPointerId) return
  const controls = viewerControlsRef.value
  try {
    if (controls && viewerDragPointerId != null) {
      controls.releasePointerCapture(viewerDragPointerId)
    }
  } catch {
    /* ignore */
  }
  window.removeEventListener('pointermove', onViewerControlsPointerMove)
  window.removeEventListener('pointerup', onViewerControlsPointerUp)
  window.removeEventListener('pointercancel', onViewerControlsPointerUp)
  viewerDragActive = false
  viewerDragPointerId = null
  persistViewerControlsPos()
}

function resetViewerControlsPosition() {
  viewerControlsPos.value = null
  persistViewerControlsPos()
}

const REF_STORE_PREFIX = 'binderdash-adv-ref:'

const referenceStructureHelp =
  'Enter a 4-letter PDB ID (e.g. 1crn), an https URL to a .pdb / .mmCIF file (.gz OK), or a PDBTM entry or JSON URL (e.g. pdbtm.unitmp.org/entry/6lfl or …/api/v1/entry/6lfl.json). PDBTM loads the RCSB structure and shows membrane planes when metadata is available.'

const referenceStructureTooltipOptions = {
  value: referenceStructureHelp,
  showDelay: 150,
  autoHide: false,
}

const referenceViewerUrl = ref('')
const referenceBlobUrlToRevoke = ref<string | null>(null)
const referenceOverlayActive = ref(false)
const referenceManualSource = ref('')
const referenceChainIdsInput = ref('')
const showInputTargetStructure = ref(false)
const selectedInputTargetId = ref<string | null>(null)
const inputTargetsList = ref<Array<{ id: string; label: string }>>([])
const inputTargetsLoading = ref(false)
const referenceLoading = ref(false)
const referenceMetrics = ref<{
  tmNormDesign: number
  tmNormReference: number
  rmsd: number
  alignedLength: number
} | null>(null)
const referenceMembraneData = ref<MembraneData | null>(null)
const isSpinning = ref(false)
const alphafoldViewEnabled = ref(true)
const goodRatingPending = ref(false)
const exportIncludeAllColumns = ref(false)
const selectTopCount = ref<number | null>(null)
const exportMenuItems = ref([
  { label: 'Download CSV', icon: 'pi pi-download', command: () => onDownloadCsv() },
  { label: 'Download PDBs', icon: 'pi pi-box', command: () => onDownloadPdbs() },
  { label: 'Download FASTA (Binders)', icon: 'pi pi-file', command: () => onDownloadFasta() }
])

// Params dialog state
const showParamsDialog = ref(false)
const currentParamsJson = ref<string>('')

// Filter options
const methodOptions = ref(['bindcraft', 'rfd', 'boltzgen', 'rfd3'])

// Length filter state
const lengthRange = ref([0, 300]) // Default range, will be updated based on data
const lengthMin = ref(0)
const lengthMax = ref(300)

// Primary scores to display in structure details
const primaryScores = ref(['Average_i_pTM', 'design_to_target_iptm', 'pae_interaction'])
const secondaryScores = ref(['Average_Binder_pLDDT', 'plddt_binder'])
// const binderRMSD = ref(['Average_Binder_RMSD', 'binder_aligned_rmsd'])

// Human-readable field name mapping
const niceFieldNames: Record<string, string> = {
  'Average_i_pTM': 'Average i-pTM',
  'design_to_target_iptm': 'Design→Target ipTM',
  'pae_interaction': 'PAE Interaction',
  'Average_Binder_RMSD': 'Average Binder RMSD',
  'Average_Target_RMSD': 'Average Target RMSD',
  'Average_Binder_pLDDT': 'Average Binder pLDDT',
  'plddt_binder': 'Binder pLDDT',
  'binder_aligned_rmsd': 'Binder Aligned RMSD',
  'interaction_pae': 'Interaction PAE',
  'min_interation_pae': 'Min interaction PAE',
  'design_ipsae_min': 'Design ipSAE min',
  iptm: 'ipTM',
  pair_pae: 'Pair PAE',
  rf3_ipsae_min: 'RF3 ipSAE Min',
  rf3_rmsd_target_aligned_binder_rmsd_all: 'RF3 RMSD (Target-aligned Binder)'
}

// Computed properties using store
const isColumnVisible = (field: string): boolean => {
  return designsStore.visibleColumns.includes(field)
}

// Computed properties for length filtering
const lengthRangeValue = computed({
  get: () => [designsStore.filters.length_min.value || lengthMin.value, designsStore.filters.length_max.value || lengthMax.value],
  set: (value: number[]) => {
    designsStore.filters.length_min.value = value[0]
    designsStore.filters.length_max.value = value[1]
    lengthMin.value = value[0]
    lengthMax.value = value[1]
  }
})


// Methods

const loadDesigns = async () => {
  // Only load designs if authentication allows it
  if (!authStore.canLoadData) {
    console.log('Authentication required - skipping designs load')
    return
  }

  try {
    await designsStore.fetchDesigns()
  } catch (error: any) {
    console.error('Error loading designs:', error)
    // Don't show toast for authentication errors - user will be redirected to login
    if (error?.message !== 'Authentication required') {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: 'Failed to load designs',
        life: 3000
      })
    }
  }
}

const viewDesign = (design: any): void => {
  designsStore.viewDesign(design)
}

const onRowClick = (event: any): void => {
  // Only trigger view if the click wasn't on a button or checkbox
  const target = event.originalEvent.target as HTMLElement
  const isButton = target.closest('button') || target.closest('.p-button')
  const isCheckbox = target.closest('.p-checkbox') || target.closest('input[type="checkbox"]')
  
  // Don't trigger view if clicking on buttons or checkboxes
  if (!isButton && !isCheckbox) {
    // Prevent the default row selection behavior
    event.originalEvent.preventDefault()
    event.originalEvent.stopPropagation()
    
    // Just view the design without affecting selection
    viewDesign(event.data)
  }
}

const downloadPdb = async (design: any): Promise<void> => {
  try {
    const filename = designsStore.getStructureFilename(design)
    if (!filename) {
      throw new Error('No structure file found for this design')
    }
    
    // Get the PDB URL for this design
    const pdbUrl = runsApi.getPdbFileUrl(design.run_id, filename)
    
    // Create a temporary anchor element to trigger download
    const link = document.createElement('a')
    link.href = pdbUrl
    link.download = filename
    link.target = '_blank'
    
    // Append to body, click, and remove
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    toast.add({
      severity: 'success',
      summary: 'Download Started',
      detail: `Downloading ${filename}`,
      life: 3000
    })
  } catch (error: any) {
    console.error('Error downloading PDB:', error)
    toast.add({
      severity: 'error',
      summary: 'Download Failed',
      detail: error.message || 'Failed to download PDB file',
      life: 3000
    })
  }
}

const openParamsDialog = (design: any): void => {
  try {
    const params = design?.params
    currentParamsJson.value = params ? JSON.stringify(params, null, 2) : ''
    showParamsDialog.value = true
  } catch (err) {
    currentParamsJson.value = ''
    showParamsDialog.value = true
  }
}

const navigateToNextRow = () => {
  designsStore.navigateStructure('next')
}

const navigateToPreviousRow = () => {
  designsStore.navigateStructure('previous')
}

const getCurrentRowPosition = () => {
  return designsStore.getCurrentRowPosition()
}

const normalizeGood = (v: unknown): boolean | null => {
  if (v === true || v === 'true' || v === 1 || v === '1') return true
  if (v === false || v === 'false' || v === 0 || v === '0') return false
  if (v === '' || (typeof v === 'string' && v.trim() === '')) return null
  return null
}

const goodCellModifier = (v: unknown): string => {
  const n = normalizeGood(v)
  if (n === true) return 'good-cell--true'
  if (n === false) return 'good-cell--false'
  return 'good-cell--empty'
}

const structureGood = computed((): boolean | null => {
  const d = designsStore.currentStructure?.design as Record<string, unknown> | undefined
  if (!d || !Object.prototype.hasOwnProperty.call(d, 'good')) return null
  return normalizeGood(d.good)
})

const setStructureGood = async (clicked: boolean) => {
  const cur = designsStore.currentStructure
  if (!cur || goodRatingPending.value) return
  const current = structureGood.value
  const nextVal: boolean | null = current === clicked ? null : clicked
  goodRatingPending.value = true
  try {
    await designsStore.patchDesignGood(cur.design, nextVal)
  } catch (err: any) {
    toast.add({
      severity: 'error',
      summary: 'Could not update rating',
      detail: err?.message || 'Request failed',
      life: 4000
    })
  } finally {
    goodRatingPending.value = false
  }
}

const toggleSpin = async () => {
  if (molstarViewerRef.value) {
    await molstarViewerRef.value.toggleSpin()
    // Update local state to reflect the change
    isSpinning.value = molstarViewerRef.value.isSpinning
  }
}

const toggleAlphaFoldView = async () => {
  if (molstarViewerRef.value) {
    await molstarViewerRef.value.toggleAlphaFoldView()
    // Update local state to reflect the change
    alphafoldViewEnabled.value = molstarViewerRef.value.alphafoldViewEnabled
  }
}

const toggleColumnSelector = () => {
  showColumnSelector.value = !showColumnSelector.value
}

const toggleFilterPanel = () => {
  showFilterPanel.value = !showFilterPanel.value
}

// Removed duplicate function - using the one defined above

const toggleColumn = (field: string): void => {
  designsStore.toggleColumn(field)
}

const clearFilters = () => {
  designsStore.clearFilters()
}

const applyFilters = () => {
  // Filters are automatically applied through the DataTable's filter system
  // This method can be used for additional custom filtering logic if needed
  console.log('Filters applied:', designsStore.filters)
}

const selectTopRows = () => {
  if (!selectTopCount.value || selectTopCount.value < 1) {
    return
  }
  
  const sortedDesigns = designsStore.orderedFilteredDesigns

  const topRows = sortedDesigns.slice(0, selectTopCount.value)
  
  // Update the store's selected designs
  designsStore.selectedDesigns = topRows
  
  toast.add({
    severity: 'success',
    summary: 'Selection Updated',
    detail: `Selected top ${selectTopCount.value} designs`,
    life: 2000
  })
}

// Export helpers
const getRowsToExport = () => {
  const selected = designsStore.selectedDesigns
  return (selected && selected.length > 0) ? selected : designsStore.filteredDesigns
}

const getColumnsToExport = () => {
  const replaceRunId = (cols: string[]) => {
    return cols.map(c => (c === 'run_id' ? 'binderdash_run_id' : c)).filter((v, i, a) => a.indexOf(v) === i)
  }

  if (exportIncludeAllColumns.value) {
    // All distinct keys across rows
    const rows = getRowsToExport()
    const keySet = new Set<string>()
    rows.forEach((r: any) => Object.keys(r).forEach(k => keySet.add(k)))
    return replaceRunId(Array.from(keySet))
  }
  return replaceRunId(designsStore.visibleColumns)
}

const toSeparatedValues = (rows: any[], cols: string[], sep: string): string => {
  const esc = (v: any) => {
    if (v == null) return ''
    
    // Handle objects by serializing them as JSON
    if (typeof v === 'object' && v !== null) {
      const s = JSON.stringify(v)
      return sep === ',' && /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
    }
    
    const s = String(v)
    return sep === ',' && /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const header = cols.join(sep)
  const valueFor = (r: any, c: string) => {
    if (c === 'binderdash_run_id') return r['run_id']
    return r[c]
  }
  const lines = rows.map(r => cols.map(c => esc(valueFor(r, c))).join(sep))
  return [header, ...lines].join('\n')
}

const downloadBlob = (blob: Blob, filename: string) => {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const onDownloadCsv = () => {
  const rows = getRowsToExport()
  const cols = getColumnsToExport()
  const content = toSeparatedValues(rows as any[], cols as string[], ',')
  downloadBlob(new Blob([content], { type: 'text/csv;charset=utf-8' }), 'designs.csv')
}

const onDownloadTsv = () => {
  const rows = getRowsToExport()
  const cols = getColumnsToExport()
  const content = toSeparatedValues(rows as any[], cols as string[], '\t')
  downloadBlob(new Blob([content], { type: 'text/tab-separated-values;charset=utf-8' }), 'designs.tsv')
}

const onDownloadPdbs = async () => {
  try {
    const rows = getRowsToExport().filter((d: any) => designsStore.getStructureFilename(d))
    if (rows.length === 0) {
      toast.add({ severity: 'warn', summary: 'No PDBs', detail: 'No structure files to download', life: 2500 })
      return
    }
    const items = rows.map((d: any) => ({ run_id: d.run_id, filename: designsStore.getStructureFilename(d) }))
    const blob = await runsApi.downloadPdbsTar(items)
    downloadBlob(blob, 'designs_pdbs.tar')
  } catch (err: any) {
    console.error('Error downloading PDBs tar:', err)
    toast.add({ severity: 'error', summary: 'Download Failed', detail: err?.message || 'Failed to download PDBs', life: 3000 })
  }
}

const onDownloadFasta = () => {
  try {
    const rows = getRowsToExport()
    if (rows.length === 0) {
      toast.add({ severity: 'warn', summary: 'No Designs', detail: 'No designs to export', life: 2500 })
      return
    }

    // Find designs with sequence data
    const designsWithSequence = rows.filter((d: any) => {
      // Check for sequence in various possible field names
      const sequenceFields = ['Sequence', 'sequence', 'binder_sequence', 'binder_seq', 'seq']
      return sequenceFields.some(field => d[field] && String(d[field]).trim())
    })

    if (designsWithSequence.length === 0) {
      toast.add({ severity: 'warn', summary: 'No Sequences', detail: 'No sequence data found in selected designs', life: 2500 })
      return
    }

    // Generate FASTA content
    const fastaContent = designsWithSequence.map((d: any) => {
      // Find the sequence field (prioritize 'Sequence' then 'sequence' then others)
      const sequenceFields = ['Sequence', 'sequence', 'binder_sequence', 'binder_seq', 'seq']
      let sequence = ''
      
      for (const field of sequenceFields) {
        if (d[field] && String(d[field]).trim()) {
          sequence = String(d[field]).trim()
          break
        }
      }

      return `>${d.design_id}\n${sequence}`
    }).join('\n')

    downloadBlob(new Blob([fastaContent], { type: 'text/plain;charset=utf-8' }), 'designs_binders.fasta')
    
    toast.add({
      severity: 'success',
      summary: 'FASTA Downloaded',
      detail: `Downloaded ${designsWithSequence.length} sequences`,
      life: 3000
    })
  } catch (err: any) {
    console.error('Error downloading FASTA:', err)
    toast.add({ severity: 'error', summary: 'Download Failed', detail: err?.message || 'Failed to download FASTA', life: 3000 })
  }
}

// Length filter methods
const updateLengthFromInputs = () => {
  designsStore.filters.length_min.value = lengthMin.value
  designsStore.filters.length_max.value = lengthMax.value
}

const updateLengthRange = () => {
  // Update the length range based on available data
  if (designsStore.designs.length > 0) {
    const lengths = designsStore.designs
      .map(design => design.Length || design.length)
      .filter(length => length != null && !isNaN(Number(length)))
      .map(length => Number(length))
    
    if (lengths.length > 0) {
      const minLength = Math.min(...lengths)
      const maxLength = Math.max(...lengths)
      lengthRange.value = [minLength, maxLength]
      
      // Set initial values if not already set
      if (designsStore.filters.length_min.value == null) {
        lengthMin.value = minLength
        designsStore.filters.length_min.value = minLength
      }
      if (designsStore.filters.length_max.value == null) {
        lengthMax.value = maxLength
        designsStore.filters.length_max.value = maxLength
      }
    }
  }
}

const getPdbUrl = () => {
  if (!designsStore.currentStructure) return ''
  return runsApi.getPdbFileUrl(designsStore.currentStructure.design.run_id, designsStore.currentStructure.filename)
}

const inputTargetDropdownOptions = computed(() =>
  inputTargetsList.value.map((t) => ({ label: t.label, value: t.id }))
)

const canLoadReferenceOverlay = computed(() => {
  if (!designsStore.currentStructure || referenceLoading.value) return false
  if (showInputTargetStructure.value) {
    if (inputTargetsList.value.length === 0) return false
    if (inputTargetsList.value.length > 1 && !selectedInputTargetId.value) return false
    return true
  }
  return referenceManualSource.value.trim().length > 0
})

const onReferenceManualEnter = (e: KeyboardEvent) => {
  e.preventDefault()
  if (!canLoadReferenceOverlay.value) return
  void loadReferenceOverlay()
}

const toggleAdvancedOptions = () => {
  showAdvancedOptions.value = !showAdvancedOptions.value
  if (showAdvancedOptions.value) {
    const rid = designsStore.currentStructure?.design.run_id
    if (rid) {
      void refreshInputTargetsForRun(rid).then(() => {
        if (selectedInputTargetId.value) {
          const ok = inputTargetsList.value.some((t) => t.id === selectedInputTargetId.value)
          if (!ok) selectedInputTargetId.value = null
        }
        if (inputTargetsList.value.length === 1) {
          selectedInputTargetId.value = inputTargetsList.value[0].id
        }
      })
    }
  }
}

const persistAdvancedRef = (runId: string) => {
  try {
    localStorage.setItem(
      REF_STORE_PREFIX + runId,
      JSON.stringify({
        manual: referenceManualSource.value,
        chains: referenceChainIdsInput.value,
        useInput: showInputTargetStructure.value,
        inputId: selectedInputTargetId.value,
        overlay: referenceOverlayActive.value,
      })
    )
  } catch {
    /* ignore quota */
  }
}

const restoreAdvancedRef = (runId: string) => {
  try {
    const raw = localStorage.getItem(REF_STORE_PREFIX + runId)
    if (!raw) return
    const o = JSON.parse(raw) as Record<string, unknown>
    if (typeof o.manual === 'string') referenceManualSource.value = o.manual
    if (typeof o.chains === 'string') referenceChainIdsInput.value = o.chains
    if (typeof o.useInput === 'boolean') showInputTargetStructure.value = o.useInput
    if (o.inputId != null && o.inputId !== '') selectedInputTargetId.value = String(o.inputId)
    if (typeof o.overlay === 'boolean') referenceOverlayActive.value = o.overlay
  } catch {
    /* ignore */
  }
}

const revokeReferenceBlob = () => {
  if (referenceBlobUrlToRevoke.value) {
    URL.revokeObjectURL(referenceBlobUrlToRevoke.value)
    referenceBlobUrlToRevoke.value = null
  }
  referenceViewerUrl.value = ''
}

const clearReferenceOverlay = () => {
  revokeReferenceBlob()
  referenceOverlayActive.value = false
  referenceMetrics.value = null
  referenceMembraneData.value = null
  const cs = designsStore.currentStructure
  if (cs?.design.run_id) persistAdvancedRef(cs.design.run_id)
}

const parseMembraneHeaders = (res: Response): MembraneData | null => {
  const p1h = res.headers.get('X-Binderdash-Membrane-Plane1')
  const p2h = res.headers.get('X-Binderdash-Membrane-Plane2')
  const nh = res.headers.get('X-Binderdash-Membrane-Normal')
  const ch = res.headers.get('X-Binderdash-Membrane-Centroid')
  const rh = res.headers.get('X-Binderdash-Membrane-Radius')
  if (!p1h || !p2h || !nh || !ch || !rh) return null
  const tri = (s: string): [number, number, number] | null => {
    const a = s.split(',').map((x) => parseFloat(x.trim()))
    if (a.length !== 3 || a.some((x) => Number.isNaN(x))) return null
    return [a[0], a[1], a[2]]
  }
  const plane1 = tri(p1h)
  const plane2 = tri(p2h)
  const normal = tri(nh)
  const centroid = tri(ch)
  const radius = parseFloat(rh)
  if (!plane1 || !plane2 || !normal || !centroid || Number.isNaN(radius)) return null
  return { plane1, plane2, normal, centroid, radius }
}

const loadReferenceOverlay = async (silent = false) => {
  const cs = designsStore.currentStructure
  if (!cs) return
  revokeReferenceBlob()
  referenceLoading.value = true
  referenceMetrics.value = null
  referenceMembraneData.value = null
  try {
    const runId = cs.design.run_id
    const filename = cs.filename
    let requestUrl: string
    if (showInputTargetStructure.value) {
      let tid = selectedInputTargetId.value
      if (!tid && inputTargetsList.value.length === 1) {
        tid = inputTargetsList.value[0].id
      }
      if (!tid) throw new Error('Select an input target structure')
      requestUrl = runsApi.getAlignedReferenceUrl(runId, filename, {
        mode: 'input_target',
        inputTargetId: tid,
        referenceChains: referenceChainIdsInput.value,
      })
    } else {
      const inputEl = document.getElementById(
        'adv-reference-source',
      ) as HTMLInputElement | null
      const domSrc = inputEl?.value?.trim() ?? ''
      if (domSrc && domSrc !== referenceManualSource.value.trim()) {
        referenceManualSource.value = domSrc
      }
      const src = referenceManualSource.value.trim()
      if (!src) throw new Error('Enter a PDB ID or URL')
      requestUrl = runsApi.getAlignedReferenceUrl(runId, filename, {
        mode: 'manual',
        source: src,
        referenceChains: referenceChainIdsInput.value,
      })
    }
    const res = await fetch(requestUrl, { credentials: 'include' })
    if (!res.ok) {
      let detail = res.statusText
      try {
        const body = await res.json()
        if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      } catch {
        try {
          const t = await res.text()
          if (t) detail = t.slice(0, 200)
        } catch {
          /* ignore */
        }
      }
      throw new Error(detail || `HTTP ${res.status}`)
    }
    const tmD = res.headers.get('X-Binderdash-TM-Norm-Design')
    const tmR = res.headers.get('X-Binderdash-TM-Norm-Reference')
    const rmsdH = res.headers.get('X-Binderdash-RMSD')
    const alenH = res.headers.get('X-Binderdash-Aligned-Length')
    if (tmD && tmR && rmsdH && alenH) {
      referenceMetrics.value = {
        tmNormDesign: parseFloat(tmD),
        tmNormReference: parseFloat(tmR),
        rmsd: parseFloat(rmsdH),
        alignedLength: parseInt(alenH, 10),
      }
    }
    referenceMembraneData.value = parseMembraneHeaders(res)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    referenceBlobUrlToRevoke.value = objectUrl
    referenceViewerUrl.value = objectUrl
    referenceOverlayActive.value = true
    persistAdvancedRef(runId)
    if (!silent) {
      toast.add({ severity: 'success', summary: 'Reference loaded', life: 2000 })
    }
  } catch (e: unknown) {
    referenceOverlayActive.value = false
    referenceMembraneData.value = null
    const msg = e instanceof Error ? e.message : String(e)
    if (!silent) {
      toast.add({ severity: 'error', summary: 'Reference failed', detail: msg, life: 5000 })
    }
  } finally {
    referenceLoading.value = false
  }
}

const refreshInputTargetsForRun = async (runId: string) => {
  inputTargetsLoading.value = true
  inputTargetsList.value = []
  try {
    const r = await runsApi.getInputTargets(runId)
    inputTargetsList.value = r.targets || []
    if (inputTargetsList.value.length === 1) {
      selectedInputTargetId.value = inputTargetsList.value[0].id
    }
  } catch {
    inputTargetsList.value = []
  } finally {
    inputTargetsLoading.value = false
  }
}

const downloadCurrentPdb = async (): Promise<void> => {
  try {
    if (!designsStore.currentStructure) return
    const filename = designsStore.currentStructure.filename
    const runId = designsStore.currentStructure.design.run_id
    if (!filename || !runId) return
    const pdbUrl = runsApi.getPdbFileUrl(runId, filename)
    const link = document.createElement('a')
    link.href = pdbUrl
    link.download = filename
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    toast.add({ severity: 'success', summary: 'Download Started', detail: `Downloading ${filename}` , life: 2500 })
  } catch (error: any) {
    console.error('Error downloading PDB:', error)
    toast.add({ severity: 'error', summary: 'Download Failed', detail: error?.message || 'Failed to download PDB file', life: 3000 })
  }
}

const hasValidValue = (value: any): boolean => {
  return value !== null && value !== undefined && value !== '' && !isNaN(Number(value))
}

const getScoreValue = (design: any, field: string): any => {
  if (field === 'min_interation_pae') {
    const correct = design.min_interaction_pae
    const typo = design.min_interation_pae
    if (hasValidValue(correct)) return correct
    if (hasValidValue(typo)) return typo
    return undefined
  }
  return design[field]
}

const formatScore = (value: any): string => {
  if (!hasValidValue(value)) return ''
  const num = Number(value)
  return num.toFixed(3)
}

const formatScoreHeader = (fieldName: string): string => {
  // Convert field names to user-friendly headers
  return niceFieldNames[fieldName] || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

// Display scores list (order as requested plus existing primary)
const displayScores = ref([
  'Average_i_pTM',
  'design_to_target_iptm',
  'design_ipsae_min',
  'interaction_pae',
  'min_interation_pae',
  'Average_Binder_RMSD',
  'Average_Target_RMSD',
  'Average_Binder_pLDDT',
  'pae_interaction',
  'plddt_binder',
  'binder_aligned_rmsd',
  'iptm',
  'pair_pae',
  'rf3_ipsae_min',
  'rf3_rmsd_target_aligned_binder_rmsd_all'
])

const getLengthValue = (design: any): string | number => {
  const len = design?.Length ?? design?.length
  return (len != null && !isNaN(Number(len))) ? Number(len) : ''
}


// Score colour utilities
const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
const lerp = (a: number, b: number, t: number) => a + (b - a) * t
const colorFromT = (t: number): string => {
  // t in [0,1], map 0=red (#e74c3c), 0.5=amber (#f1c40f), 1=green (#2ecc71)
  const r1 = 231, g1 = 76, b1 = 60
  const r2 = 241, g2 = 196, b2 = 15
  const r3 = 46, g3 = 204, b3 = 113
  if (t <= 0.5) {
    const k = t / 0.5
    const r = Math.round(lerp(r1, r2, k))
    const g = Math.round(lerp(g1, g2, k))
    const b = Math.round(lerp(b1, b2, k))
    return `rgb(${r}, ${g}, ${b})`
  } else {
    const k = (t - 0.5) / 0.5
    const r = Math.round(lerp(r2, r3, k))
    const g = Math.round(lerp(g2, g3, k))
    const b = Math.round(lerp(b2, b3, k))
    return `rgb(${r}, ${g}, ${b})`
  }
}

/** PAE (Å): ≤10 green, 10–15 orange, >15 red (lower is better). */
const paeBandColor = (v: number): string => {
  if (v <= 10) return colorFromT(1)
  if (v <= 15) return 'rgb(241, 196, 15)'
  return colorFromT(0)
}

/** Min interaction PAE (Å): ≤5 green, >5–≤7 orange, >7 red. */
const minInteractionPaeBandColor = (v: number): string => {
  if (v <= 5) return colorFromT(1)
  if (v <= 7) return 'rgb(241, 196, 15)'
  return colorFromT(0)
}

const scoreColor = (field: string, raw: any): string => {
  const v = Number(raw)
  if (!isFinite(v)) return '#dfe6e9'

  if (field === 'min_interation_pae') {
    return minInteractionPaeBandColor(v)
  }

  const paeFields = new Set(['pae_interaction', 'interaction_pae'])
  if (paeFields.has(field)) {
    return paeBandColor(v)
  }

  // ipSAE: same 0–1 “higher is better” scale as ipTM
  if (field === 'design_ipsae_min') {
    const t = clamp01((v - 0) / 1)
    return colorFromT(t)
  }

  // Field-specific ranges and whether higher is better
  const config: Record<string, { min: number, max: number, higherBetter: boolean }> = {
    'Average_i_pTM': { min: 0, max: 1, higherBetter: true },
    'design_to_target_iptm': { min: 0, max: 1, higherBetter: true },
    'Average_Binder_pLDDT': { min: 0, max: 1, higherBetter: true },
    'plddt_binder': { min: 0, max: 100, higherBetter: true },
    'Average_Binder_RMSD': { min: 0, max: 3.5, higherBetter: false },
    'Average_Target_RMSD': { min: 0, max: 3.5, higherBetter: false },
    'binder_aligned_rmsd': { min: 0, max: 3.5, higherBetter: false }
  }

  const cfg = config[field]
  if (!cfg) return '#dfe6e9'
  const span = Math.max(1e-9, cfg.max - cfg.min)
  let t = clamp01((v - cfg.min) / span)
  if (!cfg.higherBetter) t = 1 - t
  return colorFromT(t)
}

const STATIC_STRUCTURE_DETAIL_FIELDS = new Set([
  'design_id',
  'project_id',
  'run_name',
  'method',
  'Length',
  'length'
])

const isBooleanDetailValue = (v: unknown): boolean => v === true || v === false

const isNumericDetailValue = (v: unknown): boolean => {
  if (v === null || v === undefined || v === '') return false
  if (typeof v === 'boolean') return false
  const n = Number(v)
  return Number.isFinite(n)
}

const isStringDetailValue = (v: unknown): boolean => typeof v === 'string' && v !== ''

const getDetailFieldValue = (design: Record<string, unknown> | undefined, field: string): unknown => {
  if (!design) return undefined
  return getScoreValue(design, field)
}

const columnHeaderForDetail = (field: string): string => {
  const col = designsStore.columns.find(c => c.field === field)
  if (col?.header) return col.header
  return formatScoreHeader(field)
}

const formatExtraScoreValue = (value: unknown): string => {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (isNumericDetailValue(value)) return Number(value).toFixed(3)
  return ''
}

const extraScoreBarColor = (field: string, raw: unknown): string => {
  if (raw === true) return '#2ecc71'
  if (raw === false) return '#e74c3c'
  return scoreColor(field, raw)
}

const extraVisibleScoreFields = computed((): string[] => {
  const design = designsStore.currentStructure?.design as Record<string, unknown> | undefined
  if (!design) return []
  const primary = new Set(displayScores.value)
  const out: string[] = []
  for (const field of designsStore.visibleColumns) {
    if (STATIC_STRUCTURE_DETAIL_FIELDS.has(field) || primary.has(field)) continue
    const v = getDetailFieldValue(design, field)
    if (v !== null && v !== undefined && typeof v === 'object') continue
    if (isBooleanDetailValue(v) || isNumericDetailValue(v)) out.push(field)
  }
  return out
})

const extraVisibleDesignDataFields = computed((): string[] => {
  const design = designsStore.currentStructure?.design as Record<string, unknown> | undefined
  if (!design) return []
  const primary = new Set(displayScores.value)
  const out: string[] = []
  for (const field of designsStore.visibleColumns) {
    if (STATIC_STRUCTURE_DETAIL_FIELDS.has(field) || primary.has(field)) continue
    const v = getDetailFieldValue(design, field)
    if (isStringDetailValue(v) && !isNumericDetailValue(v)) out.push(field)
  }
  return out
})

const getVisibleColumns = () => {
  // If columns haven't been loaded yet, return empty array
  if (designsStore.columns.length === 0) {
    return []
  }
  
  // Filter the full column configuration to only show visible columns
  return designsStore.columns.filter((col: any) => 
    designsStore.visibleColumns.includes(col.field)
  )
}


// Watchers
watch(() => authStore.canLoadData, (canLoad) => {
  if (canLoad && designsStore.designs.length === 0) {
    loadDesigns()
  }
}, { immediate: true })

// Watch for changes in selected runs and update designs store
watch(() => folderStore.selectedRuns, (newSelectedRuns) => {
  if (newSelectedRuns && newSelectedRuns.length > 0) {
    // Update the designs store with the selected run IDs
    const runIds = newSelectedRuns.map(run => run.run_id)
    designsStore.setSelectedRunIds(runIds)
  } else {
    // Clear the run filter if no runs are selected
    designsStore.setSelectedRunIds([])
  }
}, { deep: true, immediate: true })

// Sync spinning state when viewer changes
watch(() => molstarViewerRef.value?.isSpinning, (newSpinningState) => {
  if (newSpinningState !== undefined) {
    isSpinning.value = newSpinningState
  }
}, { immediate: true })

// Sync alphafoldView state when viewer changes
watch(() => molstarViewerRef.value?.alphafoldViewEnabled, (newAlphaFoldState) => {
  if (newAlphaFoldState !== undefined) {
    alphafoldViewEnabled.value = newAlphaFoldState
  }
}, { immediate: true })

// Update length range when designs are loaded
watch(() => designsStore.designs, () => {
  updateLengthRange()
}, { deep: true, immediate: true })

watch(
  () => designsStore.currentStructure?.design.run_id,
  async (runId, prev) => {
    try {
      if (!runId) {
        revokeReferenceBlob()
        referenceMetrics.value = null
        referenceMembraneData.value = null
        inputTargetsList.value = []
        selectedInputTargetId.value = null
        return
      }
      if (runId === prev) {
        return
      }
      revokeReferenceBlob()
      referenceMetrics.value = null
      referenceMembraneData.value = null
      restoreAdvancedRef(runId)
      const needInputTargets =
        showAdvancedOptions.value ||
        (referenceOverlayActive.value && showInputTargetStructure.value)
      if (needInputTargets) {
        await refreshInputTargetsForRun(runId)
        if (selectedInputTargetId.value) {
          const ok = inputTargetsList.value.some((t) => t.id === selectedInputTargetId.value)
          if (!ok) selectedInputTargetId.value = null
        }
        if (inputTargetsList.value.length === 1) {
          selectedInputTargetId.value = inputTargetsList.value[0].id
        }
      } else {
        inputTargetsList.value = []
      }
      if (referenceOverlayActive.value && canLoadReferenceOverlay.value) {
        await loadReferenceOverlay(true)
      } else if (referenceOverlayActive.value) {
        referenceOverlayActive.value = false
        persistAdvancedRef(runId)
      }
    } catch (e) {
      console.error('DesignsView: reference/run watcher failed', e)
    }
  },
  { immediate: true }
)

watch(showInputTargetStructure, (useInput) => {
  const rid = designsStore.currentStructure?.design.run_id
  if (useInput && rid && inputTargetsList.value.length === 0 && !inputTargetsLoading.value) {
    void refreshInputTargetsForRun(rid)
  }
})

watch(
  () => designsStore.currentStructure?.filename,
  async (fn, prev) => {
    if (!fn || fn === prev || !referenceOverlayActive.value) return
    if (canLoadReferenceOverlay.value) {
      await loadReferenceOverlay(true)
    }
  }
)

watch(
  [referenceManualSource, referenceChainIdsInput, showInputTargetStructure, selectedInputTargetId],
  () => {
    const rid = designsStore.currentStructure?.design.run_id
    if (rid) persistAdvancedRef(rid)
  }
)

watch(
  () => designsStore.currentStructure,
  () => {
    void nextTick(() => clampViewerControlsIfNeeded())
  }
)

function onViewerControlsResize() {
  clampViewerControlsIfNeeded()
}

// Lifecycle
onMounted(() => {
  loadViewerControlsPos()
  window.addEventListener('resize', onViewerControlsResize)
  if (authStore.canLoadData) {
    loadDesigns()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onViewerControlsResize)
  window.removeEventListener('pointermove', onViewerControlsPointerMove)
  window.removeEventListener('pointerup', onViewerControlsPointerUp)
  window.removeEventListener('pointercancel', onViewerControlsPointerUp)
})

// Expose methods to parent component
defineExpose({
  loadDesigns
})
</script>

<style scoped>
.designs-view {
  --rating-good-bg: #d8f3dc;
  --rating-good-fg: #1b4332;
  --rating-bad-bg: #fcd4e0;
  --rating-bad-fg: #9d174d;

  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.designs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.designs-header h2 {
  margin: 0;
  color: #495057;
}

.designs-controls {
  display: flex;
  gap: 0.5rem;
}

.designs-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.designs-table-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
}

.column-selector-panel {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
  border: 1px solid #e9ecef;
  margin-bottom: 1.5rem;
}

.column-selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.column-selector-header h3 {
  margin: 0;
  color: #495057;
}

/*
.close-button {
  padding: 0.5rem;
  min-width: auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button .p-button-icon {
  margin-left: 0.125rem;
}
*/

.filter-panel {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
  border: 1px solid #e9ecef;
  margin-bottom: 1.5rem;
}

.filter-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.filter-panel-header h3 {
  margin: 0;
  color: #495057;
}

.filter-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.filter-row label {
  min-width: 120px;
  font-weight: 500;
  color: #495057;
}

.filter-input {
  flex: 1;
  max-width: 300px;
}

.filter-input-small {
  width: 120px;
}

.score-range {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.length-range {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  max-width: 400px;
}

.length-inputs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.length-slider {
  width: 100%;
}

.range-separator {
  color: #6c757d;
  font-weight: 500;
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e9ecef;
}

.advanced-options-section {
  margin-top: 1rem;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.advanced-options-disclosure {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  margin: 0;
  border: none;
  background: #f8f9fa;
  padding: 0.65rem 1rem;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: #495057;
}

.advanced-options-disclosure:hover {
  background: #e9ecef;
}

.advanced-options-chevron {
  font-size: 0.85rem;
  color: #6c757d;
  flex-shrink: 0;
}

.advanced-options-disclosure-label {
  font-weight: 600;
  font-size: 1rem;
}

.advanced-options-expanded {
  padding: 1rem 1.25rem 1.25rem;
  border-top: 1px solid #e9ecef;
}

.advanced-options-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.advanced-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.advanced-row--full {
  flex-wrap: wrap;
}

.advanced-label {
  min-width: 140px;
  font-weight: 500;
  color: #495057;
}

.advanced-label-with-info {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.advanced-label-with-info label {
  margin: 0;
  cursor: default;
}

.advanced-reference-info-icon {
  font-size: 0.7rem;
  color: #6c757d;
  cursor: help;
  line-height: 1;
}

.advanced-reference-info-icon:hover,
.advanced-reference-info-icon:focus-visible {
  color: #495057;
  outline: none;
}

.advanced-checkbox-label {
  margin: 0;
  cursor: pointer;
  color: #495057;
}

.advanced-input {
  flex: 1;
  min-width: 200px;
  max-width: 100%;
}

.advanced-dropdown {
  flex: 1;
  min-width: 200px;
  max-width: 420px;
}

.advanced-hint {
  margin: 0;
  font-size: 0.9rem;
  color: #6c757d;
}

.advanced-hint--warn {
  color: #856404;
}

.advanced-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.reference-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  font-size: 0.875rem;
  color: #495057;
  padding-top: 0.5rem;
  border-top: 1px solid #e9ecef;
}

/* Removed duplicate rule - using .column-selector-header h3 above */

.column-toggles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
}

.column-toggle {
  display: flex;
  align-items: center;
  padding: 0.5rem;
  border-radius: 4px;
  background: #f8f9fa;
}

.structure-viewer-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.viewer-header h3 {
  margin: 0;
  color: #495057;
}

.viewer-controls {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.35rem;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e9ecef;
  border-radius: 9999px;
  padding: 0.25rem 0.5rem 0.25rem 0.15rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  opacity: 1;
  z-index: 5;
}

.viewer-controls-drag {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0.2rem 0.4rem;
  margin-left: -0.05rem;
  margin-right: 0.1rem;
  cursor: grab;
  touch-action: none;
  color: #868e96;
  border-right: 1px solid #dee2e6;
  border-radius: 9999px 0 0 9999px;
  user-select: none;
}

.viewer-controls-drag:hover {
  color: #495057;
  background: rgba(0, 0, 0, 0.05);
}

.viewer-controls-drag:active {
  cursor: grabbing;
}

.viewer-controls-drag:focus-visible {
  outline: 2px solid #667eea;
  outline-offset: 1px;
}

.structure-counter {
  font-weight: 500;
  color: #495057;
  min-width: 60px;
  text-align: center;
}

.viewer-container {
  position: relative;
}

/* Controls are always visible */

.structure-info {
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.details-section {
  margin-bottom: 0.75rem;
}

.details-section-title {
  font-weight: 600;
  color: #495057;
  margin-bottom: 0.5rem;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  background: #ffffff;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
}

.detail-item.clickable {
  cursor: pointer;
}

.score-bar {
  height: 6px;
  border-radius: 3px;
  margin-bottom: 0.25rem;
}

.detail-label {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.detail-value {
  font-size: 1rem;
  color: #343a40;
  font-weight: 600;
  word-break: break-all;
}

.file-item .file-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.truncate-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-item:hover {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  border-color: #e2e6ea;
}

/* Removed full-width spanning for file item to match other cards */

.file-value {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.file-value :deep(.p-button) {
  flex-shrink: 0;
  aspect-ratio: 1;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  /* Assume ~8px per char average for this font size; 128 chars ≈ 1024px */
  max-width: 1024px;
}


.no-selection {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 3rem;
}

.no-selection-content {
  text-align: center;
  color: #6c757d;
}

.no-selection-content h3 {
  margin: 1rem 0 0.5rem 0;
  color: #495057;
}

.no-selection-content p {
  margin: 0;
  font-size: 1rem;
}

/* PrimeVue overrides */
:deep(.p-datatable) {
  border: none;
}

:deep(.p-datatable .p-datatable-thead > tr > th) {
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
  font-weight: 600;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  border-bottom: 1px solid #f1f3f4;
}

:deep(.p-datatable .p-datatable-tbody > tr:hover > td) {
  background: #f8f9fa;
}

:deep(.p-datatable .p-datatable-tbody > tr) {
  cursor: pointer;
}

:deep(.p-datatable .p-datatable-tbody > tr > td) {
  user-select: none;
}

/* Pagination spacing improvements */
:deep(.p-datatable .p-paginator) {
  padding: 1rem 0;
  gap: 0.5rem;
}

:deep(.p-datatable .p-paginator .p-paginator-pages) {
  gap: 0.25rem;
}

:deep(.p-datatable .p-paginator .p-paginator-pages .p-paginator-page) {
  margin: 0 0.125rem;
}

:deep(.p-datatable .p-paginator .p-paginator-first,
       .p-datatable .p-paginator .p-paginator-prev,
       .p-datatable .p-paginator .p-paginator-next,
       .p-datatable .p-paginator .p-paginator-last) {
  margin: 0 0.25rem;
}

:deep(.p-datatable .p-paginator .p-paginator-current) {
  margin: 0 1rem;
}

:deep(.p-datatable .p-paginator .p-dropdown) {
  margin-left: 0.5rem;
}

.params-json-container {
  max-height: 70vh;
  overflow: auto;
}

.params-pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.9rem;
  margin: 0;
}

/* Select top controls styling */
.select-top-input {
  width: 60px;
  min-width: 60px;
}

.select-top-input :deep(.p-inputnumber-input) {
  text-align: center;
  width: 100%;
}

.select-top-controls {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
}

.viewer-controls :deep(.p-button.plddt-disabled .p-button-label) {
  text-decoration: line-through;
}

.viewer-controls :deep(.viewer-thumb-btn.p-button) {
  border-width: 1px;
  border-style: solid;
}

.viewer-controls :deep(.viewer-thumb-btn--good.p-button) {
  background: var(--rating-good-bg) !important;
  color: var(--rating-good-fg) !important;
  border-color: color-mix(in srgb, var(--rating-good-fg) 20%, transparent) !important;
}

.viewer-controls :deep(.viewer-thumb-btn--good.p-button:not(:disabled):hover) {
  background: color-mix(in srgb, var(--rating-good-bg) 82%, var(--rating-good-fg)) !important;
  border-color: color-mix(in srgb, var(--rating-good-fg) 35%, transparent) !important;
}

.viewer-controls :deep(.viewer-thumb-btn--good.p-button.viewer-thumb-btn--selected) {
  box-shadow: inset 0 0 0 2px var(--rating-good-fg);
}

.viewer-controls :deep(.viewer-thumb-btn--bad.p-button) {
  background: var(--rating-bad-bg) !important;
  color: var(--rating-bad-fg) !important;
  border-color: color-mix(in srgb, var(--rating-bad-fg) 22%, transparent) !important;
}

.viewer-controls :deep(.viewer-thumb-btn--bad.p-button:not(:disabled):hover) {
  background: color-mix(in srgb, var(--rating-bad-bg) 80%, var(--rating-bad-fg)) !important;
  border-color: color-mix(in srgb, var(--rating-bad-fg) 38%, transparent) !important;
}

.viewer-controls :deep(.viewer-thumb-btn--bad.p-button.viewer-thumb-btn--selected) {
  box-shadow: inset 0 0 0 2px var(--rating-bad-fg);
}

.viewer-controls :deep(.viewer-thumb-btn.p-button:disabled) {
  opacity: 0.45;
}

.good-cell {
  box-sizing: border-box;
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-height: 1.85rem;
  line-height: 1;
}

.good-cell--true,
.good-cell--false {
  width: 100%;
  padding: 0.35rem 0.5rem;
  border-radius: 0.35rem;
}

.good-cell--true {
  background-color: var(--rating-good-bg);
  color: var(--rating-good-fg);
}

.good-cell--false {
  background-color: var(--rating-bad-bg);
  color: var(--rating-bad-fg);
}

.good-cell--empty {
  width: 100%;
  justify-content: center;
  padding: 0.15rem 0;
}

.good-cell-symbol {
  font-size: 1.15rem;
  font-weight: 700;
}

.good-cell-dash {
  color: var(--p-text-muted-color, #6c757d);
  font-size: 0.95rem;
  font-weight: 400;
}
</style>
