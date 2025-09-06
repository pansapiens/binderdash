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
            <div class="protocol-filter">
              <label>Filter by Protocol:</label>
              <Dropdown 
                v-model="selectedProtocol" 
                :options="protocolOptions" 
                optionLabel="label"
                optionValue="value"
                placeholder="All Protocols"
                class="protocol-dropdown"
                @change="onProtocolFilterChange"
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
        <div v-if="selectedRunIds.length > 0 && combinedData.length > 0" class="charts-section">
          <div class="chart-controls">
            <div class="control-group">
              <h4>Scatter Plot</h4>
              <div class="axis-controls">
                <div class="axis-control">
                  <label>X Axis:</label>
                  <Dropdown 
                    v-model="scatterXCol" 
                    :options="numericColumns" 
                    placeholder="Select X column..."
                    class="axis-dropdown"
                    @change="updateAllPlots"
                  />
                </div>
                <div class="axis-control">
                  <label>Y Axis:</label>
                  <Dropdown 
                    v-model="scatterYCol" 
                    :options="numericColumns" 
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

<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import MultiSelect from 'primevue/multiselect'
import { useToast } from 'primevue/usetoast'
import embed from 'vega-embed'
import { runsApi, plotsApi } from '../webapi'

const toast = useToast()

// State
const availableRuns = ref<any[]>([])
const selectedRunIds = ref<string[]>([])
const selectedProject = ref<string | null>(null)
const selectedProtocol = ref<string | null>(null)
const combinedData = ref<any[]>([])
const numericColumns = ref<string[]>([])
const scatterXCol = ref<string | null>(null)
const scatterYCol = ref<string | null>(null)
const loading = ref(false)
const scatterLoading = ref(false)
const xHistogramLoading = ref(false)
const yHistogramLoading = ref(false)

// Refs for chart containers
const scatterPlotContainer = ref<HTMLElement | null>(null)
const xHistogramPlotContainer = ref<HTMLElement | null>(null)
const yHistogramPlotContainer = ref<HTMLElement | null>(null)

// Computed
const projectOptions = computed(() => {
  const projects = [...new Set(availableRuns.value.map(run => run.project_id))]
  return projects.map(project => ({ label: project, value: project }))
})

const protocolOptions = computed(() => {
  const protocols = [...new Set(availableRuns.value.map(run => run.protocol))]
  return protocols.map(protocol => ({ label: protocol, value: protocol }))
})

const filteredRuns = computed(() => {
  let filtered = availableRuns.value
  
  if (selectedProject.value) {
    filtered = filtered.filter(run => run.project_id === selectedProject.value)
  }
  
  if (selectedProtocol.value) {
    filtered = filtered.filter(run => run.protocol === selectedProtocol.value)
  }
  
  return filtered
})

// Vega-Lite specification creation functions
const createScatterPlotSpec = (data: any, xCol: any, yCol: any, title = 'Scatter Plot'): any => {
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

const createHistogramSpec = (data: any, col: any, title = 'Distribution'): any => {
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
      display_name: `${run.project_id}/${run.metadata?.name || 'unknown'} (${run.protocol})`,
      protocol: run.protocol,
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
  combinedData.value = []
  numericColumns.value = []
  scatterXCol.value = null
  scatterYCol.value = null
}

const onProtocolFilterChange = () => {
  // Clear selected runs when protocol filter changes
  selectedRunIds.value = []
  combinedData.value = []
  numericColumns.value = []
  scatterXCol.value = null
  scatterYCol.value = null
}

const onRunsSelected = async () => {
  if (selectedRunIds.value.length === 0) {
    combinedData.value = []
    numericColumns.value = []
    scatterXCol.value = null
    scatterYCol.value = null
    return
  }
  
  try {
    // Get combined data from all selected runs
    const result = await plotsApi.getCombinedData(selectedRunIds.value)
    combinedData.value = result.data
    numericColumns.value = result.numericColumns
    
    // Set default columns based on available numeric columns
    if (numericColumns.value.length > 0) {
      // Look for common score columns first
      const xCol = numericColumns.value.find(col => 
        col.includes('plddt') || col.includes('pLDDT')
      ) || numericColumns.value[0]
      
      const yCol = numericColumns.value.find(col => 
        col.includes('pae') || col.includes('i_pTM') || col.includes('ipTM')
      ) || (numericColumns.value.length > 1 ? numericColumns.value[1] : numericColumns.value[0])
      
      scatterXCol.value = xCol
      scatterYCol.value = yCol
    }
    
    // Load initial plots if we have valid columns
    if (scatterXCol.value && scatterYCol.value) {
      // Use nextTick to ensure DOM is updated before rendering plots
      await nextTick()
      // Add a small delay to ensure DOM elements are fully rendered
      setTimeout(async () => {
        await updateAllPlots()
      }, 100)
    }
    
  } catch (error) {
    console.error('Error loading data:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to load data',
      life: 3000
    })
  }
}

const updateAllPlots = async () => {
  if (selectedRunIds.value.length === 0) return
  
  console.log('Updating all plots:', {
    selectedRunIds: selectedRunIds.value.length,
    scatterXCol: scatterXCol.value,
    scatterYCol: scatterYCol.value,
    combinedDataLength: combinedData.value.length
  })
  
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
  if (!scatterXCol.value || !scatterYCol.value || combinedData.value.length === 0) {
    console.log('Skipping scatter plot update:', {
      scatterXCol: scatterXCol.value,
      scatterYCol: scatterYCol.value,
      combinedDataLength: combinedData.value.length
    })
    return
  }
  
  console.log('Updating scatter plot with:', {
    xCol: scatterXCol.value,
    yCol: scatterYCol.value,
    totalDataPoints: combinedData.value.length
  })
  
  scatterLoading.value = true
  try {
    // Filter data to only include rows with valid values for both columns
    const filteredData = combinedData.value.filter(row => 
      row[scatterXCol.value!] != null && 
      row[scatterYCol.value!] != null &&
      !isNaN(row[scatterXCol.value!]) && 
      !isNaN(row[scatterYCol.value!])
    )
    
    console.log('Filtered data points:', filteredData.length)
    
    if (filteredData.length === 0) {
      console.warn('No valid data points for scatter plot')
      return
    }
    
    // Clear previous chart
    if (scatterPlotContainer.value) {
      scatterPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `${scatterYCol.value} vs ${scatterXCol.value}${selectedRunIds.value.length > 1 ? ` (${selectedRunIds.value.length} runs)` : ''}`
    const spec = createScatterPlotSpec(filteredData, scatterXCol.value, scatterYCol.value, title)
    
    // Render new chart
    if (scatterPlotContainer.value) {
      // Check if container has dimensions
      const rect = scatterPlotContainer.value.getBoundingClientRect()
      console.log('Scatter plot container dimensions:', rect)
      
      if (rect.width > 0 && rect.height > 0) {
        await embed(scatterPlotContainer.value, spec, {
          actions: false,
          renderer: 'svg'
        })
        console.log('Scatter plot rendered successfully')
      } else {
        console.warn('Scatter plot container has no dimensions, retrying...')
        // Retry after a short delay
        setTimeout(async () => {
          if (scatterPlotContainer.value) {
            await embed(scatterPlotContainer.value, spec, {
              actions: false,
              renderer: 'svg'
            })
            console.log('Scatter plot rendered on retry')
          }
        }, 200)
      }
    }
    
  } catch (error) {
    console.error('Error creating scatter plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to create scatter plot',
      life: 3000
    })
  } finally {
    scatterLoading.value = false
  }
}

const updateXHistogramPlot = async () => {
  if (!scatterXCol.value || combinedData.value.length === 0) return
  
  xHistogramLoading.value = true
  try {
    // Filter data to only include rows with valid values for the column
    const filteredData = combinedData.value.filter(row => 
      row[scatterXCol.value!] != null && 
      !isNaN(row[scatterXCol.value!])
    )
    
    if (filteredData.length === 0) {
      console.warn('No valid data points for X histogram')
      return
    }
    
    // Clear previous chart
    if (xHistogramPlotContainer.value) {
      xHistogramPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `Distribution of ${scatterXCol.value}${selectedRunIds.value.length > 1 ? ` (${selectedRunIds.value.length} runs)` : ''}`
    const spec = createHistogramSpec(filteredData, scatterXCol.value, title)
    
    // Render new chart
    if (xHistogramPlotContainer.value) {
      await embed(xHistogramPlotContainer.value, spec, {
        actions: false,
        renderer: 'svg'
      })
    }
    
  } catch (error) {
    console.error('Error creating X histogram plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to create X histogram plot',
      life: 3000
    })
  } finally {
    xHistogramLoading.value = false
  }
}

const updateYHistogramPlot = async () => {
  if (!scatterYCol.value || combinedData.value.length === 0) return
  
  yHistogramLoading.value = true
  try {
    // Filter data to only include rows with valid values for the column
    const filteredData = combinedData.value.filter(row => 
      row[scatterYCol.value!] != null && 
      !isNaN(row[scatterYCol.value!])
    )
    
    if (filteredData.length === 0) {
      console.warn('No valid data points for Y histogram')
      return
    }
    
    // Clear previous chart
    if (yHistogramPlotContainer.value) {
      yHistogramPlotContainer.value.innerHTML = ''
    }
    
    // Create Vega-Lite spec in frontend
    const title = `Distribution of ${scatterYCol.value}${selectedRunIds.value.length > 1 ? ` (${selectedRunIds.value.length} runs)` : ''}`
    const spec = createHistogramSpec(filteredData, scatterYCol.value, title)
    
    // Render new chart
    if (yHistogramPlotContainer.value) {
      await embed(yHistogramPlotContainer.value, spec, {
        actions: false,
        renderer: 'svg'
      })
    }
    
  } catch (error) {
    console.error('Error creating Y histogram plot:', error)
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to create Y histogram plot',
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
  grid-template-columns: 1fr 1fr 2fr;
  gap: 1.5rem;
  align-items: end;
}

.project-filter,
.protocol-filter,
.run-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-filter label,
.protocol-filter label,
.run-selector label {
  font-weight: 500;
  color: #495057;
  font-size: 0.9rem;
}

.project-dropdown,
.protocol-dropdown,
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

@media (max-width: 1200px) {
  .run-selection-controls {
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  
  .run-selector {
    grid-column: 1 / -1;
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