<template>
  <div class="api-keys-view">
    <Button
      label="Back to Designs"
      icon="pi pi-arrow-left"
      severity="secondary"
      text
      class="api-keys-view__back"
      @click="emit('back')"
    />

    <Panel v-if="issuedKey" header="New API key created" class="api-keys-view__issued">
      <Message severity="warn" :closable="false">
        Copy this key now — it will not be shown again.
      </Message>
      <div class="api-keys-view__secret-row">
        <code class="api-keys-view__secret" ref="secretCodeRef">{{ issuedKey.key }}</code>
        <Button icon="pi pi-copy" label="Copy" size="small" @click="copySecret" />
        <Button icon="pi pi-times" label="Dismiss" size="small" severity="secondary" text @click="issuedKey = null" />
      </div>

      <Button
        :label="curlExpanded ? 'Hide curl example' : 'Show curl example'"
        :icon="curlExpanded ? 'pi pi-chevron-up' : 'pi pi-chevron-down'"
        text
        size="small"
        class="api-keys-view__curl-toggle"
        @click="curlExpanded = !curlExpanded"
      />
      <pre v-if="curlExpanded" class="api-keys-view__curl">{{ curlSnippet }}</pre>
    </Panel>

    <Panel header="Create a new key">
      <div class="api-keys-view__create-row">
        <InputText
          v-model="newKeyName"
          placeholder="Key name"
          class="api-keys-view__create-name"
          @keyup.enter="createKey"
        />
        <Select
          v-model="newKeyExpiry"
          :options="expiryOptions"
          option-label="label"
          option-value="value"
          class="api-keys-view__create-expiry"
        />
        <Button
          label="Create"
          icon="pi pi-plus"
          :loading="creating"
          :disabled="!newKeyName.trim()"
          @click="createKey"
        />
      </div>
    </Panel>

    <Panel header="Your API keys">
      <Message v-if="listError" severity="error" :closable="false">
        {{ listError }}
      </Message>

      <DataTable
        :value="keys"
        data-key="id"
        stripedRows
        :loading="loading"
        :rowHover="true"
      >
        <template #empty>
          <div class="api-keys-view__empty">
            <i class="pi pi-key" aria-hidden="true" />
            <p>No API keys yet.</p>
          </div>
        </template>
        <Column field="name" header="Name" />
        <Column field="key_prefix" header="Prefix">
          <template #body="{ data }">
            <code>{{ data.key_prefix }}…</code>
          </template>
        </Column>
        <Column header="Created">
          <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
        </Column>
        <Column header="Last used">
          <template #body="{ data }">{{ data.last_used_at ? formatDate(data.last_used_at) : '—' }}</template>
        </Column>
        <Column header="Expires">
          <template #body="{ data }">{{ data.expires_at ? formatDate(data.expires_at) : 'Never' }}</template>
        </Column>
        <Column header="Status">
          <template #body="{ data }">
            <Tag :value="data.status" :severity="statusSeverity(data.status)" />
          </template>
        </Column>
        <Column header="Actions">
          <template #body="{ data }">
            <Button
              v-if="data.status === 'active'"
              icon="pi pi-trash"
              severity="danger"
              text
              v-tooltip.top="'Revoke'"
              :loading="revokingId === data.id"
              @click="confirmRevoke(data)"
            />
          </template>
        </Column>
      </DataTable>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Panel from 'primevue/panel'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { apiKeysApi, parseApiTimestamp } from '../webapi'
import type { ApiKeyDto, CreatedApiKeyDto } from '../webapi'

const emit = defineEmits<{
  back: []
}>()

const toast = useToast()

const keys = ref<ApiKeyDto[]>([])
const loading = ref(false)
const listError = ref<string | null>(null)

const expiryOptions = [
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
  { label: '365 days', value: 365 },
  { label: 'Never', value: null }
]

const newKeyName = ref('')
const newKeyExpiry = ref<number | null>(90)
const creating = ref(false)

const issuedKey = ref<CreatedApiKeyDto | null>(null)
const curlExpanded = ref(false)
const secretCodeRef = ref<HTMLElement | null>(null)

const revokingId = ref<number | null>(null)

const curlSnippet = computed(() => {
  if (!issuedKey.value) return ''
  const origin = window.location.origin
  return `curl -H "X-Binderdash-Api-Key: ${issuedKey.value.key}" ${origin}/api/runs`
})

function formatDate(value: string): string {
  const d = parseApiTimestamp(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

function statusSeverity(status: ApiKeyDto['status']): 'success' | 'warn' | 'danger' {
  if (status === 'active') return 'success'
  if (status === 'expired') return 'warn'
  return 'danger'
}

async function loadKeys() {
  loading.value = true
  listError.value = null
  try {
    const response = await apiKeysApi.list()
    keys.value = response.keys
  } catch (error) {
    console.error('Failed to list API keys:', error)
    listError.value = error instanceof Error ? error.message : 'Failed to load API keys'
  } finally {
    loading.value = false
  }
}

async function createKey() {
  const name = newKeyName.value.trim()
  if (!name) return
  creating.value = true
  try {
    const created = await apiKeysApi.create(name, newKeyExpiry.value)
    issuedKey.value = created
    curlExpanded.value = false
    newKeyName.value = ''
    newKeyExpiry.value = 90
    await loadKeys()
    toast.add({
      severity: 'success',
      summary: 'Key created',
      detail: `API key "${created.name}" created.`,
      life: 4000
    })
  } catch (error) {
    console.error('Failed to create API key:', error)
    toast.add({
      severity: 'error',
      summary: 'Create failed',
      detail: error instanceof Error ? error.message : 'Request failed',
      life: 5000
    })
  } finally {
    creating.value = false
  }
}

async function confirmRevoke(key: ApiKeyDto) {
  // No ConfirmationService registered in the app — plain window.confirm matches
  // the pattern already used for saved-set deletion (SavedSetsList.vue).
  if (!window.confirm(`Revoke API key "${key.name}"? Any client using it will stop working immediately.`)) return
  revokingId.value = key.id
  try {
    await apiKeysApi.revoke(key.id)
    await loadKeys()
    toast.add({
      severity: 'success',
      summary: 'Revoked',
      detail: `API key "${key.name}" revoked.`,
      life: 4000
    })
  } catch (error) {
    console.error('Failed to revoke API key:', error)
    toast.add({
      severity: 'error',
      summary: 'Revoke failed',
      detail: error instanceof Error ? error.message : 'Request failed',
      life: 5000
    })
  } finally {
    revokingId.value = null
  }
}

async function copySecret() {
  const secret = issuedKey.value?.key
  if (!secret) return

  // navigator.clipboard is undefined outside a secure context (e.g. served over
  // plain HTTP on the LAN), so fall back to selecting the text for manual copy.
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(secret)
      toast.add({ severity: 'success', summary: 'Copied', detail: 'API key copied to clipboard.', life: 3000 })
      return
    } catch (error) {
      console.error('Clipboard write failed:', error)
    }
  }

  const el = secretCodeRef.value
  if (el) {
    const range = document.createRange()
    range.selectNodeContents(el)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
  }
  toast.add({
    severity: 'info',
    summary: 'Select and copy',
    detail: 'Clipboard access is unavailable here — the key text has been selected for you to copy manually.',
    life: 6000
  })
}

onMounted(loadKeys)
</script>

<style scoped>
.api-keys-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.api-keys-view__back {
  align-self: flex-start;
}

.api-keys-view__secret-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}

.api-keys-view__secret {
  flex: 1 1 auto;
  min-width: 16rem;
  padding: 0.5rem 0.75rem;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  word-break: break-all;
}

.api-keys-view__curl-toggle {
  margin-top: 0.5rem;
}

.api-keys-view__curl {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.api-keys-view__create-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.api-keys-view__create-name {
  flex: 1 1 16rem;
}

.api-keys-view__create-expiry {
  flex: 0 0 10rem;
}

.api-keys-view__empty {
  padding: 1.5rem;
  text-align: center;
  color: #6c757d;
}
</style>
