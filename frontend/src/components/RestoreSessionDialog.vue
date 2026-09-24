<template>
  <Dialog
    :visible="visible"
    @update:visible="(v: boolean) => emit('update:visible', v)"
    modal
    header="Restore session from JSON"
    :style="{ width: '34rem' }"
  >
    <p class="restore-intro">
      Load a <code>binderdash_session.json</code> or <code>prepare_sequences.json</code> from a
      downloaded design bundle to put the interface back the way it was when the bundle was
      made. Runs that are no longer on this server are reported and skipped.
    </p>

    <input
      ref="fileInput"
      type="file"
      accept="application/json,.json"
      class="restore-file-input"
      @change="onFileChosen"
    />

    <Message v-if="error" severity="error" :closable="false" class="mt-3">{{ error }}</Message>

    <div v-if="outcomes.length > 0" class="restore-outcomes mt-3">
      <div v-for="outcome in outcomes" :key="outcome.section" class="restore-outcome">
        <i :class="iconFor(outcome.status)" aria-hidden="true" />
        <span class="restore-outcome__section">{{ outcome.section }}</span>
        <span class="restore-outcome__detail">{{ outcome.detail ?? outcome.status }}</span>
      </div>
    </div>

    <template #footer>
      <Button label="Close" severity="secondary" text @click="emit('update:visible', false)" />
      <Button
        label="Choose file…"
        icon="pi pi-upload"
        :loading="busy"
        @click="fileInput?.click()"
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useToast } from 'primevue/usetoast'
import { applySessionState, isSessionState } from '../session/sessionState'
import { applyPrepareState, isPrepareState } from '../session/prepareState'
import type { RestoreOutcome } from '../session/types'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ (e: 'update:visible', value: boolean): void }>()

const toast = useToast()
const fileInput = ref<HTMLInputElement | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)
const outcomes = ref<RestoreOutcome[]>([])

function iconFor(status: RestoreOutcome['status']): string {
  if (status === 'applied') return 'pi pi-check-circle restore-icon--ok'
  if (status === 'partial') return 'pi pi-exclamation-triangle restore-icon--warn'
  return 'pi pi-minus-circle restore-icon--skip'
}

async function onFileChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  busy.value = true
  error.value = null
  outcomes.value = []
  try {
    const payload = JSON.parse(await file.text())
    if (isSessionState(payload)) {
      outcomes.value = await applySessionState(payload)
    } else if (isPrepareState(payload)) {
      outcomes.value = applyPrepareState(payload)
    } else {
      throw new Error(
        'This file is not a Binderdash session or prepare-sequences file. Look for ' +
          'binderdash_session.json or prepare_sequences.json inside a design bundle.'
      )
    }
    toast.add({
      severity: 'success',
      summary: 'Session restored',
      detail: `${outcomes.value.filter((o) => o.status !== 'skipped').length} section(s) applied`,
      life: 4000
    })
  } catch (err: any) {
    error.value = err?.message ?? 'Could not read that file.'
  } finally {
    busy.value = false
    // Allow re-picking the same file after a failed attempt.
    input.value = ''
  }
}
</script>

<style scoped>
.restore-intro {
  margin: 0 0 0.5rem 0;
  font-size: 0.9rem;
  line-height: 1.5;
}

.restore-file-input {
  display: none;
}

.restore-outcomes {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.restore-outcome {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.restore-outcome__section {
  font-weight: 600;
  min-width: 9rem;
}

.restore-outcome__detail {
  color: var(--p-text-muted-color, #6b7280);
}

.restore-icon--ok {
  color: var(--p-green-500, #22c55e);
}

.restore-icon--warn {
  color: var(--p-orange-500, #f59e0b);
}

.restore-icon--skip {
  color: var(--p-text-muted-color, #9ca3af);
}
</style>
