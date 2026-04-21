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
    <canvas
      v-show="!loading && !error"
      ref="membraneCanvasEl"
      class="molstar-membrane-overlay"
      aria-hidden="true"
    />
    <canvas
      v-show="!loading && !error"
      ref="tagMarkerCanvasEl"
      class="molstar-tag-marker-overlay"
      aria-hidden="true"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onUnmounted, watch, nextTick, readonly, withDefaults } from 'vue'
import { PDBeMolstarPlugin } from 'pdbe-molstar/lib/viewer'
import 'pdbe-molstar/lib/styles/pdbe-molstar-light.scss'
import type { MembraneData } from '../membraneOverlay'
import { paintMembraneScreenOverlay } from '../membraneScreenOverlay'
import { extractTerminalCaFromMolstarPlugin } from '../molstarTerminalCa'
import { paintTagMarkerScreenOverlay } from '../tagMarkerScreenOverlay'

if (typeof window !== 'undefined') {
  window.PDBeMolstarPlugin = PDBeMolstarPlugin
}

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

// Extend Window interface for PDBeMolstarPlugin
declare global {
  interface Window {
    PDBeMolstarPlugin: any
  }
}

// Props
const props = withDefaults(
  defineProps<{
    pdbUrl: string
    /** TM-aligned reference (URL or blob URL), shown as a second structure */
    referenceUrl?: string
    /**
     * Format for `referenceUrl` when it has no path suffix (e.g. blob: from our API).
     * Aligned references are mmCIF; without this, Mol* may mis-parse blob URLs as PDB.
     */
    referenceDataFormat?: 'pdb' | 'mmcif'
    /** PDBTM-derived membrane planes in design coordinates (from reference API headers). */
    membraneData?: MembraneData | null
    structureInfo?: any
    autoFocus?: boolean
    showControls?: boolean
    backgroundColor?: { r: number, g: number, b: number }
    /** Visual marker at binder N- or C-terminus (PDB primary structure only). */
    tagOverlay?: 'none' | 'N' | 'C'
    tagBinderChain?: string
  }>(),
  {
    tagOverlay: 'none',
    tagBinderChain: 'B',
  }
)

// State
const molstarContainer = ref<HTMLElement | null>(null)
const membraneCanvasEl = ref<HTMLCanvasElement | null>(null)
const tagMarkerCanvasEl = ref<HTMLCanvasElement | null>(null)
const viewerInstance = ref<any>(null)
let overlayDidDrawSub: { unsubscribe: () => void } | null = null
let overlayResizeObserver: ResizeObserver | null = null
const tagMarkerWorldPos = ref<{ x: number; y: number; z: number } | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const isSpinning = ref(false)
const alphafoldViewEnabled = ref(true)
/** Structure 2 = appended reference; toggled via PDBe `visual.structureVisibility`. */
const referenceStructureVisible = ref(true)
/** False after unmount; avoids parsing against a torn-down plugin state tree. */
const viewerAlive = ref(true)
onBeforeUnmount(() => {
  viewerAlive.value = false
})

let loadStructureTail: Promise<void> = Promise.resolve()
let lastCompletedStructureLoadKey: string | null = null

// Methods
const loadMolstarResources = () => Promise.resolve()

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
 * Set `awaitLoad: false` when called from inside the load flow itself;
 * awaiting `loadStructureTail` from `runLoadStructure` would deadlock.
 */
const applyBinderTagOverlay = async (options: { awaitLoad?: boolean } = {}) => {
  if (!viewerAlive.value) return
  if (props.tagOverlay === 'none' || !props.pdbUrl) {
    tagMarkerWorldPos.value = null
    paintTagMarkerIfActive()
    return
  }
  if (options.awaitLoad !== false) {
    // Wait for any in-flight structure load so Mol*'s state tree is populated
    // before we read atoms — this is what lets us avoid a second CIF fetch.
    try {
      await loadStructureTail
    } catch {
      /* fall through — we'll try with whatever state is available */
    }
  }
  if (!viewerAlive.value || !viewerInstance.value) return
  const chain = (props.tagBinderChain && props.tagBinderChain.trim()) || 'B'
  try {
    const plugin = (viewerInstance.value as any)?.plugin
    const coords = extractTerminalCaFromMolstarPlugin(plugin, chain)
    if (!coords) {
      console.warn(
        'MolstarViewer: could not find terminal CA atoms for binder chain',
        chain
      )
      tagMarkerWorldPos.value = null
      paintTagMarkerIfActive()
      return
    }
    const pt = props.tagOverlay === 'N' ? coords.n : coords.c
    tagMarkerWorldPos.value = { x: pt.x, y: pt.y, z: pt.z }
    paintTagMarkerIfActive()
  } catch (e) {
    console.warn('MolstarViewer: His-tag overlay failed', e)
    tagMarkerWorldPos.value = null
    paintTagMarkerIfActive()
  }
}

const REFERENCE_STRUCTURE_INDEX = 2

const syncReferenceVisibilityAfterAppend = async () => {
  if (!viewerInstance.value || !hasReferenceUrl()) return
  try {
    await viewerInstance.value.visual.structureVisibility(
      REFERENCE_STRUCTURE_INDEX,
      referenceStructureVisible.value
    )
  } catch (e) {
    console.warn('PDBe Molstar: reference structure visibility sync failed', e)
  }
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

const unsubscribeOverlayPaint = () => {
  overlayDidDrawSub?.unsubscribe()
  overlayDidDrawSub = null
}

const clearMembraneCanvasPixels = () => {
  const overlay = membraneCanvasEl.value
  if (!overlay) return
  const ctx = overlay.getContext('2d')
  if (ctx && overlay.width > 0 && overlay.height > 0) {
    ctx.clearRect(0, 0, overlay.width, overlay.height)
  }
}

const clearTagMarkerCanvasPixels = () => {
  const overlay = tagMarkerCanvasEl.value
  if (!overlay) return
  const ctx = overlay.getContext('2d')
  if (ctx && overlay.width > 0 && overlay.height > 0) {
    ctx.clearRect(0, 0, overlay.width, overlay.height)
  }
}

const clearMembraneOverlayOnly = () => {
  unsubscribeOverlayPaint()
  clearMembraneCanvasPixels()
  clearTagMarkerCanvasPixels()
  tagMarkerWorldPos.value = null
}

const syncOverlayCanvasLayout = (overlay: HTMLCanvasElement | null) => {
  const container = molstarContainer.value
  if (!container || !overlay) return
  const gl = container.querySelector('canvas') as HTMLCanvasElement | null
  if (!gl || gl.width < 2 || gl.height < 2) return
  overlay.width = gl.width
  overlay.height = gl.height
  const cr = container.getBoundingClientRect()
  const gr = gl.getBoundingClientRect()
  overlay.style.left = `${gr.left - cr.left}px`
  overlay.style.top = `${gr.top - cr.top}px`
  overlay.style.width = `${gr.width}px`
  overlay.style.height = `${gr.height}px`
}

const syncMembraneCanvasLayout = () => {
  syncOverlayCanvasLayout(membraneCanvasEl.value)
}

const paintMembraneIfActive = () => {
  const overlay = membraneCanvasEl.value
  const c3d = viewerInstance.value?.plugin?.canvas3d
  const md = props.membraneData
  if (!overlay || !c3d?.camera?.project) {
    clearMembraneCanvasPixels()
    return
  }
  if (!md || !hasReferenceUrl() || !referenceStructureVisible.value) {
    clearMembraneCanvasPixels()
    return
  }
  syncMembraneCanvasLayout()
  const ctx = overlay.getContext('2d')
  if (!ctx || overlay.width < 2 || overlay.height < 2) return
  paintMembraneScreenOverlay(
    ctx,
    (o, p) => c3d.camera.project(o, p),
    overlay.width,
    overlay.height,
    md,
  )
}

const paintTagMarkerIfActive = () => {
  const overlay = tagMarkerCanvasEl.value
  const c3d = viewerInstance.value?.plugin?.canvas3d
  const pos = tagMarkerWorldPos.value
  if (!overlay || !c3d?.camera?.project) {
    clearTagMarkerCanvasPixels()
    return
  }
  if (props.tagOverlay === 'none' || !pos) {
    clearTagMarkerCanvasPixels()
    return
  }
  syncOverlayCanvasLayout(overlay)
  const ctx = overlay.getContext('2d')
  if (!ctx || overlay.width < 2 || overlay.height < 2) return
  paintTagMarkerScreenOverlay(
    ctx,
    props.tagOverlay,
    (o, p) => c3d.camera.project(o, p),
    overlay.width,
    overlay.height,
    pos.x,
    pos.y,
    pos.z,
  )
}

const paintAllOverlays = () => {
  paintMembraneIfActive()
  paintTagMarkerIfActive()
}

const setupOverlayResizeObserver = () => {
  overlayResizeObserver?.disconnect()
  const el = molstarContainer.value
  if (!el || typeof ResizeObserver === 'undefined') return
  overlayResizeObserver = new ResizeObserver(() => {
    paintAllOverlays()
  })
  overlayResizeObserver.observe(el)
}

const subscribeOverlayPaint = async () => {
  unsubscribeOverlayPaint()
  await nextTick()
  const c3d = viewerInstance.value?.plugin?.canvas3d
  if (!c3d?.didDraw?.subscribe) return
  try {
    overlayDidDrawSub = c3d.didDraw.subscribe(() => {
      paintAllOverlays()
    })
  } catch {
    /* ignore */
  }
  setupOverlayResizeObserver()
  requestAnimationFrame(() => {
    paintAllOverlays()
  })
}

const syncMembraneAfterReference = async () => {
  clearMembraneCanvasPixels()
  await subscribeOverlayPaint()
}

const appendReferenceStructure = async (): Promise<boolean> => {
  if (!viewerInstance.value || !hasReferenceUrl()) return false
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
    return false
  }
  try {
    const vis = viewerInstance.value.visual
    if (typeof vis?.visibility === 'function') {
      await vis.visibility({ het: true, nonStandard: true, coarse: true })
    }
  } catch (e) {
    console.warn('PDBe Molstar: visibility tweak for reference het/coarse failed', e)
  }
  await syncReferenceVisibilityAfterAppend()
  return true
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

const runLoadStructure = async (): Promise<void> => {
  if (!viewerAlive.value) return
  if (!molstarContainer.value) {
    return
  }

  if (!props.pdbUrl) {
    clearMembraneOverlayOnly()
    viewerInstance.value = null
    if (molstarContainer.value) {
      molstarContainer.value.innerHTML = ''
    }
    loading.value = false
    error.value = null
    lastCompletedStructureLoadKey = null
    return
  }

  const requestedLoadKey = JSON.stringify({
    pdbUrl: props.pdbUrl,
    referenceUrl: props.referenceUrl ?? '',
    referenceDataFormat: props.referenceDataFormat ?? ''
  })
  if (viewerInstance.value && requestedLoadKey === lastCompletedStructureLoadKey) {
    return
  }

  try {
    loading.value = true
    error.value = null

    await loadMolstarResources()
    if (!viewerAlive.value) return

    if (!window.PDBeMolstarPlugin) {
      throw new Error('PDBeMolstarPlugin not available after loading resources')
    }

    const ref = hasReferenceUrl()

    if (viewerInstance.value && !ref) {
      clearMembraneOverlayOnly()
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
      if (!viewerAlive.value) return
      if (success) {
        await ensurePrimaryHetCoarseVisible()
        if (props.autoFocus !== false) {
          await focusOnStructure()
        }
        await applyBinderTagOverlay({ awaitLoad: false })
        await subscribeOverlayPaint()
        lastCompletedStructureLoadKey = requestedLoadKey
        return
      }
      await fullReload()
      if (!viewerAlive.value) return
      await applyBinderTagOverlay({ awaitLoad: false })
      lastCompletedStructureLoadKey = requestedLoadKey
      return
    }

    await fullReload()
    if (!viewerAlive.value) return
    if (ref) {
      const refOk = await appendReferenceStructure()
      if (!viewerAlive.value) return
      if (refOk) {
        await syncMembraneAfterReference()
      } else {
        clearMembraneOverlayOnly()
        await subscribeOverlayPaint()
      }
      if (props.autoFocus !== false) {
        await focusOnStructure()
      }
    }
    await applyBinderTagOverlay({ awaitLoad: false })
    lastCompletedStructureLoadKey = requestedLoadKey
  } catch (err) {
    if (!viewerAlive.value) return
    console.error('Error loading Molstar viewer:', err)
    error.value = (err as Error).message || 'Failed to load structure'
    lastCompletedStructureLoadKey = null
  } finally {
    loading.value = false
  }
}

/** Serialised so rapid table / prev-next switches do not overlap Mol* loads (avoids Invalid data cell). */
const loadStructure = (): Promise<void> => {
  const next = loadStructureTail.then(() => runLoadStructure())
  loadStructureTail = next.catch(() => undefined)
  return next
}

const fullReload = async () => {
  if (!viewerAlive.value) return
  lastLayoutShowControlsKnown.value = null
  clearMembraneOverlayOnly()
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

  if (!viewerAlive.value || !molstarContainer.value) return

  // Create plugin instance
  const viewer = new PDBeMolstarPlugin()
  
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
  if (!viewerAlive.value) return

  viewerInstance.value = viewer

  await nextTick()
  if (!viewerAlive.value) return
  syncLayoutShowControlsFromPlugin()
  if (lastLayoutShowControlsKnown.value == null) {
    seedLayoutShowControlsFromProps()
  }

  await ensurePrimaryHetCoarseVisible()

  if (props.autoFocus !== false) {
    await focusOnStructure()
  }

  await subscribeOverlayPaint()
}

// Watchers
watch(
  () =>
    [props.pdbUrl, props.referenceUrl ?? '', props.referenceDataFormat ?? ''] as const,
  () => {
    nextTick(() => {
      loadStructure()
    })
  },
  { immediate: false }
)

watch(
  () => props.membraneData,
  async () => {
    await nextTick()
    if (!viewerInstance.value) return
    if (!hasReferenceUrl()) {
      clearMembraneCanvasPixels()
      return
    }
    await syncMembraneAfterReference()
  }
)

watch(
  () => [props.tagOverlay, props.tagBinderChain] as const,
  async () => {
    await nextTick()
    if (!loading.value) await applyBinderTagOverlay()
  }
)

// Lifecycle
onMounted(() => {
  if (props.pdbUrl) {
    loadStructure()
  }
})

onUnmounted(() => {
  overlayResizeObserver?.disconnect()
  overlayResizeObserver = null
  clearMembraneOverlayOnly()
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

const toggleReferenceStructureVisibility = async (forceState?: boolean) => {
  if (!viewerInstance.value || !hasReferenceUrl()) return
  const next =
    forceState !== undefined ? forceState : !referenceStructureVisible.value
  referenceStructureVisible.value = next
  try {
    await viewerInstance.value.visual.structureVisibility(REFERENCE_STRUCTURE_INDEX, next)
  } catch (e) {
    console.warn('PDBe Molstar: toggle reference structure visibility failed', e)
  }
  paintAllOverlays()
}

/** Call when the user clears the overlay so the next load defaults to reference visible. */
const resetReferenceVisibilityPreference = () => {
  referenceStructureVisible.value = true
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
          const refOk = await appendReferenceStructure()
          if (refOk) await syncMembraneAfterReference()
          else {
            clearMembraneOverlayOnly()
            await subscribeOverlayPaint()
          }
        } else {
          await subscribeOverlayPaint()
        }
        if (props.autoFocus !== false) {
          await focusOnStructure()
        }
        await applyBinderTagOverlay()
      } else {
        await loadStructure()
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
  toggleReferenceStructureVisibility,
  resetReferenceVisibilityPreference,
  isSpinning: readonly(isSpinning),
  alphafoldViewEnabled: readonly(alphafoldViewEnabled),
  referenceStructureVisible: readonly(referenceStructureVisible),
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

.molstar-membrane-overlay {
  position: absolute;
  pointer-events: none;
  z-index: 3;
}

.molstar-tag-marker-overlay {
  position: absolute;
  pointer-events: none;
  z-index: 4;
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