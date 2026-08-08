<template>
  <div class="saved-sets-view">
    <div class="panel-header">
      <h2>Saved Sets</h2>
      <p class="hint">
        Manage Saved Sets: view their designs, rename, delete, download a ZIP, or reapply their
        filter recipe to build a new set. To include a Set in the Designs table, use
        <strong>Select Runs</strong> instead — this tab is for management only.
      </p>
    </div>

    <SavedSetDesignsTable
      v-if="viewingSavedSetId"
      :saved-set-id="viewingSavedSetId"
      @back="viewingSavedSetId = null"
    />
    <SavedSetsList
      v-else
      @view-designs="(id) => (viewingSavedSetId = id)"
      @reapply-filters="emit('reapply-filters')"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useFilteringStore } from '../stores'
import SavedSetsList from './SavedSetsList.vue'
import SavedSetDesignsTable from './SavedSetDesignsTable.vue'

const emit = defineEmits<{
  'reapply-filters': []
}>()

const filteringStore = useFilteringStore()
const viewingSavedSetId = ref<string | null>(null)

onMounted(() => {
  filteringStore.fetchSavedSets()
})
</script>

<style scoped>
.saved-sets-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.panel-header h2 {
  margin: 0 0 0.5rem 0;
  color: #495057;
}

.hint {
  margin: 0 0 1rem 0;
  color: #6c757d;
  font-size: 0.95rem;
}
</style>
