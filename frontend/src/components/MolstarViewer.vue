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

// Extend Window interface for PDBeMolstarPlugin
declare global {
  interface Window {
    PDBeMolstarPlugin: any
  }
}

// Props
const props = defineProps<{
  pdbUrl: string
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
  const lower = url.toLowerCase()
  if (lower.endsWith('.cif')) return 'mmcif'
  return 'pdb'
}

const loadStructure = async () => {
  if (!props.pdbUrl || !molstarContainer.value) {
    return
  }

  try {
    loading.value = true
    error.value = null
    
    
    // Load Molstar resources if not already loaded
    await loadMolstarResources()
    
    // Check if plugin is available
    if (!window.PDBeMolstarPlugin) {
      throw new Error('PDBeMolstarPlugin not available after loading resources')
    }
    
    // If viewer instance exists, use update method for better performance
    if (viewerInstance.value) {
      
      // Store current control panel state before update
      let controlsVisible = true
      try {
        // Try to get current control panel state (this might not be available in all versions)
        controlsVisible = viewerInstance.value.canvas?.controlsVisible ?? true
      } catch (e) {
        console.warn('Could not determine control panel state:', e)
      }
      
      const updateOptions = {
        customData: {
          url: props.pdbUrl,
          format: getFormatFromUrl(props.pdbUrl),
          binary: false
        },
        // Preserve essential visual settings to maintain consistent theme
        alphafoldView: alphafoldViewEnabled.value,
        visualStyle: 'cartoon',
        hideStructure: ['water'],
        bgColor: props.backgroundColor || { r: 255, g: 255, b: 255 },
        // Explicitly preserve control panel settings
        hideControls: controlsVisible,
      }
      
      // Use the update method to load new structure
      const success = await viewerInstance.value.visual.update(updateOptions, true)
      
      if (success) {
        
        // Restore control panel state after update
        try {
          if (controlsVisible) {
            viewerInstance.value.canvas.toggleControls(true)
          }
        } catch (e) {
          console.warn('Could not restore control panel state:', e)
        }
 
        // Auto-focus on the new structure if enabled
        if (props.autoFocus !== false) {
          await focusOnStructure()
        }
        
        loading.value = false
        return
      } else {
        // Fall back to full reload if update fails
        await fullReload()
      }
    } else {
      // First time loading - create new instance
      await fullReload()
    }

  } catch (err) {
    console.error('Error loading Molstar viewer:', err)
    error.value = (err as Error).message || 'Failed to load structure'
    loading.value = false
  }
}

const fullReload = async () => {
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
  
  // Set options following the documentation pattern
  const options = {
    customData: {
      url: props.pdbUrl,
      format: getFormatFromUrl(props.pdbUrl),
      binary: false
    },
    // APPEARANCE
    alphafoldView: alphafoldViewEnabled.value,
    visualStyle: 'cartoon',
    hideStructure: ['water'],
    bgColor: props.backgroundColor || { r: 255, g: 255, b: 255 },
    
    // BEHAVIOR
    selectInteraction: true,
    
    // INTERFACE
    hideControls: props.showControls === false,
    sequencePanel: false,
    pdbeLink: false,
    loadingOverlay: false,
    expanded: false,
    landscape: false,
    reactive: true
  }
  
  
  // Call render method to display the 3D view
  await viewer.render(molstarContainer.value, options)
  
  
  // Store reference
  viewerInstance.value = viewer
  
  // Auto-focus on the new structure if enabled
  if (props.autoFocus !== false) {
    await focusOnStructure()
  }
  
  loading.value = false
}

// Watchers
watch(() => props.pdbUrl, () => {
  if (props.pdbUrl) {
    nextTick(() => {
      loadStructure()
    })
  }
}, { immediate: false })

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

const toggleSpin = async (forceState?: boolean) => {
  if (viewerInstance.value) {
    try {
      // If forceState is provided, use it; otherwise toggle current state
      const newState = forceState !== undefined ? forceState : !isSpinning.value
      await viewerInstance.value.visual.toggleSpin(newState)
      isSpinning.value = newState
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
      
      // Store current control panel state before update
      let controlsVisible = true
      try {
        controlsVisible = viewerInstance.value.canvas?.controlsVisible ?? true
      } catch (e) {
        console.warn('Could not determine control panel state:', e)
      }
      
      const updateOptions = {
        customData: {
          url: props.pdbUrl,
          format: 'pdb',
          binary: false
        },
        alphafoldView: newState,
        visualStyle: 'cartoon',
        hideStructure: ['water'],
        bgColor: props.backgroundColor || { r: 255, g: 255, b: 255 },
        hideControls: controlsVisible,
      }
      
      const success = await viewerInstance.value.visual.update(updateOptions, true)
      
      if (success) {
        // Restore control panel state after update
        try {
          if (controlsVisible) {
            viewerInstance.value.canvas.toggleControls(true)
          }
        } catch (e) {
          console.warn('Could not restore control panel state:', e)
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