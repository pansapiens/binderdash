<template>
  <div class="user-menu">
    <Button
      type="button"
      icon="pi pi-user"
      :label="displayLabel"
      severity="secondary"
      size="small"
      class="user-menu__trigger"
      @click="toggle"
      aria-haspopup="true"
      aria-controls="user-menu-overlay"
    />
    <Menu
      id="user-menu-overlay"
      ref="menuRef"
      :model="items"
      :popup="true"
      :pt="userMenuPt"
    >
      <template #start>
        <div class="user-menu__card">
          <p v-if="displayName" class="user-menu__name">{{ displayName }}</p>
          <p v-if="email" class="user-menu__email">{{ email }}</p>
        </div>
      </template>
    </Menu>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Menu from 'primevue/menu'
import { useAuthStore } from '../stores'

const emit = defineEmits<{
  navigate: [view: 'account' | 'api-keys']
}>()

const authStore = useAuthStore()
const menuRef = ref<InstanceType<typeof Menu> | null>(null)

const displayName = computed(() => authStore.user?.display_name || authStore.user?.username || null)
const email = computed(() => authStore.user?.email || null)
const displayLabel = computed(() => authStore.user?.display_name || authStore.user?.username || 'Account')

function toggle(event: Event) {
  menuRef.value?.toggle(event)
}

const items = computed(() => [
  {
    label: 'Account',
    icon: 'pi pi-id-card',
    command: () => emit('navigate', 'account')
  },
  {
    label: 'API keys',
    icon: 'pi pi-key',
    visible: () => authStore.canManageApiKeys,
    command: () => emit('navigate', 'api-keys')
  },
  {
    separator: true
  },
  {
    label: 'Logout',
    icon: 'pi pi-sign-out',
    command: () => authStore.logout()
  }
])

// The Menu overlay teleports to <body> via Portal, so it never sits inside
// .app-header — App.vue's unscoped global CSS can't reach it via descendant
// selectors. Style it here through a `pt` root class instead.
const userMenuPt = {
  root: { class: 'user-menu-overlay' }
}
</script>

<style scoped>
.user-menu {
  display: inline-flex;
}

.user-menu__trigger {
  font-size: 0.8rem !important;
  padding: 0.45rem 0.85rem !important;
  flex-shrink: 0;
}
</style>

<style>
/* Unscoped: the Menu popup is teleported to <body>, outside this component's
   scoped-style boundary and outside .app-header, so it needs its own escape
   hatch from the global `[class*="p-"] { color: ... !important }` rule. */
.user-menu-overlay.p-menu {
  color: #495057 !important;
}

.user-menu-overlay .user-menu__card {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #dee2e6;
}

.user-menu-overlay .user-menu__name {
  margin: 0;
  font-weight: 600;
  color: #495057 !important;
}

.user-menu-overlay .user-menu__email {
  margin: 0.15rem 0 0 0;
  font-size: 0.85rem;
  color: #6c757d !important;
}

/* Header trigger inherits `color: white !important` from .app-header * —
   same escape hatch already used for the old logout button. */
.app-header .user-menu__trigger.p-button {
  color: #fff !important;
  background: rgba(0, 0, 0, 0.35) !important;
  border: 1px solid rgba(255, 255, 255, 0.55) !important;
}

.app-header .user-menu__trigger.p-button .p-button-icon,
.app-header .user-menu__trigger.p-button .p-button-label {
  color: #fff !important;
}

.app-header .user-menu__trigger.p-button:hover {
  background: rgba(0, 0, 0, 0.5) !important;
  border-color: rgba(255, 255, 255, 0.75) !important;
}
</style>
