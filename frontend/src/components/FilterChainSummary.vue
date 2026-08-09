<script setup lang="ts">
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import { useAppStore, useFilteringStore } from '../stores'
import { formatFilterLabel, formatDiversityLabel } from '../utils/filterLabel'
import type { FilterChainItem } from '../stores/filtering'

withDefaults(
  defineProps<{
    /** Show a "Edit filters" shortcut to the Filtering tab (Designs-tab usage only). */
    showEditFiltersLink?: boolean
  }>(),
  { showEditFiltersLink: false }
)

const filteringStore = useFilteringStore()
const appStore = useAppStore()

function itemLabel(item: FilterChainItem): string {
  const base =
    item.type === 'diversity' ? formatDiversityLabel(filteringStore.budget, filteringStore.alpha) : formatFilterLabel(item)
  return item.remaining != null ? `${base} (${item.remaining})` : base
}

function itemTooltip(item: FilterChainItem): string {
  const noun = item.type === 'diversity' ? 'diversity selection' : 'this filter'
  return item.enabled ? `Click to disable ${noun}` : `Click to enable ${noun}`
}

function toggleItem(item: FilterChainItem) {
  if (item.type === 'diversity') {
    filteringStore.toggleDiversityEnabled()
  } else {
    filteringStore.toggleFilterEnabled(item.index)
  }
}
</script>

<template>
  <div class="filter-chain-summary">
    <div class="filter-chain-summary__chain">
      <Tag
        class="filter-chain-summary__tag filter-chain-summary__tag--total"
        severity="secondary"
        :value="filteringStore.initialDesignCount != null ? String(filteringStore.initialDesignCount) : '…'"
        v-tooltip.bottom="'Total designs before filtering'"
      />
      <template v-for="(item, idx) in filteringStore.filterChain" :key="`${item.type}-${item.index}-${idx}`">
        <i class="pi pi-angle-right filter-chain-summary__arrow" aria-hidden="true" />
        <Tag
          :value="itemLabel(item)"
          :severity="item.enabled ? (item.type === 'diversity' ? 'warning' : 'info') : 'secondary'"
          :class="[
            'filter-chain-summary__tag',
            item.type === 'diversity' ? 'filter-chain-summary__tag--diversity' : null,
            { 'filter-chain-summary__tag--disabled': !item.enabled }
          ]"
          v-tooltip.bottom="itemTooltip(item)"
          @click="toggleItem(item)"
        />
      </template>
      <span v-if="filteringStore.filterChain.length === 0" class="filter-chain-summary__empty-hint">
        No hard filters configured.
      </span>
    </div>
    <Button
      v-if="showEditFiltersLink"
      label="Edit filters"
      icon="pi pi-arrow-right"
      text
      size="small"
      @click="appStore.setActiveTab('filtering')"
    />
  </div>
</template>

<style scoped>
.filter-chain-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.filter-chain-summary__chain {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex-wrap: wrap;
}

.filter-chain-summary__arrow {
  font-size: 0.7rem;
  color: #adb5bd;
}

.filter-chain-summary__empty-hint {
  font-size: 0.85rem;
  color: #6c757d;
}

.filter-chain-summary__tag {
  cursor: pointer;
  user-select: none;
}

.filter-chain-summary__tag--total {
  cursor: default;
  font-weight: 700;
}

.filter-chain-summary__tag--disabled {
  opacity: 0.5;
  text-decoration: line-through;
}

.filter-chain-summary__tag--diversity {
  font-style: italic;
}
</style>
