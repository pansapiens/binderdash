/**
 * Folder Store
 * Manages folder browser state and folder operations
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { treeApi, runsApi } from '../webapi'
import { PERSISTENCE_KEYS } from '../persistence/keys'
import { kvGet, kvSet } from '../persistence/store'
import type { FolderNode, Run, FolderState } from '../types/store'

export const useFolderStore = defineStore('folders', () => {
    // State
    const folders = ref<FolderNode[]>([])
    const selectedKeys = ref<Record<string, any>>({})
    const expandedKeys = ref<Record<string, boolean>>({})
    const scanResults = ref<Run[]>([])
    const selectedRuns = ref<Run[]>([])
    const loading = ref(false)
    const scanning = ref(false)
    const foldersPersistenceHydrated = ref(false)

    const persistFoldersUi = () => {
        if (!foldersPersistenceHydrated.value) return
        void kvSet(PERSISTENCE_KEYS.foldersUi, {
            selectedKeys: { ...selectedKeys.value },
            expandedKeys: { ...expandedKeys.value }
        })
    }

    watch([selectedKeys, expandedKeys], () => persistFoldersUi(), { deep: true })

    const hydrateFromPersistence = async () => {
        try {
            const data = await kvGet<{ selectedKeys?: Record<string, unknown>; expandedKeys?: Record<string, boolean> }>(
                PERSISTENCE_KEYS.foldersUi
            )
            if (data?.selectedKeys && typeof data.selectedKeys === 'object') {
                selectedKeys.value = data.selectedKeys as Record<string, unknown>
            }
            if (data?.expandedKeys && typeof data.expandedKeys === 'object') {
                expandedKeys.value = data.expandedKeys
            }
        } catch (e) {
            console.warn('Failed to hydrate folder persistence from IndexedDB', e)
        } finally {
            foldersPersistenceHydrated.value = true
        }
    }

    // Getters
    const selectedFolderNodes = computed(() => {
        const selected: FolderNode[] = []
        for (const [key, value] of Object.entries(selectedKeys.value)) {
            if (value !== null) {
                const findNode = (nodes: FolderNode[], targetKey: string): FolderNode | null => {
                    for (const node of nodes) {
                        if (node.key === targetKey) {
                            return node
                        }
                        if (node.children) {
                            const found = findNode(node.children, targetKey)
                            if (found) return found
                        }
                    }
                    return null
                }

                const node = findNode(folders.value, key)
                if (node) {
                    selected.push(node)
                }
            }
        }
        return selected
    })

    const hasSelectedFolders = computed(() => Object.values(selectedKeys.value).some(value => value !== null))

    const totalScanResults = computed(() => scanResults.value.length)

    // Actions
    const fetchFolders = async (path = '') => {
        loading.value = true
        try {
            const data = await treeApi.getTree(path)
            folders.value = data.folders.map(folder => ({
                key: folder.path,
                name: folder.name,
                path: folder.path,
                has_children: folder.has_children,
                children: folder.has_children ? undefined : undefined, // Use undefined for lazy loading
                leaf: !folder.has_children,
                selectable: true
            }))
        } catch (err) {
            console.error('Error loading folders:', err)
            throw err
        } finally {
            loading.value = false
        }
    }

    const loadChildren = async (node: FolderNode): Promise<void> => {
        try {
            const data = await treeApi.getTree(node.path)
            node.children = data.folders.map((folder: any) => ({
                key: folder.path,
                name: folder.name,
                path: folder.path,
                has_children: folder.has_children,
                children: folder.has_children ? undefined : undefined, // Use undefined for lazy loading
                leaf: !folder.has_children,
                selectable: true
            }))
        } catch (err) {
            console.error('Error loading children:', err)
            throw err
        }
    }


    const toggleNodeSelection = (nodeKey: string) => {
        if (selectedKeys.value[nodeKey]) {
            delete selectedKeys.value[nodeKey]
        } else {
            selectedKeys.value[nodeKey] = true
        }
    }

    const scanSelectedFolders = async (options?: { forceRescanOfIngested?: boolean }) => {
        if (selectedFolderNodes.value.length === 0) return []

        scanning.value = true
        try {
            const folderPaths = selectedFolderNodes.value.map(folder => folder.path)
            const data = await runsApi.scanRuns(folderPaths, options)
            scanResults.value = data.runs
            selectedRuns.value = [...data.runs]

            return data.runs
        } catch (err) {
            console.error('Error scanning folders:', err)
            throw err
        } finally {
            scanning.value = false
        }
    }

    const scanFolders = async (
        folderPaths: string[],
        options?: { forceRescanOfIngested?: boolean }
    ) => {
        scanning.value = true
        try {
            const data = await runsApi.scanRuns(folderPaths, options)
            scanResults.value = data.runs
            selectedRuns.value = [...data.runs]

            return data.runs
        } catch (err) {
            console.error('Error scanning folders:', err)
            throw err
        } finally {
            scanning.value = false
        }
    }

    const clearSelection = () => {
        selectedKeys.value = {}
        selectedRuns.value = []
        scanResults.value = []
    }

    const expandNode = (nodeKey: string) => {
        expandedKeys.value[nodeKey] = true
    }

    const collapseNode = (nodeKey: string) => {
        expandedKeys.value[nodeKey] = false
    }

    const isNodeExpanded = (nodeKey: string) => {
        return expandedKeys.value[nodeKey] === true
    }

    const isNodeSelected = (nodeKey: string) => {
        return selectedKeys.value[nodeKey] === true
    }

    const getFolderIcon = (node: FolderNode): string => {
        if (node.has_children) {
            return 'pi pi-folder-open'
        }
        return 'pi pi-folder'
    }

    return {
        // State
        folders,
        selectedKeys,
        expandedKeys,
        scanResults,
        selectedRuns,
        loading,
        scanning,

        // Getters
        selectedFolderNodes,
        hasSelectedFolders,
        totalScanResults,

        // Actions
        fetchFolders,
        loadChildren,
        toggleNodeSelection,
        scanSelectedFolders,
        scanFolders,
        clearSelection,
        expandNode,
        collapseNode,
        isNodeExpanded,
        isNodeSelected,
        getFolderIcon,
        hydrateFromPersistence
    }
})
