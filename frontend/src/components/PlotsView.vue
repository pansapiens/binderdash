<template>
  <div class="plots-view">
    <div class="plots-header">
      <h2>Plots & Analytics</h2>
      <div class="plots-controls">
        <Button 
          label="Refresh Data" 
          icon="pi pi-refresh" 
          @click="loadRunData"
          :loading="loading"
        />
      </div>
    </div>

    <div class="plots-content">
      <div v-if="availableRuns.length === 0" class="no-data">
        <div class="no-data-content">
          <i class="pi pi-chart-line" style="font-size: 3rem; color: #6c757d;"></i>
          <h3>No Data Available</h3>
          <p>Scan some folders first to generate plots and analytics</p>
        </div>
      </div>

      <div v-else class="plots-container">
        <!-- Run Selection -->
        <div class="run-selection">
          <h3>Select Runs for Plotting</h3>
          <div class="run-selection-controls">
            <div class="project-filter">
              <label>Filter by Project:</label>
              <Dropdown 
                v-model="selectedProject" 
                :options="projectOptions" 
                optionLabel="label"
                optionValue="value"
                placeholder="All Projects"
                class="project-dropdown"
                @change="onProjectFilterChange"
                showClear
              />
            </div>
            <div class="run-selector">
              <label>Select Runs:</label>
              <MultiSelect 
                v-model="selectedRunIds" 
                :options="filteredRuns" 
                optionLabel="display_name" 
                optionValue="run_id"
                placeholder="Select runs..."
                class="run-multiselect"
                @change="onRunsSelected"
                :maxSelectedLabels="3"
                selectedItemsLabel="{0} runs selected"
              />
            </div>
          </div>
        </div>

        <!-- Plot Controls and Charts -->
        <div v-if="selectedRunIds.length > 0 && columnsData" class="charts-section">
          <div class="chart-controls">
            <div class="control-group">
              <h4>Scatter Plot</h4>
              <div class="axis-controls">
                <div class="axis-control">
                  <label>X Axis:</label>
                  <Dropdown 
                    v-model="scatterXCol" 
                    :options="columnsData.numeric_columns" 
                    placeholder="Select X column..."
                    class="axis-dropdown"
                    @change="updateAllPlots"
                  />
                </div>
                <div class="axis-control">
                  <label>Y Axis:</label>
                  <Dropdown 
                    v-model="scatterYCol" 
                    :options="columnsData.numeric_columns" 
                    placeholder="Select Y column..."
                    class="axis-dropdown"
                    @change="updateAllPlots"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="charts-grid">
            <div class="chart-container">
              <div class="chart-header">
                <h4>Scatter Plot</h4>
                <div v-if="scatterLoading" class="chart-loading">
                  <i class="pi pi-spin pi-spinner"></i>
                </div>
              </div>
              <div 
                ref="scatterPlotContainer" 
                class="chart-plot"
                :class="{ 'loading': scatterLoading }"
              >
                <div v-if="!scatterXCol || !scatterYCol" class="chart-placeholder">
                  <i class="pi pi-chart-scatter" style="font-size: 2rem; color: #6c757d;"></i>
                  <div>Select X and Y columns to view scatter plot</div>
                </div>
              </div>
            </div>

            <div class="chart-container">
              <div class="chart-header">
                <h4>Distribution of {{ scatterXCol || 'X Column' }}</h4>
                <div v-if="xHistogramLoading" class="chart-loading">
                  <i class="pi pi-spin pi-spinner"></i>
                </div>
              </div>
              <div 
                ref="xHistogramPlotContainer" 
                class="chart-plot"
                :class="{ 'loading': xHistogramLoading }"
              >
                <div v-if="!scatterXCol" class="chart-placeholder">
                  <i class="pi pi-chart-bar" style="font-size: 2rem; color: #6c757d;"></i>
                  <div>Select X column to view distribution</div>
                </div>
              </div>
            </div>

            <div class="chart-container">
              <div class="chart-header">
                <h4>Distribution of {{ scatterYCol || 'Y Column' }}</h4>
                <div v-if="yHistogramLoading" class="chart-loading">
                  <i class="pi pi-spin pi-spinner"></i>
                </div>
              </div>
              <div 
                ref="yHistogramPlotContainer" 
                class="chart-plot"
                :class="{ 'loading': yHistogramLoading }"
              >
                <div v-if="!scatterYCol" class="chart-placeholder">
                  <i class="pi pi-chart-bar" style="font-size: 2rem; color: #6c757d;"></i>
                  <div>Select Y column to view distribution</div>
                </div>
              </div>
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
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import { useToast } from 'primevue/usetoast'
import embed from 'vega-embed'
import { runsApi, plotsApi } from '../webapi.js'

const toast = useToast()

// State
const availableRuns = ref([])
const selectedRunIds = ref([])
const selectedProject = ref(null)
const columnsData = ref(null)
const scatterXCol = ref(null)
const scatterYCol = ref(null)
const loading = ref(false)
const scatterLoading = ref(false)
const xHistogramLoading = ref(false)
const yHistogramLoading = ref(false)

// Refs for chart containers
const scatterPlotContainer = ref(null)
const xHistogramPlotContainer = ref(null)
const yHistogramPlotContainer = ref(null)

// Computed
const projectOptions = computed(() => {
  const projects = [...new Set(availableRuns.value.map(run => run.project_id))]
  return projects.map(project => ({ label: project, value: project }))
})

const filteredRuns = computed(() => {
  if (!selectedProject.value) {
    return availableRuns.value
  }
  return availableRuns.value.filter(run => run.project_id === selectedProject.value)
})

// Vega-Lite specification creation functions
const createScatterPlotSpec = (data, xCol, yCol, title = 'Scatter Plot') => {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: title,
    data: { values: data },
    mark: { type: 'circle', size: 60, opacity: 0.7 },
    encoding: {
      x: {
        field: xCol,
        type: 'quantitative',
        scale: { zero: false },
        title: xCol,
      },
      y: {
        field: yCol,
        type: 'quantitative',
        scale: { zero: false },
        title: yCol,
      },
      tooltip: [
        { field: xCol, type: 'quantitative', format: '.3f' },
        { field: yCol, type: 'quantitative', format: '.3f' },
      ],
    },
    width: 400,
    height: 300,
  }
}

const createHistogramSpec = (data, col, title = 'Distribution') => {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    title: title,
    data: { values: data },
    layer: [
      {
        mark: { type: 'bar', opacity: 0.7, color: '#667eea' },
        encoding: {
          x: {
            field: col,
            type: 'quantitative',
            bin: { maxbins: 30 },
            title: col,
          },
          y: {
            aggregate: 'count',
            type: 'quantitative',
            title: 'Count',
          },
          tooltip: [
            {
              field: col,
              type: 'quantitative',
              bin: true,
              title: `${col} (binned)`,
            },
            {
              aggregate: 'count',
              type: 'quantitative',
              title: 'Count',
            },
          ],
        },
      }
    ],
    width: 400,
    height: 300,
  }
}

// Methods
const loadRunData = async () => {
  loading.value = true
  try {
    const data = await runsApi.listRuns()
    
    // Transform runs for dropdown display
    availableRuns.value = data.runs.map(run => ({
      run_id: run.run_id,
      display_name: `${run.project_id}/${run.metadata?.name || 'unknown'} (${run.run_type})`,
      run_type: run.run_type,
      project_id: run.project_id,
      path: run.path
    }))
    
    // Auto-select first run if available and none selected
    if (availableRuns.value.length > 0 && selectedRunIds.value.length === 0) {
      selectedRunIds.value = [availableRuns.value[0].run_id]
      await onRunsSelected()
    }
    
  } catch (error) {
    console.error('Error loading run data:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load run data',
      life: 3000
    })
  } finally {
    loading.value = false
  }
}

const onProjectFilterChange = () => {
  // Clear selected runs when project filter changes
  selectedRunIds.value = []
  columnsData.value = null
  scatterXCol.value = null
  scatterYCol.value = null
}

const onRunsSelected = async () => {
  if (selectedRunIds.value.length === 0) {
    columnsData.value = null
    scatterXCol.value = null
    scatterYCol.value = null
    return
  }
  
  try {
    // Use the multiple runs endpoint to get combined column data
    columnsData.value = await plotsApi.getPlotColumnsMultiple(selectedRunIds.value)
    
    // Set default columns based on backend suggestions
    if (columnsData.value.defaults.x) {
      scatterXCol.value = columnsData.value.defaults.x
    }
    if (columnsData.value.defaults.y) {
      scatterYCol.value = columnsData.value.defaults.y
    }
    
    // Load initial plots if we have valid defaults
    if (scatterXCol.value && scatterYCol.value) {
      await updateAllPlots()
    }
    
  } catch (error) {
    console.error('Error loading column data:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load column data',
      life: 3000
    })
  }
}

const updateAllPlots = async () => {
  if (selectedRunIds.value.length === 0) return
  
  // Update scatter plot
  if (scatterXCol.value && scatterYCol.value) {
    await updateScatterPlot()
  }
  
  // Update X histogram
  if (scatterXCol.value) {
    await updateXHistogramPlot()
  }
  
  // Update Y histogram
  if (scatterYCol.value) {
    await updateYHistogramPlot()
  }
}

const updateScatterPlot = async () => {
  if (selectedRunIds.value.length === 0 || !scatterXCol.value || !scatterYCol.value) return
  
  scatterLoading.value = true
  try {
    // Use the multiple runs endpoint to get combined data
    const data = await plotsApi.getScatterPlotMultiple(
      selectedRunIds.value,
      scatterXCol.value,
      scatterYCol.value
    )
    
    // Clear previous chart
    if (scatterPlotContainer.value) {
      scatterPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `${scatterYCol.value} vs ${scatterXCol.value}${data.run_count > 1 ? ` (${data.run_count} runs)` : ''}`
    const spec = createScatterPlotSpec(data.data, scatterXCol.value, scatterYCol.value, title)
    
    // Render new chart
    await embed(scatterPlotContainer.value, spec, {
      actions: false,
      renderer: 'svg'
    })
    
  } catch (error) {
    console.error('Error loading scatter plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load scatter plot',
      life: 3000
    })
  } finally {
    scatterLoading.value = false
  }
}

const updateXHistogramPlot = async () => {
  if (selectedRunIds.value.length === 0 || !scatterXCol.value) return
  
  xHistogramLoading.value = true
  try {
    // Use the multiple runs endpoint to get combined data
    const data = await plotsApi.getHistogramPlotMultiple(selectedRunIds.value, scatterXCol.value)
    
    // Clear previous chart
    if (xHistogramPlotContainer.value) {
      xHistogramPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `Distribution of ${scatterXCol.value}${data.run_count > 1 ? ` (${data.run_count} runs)` : ''}`
    const spec = createHistogramSpec(data.data, scatterXCol.value, title)
    
    // Render new chart
    await embed(xHistogramPlotContainer.value, spec, {
      actions: false,
      renderer: 'svg'
    })
    
  } catch (error) {
    console.error('Error loading X histogram plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load X histogram plot',
      life: 3000
    })
  } finally {
    xHistogramLoading.value = false
  }
}

const updateYHistogramPlot = async () => {
  if (selectedRunIds.value.length === 0 || !scatterYCol.value) return
  
  yHistogramLoading.value = true
  try {
    // Use the multiple runs endpoint to get combined data
    const data = await plotsApi.getHistogramPlotMultiple(selectedRunIds.value, scatterYCol.value)
    
    // Clear previous chart
    if (yHistogramPlotContainer.value) {
      yHistogramPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `Distribution of ${scatterYCol.value}${data.run_count > 1 ? ` (${data.run_count} runs)` : ''}`
    const spec = createHistogramSpec(data.data, scatterYCol.value, title)
    
    // Render new chart
    await embed(yHistogramPlotContainer.value, spec, {
      actions: false,
      renderer: 'svg'
    })
    
  } catch (error) {
    console.error('Error loading Y histogram plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load Y histogram plot',
      life: 3000
    })
  } finally {
    yHistogramLoading.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadRunData()
})
</script>

<style scoped>
.plots-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  height: 100%;
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
  flex: 1;
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

.plots-container {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.run-selection {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.run-selection h3 {
  margin: 0 0 1rem 0;
  color: #495057;
}

.run-selection-controls {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 2rem;
  align-items: end;
}

.project-filter,
.run-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-filter label,
.run-selector label {
  font-weight: 500;
  color: #495057;
  font-size: 0.9rem;
}

.project-dropdown,
.run-multiselect {
  width: 100%;
}

.charts-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 1.5rem;
}

.chart-controls {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #e9ecef;
}

.control-group h4 {
  margin: 0 0 1rem 0;
  color: #495057;
  font-size: 1.1rem;
}

.axis-controls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.axis-control {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.axis-control label {
  font-weight: 500;
  color: #495057;
  font-size: 0.9rem;
}

.axis-dropdown {
  width: 100%;
}

.charts-grid {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.chart-container {
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.chart-header h4 {
  margin: 0;
  color: #495057;
  font-size: 1rem;
}

.chart-loading {
  color: #667eea;
}

.chart-plot {
  min-height: 350px;
  padding: 1rem;
  background: white;
}

.chart-plot.loading {
  opacity: 0.6;
}

.chart-placeholder {
  height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  text-align: center;
  gap: 0.5rem;
}

@media (max-width: 1400px) {
  .charts-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 1000px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
  
  .run-selection-controls {
    grid-template-columns: 1fr;
  }
  
  .axis-controls {
    grid-template-columns: 1fr;
  }
}
</style>