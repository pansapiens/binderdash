<template>
  <div class="molstar-viewer-container">
    <div v-if="loading" class="molstar-loading">
      <div class="loading-content">
        <i class="pi pi-spinner pi-spin" style="font-size: 2rem; color: #667eea;"></i>
        <p>Loading structure...</p>
      </div>
    </div>
    <div v-else-if="error" class="molstar-error">
      <div class="error-content">
        <i class="pi pi-exclamation-triangle" style="font-size: 2rem; color: #dc3545; margin-bottom: 1rem; display: block;"></i>
        <div>Failed to load structure</div>
        <div style="font-size: 0.9rem; margin-top: 0.5rem;">
          Error: {{ error }}
        </div>
      </div>
    </div>
    <div 
      ref="molstarContainer" 
      class="molstar-viewer" 
      v-show="!loading && !error"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, readonly } from 'vue'

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// Extend Window interface for PDBeMolstarPlugin
declare global {
  interface Window {
    PDBeMolstarPlugin: any
  }
}

// Props
const props = defineProps<{
  pdbUrl: string
  /** TM-aligned reference (URL or blob URL), shown as a second structure */
  referenceUrl?: string
  /**
   * Format for `referenceUrl` when it has no path suffix (e.g. blob: from our API).
   * Aligned references are mmCIF; without this, Mol* may mis-parse blob URLs as PDB.
   */
  referenceDataFormat?: 'pdb' | 'mmcif'
  structureInfo?: any
  autoFocus?: boolean
  showControls?: boolean
  backgroundColor?: { r: number, g: number, b: number }
}>()

// State
const molstarContainer = ref<HTMLElement | null>(null)
const viewerInstance = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const isSpinning = ref(false)
const alphafoldViewEnabled = ref(true)

// Methods
const loadMolstarResources = () => {
  return new Promise<void>((resolve, reject) => {
    // Check if already loaded
    if (window.PDBeMolstarPlugin) {
      resolve()
      return
    }
    
    // Load CSS
    const cssLink = document.createElement('link')
    cssLink.rel = 'stylesheet'
    cssLink.type = 'text/css'
    cssLink.href = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.8.0/build/pdbe-molstar-light.css'
    document.head.appendChild(cssLink)
    
    // Load JS
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.8.0/build/pdbe-molstar-plugin.js'
    script.onload = () => {
      // Wait a bit for the plugin to fully initialize
      setTimeout(() => {
        resolve()
      }, 200)
    }
    script.onerror = () => {
      reject(new Error('Failed to load PDBe Molstar from CDN'))
    }
    document.head.appendChild(script)
  })
}

const getFormatFromUrl = (url: string): string => {
  let lower = url.toLowerCase()
  const q = lower.indexOf('?')
  if (q >= 0) lower = lower.slice(0, q)
  if (lower.endsWith('.gz')) lower = lower.slice(0, -3)
  if (lower.endsWith('.cif')) return 'mmcif'
  return 'pdb'
}

/** Mol* `parseTrajectory` format for the reference overlay (blob URLs have no `.cif` suffix). */
const getReferenceTrajectoryFormat = (): string => {
  if (props.referenceDataFormat === 'mmcif') return 'mmcif'
  if (props.referenceDataFormat === 'pdb') return 'pdb'
  const url = props.referenceUrl!.trim()
  if (url.toLowerCase().startsWith('blob:')) return 'mmcif'
  return getFormatFromUrl(url)
}

const hasReferenceUrl = (): boolean => {
  const r = props.referenceUrl
  return typeof r === 'string' && r.trim().length > 0
}

/**
 * Standalone Mol* `hide-controls=1` (see https://molstar.org/viewer-docs/query-parameters/) maps to
 * PDBe init `hideControls`, not to URL query params — we embed PDBeMolstarPlugin, not molstar.org/viewer.
 * Disabling the canvas wrench needs `hideCanvasControls` containing `'controlToggle'` or `'all'`;
 * we pass an empty array so the toggle stays available.
 *
 * `visual.update` merges with DefaultParams then always runs `Layout.Update(pluginLayoutStateFromInitParams)`.
 * Omitted keys revert to defaults — e.g. `reactive` defaults to false while `render()` uses `reactive: true`.
 * That flips `controlsDisplay` and breaks the canvas spanner after reference `update`; merge the same
 * interface fields into every `visual.update` as in `fullReload`.
 *
 * `hideControls` in each update still drives `showControls`; if `plugin.layout.state.showControls` is
 * briefly undefined, falling back to `props.showControls === false` re-hides panels — we cache layout.
 */
const lastLayoutShowControlsKnown = ref<boolean | null>(null)

function syncLayoutShowControlsFromPlugin() {
  try {
    const show = viewerInstance.value?.plugin?.layout?.state?.showControls
    if (typeof show === 'boolean') {
      lastLayoutShowControlsKnown.value = show
    }
  } catch {
    /* ignore */
  }
}

function seedLayoutShowControlsFromProps() {
  lastLayoutShowControlsKnown.value = props.showControls !== false
}

const getHideControlsForPluginUpdate = (): boolean => {
  syncLayoutShowControlsFromPlugin()
  try {
    const show = viewerInstance.value?.plugin?.layout?.state?.showControls
    if (typeof show === 'boolean') {
      return !show
    }
  } catch {
    /* ignore */
  }
  if (lastLayoutShowControlsKnown.value != null) {
    return !lastLayoutShowControlsKnown.value
  }
  return props.showControls === false
}

/** Must match `fullReload` / `render` options — `visual.update` shallow-merges with DefaultParams otherwise. */
const pdbeInterfaceParamsForVisualUpdate = () => ({
  reactive: true,
  landscape: false,
  expanded: false,
  hideCanvasControls: [] as string[],
  /** Top sequence strip (residue / chain context); `false` keeps `regionState.top` hidden. */
  sequencePanel: true,
  leftPanel: true,
  rightPanel: true,
  pdbeLink: false,
  loadingOverlay: false,
})

/**
 * Primary structure: polymer cartoon plus het / non-standard / coarse as spacefill so ligands are visible.
 * A plain `visualStyle: 'cartoon'` omits those components.
 */
const primaryStructureVisualOptions = () => ({
  alphafoldView: alphafoldViewEnabled.value,
  visualStyle: {
    polymer: 'cartoon',
    het: 'spacefill',
    nonStandard: 'spacefill',
    coarse: 'spacefill',
  },
  hideStructure: ['water'],
  bgColor: props.backgroundColor || { r: 255, g: 255, b: 255 },
  hideControls: getHideControlsForPluginUpdate(),
})

const sharedVisualOptions = () => primaryStructureVisualOptions()

/**
 * Reference overlay: polymer cartoon + het/nonStandard/coarse spacefill.
 * `alphafoldView` must be false here — the pLDDT theme applies to every component when true and
 * often leaves HET/coarse without a usable colour.
 */
const referenceOverlayVisualOptions = () => ({
  alphafoldView: false,
  visualStyle: {
    polymer: 'cartoon',
    het: 'spacefill',
    nonStandard: 'spacefill',
    coarse: 'spacefill',
  },
  hideStructure: ['water'],
  bgColor: props.backgroundColor || { r: 255, g: 255, b: 255 },
  hideControls: getHideControlsForPluginUpdate(),
})

const appendReferenceStructure = async () => {
  if (!viewerInstance.value || !hasReferenceUrl()) return
  const url = props.referenceUrl!.trim()
  const updateOptions = {
    customData: {
      url,
      format: getReferenceTrajectoryFormat(),
      binary: false
    },
    ...pdbeInterfaceParamsForVisualUpdate(),
    ...referenceOverlayVisualOptions(),
  }
  const success = await viewerInstance.value.visual.update(updateOptions, false)
  if (!success) {
    console.warn('PDBe Molstar: could not append reference structure')
    return
  }
  try {
    const vis = viewerInstance.value.visual
    if (typeof vis?.visibility === 'function') {
      await vis.visibility({ het: true, nonStandard: true, coarse: true })
    }
  } catch (e) {
    console.warn('PDBe Molstar: visibility tweak for reference het/coarse failed', e)
  }
}

const ensurePrimaryHetCoarseVisible = async () => {
  try {
    const vis = viewerInstance.value?.visual
    if (typeof vis?.visibility === 'function') {
      await vis.visibility({ het: true, nonStandard: true, coarse: true })
    }
  } catch (e) {
    console.warn('PDBe Molstar: visibility for primary het/coarse failed', e)
  }
}

const loadStructure = async () => {
  if (!molstarContainer.value) {
    return
  }

  if (!props.pdbUrl) {
    viewerInstance.value = null
    if (molstarContainer.value) {
      molstarContainer.value.innerHTML = ''
    }
    loading.value = false
    error.value = null
    return
  }

  try {
    loading.value = true
    error.value = null

    await loadMolstarResources()

    if (!window.PDBeMolstarPlugin) {
      throw new Error('PDBeMolstarPlugin not available after loading resources')
    }

    const ref = hasReferenceUrl()

    if (viewerInstance.value && !ref) {
      const updateOptions = {
        customData: {
          url: props.pdbUrl,
          format: getFormatFromUrl(props.pdbUrl),
          binary: false
        },
        ...pdbeInterfaceParamsForVisualUpdate(),
        ...sharedVisualOptions(),
      }
      const success = await viewerInstance.value.visual.update(updateOptions, true)
      if (success) {
        await ensurePrimaryHetCoarseVisible()
        if (props.autoFocus !== false) {
          await focusOnStructure()
        }
        loading.value = false
        return
      }
      await fullReload()
      return
    }

    await fullReload()
    if (ref) {
      await appendReferenceStructure()
      if (props.autoFocus !== false) {
        await focusOnStructure()
      }
    }
  } catch (err) {
    console.error('Error loading Molstar viewer:', err)
    error.value = (err as Error).message || 'Failed to load structure'
    loading.value = false
  }
}

const fullReload = async () => {
  lastLayoutShowControlsKnown.value = null
  // Clear previous viewer
  if (viewerInstance.value) {
    try {
      viewerInstance.value = null
    } catch (e) {
      console.warn('Error cleaning up previous viewer:', e)
    }
  }
  
  // Clear container
  if (molstarContainer.value) {
    molstarContainer.value.innerHTML = ''
  }
  
  // Create plugin instance
  const viewer = new window.PDBeMolstarPlugin()
  
  const appearance = primaryStructureVisualOptions()
  // Set options following the documentation pattern
  const options = {
    customData: {
      url: props.pdbUrl,
      format: getFormatFromUrl(props.pdbUrl),
      binary: false
    },
    // APPEARANCE
    ...appearance,
    
    // BEHAVIOR
    selectInteraction: true,
    
    // INTERFACE (hideCanvasControls must not include 'controlToggle' or spanner does nothing)
    hideControls: props.showControls === false,
    hideCanvasControls: [] as string[],
    sequencePanel: true,
    leftPanel: true,
    rightPanel: true,
    pdbeLink: false,
    loadingOverlay: false,
    expanded: false,
    landscape: false,
    reactive: true
  }
  
  
  // Call render method to display the 3D view
  await viewer.render(molstarContainer.value, options)

  viewerInstance.value = viewer

  await nextTick()
  syncLayoutShowControlsFromPlugin()
  if (lastLayoutShowControlsKnown.value == null) {
    seedLayoutShowControlsFromProps()
  }

  await ensurePrimaryHetCoarseVisible()

  if (props.autoFocus !== false) {
    await focusOnStructure()
  }

  loading.value = false
}

// Watchers
watch(
  () => [props.pdbUrl, props.referenceUrl ?? '', props.referenceDataFormat ?? ''] as const,
  () => {
    nextTick(() => {
      loadStructure()
    })
  },
  { immediate: false }
)

// Lifecycle
onMounted(() => {
  if (props.pdbUrl) {
    loadStructure()
  }
})

onUnmounted(() => {
  if (viewerInstance.value) {
    try {
      // Clean up the viewer instance
      viewerInstance.value = null
    } catch (e) {
      console.warn('Error disposing Molstar viewer:', e)
    }
  }
})

// Helper methods for controlling the viewer
const focusOnStructure = async () => {
  if (viewerInstance.value) {
    try {
      await viewerInstance.value.visual.reset({ camera: true })
    } catch (e) {
      console.warn('Error focusing on structure:', e)
    }
  }
}

/** PDBe `toggleSpin` uses `speed: 1`; quarter speed reads more comfortably. */
const MOLSTAR_SPIN_SPEED = 0.25

const applyReducedSpinSpeed = async () => {
  await delay(40)
  const c3d = viewerInstance.value?.plugin?.canvas3d
  if (!c3d || typeof c3d.setProps !== 'function') return
  const tb = c3d.props?.trackball
  if (!tb || tb.animate?.name !== 'spin') return
  try {
    const prevParams = (tb.animate.params && typeof tb.animate.params === 'object')
      ? tb.animate.params
      : {}
    await c3d.setProps({
      trackball: {
        ...tb,
        animate: { name: 'spin', params: { ...prevParams, speed: MOLSTAR_SPIN_SPEED } },
      },
    })
  } catch (e) {
    console.warn('PDBe Molstar: could not set spin speed', e)
  }
}

const toggleSpin = async (forceState?: boolean) => {
  if (viewerInstance.value) {
    try {
      const newState = forceState !== undefined ? forceState : !isSpinning.value
      await viewerInstance.value.visual.toggleSpin(newState)
      isSpinning.value = newState
      if (newState) {
        await applyReducedSpinSpeed()
      }
    } catch (e) {
      console.warn('Error toggling spin:', e)
    }
  }
}

const setBackgroundColor = async (color: { r: number, g: number, b: number }) => {
  if (viewerInstance.value) {
    try {
      await viewerInstance.value.canvas.setBgColor(color)
    } catch (e) {
      console.warn('Error setting background color:', e)
    }
  }
}

const toggleControls = (isVisible?: boolean) => {
  if (viewerInstance.value) {
    try {
      viewerInstance.value.canvas.toggleControls(isVisible)
    } catch (e) {
      console.warn('Error toggling controls:', e)
    }
  }
}


const highlightResidues = async (data: any[]) => {
  if (viewerInstance.value) {
    try {
      await viewerInstance.value.visual.highlight({ data })
    } catch (e) {
      console.warn('Error highlighting residues:', e)
    }
  }
}

const clearHighlight = async () => {
  if (viewerInstance.value) {
    try {
      await viewerInstance.value.visual.clearHighlight()
    } catch (e) {
      console.warn('Error clearing highlight:', e)
    }
  }
}

const toggleAlphaFoldView = async (forceState?: boolean) => {
  if (viewerInstance.value && props.pdbUrl) {
    try {
      const newState = forceState !== undefined ? forceState : !alphafoldViewEnabled.value
      alphafoldViewEnabled.value = newState
      const updateOptions = {
        customData: {
          url: props.pdbUrl,
          format: getFormatFromUrl(props.pdbUrl),
          binary: false
        },
        ...pdbeInterfaceParamsForVisualUpdate(),
        ...primaryStructureVisualOptions(),
      }
      
      const success = await viewerInstance.value.visual.update(updateOptions, true)
      
      if (success) {
        await ensurePrimaryHetCoarseVisible()
        if (hasReferenceUrl()) {
          await appendReferenceStructure()
        }
        if (props.autoFocus !== false) {
          await focusOnStructure()
        }
      } else {
        await fullReload()
        if (hasReferenceUrl()) {
          await appendReferenceStructure()
        }
      }
    } catch (e) {
      console.warn('Error toggling AlphaFold view:', e)
    }
  }
}

// Expose methods and state
defineExpose({
  loadStructure,
  focusOnStructure,
  toggleSpin,
  setBackgroundColor,
  toggleControls,
  highlightResidues,
  clearHighlight,
  toggleAlphaFoldView,
  isSpinning: readonly(isSpinning),
  alphafoldViewEnabled: readonly(alphafoldViewEnabled),
  dispose: () => {
    if (viewerInstance.value) {
      try {
        viewerInstance.value = null
      } catch (e) {
        console.warn('Error disposing Molstar viewer:', e)
      }
    }
  }
})
</script>

<style scoped>
.molstar-viewer-container {
  width: 100%;
  height: 600px;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.molstar-viewer {
  width: 100%;
  height: 100%;
}

.molstar-loading {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
}

.loading-content {
  text-align: center;
  color: #6c757d;
}

.loading-content p {
  margin: 1rem 0 0 0;
  font-size: 1rem;
}

.molstar-error {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  color: #dc3545;
  font-size: 1.1rem;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
}

.error-content {
  text-align: center;
}
</style>