<template>
  <Panel
    :header="header"
    toggleable
    v-model:collapsed="collapsed"
    :pt="panelPt"
    v-bind="attrs"
  >
    <slot />
  </Panel>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'
import Panel from 'primevue/panel'

defineOptions({ inheritAttrs: false })

defineProps<{
  header: string
}>()

const collapsed = defineModel<boolean>('collapsed', { default: true })
const attrs = useAttrs()

function clickCameFromPanelToggle(e: MouseEvent): boolean {
  const nodes = typeof e.composedPath === 'function' ? e.composedPath() : []
  for (const node of nodes) {
    if (!(node instanceof Element)) continue
    if (
      node.classList.contains('p-panel-toggle-button') ||
      node.classList.contains('p-panel-header-actions') ||
      node.classList.contains('p-panel-header-action')
    ) {
      return true
    }
  }
  return false
}

function onHeaderClick(e: MouseEvent) {
  if (clickCameFromPanelToggle(e)) return
  collapsed.value = !collapsed.value
}

function stopPanelToggleClick(e: MouseEvent) {
  // PrimeVue's toggle button already flips `collapsed`. The header click
  // handler does the same for clicks on the title, so a button click must
  // not bubble or the panel opens and immediately closes.
  e.stopPropagation()
}

const panelPt = {
  header: {
    class: 'toggle-panel-header',
    onClick: onHeaderClick
  },
  pcToggleButton: {
    root: {
      onClick: stopPanelToggleClick
    }
  }
}
</script>

<style scoped>
:deep(.toggle-panel-header) {
  cursor: pointer;
  user-select: none;
}
</style>
