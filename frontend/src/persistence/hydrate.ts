import { useDesignsStore } from '../stores/designs'
import { useFolderStore } from '../stores/folders'
import { usePlotsStore } from '../stores/plots'
import { useFilteringStore } from '../stores/filtering'

export async function hydratePersistedState(): Promise<void> {
    await Promise.all([
        useDesignsStore().hydrateFromPersistence(),
        useFolderStore().hydrateFromPersistence(),
        usePlotsStore().hydrateFromPersistence(),
        useFilteringStore().hydrateFromPersistence(),
    ])
}
