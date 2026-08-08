<script setup lang="ts">
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import { useAppStore, useFilteringStore } from '../stores'
import { formatFilterLabel } from '../utils/filterLabel'

withDefaults(
  defineProps<{
    /** Show a "Edit filters" shortcut to the Filtering tab (Designs-tab usage only). */
    showEditFiltersLink?: boolean
  }>(),
  { showEditFiltersLink: false }
)

const filteringStore = useFilteringStore()
const appStore = useAppStore()

function toggleFilter(index: number) {
  filteringStore.toggleFilterEnabled(index)
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
      <template v-for="item in filteringStore.filterChain" :key="item.index">
        <i class="pi pi-angle-right filter-chain-summary__arrow" aria-hidden="true" />
        <Tag
          :value="item.remaining != null ? `${formatFilterLabel(item)} (${item.remaining})` : formatFilterLabel(item)"
          :severity="item.enabled ? 'info' : 'secondary'"
          :class="['filter-chain-summary__tag', { 'filter-chain-summary__tag--disabled': !item.enabled }]"
          v-tooltip.bottom="item.enabled ? 'Click to disable this filter' : 'Click to enable this filter'"
          @click="toggleFilter(item.index)"
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
</style>
