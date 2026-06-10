<template>
  <div v-if="desktopMode" class="desktop-settings">
    <Message v-if="needsSetup" severity="warn" :closable="false" class="desktop-settings__banner">
      Choose a folder containing your binder design run outputs. This path is saved for future sessions.
    </Message>

    <div class="desktop-settings__panel">
      <h3>Desktop settings</h3>
      <p class="desktop-settings__hint">
        Run base directories are the roots scanned in the folder tree below.
      </p>

      <div v-if="runBaseDirs.length" class="desktop-settings__dir-list">
        <div v-for="dir in runBaseDirs" :key="dir" class="desktop-settings__dir-item">
          <i class="pi pi-folder" aria-hidden="true" />
          <span>{{ dir }}</span>
        </div>
      </div>
      <p v-else class="desktop-settings__empty">No run base directory configured.</p>

      <div class="desktop-settings__manual" v-if="!hasPywebview">
        <label for="manualRunBaseDir">Folder path</label>
        <InputText
          id="manualRunBaseDir"
          v-model="manualPath"
          class="desktop-settings__input"
          placeholder="/path/to/runs"
        />
      </div>

      <div class="desktop-settings__actions">
        <Button
          label="Choose folder"
          icon="pi pi-folder-open"
          severity="secondary"
          outlined
          :loading="picking"
          @click="pickFolder"
        />
        <Button
          v-if="!hasPywebview"
          label="Save path"
          icon="pi pi-save"
          :loading="saving"
          :disabled="!manualPath.trim()"
          @click="saveManualPath"
        />
        <Button
          label="Open data folder"
          icon="pi pi-external-link"
          severity="secondary"
          text
          :loading="openingDataDir"
          @click="openDataDir"
        />
      </div>

      <p v-if="dataDir" class="desktop-settings__data-dir">
        App data: <code>{{ dataDir }}</code>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { desktopApi } from '../webapi'
import { useAuthStore, useFolderStore } from '../stores'

declare global {
  interface Window {
    pywebview?: {
      api?: {
        select_run_base_dir?: () => Promise<string | null>
      }
    }
  }
}

const toast = useToast()
const authStore = useAuthStore()
const folderStore = useFolderStore()

const desktopMode = ref(false)
const needsSetup = ref(false)
const runBaseDirs = ref<string[]>([])
const dataDir = ref('')
const manualPath = ref('')
const picking = ref(false)
const saving = ref(false)
const openingDataDir = ref(false)

const hasPywebview = computed(() => Boolean(window.pywebview?.api?.select_run_base_dir))

const loadDesktopInfo = async () => {
  if (!authStore.authStatus?.desktop_mode) {
    desktopMode.value = false
    return
  }
  desktopMode.value = true
  try {
    const info = await desktopApi.getInfo()
    needsSetup.value = info.needs_setup
    runBaseDirs.value = info.run_base_dirs
    dataDir.value = info.data_dir
    if (info.run_base_dirs.length === 1) {
      manualPath.value = info.run_base_dirs[0]
    }
  } catch (error) {
    console.error('Failed to load desktop info:', error)
  }
}

const applyRunBaseDirs = async (dirs: string[]) => {
  saving.value = true
  try {
    const result = await desktopApi.putRunBaseDirs(dirs)
    runBaseDirs.value = result.run_base_dirs
    needsSetup.value = result.needs_setup
    await folderStore.fetchFolders()
    toast.add({
      severity: 'success',
      summary: 'Run base directory updated',
      life: 4000
    })
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Could not save run base directory',
      detail: error?.message ?? String(error),
      life: 8000
    })
  } finally {
    saving.value = false
  }
}

const pickFolder = async () => {
  const picker = window.pywebview?.api?.select_run_base_dir
  if (picker) {
    picking.value = true
    try {
      const chosen = await picker()
      if (chosen) {
        await applyRunBaseDirs([chosen])
      }
    } catch (error: any) {
      toast.add({
        severity: 'error',
        summary: 'Folder picker failed',
        detail: error?.message ?? String(error),
        life: 8000
      })
    } finally {
      picking.value = false
    }
    return
  }
  if (!manualPath.value.trim()) {
    toast.add({
      severity: 'info',
      summary: 'Enter a folder path',
      detail: 'Native folder picker is only available in the desktop app.',
      life: 6000
    })
  }
}

const saveManualPath = async () => {
  const path = manualPath.value.trim()
  if (!path) return
  await applyRunBaseDirs([path])
}

const openDataDir = async () => {
  openingDataDir.value = true
  try {
    await desktopApi.openDataDir()
  } catch (error: any) {
    toast.add({
      severity: 'error',
      summary: 'Could not open data folder',
      detail: error?.message ?? String(error),
      life: 8000
    })
  } finally {
    openingDataDir.value = false
  }
}

onMounted(() => {
  void loadDesktopInfo()
})

defineExpose({ loadDesktopInfo })
</script>

<style scoped>
.desktop-settings {
  margin-bottom: 1.5rem;
}

.desktop-settings__banner {
  margin-bottom: 1rem;
}

.desktop-settings__panel {
  padding: 1rem 1.25rem;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  background: #f8f9fa;
}

.desktop-settings__panel h3 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
}

.desktop-settings__hint {
  margin: 0 0 1rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.desktop-settings__dir-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.desktop-settings__dir-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
}

.desktop-settings__empty {
  margin: 0 0 1rem;
  color: #6c757d;
  font-style: italic;
}

.desktop-settings__manual {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.desktop-settings__input {
  width: 100%;
  max-width: 36rem;
}

.desktop-settings__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.desktop-settings__data-dir {
  margin: 1rem 0 0;
  font-size: 0.85rem;
  color: #6c757d;
}

.desktop-settings__data-dir code {
  font-size: 0.8rem;
}
</style>
