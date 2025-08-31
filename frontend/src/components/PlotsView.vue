<template>
  <div class="plots-view">
    <div class="plots-header">
      <h2>Plots & Analytics</h2>
      <div class="plots-controls">
        <Button 
          label="Refresh Data" 
          icon="pi pi-refresh" 
          @click="loadPlotData"
          :loading="loading"
        />
      </div>
    </div>

    <div class="plots-content">
      <div v-if="runs.length === 0" class="no-data">
        <div class="no-data-content">
          <i class="pi pi-chart-line" style="font-size: 3rem; color: #6c757d;"></i>
          <h3>No Data Available</h3>
          <p>Scan some folders first to generate plots and analytics</p>
        </div>
      </div>

      <div v-else class="plots-grid">
        <div class="plot-card">
          <h3>Run Distribution by Type</h3>
          <div class="plot-container">
            <div ref="runTypeChart" class="chart-placeholder">
              <div class="placeholder-content">
                <i class="pi pi-pie-chart" style="font-size: 2rem; color: #6c757d;"></i>
                <div>Run Type Distribution</div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                  {{ getRunTypeStats() }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="plot-card">
          <h3>PDB Files per Run</h3>
          <div class="plot-container">
            <div ref="pdbCountChart" class="chart-placeholder">
              <div class="placeholder-content">
                <i class="pi pi-bar-chart" style="font-size: 2rem; color: #6c757d;"></i>
                <div>PDB Files Distribution</div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                  Total: {{ totalPdbFiles }} files
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="plot-card">
          <h3>Run Timeline</h3>
          <div class="plot-container">
            <div ref="timelineChart" class="chart-placeholder">
              <div class="placeholder-content">
                <i class="pi pi-calendar" style="font-size: 2rem; color: #6c757d;"></i>
                <div>Run Timeline</div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                  {{ runs.length }} runs loaded
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="plot-card">
          <h3>Performance Metrics</h3>
          <div class="plot-container">
            <div ref="metricsChart" class="chart-placeholder">
              <div class="placeholder-content">
                <i class="pi pi-chart-bar" style="font-size: 2rem; color: #6c757d;"></i>
                <div>Performance Metrics</div>
                <div style="font-size: 0.9rem; margin-top: 0.5rem;">
                  Select runs to view metrics
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="analytics-summary">
        <h3>Analytics Summary</h3>
        <div class="summary-grid">
          <div class="summary-card">
            <div class="summary-icon">
              <i class="pi pi-folder"></i>
            </div>
            <div class="summary-content">
              <div class="summary-value">{{ runs.length }}</div>
              <div class="summary-label">Total Runs</div>
            </div>
          </div>
          
          <div class="summary-card">
            <div class="summary-icon">
              <i class="pi pi-cube"></i>
            </div>
            <div class="summary-content">
              <div class="summary-value">{{ totalPdbFiles }}</div>
              <div class="summary-label">PDB Files</div>
            </div>
          </div>
          
          <div class="summary-card">
            <div class="summary-icon">
              <i class="pi pi-tag"></i>
            </div>
            <div class="summary-content">
              <div class="summary-value">{{ uniqueRunTypes.length }}</div>
              <div class="summary-label">Run Types</div>
            </div>
          </div>
          
          <div class="summary-card">
            <div class="summary-icon">
              <i class="pi pi-calendar"></i>
            </div>
            <div class="summary-content">
              <div class="summary-value">{{ averagePdbPerRun }}</div>
              <div class="summary-label">Avg PDB/Run</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import Button from 'primevue/button'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

// State
const runs = ref([])
const loading = ref(false)

// Computed
const totalPdbFiles = computed(() => {
  return runs.value.reduce((total, run) => total + run.pdb_files.length, 0)
})

const uniqueRunTypes = computed(() => {
  return [...new Set(runs.value.map(run => run.run_type))]
})

const averagePdbPerRun = computed(() => {
  if (runs.value.length === 0) return 0
  return Math.round((totalPdbFiles.value / runs.value.length) * 10) / 10
})

// Methods
const loadPlotData = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/runs')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    runs.value = data.runs
  } catch (error) {
    console.error('Error loading plot data:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load plot data',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const getRunTypeStats = () => {
  const stats = {}
  runs.value.forEach(run => {
    stats[run.run_type] = (stats[run.run_type] || 0) + 1
  })
  return Object.entries(stats)
    .map(([type, count]) => `${type}: ${count}`)
    .join(', ')
}

const loadVegaLiteCharts = () => {
  // TODO: Implement Vega-Lite charts
  // This would involve:
  // 1. Loading vega-embed library
  // 2. Creating chart specifications
  // 3. Rendering charts in the placeholder containers
}

// Lifecycle
onMounted(() => {
  loadPlotData()
})
</script>

<style scoped>
.plots-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.plots-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e9ecef;
}

.plots-header h2 {
  margin: 0;
  color: #495057;
}

.plots-controls {
  display: flex;
  gap: 0.5rem;
}

.plots-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.no-data {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 3rem;
}

.no-data-content {
  text-align: center;
  color: #6c757d;
}

.no-data-content h3 {
  margin: 1rem 0 0.5rem 0;
  color: #495057;
}

.no-data-content p {
  margin: 0;
  font-size: 1rem;
}

.plots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 1.5rem;
}

.plot-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.plot-card h3 {
  margin: 0 0 1rem 0;
  color: #495057;
  font-size: 1.1rem;
}

.plot-container {
  height: 300px;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
}

.chart-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  color: #6c757d;
}

.placeholder-content {
  text-align: center;
}

.placeholder-content > div:first-child {
  margin-bottom: 0.5rem;
}

.analytics-summary {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.analytics-summary h3 {
  margin: 0 0 1rem 0;
  color: #495057;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
}

.summary-icon {
  width: 48px;
  height: 48px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
}

.summary-content {
  flex: 1;
}

.summary-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: #495057;
  line-height: 1;
}

.summary-label {
  font-size: 0.9rem;
  color: #6c757d;
  margin-top: 0.25rem;
}

@media (max-width: 768px) {
  .plots-grid {
    grid-template-columns: 1fr;
  }
  
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
