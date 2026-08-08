<script setup lang="ts">
import { computed } from 'vue'
import { useDesignsStore, useRunsStore } from '../stores'
import FilterSetBuilder from './FilterSetBuilder.vue'
import FilterChainSummary from './FilterChainSummary.vue'

const designsStore = useDesignsStore()
const runsStore = useRunsStore()

// Run scope comes solely from the Designs tab's selection (see plan §7A — the
// Filtering tab no longer has its own run picker).
const activeRunNames = computed(() => {
  const byId = new Map(runsStore.availableRuns.map((r) => [r.run_id, r]))
  return designsStore.selectedRunIds.map((id) => byId.get(id)?.metadata?.name ?? id)
})

const activeDesignCount = computed(() => designsStore.designs.length)
</script>

<template>
  <div class="filtering-view">
    <div class="filtering-run-scope">
      <template v-if="designsStore.selectedRunIds.length > 0">
        Filtering <strong>{{ designsStore.selectedRunIds.length }}</strong> run(s),
        <strong>{{ activeDesignCount }}</strong> designs:
        <span class="filtering-run-scope__names">{{ activeRunNames.join(', ') }}</span>
      </template>
      <template v-else>
        No runs selected. Use the <strong>Select Runs</strong> tab to choose which runs
        to filter.
      </template>
    </div>

    <FilterChainSummary v-if="designsStore.selectedRunIds.length > 0" />

    <FilterSetBuilder />
  </div>
</template>

<style scoped>
.filtering-view {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.filtering-run-scope {
  font-size: 0.9rem;
  color: #495057;
  background: #f1f3f5;
  border-radius: 6px;
  padding: 0.6rem 0.9rem;
}

.filtering-run-scope__names {
  color: #6c757d;
}
</style>
