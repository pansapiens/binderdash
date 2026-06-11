<template>
  <div class="plots-view">
    <div class="plots-header">
      <h2>Plots & Analytics</h2>
      <div class="plots-controls"></div>
    </div>

    <div class="plots-content">
      <div v-if="!hasPlotData" class="no-data">
        <div class="no-data-content">
          <i class="pi pi-chart-line" style="font-size: 3rem; color: #6c757d;"></i>
          <h3>No Data Available</h3>
          <p>Ingest runs on <strong>Ingest Runs</strong>, select them on <strong>Select Runs</strong>, filter on <strong>Designs</strong>, then view plots of that set here.</p>
        </div>
      </div>

      <div v-else class="plots-container">
        <div v-if="plotsStore.combinedData.length > 0" class="charts-section">
          <div class="chart-controls">
            <div class="control-group">
              <h4>Scatter Plot</h4>
              <div class="axis-controls">
                <div class="axis-control">
                  <label>X Axis:</label>
                  <Dropdown 
                    v-model="plotsStore.scatterXCol" 
                    :options="plotsStore.numericColumns" 
                    placeholder="Select X column..."
                    class="axis-dropdown"
                    filter
                    filterPlaceholder="Search metrics..."
                    @change="onScatterAxisChange"
                  />
                </div>
                <div class="axis-control">
                  <label>Y Axis:</label>
                  <Dropdown 
                    v-model="plotsStore.scatterYCol" 
                    :options="plotsStore.numericColumns" 
                    placeholder="Select Y column..."
                    class="axis-dropdown"
                    filter
                    filterPlaceholder="Search metrics..."
                    @change="onScatterAxisChange"
                  />
                </div>
                <div class="axis-control">
                  <label>Colour:</label>
                  <Dropdown 
                    v-model="plotsStore.scatterColorCol" 
                    :options="plotsStore.plotColumns" 
                    placeholder="None"
                    class="axis-dropdown"
                    filter
                    filterPlaceholder="Search columns..."
                    showClear
                    @change="onScatterAxisChange"
                  />
                </div>
                <div class="axis-control">
                  <label>Size:</label>
                  <Dropdown 
                    v-model="plotsStore.scatterSizeCol" 
                    :options="plotsStore.numericColumns" 
                    placeholder="None"
                    class="axis-dropdown"
                    filter
                    filterPlaceholder="Search metrics..."
                    showClear
                    @change="onScatterAxisChange"
                  />
                </div>
              </div>
            </div>
          </div>

          <div class="chart-container chart-container--marginal">
            <div class="chart-header">
              <h4>
                <template v-if="plotsStore.scatterXCol && plotsStore.scatterYCol">
                  {{ plotsStore.scatterYCol }} vs {{ plotsStore.scatterXCol }}
                </template>
                <template v-else>Scatter plot with marginal histograms</template>
              </h4>
              <div v-if="scatterLoading" class="chart-loading">
                <i class="pi pi-spin pi-spinner"></i>
              </div>
            </div>
            <div
              class="chart-plot chart-plot--marginal"
              :class="{ loading: scatterLoading }"
            >
              <div v-if="!plotsStore.scatterXCol || !plotsStore.scatterYCol" class="chart-placeholder">
                <i class="pi pi-chart-scatter" style="font-size: 2rem; color: #6c757d;"></i>
                <div>Select X and Y columns to view scatter plot</div>
              </div>
              <div
                v-else
                ref="marginalChartContainer"
                class="marginal-chart"
                :style="marginalChartHeightPx ? { height: `${marginalChartHeightPx}px` } : undefined"
              ></div>
            </div>
          </div>

          <div
            v-if="plotsStore.scatterXCol && plotsStore.scatterYCol"
            class="distribution-row"
          >
            <div class="chart-container">
              <div class="chart-header">
                <h4>Distribution of {{ plotsStore.scatterXCol }}</h4>
              </div>
              <div ref="xDistContainer" class="chart-plot chart-plot--distribution"></div>
            </div>
            <div class="chart-container">
              <div class="chart-header">
                <h4>Distribution of {{ plotsStore.scatterYCol }}</h4>
              </div>
              <div ref="yDistContainer" class="chart-plot chart-plot--distribution"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import Dropdown from 'primevue/dropdown'
import { useToast } from 'primevue/usetoast'
import embed from 'vega-embed'
import { usePlotsStore, useDesignsStore } from '../stores'

const toast = useToast()

const plotsStore = usePlotsStore()
const designsStore = useDesignsStore()

const scatterLoading = ref(false)

const marginalChartContainer = ref<HTMLElement | null>(null)
const marginalChartHeightPx = ref<number | null>(null)
const xDistContainer = ref<HTMLElement | null>(null)
const yDistContainer = ref<HTMLElement | null>(null)

const MARGINAL_BIN_MAX = 20
const DIST_BIN_MAX = 30
const MARGINAL_FRAC = 0.18
const MARGINAL_MIN_PX = 44
const MARGINAL_MAX_PX = 140
const MARGINAL_SPACING_PX = 6
const LEGEND_RESERVE_PX = 200
const PLOT_AXIS_LABEL_FONT = 14
const PLOT_AXIS_TITLE_FONT = 16
const PLOT_LEGEND_LABEL_FONT = 14
const PLOT_LEGEND_TITLE_FONT = 15

const hasPlotData = computed(() => designsStore.filteredDesigns.length > 0)

const plotRunCount = computed(() => {
  const ids = new Set(plotsStore.combinedData.map((row: any) => row.run_id).filter(Boolean))
  return ids.size
})

const containerSpec = (): Record<string, unknown> => ({
  width: 'container',
  height: 'container',
  autosize: { type: 'fit', contains: 'padding' },
})

const embedChart = async (container: HTMLElement | null, spec: Record<string, unknown>): Promise<boolean> => {
  if (!container) return false
  const rect = container.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return false
  container.innerHTML = ''
  await embed(container, spec, { actions: false, renderer: 'svg' })
  return true
}

const filterNumericRows = (data: any[], col: string): any[] =>
  data.filter((row) => {
    const v = row[col]
    if (v == null) return false
    const n = typeof v === 'number' ? v : Number(v)
    return Number.isFinite(n)
  })

const numericExtent = (data: any[], col: string): [number, number] => {
  const vals = data
    .map((row) => {
      const v = row[col]
      return typeof v === 'number' ? v : Number(v)
    })
    .filter(Number.isFinite)
  if (vals.length === 0) return [0, 1]
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  if (min === max) return [min - 0.5, max + 0.5]
  const pad = (max - min) * 0.02
  return [min - pad, max + pad]
}

const inferFieldType = (data: any[], field: string): 'quantitative' | 'nominal' => {
  const vals = data.map((row) => row[field]).filter((v) => v != null && v !== '')
  if (vals.length === 0) return 'nominal'
  const numericCount = vals.filter((v) => {
    const n = typeof v === 'number' ? v : Number(v)
    return Number.isFinite(n)
  }).length
  return numericCount / vals.length > 0.9 ? 'quantitative' : 'nominal'
}

const tooltipField = (field: string, type: 'quantitative' | 'nominal') => ({
  field,
  type,
  title: field,
  ...(type === 'quantitative' ? { format: '.3f' } : {}),
})

const colorEncoding = (data: any[], colorCol: string | null) => {
  if (!colorCol) return undefined
  const colorType = inferFieldType(data, colorCol)
  return {
    field: colorCol,
    type: colorType,
    title: colorCol,
    ...(colorType === 'quantitative' ? { scale: { scheme: 'viridis' } } : {}),
  }
}

const marginalBarMark = (): Record<string, unknown> => ({
  type: 'bar',
  opacity: 0.35,
  color: '#667eea',
})

// Explicit step (rather than maxbins) so bins tile the domain exactly: the last
// bin ends on the domain max, preventing the final bar from overhanging the
// scatter edge (the marginal shares the scatter's x/y scale domain).
const marginalBinParams = (domain: [number, number]) => {
  const span = domain[1] - domain[0]
  const step = span > 0 ? span / MARGINAL_BIN_MAX : 1
  return { extent: domain, step, nice: false }
}

const quantitativeScale = (domain: [number, number]) => ({
  domain,
  nice: false,
  zero: false,
})

const plotVegaConfig = (legendDisabled = false): Record<string, unknown> => ({
  view: { stroke: 'transparent' },
  axis: {
    labelFontSize: PLOT_AXIS_LABEL_FONT,
    titleFontSize: PLOT_AXIS_TITLE_FONT,
    titleFontWeight: 'normal',
  },
  legend: legendDisabled
    ? { disable: true }
    : {
        labelFontSize: PLOT_LEGEND_LABEL_FONT,
        titleFontSize: PLOT_LEGEND_TITLE_FONT,
      },
})

const buildAestheticEncodings = (
  data: any[],
  colorCol: string | null,
  sizeCol: string | null,
  showLegend: boolean,
): Record<string, unknown> => {
  const encoding: Record<string, unknown> = {}
  const legendCfg = showLegend ? { orient: 'right' as const, padding: 4 } : null

  if (colorCol) {
    const color = colorEncoding(data, colorCol)
    if (color) {
      encoding.color = { ...color, legend: legendCfg }
    }
  }

  if (sizeCol) {
    encoding.size = {
      field: sizeCol,
      type: 'quantitative',
      title: sizeCol,
      scale: { range: [30, 300] },
      legend: legendCfg,
    }
  }

  return encoding
}

const buildScatterEncoding = (
  data: any[],
  xCol: string,
  yCol: string,
  xDomain: [number, number],
  yDomain: [number, number],
  colorCol: string | null,
  sizeCol: string | null,
  showLegend = false,
): { mark: Record<string, unknown>; encoding: Record<string, unknown> } => {
  const encoding: Record<string, unknown> = {
    x: {
      field: xCol,
      type: 'quantitative',
      scale: quantitativeScale(xDomain),
      title: xCol,
    },
    y: {
      field: yCol,
      type: 'quantitative',
      scale: quantitativeScale(yDomain),
      title: yCol,
    },
    tooltip: [
      tooltipField(xCol, 'quantitative'),
      tooltipField(yCol, 'quantitative'),
    ],
    ...buildAestheticEncodings(data, colorCol, sizeCol, showLegend),
  }

  const mark: Record<string, unknown> = { type: 'circle', opacity: 0.7 }
  if (!sizeCol) {
    mark.size = 60
  }

  if (colorCol) {
    const colorType = inferFieldType(data, colorCol)
    ;(encoding.tooltip as unknown[]).push(tooltipField(colorCol, colorType))
  }
  if (sizeCol) {
    ;(encoding.tooltip as unknown[]).push(tooltipField(sizeCol, 'quantitative'))
  }

  return { mark, encoding }
}

type MarginalDims = { scatterW: number; scatterH: number; marginal: number }

const marginalChartHeight = (dims: MarginalDims): number =>
  dims.marginal + MARGINAL_SPACING_PX + dims.scatterH

const computeMarginalDims = (container: HTMLElement, hasLegend: boolean): MarginalDims | null => {
  const plotEl = container.parentElement
  const style = plotEl ? getComputedStyle(plotEl) : getComputedStyle(container)
  const padX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight)
  const outerW = (plotEl ?? container).clientWidth - padX
  if (outerW <= 0) return null

  const legendReserve = hasLegend ? LEGEND_RESERVE_PX : 0
  const usableW = outerW - legendReserve
  const maxChartHeight = Math.min(window.innerHeight * 0.8, 900)

  let marginal = Math.round(
    Math.min(Math.max(usableW * MARGINAL_FRAC, MARGINAL_MIN_PX), MARGINAL_MAX_PX)
  )
  let scatterSize = Math.max(120, Math.floor(usableW - marginal - MARGINAL_SPACING_PX))

  // Refine marginal from the laid-out chart height (square scatter → predictable height).
  let chartHeight = marginalChartHeight({ scatterW: scatterSize, scatterH: scatterSize, marginal })
  if (chartHeight > maxChartHeight) {
    scatterSize = Math.max(120, Math.floor(maxChartHeight - marginal - MARGINAL_SPACING_PX))
    chartHeight = marginalChartHeight({ scatterW: scatterSize, scatterH: scatterSize, marginal })
  }

  marginal = Math.round(
    Math.min(
      Math.max(Math.min(usableW, chartHeight) * MARGINAL_FRAC, MARGINAL_MIN_PX),
      MARGINAL_MAX_PX,
    )
  )
  scatterSize = Math.max(120, Math.floor(usableW - marginal - MARGINAL_SPACING_PX))

  return { scatterW: scatterSize, scatterH: scatterSize, marginal }
}

// Single concatenated spec so Vega-Lite aligns the marginal plot frames natively
// (bounds: "flush" aligns the inner plotting rectangles, not the axis-inclusive bounds).
const createMarginalScatterSpec = (
  data: any[],
  xCol: string,
  yCol: string,
  xDomain: [number, number],
  yDomain: [number, number],
  colorCol: string | null,
  sizeCol: string | null,
  dims: MarginalDims,
): Record<string, unknown> => {
  const { mark, encoding } = buildScatterEncoding(
    data, xCol, yCol, xDomain, yDomain, colorCol, sizeCol, true,
  )

  const topMarginal = {
    width: dims.scatterW,
    height: dims.marginal,
    mark: marginalBarMark(),
    encoding: {
      x: {
        field: xCol,
        type: 'quantitative',
        bin: marginalBinParams(xDomain),
        scale: quantitativeScale(xDomain),
        axis: null,
        title: null,
      },
      y: {
        aggregate: 'count',
        type: 'quantitative',
        scale: { nice: false, zero: true },
        axis: null,
        title: null,
      },
    },
  }

  const rightMarginal = {
    width: dims.marginal,
    height: dims.scatterH,
    mark: marginalBarMark(),
    encoding: {
      y: {
        field: yCol,
        type: 'quantitative',
        bin: marginalBinParams(yDomain),
        scale: quantitativeScale(yDomain),
        axis: null,
        title: null,
      },
      x: {
        aggregate: 'count',
        type: 'quantitative',
        scale: { nice: false, zero: true },
        axis: null,
        title: null,
      },
    },
  }

  const scatter = {
    width: dims.scatterW,
    height: dims.scatterH,
    mark,
    encoding,
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    data: { values: data },
    spacing: MARGINAL_SPACING_PX,
    bounds: 'flush',
    vconcat: [
      topMarginal,
      {
        spacing: MARGINAL_SPACING_PX,
        bounds: 'flush',
        hconcat: [scatter, rightMarginal],
      },
    ],
    config: plotVegaConfig(false),
  }
}

const createDistributionSpec = (
  data: any[],
  valueCol: string,
  extent: [number, number],
  colorCol: string | null,
): Record<string, unknown> | null => {
  const rows = filterNumericRows(data, valueCol)
  if (rows.length === 0) return null

  const n = rows.length
  const binWidth = (extent[1] - extent[0]) / DIST_BIN_MAX
  const useColorGroups = Boolean(
    colorCol && inferFieldType(rows, colorCol) === 'nominal'
  )

  const densityTransform: Record<string, unknown> = {
    density: valueCol,
    extent,
    as: ['value', 'density'],
    ...(useColorGroups ? { groupby: [colorCol] } : {}),
  }

  const densityLayer: Record<string, unknown> = {
    transform: [
      densityTransform,
      { calculate: `datum.density * ${n} * ${binWidth}`, as: 'scaled_density' },
    ],
    mark: { type: 'area', opacity: 0.45, interpolate: 'monotone' },
    encoding: {
      x: {
        field: 'value',
        type: 'quantitative',
        scale: quantitativeScale(extent),
      },
      y: {
        field: 'scaled_density',
        type: 'quantitative',
        stack: null,
        title: 'Count',
      },
      ...(useColorGroups && colorCol
        ? { color: colorEncoding(rows, colorCol) }
        : {}),
    },
  }

  const histogramLayer: Record<string, unknown> = {
    mark: { type: 'bar', opacity: 0.35, color: '#667eea' },
    encoding: {
      x: {
        field: valueCol,
        type: 'quantitative',
        bin: { maxbins: DIST_BIN_MAX, extent, nice: false, anchor: extent[0] },
        scale: quantitativeScale(extent),
        title: valueCol,
      },
      y: {
        aggregate: 'count',
        type: 'quantitative',
        title: 'Count',
      },
    },
  }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
    data: { values: rows },
    ...containerSpec(),
    layer: [histogramLayer, densityLayer],
    resolve: { scale: { y: 'shared', x: 'shared' } },
    config: plotVegaConfig(),
  }
}

const renderDistributionPlots = async (
  data: any[],
  xCol: string,
  yCol: string,
  colorCol: string | null,
): Promise<void> => {
  const xExtent = numericExtent(filterNumericRows(data, xCol), xCol)
  const yExtent = numericExtent(filterNumericRows(data, yCol), yCol)

  const xSpec = createDistributionSpec(data, xCol, xExtent, colorCol)
  const ySpec = createDistributionSpec(data, yCol, yExtent, colorCol)

  await Promise.all([
    xSpec ? embedChart(xDistContainer.value, xSpec) : Promise.resolve(false),
    ySpec ? embedChart(yDistContainer.value, ySpec) : Promise.resolve(false),
  ])
}

const renderMarginalScatter = async (
  data: any[],
  xCol: string,
  yCol: string,
  colorCol: string | null,
  sizeCol: string | null,
): Promise<boolean> => {
  const container = marginalChartContainer.value
  if (!container) return false

  const dims = computeMarginalDims(container, Boolean(colorCol || sizeCol))
  if (!dims) return false

  marginalChartHeightPx.value = marginalChartHeight(dims)

  const xDomain = numericExtent(data, xCol)
  const yDomain = numericExtent(data, yCol)

  const spec = createMarginalScatterSpec(
    data, xCol, yCol, xDomain, yDomain, colorCol, sizeCol, dims,
  )
  container.innerHTML = ''
  await embed(container, spec, { actions: false, renderer: 'svg' })
  return true
}

const onScatterAxisChange = () => {
  plotsStore.recordScatterAxisPreferences()
  void updateAllPlots()
}

const syncFromDesignTable = async () => {
  if (designsStore.loading) return
  plotsStore.setDataFromDesigns(designsStore.filteredDesigns as any[])
  await nextTick()
  await updateAllPlots()
}

const updateAllPlots = async () => {
  if (plotsStore.combinedData.length === 0) return
  
  console.log('Updating all plots:', {
    designCount: plotsStore.combinedData.length,
    runCount: plotRunCount.value,
    scatterXCol: plotsStore.scatterXCol,
    scatterYCol: plotsStore.scatterYCol
  })
  
  if (plotsStore.scatterXCol && plotsStore.scatterYCol) {
    await updateScatterPlot()
  }
}

const updateScatterPlot = async () => {
  if (!plotsStore.scatterXCol || !plotsStore.scatterYCol || plotsStore.combinedData.length === 0) {
    console.log('Skipping scatter plot update:', {
      scatterXCol: plotsStore.scatterXCol,
      scatterYCol: plotsStore.scatterYCol,
      combinedDataLength: plotsStore.combinedData.length
    })
    return
  }
  
  console.log('Updating scatter plot with:', {
    xCol: plotsStore.scatterXCol,
    yCol: plotsStore.scatterYCol,
    totalDataPoints: plotsStore.combinedData.length
  })
  
  scatterLoading.value = true
  try {
    // Filter data to only include rows with valid values for both columns
    const filteredData = plotsStore.combinedData.filter((row: any) => {
      const vx = row[plotsStore.scatterXCol!]
      const vy = row[plotsStore.scatterYCol!]
      if (vx == null || vy == null) return false
      const nx = typeof vx === 'number' ? vx : Number(vx)
      const ny = typeof vy === 'number' ? vy : Number(vy)
      return Number.isFinite(nx) && Number.isFinite(ny)
    })
    
    console.log('Filtered data points:', filteredData.length)
    
    if (filteredData.length === 0) {
      console.warn('No valid data points for scatter plot')
      return
    }
    
    const rendered = await renderMarginalScatter(
      filteredData,
      plotsStore.scatterXCol,
      plotsStore.scatterYCol,
      plotsStore.scatterColorCol,
      plotsStore.scatterSizeCol,
    )
    await renderDistributionPlots(
      filteredData,
      plotsStore.scatterXCol,
      plotsStore.scatterYCol,
      plotsStore.scatterColorCol,
    )
    if (!rendered) {
      setTimeout(async () => {
        await renderMarginalScatter(
          filteredData,
          plotsStore.scatterXCol!,
          plotsStore.scatterYCol!,
          plotsStore.scatterColorCol,
          plotsStore.scatterSizeCol,
        )
        await renderDistributionPlots(
          filteredData,
          plotsStore.scatterXCol!,
          plotsStore.scatterYCol!,
          plotsStore.scatterColorCol,
        )
      }, 200)
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

watch(
  () => [
    designsStore.filteredDesigns,
    designsStore.loading,
    plotsStore.scatterXCol,
    plotsStore.scatterYCol,
    plotsStore.scatterColorCol,
    plotsStore.scatterSizeCol
  ],
  () => {
    void syncFromDesignTable()
  },
  { deep: true, immediate: true }
)

let resizeObserver: ResizeObserver | null = null
let resizeTimer: ReturnType<typeof setTimeout> | null = null

const scheduleScatterRerender = () => {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    if (plotsStore.scatterXCol && plotsStore.scatterYCol) {
      void updateScatterPlot()
    }
  }, 150)
}

watch(marginalChartContainer, (el) => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (typeof ResizeObserver === 'undefined' || !el) return
  resizeObserver = new ResizeObserver(() => scheduleScatterRerender())
  resizeObserver.observe(el)
})

onBeforeUnmount(() => {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeObserver?.disconnect()
  resizeObserver = null
})

defineExpose({
  syncFromDesignTable,
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.chart-container {
  border: 1px solid #e9ecef;
  border-radius: 6px;
  overflow: hidden;
  min-width: 0;
}

.chart-container--marginal {
  max-width: 1020px;
}

.distribution-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.chart-plot--distribution {
  min-height: 220px;
  aspect-ratio: 2 / 1;
  display: block;
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
  width: 100%;
  box-sizing: border-box;
  padding: 1rem;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.chart-plot--marginal {
  display: block;
}

.marginal-chart {
  width: 100%;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.marginal-chart :deep(svg) {
  display: block;
  max-width: 100%;
  height: auto;
}

.chart-plot.loading {
  opacity: 0.6;
}

.chart-placeholder {
  aspect-ratio: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  text-align: center;
  gap: 0.5rem;
}

@media (max-width: 1200px) {
  .axis-controls {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .distribution-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1000px) {
  .axis-controls {
    grid-template-columns: 1fr;
  }
}
</style>