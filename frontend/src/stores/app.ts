/**
 * App Store
 * Manages global application state
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Notification, AppState } from '../types/store'

export const useAppStore = defineStore('app', () => {
    // State
    const activeTab = ref('designs')
    const notifications = ref<Notification[]>([])
    const theme = ref<'light' | 'dark'>('light')
    const sidebarCollapsed = ref(false)

    // Getters
    const hasNotifications = computed(() => notifications.value.length > 0)

    const unreadNotifications = computed(() =>
        notifications.value.filter(n => !n.life || n.life > 0).length
    )

    // Actions
    const setActiveTab = (tab: string) => {
        activeTab.value = tab
    }

    const addNotification = (notification: Omit<Notification, 'id'>) => {
        const newNotification: Notification = {
            id: Date.now().toString(),
            ...notification
        }
        notifications.value.push(newNotification)

        // Auto-remove notification after its life time
        if (notification.life && notification.life > 0) {
            setTimeout(() => {
                removeNotification(newNotification.id)
            }, notification.life)
        }
    }

    const removeNotification = (id: string) => {
        const index = notifications.value.findIndex(n => n.id === id)
        if (index > -1) {
            notifications.value.splice(index, 1)
        }
    }

    const clearNotifications = () => {
        notifications.value = []
    }

    const toggleTheme = () => {
        theme.value = theme.value === 'light' ? 'dark' : 'light'
    }

    const toggleSidebar = () => {
        sidebarCollapsed.value = !sidebarCollapsed.value
    }

    const setTheme = (newTheme: 'light' | 'dark') => {
        theme.value = newTheme
    }

    const setSidebarCollapsed = (collapsed: boolean) => {
        sidebarCollapsed.value = collapsed
    }

    return {
        // State
        activeTab,
        notifications,
        theme,
        sidebarCollapsed,

        // Getters
        hasNotifications,
        unreadNotifications,

        // Actions
        setActiveTab,
        addNotification,
        removeNotification,
        clearNotifications,
        toggleTheme,
        toggleSidebar,
        setTheme,
        setSidebarCollapsed
    }
})
