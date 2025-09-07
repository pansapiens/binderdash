import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import { authApi, setCsrfToken } from '../webapi'

interface AuthStatus {
    auth_enabled: boolean
    disable_authentication: boolean
    local_users_count: number
}

interface User {
    username: string
}

interface LoginResponse {
    message: string
    user: {
        username: string
    }
    csrf_token: string
}

export const useAuthStore = defineStore('auth', () => {
    // State
    const user = ref<User | null>(null)
    const authStatus = ref<AuthStatus | null>(null)
    const isLoading = ref(false)
    const csrfToken = ref<string | null>(null)

    // Getters
    const isAuthenticated = computed(() => !!user.value)
    const isAuthEnabled = computed(() => authStatus.value?.auth_enabled ?? false)
    const isAuthDisabled = computed(() => authStatus.value?.disable_authentication ?? false)
    const shouldShowLogin = computed(() => isAuthEnabled.value && !isAuthenticated.value)

    // Actions
    const setCsrfTokenLocal = (token: string) => {
        csrfToken.value = token
        setCsrfToken(token) // Update webapi token
    }

    const clearAuth = () => {
        user.value = null
        csrfToken.value = null
        setCsrfToken(null) // Clear webapi token
    }

    const setUser = (userData: User) => {
        user.value = userData
    }

    const setAuthStatus = (status: AuthStatus) => {
        authStatus.value = status
    }

    // Check auth status from server
    const checkAuthStatus = async () => {
        try {
            const status = await authApi.getStatus()
            setAuthStatus(status)
            return status
        } catch (error) {
            console.error('Failed to check auth status:', error)
        }
        return null
    }

    // Login
    const login = async (username: string, password: string): Promise<void> => {
        isLoading.value = true

        try {
            const data = await authApi.login(username, password)
            setUser(data.user)
            setCsrfTokenLocal(data.csrf_token)

        } catch (error: any) {
            clearAuth()
            throw error
        } finally {
            isLoading.value = false
        }
    }

    // Get user info
    const fetchUserInfo = async () => {
        if (!isAuthenticated.value) return

        try {
            const userData = await authApi.getMe()
            setUser(userData)
        } catch (error: any) {
            console.error('Failed to fetch user info:', error)
            // If we get a 401, the session is invalid - clear auth
            if (error?.response?.status === 401) {
                clearAuth()
            }
            throw error
        }
    }

    // Logout
    const logout = async () => {
        try {
            await authApi.logout()
        } catch (error) {
            console.error('Logout error:', error)
        } finally {
            clearAuth()
        }
    }

    // Initialize auth state
    const initializeAuth = async () => {
        // Check auth status first
        await checkAuthStatus()

        // If auth is disabled, no need to check session
        if (isAuthDisabled.value) {
            return
        }

        // Try to fetch user info to check if session is valid
        try {
            await fetchUserInfo()
        } catch (error) {
            // Session is invalid or doesn't exist, clear auth
            clearAuth()
        }
    }

    // Check if data loading is allowed (either auth disabled or user authenticated)
    const canLoadData = computed(() => {
        return isAuthDisabled.value || isAuthenticated.value
    })

    // Get CSRF token for API requests
    const getCsrfHeader = () => {
        if (!csrfToken.value) return {}
        return { 'X-CSRF-Token': csrfToken.value }
    }

    return {
        // State
        user,
        authStatus,
        isLoading,
        csrfToken,

        // Getters
        isAuthenticated,
        isAuthEnabled,
        isAuthDisabled,
        shouldShowLogin,
        canLoadData,

        // Actions
        login,
        logout,
        initializeAuth,
        checkAuthStatus,
        getCsrfHeader,
        clearAuth,
    }
})
