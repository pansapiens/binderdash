<template>
  <div class="account-view">
    <Button
      label="Back to Designs"
      icon="pi pi-arrow-left"
      severity="secondary"
      text
      class="account-view__back"
      @click="emit('back')"
    />

    <Panel header="Account">
      <div class="account-view__rows">
        <div v-if="user?.picture_url && !pictureFailed" class="account-view__row account-view__row--picture">
          <img
            :src="user.picture_url"
            alt="Profile picture"
            class="account-view__picture"
            @error="onPictureError"
          />
        </div>

        <div v-if="displayName" class="account-view__row">
          <span class="account-view__label">Name</span>
          <span class="account-view__value">{{ displayName }}</span>
        </div>

        <div v-if="user?.email" class="account-view__row">
          <span class="account-view__label">Email</span>
          <span class="account-view__value">{{ user.email }}</span>
        </div>

        <div v-if="user?.username" class="account-view__row">
          <span class="account-view__label">Username</span>
          <span class="account-view__value">{{ user.username }}</span>
        </div>

        <div v-if="user?.provider" class="account-view__row">
          <span class="account-view__label">Sign-in provider</span>
          <Tag :value="user.provider" severity="info" />
        </div>

        <div v-if="user?.auth_method" class="account-view__row">
          <span class="account-view__label">This session</span>
          <Tag :value="authMethodLabel" severity="secondary" />
        </div>

        <div v-if="user?.is_admin" class="account-view__row">
          <span class="account-view__label">Role</span>
          <Tag value="Admin" severity="warn" />
        </div>

        <div v-if="lastLoginDisplay" class="account-view__row">
          <span class="account-view__label">Last sign-in</span>
          <span class="account-view__value">{{ lastLoginDisplay }}</span>
        </div>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Panel from 'primevue/panel'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useAuthStore } from '../stores'
import { parseApiTimestamp } from '../webapi'

const emit = defineEmits<{
  back: []
}>()

const authStore = useAuthStore()
const pictureFailed = ref(false)

const user = computed(() => authStore.user)

const displayName = computed(() => user.value?.display_name || null)

const authMethodLabel = computed(() => {
  return user.value?.auth_method === 'api_key' ? 'API key' : 'Session'
})

const lastLoginDisplay = computed(() => {
  const raw = user.value?.last_login_at
  if (!raw) return null
  const d = parseApiTimestamp(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString()
})

function onPictureError() {
  pictureFailed.value = true
}
</script>

<style scoped>
.account-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 32rem;
}

.account-view__back {
  align-self: flex-start;
}

.account-view__rows {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.account-view__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.account-view__row--picture {
  justify-content: center;
}

.account-view__label {
  font-weight: 600;
  color: #495057;
}

.account-view__value {
  color: #495057;
}

.account-view__picture {
  width: 4rem;
  height: 4rem;
  border-radius: 50%;
  object-fit: cover;
}
</style>
