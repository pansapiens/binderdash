import { useDesignsStore } from '../stores/designs'
import { useFolderStore } from '../stores/folders'

export async function hydratePersistedState(): Promise<void> {
    await Promise.all([useDesignsStore().hydrateFromPersistence(), useFolderStore().hydrateFromPersistence()])
}
