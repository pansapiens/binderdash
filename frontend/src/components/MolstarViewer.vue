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
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

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
}>()

// State
const molstarContainer = ref<HTMLElement | null>(null)
const viewerInstance = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)

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
    cssLink.href = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.7.0/build/pdbe-molstar-light.css'
    document.head.appendChild(cssLink)
    
    // Load JS
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.7.0/build/pdbe-molstar-plugin.js'
    script.onload = () => {
      // Wait a bit for the plugin to fully initialize
      setTimeout(() => {
        console.log('PDBe Molstar plugin loaded successfully')
        resolve()
      }, 200)
    }
    script.onerror = () => {
      reject(new Error('Failed to load PDBe Molstar from CDN'))
    }
    document.head.appendChild(script)
  })
}

const loadStructure = async () => {
  if (!props.pdbUrl || !molstarContainer.value) {
    return
  }

  try {
    loading.value = true
    error.value = null
    
    console.log('Loading structure from:', props.pdbUrl)
    
    // Clear previous viewer
    if (viewerInstance.value) {
      try {
        // Clean up previous instance if it exists
        viewerInstance.value = null
      } catch (e) {
        console.warn('Error cleaning up previous viewer:', e)
      }
    }
    
    // Clear container
    molstarContainer.value.innerHTML = ''
    
    // Load Molstar resources
    await loadMolstarResources()
    
    // Check if plugin is available
    if (!window.PDBeMolstarPlugin) {
      throw new Error('PDBeMolstarPlugin not available after loading resources')
    }
    
    // Create plugin instance
    const viewer = new window.PDBeMolstarPlugin()
    console.log('Created PDBe Molstar plugin instance')
    
    // Set options following the documentation pattern
    const options = {
      customData: {
        url: props.pdbUrl,
        format: 'pdb',
        binary: false
      },
      // APPEARANCE
      visualStyle: 'cartoon',
      hideStructure: ['water'],
      bgColor: { r: 255, g: 255, b: 255 },
      
      // BEHAVIOR
      selectInteraction: true,
      
      // INTERFACE
      hideControls: false,
      sequencePanel: false,
      pdbeLink: false,
      loadingOverlay: false,
      expanded: false,
      landscape: false,
      reactive: true
    }
    
    console.log('Rendering with options:', options)
    
    // Call render method to display the 3D view
    await viewer.render(molstarContainer.value, options)
    
    console.log('PDBe Molstar rendered successfully')
    
    // Store reference
    viewerInstance.value = viewer
    loading.value = false

  } catch (err) {
    console.error('Error loading Molstar viewer:', err)
    error.value = (err as Error).message || 'Failed to load structure'
    loading.value = false
  }
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

// Expose methods
defineExpose({
  loadStructure,
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
  height: 400px;
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