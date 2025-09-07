import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import { authApi, setAuthToken } from '../webapi'

interface AuthStatus {
    auth_enabled: boolean
    disable_authentication: boolean
    local_users_count: number
}

interface User {
    username: string
}

interface LoginResponse {
    access_token: string
    token_type: string
}

export const useAuthStore = defineStore('auth', () => {
    // State
    const token = ref<string | null>(null)
    const user = ref<User | null>(null)
    const authStatus = ref<AuthStatus | null>(null)
    const isLoading = ref(false)

    // Getters
    const isAuthenticated = computed(() => !!token.value)
    const isAuthEnabled = computed(() => authStatus.value?.auth_enabled ?? false)
    const isAuthDisabled = computed(() => authStatus.value?.disable_authentication ?? false)
    const shouldShowLogin = computed(() => isAuthEnabled.value && !isAuthenticated.value)

    // Actions
    const setToken = (newToken: string) => {
        token.value = newToken
        setAuthToken(newToken) // Update webapi token
        // Store in localStorage for persistence
        localStorage.setItem('binderdash_token', newToken)
    }

    const clearToken = () => {
        token.value = null
        user.value = null
        setAuthToken(null) // Clear webapi token
        localStorage.removeItem('binderdash_token')
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
            setToken(data.access_token)

            // Get user info
            await fetchUserInfo()

        } catch (error: any) {
            clearToken()
            throw error
        } finally {
            isLoading.value = false
        }
    }

    // Get user info
    const fetchUserInfo = async () => {
        if (!token.value) return

        try {
            const userData = await authApi.getMe()
            setUser(userData)
        } catch (error: any) {
            console.error('Failed to fetch user info:', error)
            // If we get a 401, the token is invalid - clear it
            if (error?.response?.status === 401) {
                clearToken()
            }
            throw error
        }
    }

    // Logout
    const logout = () => {
        clearToken()
    }

    // Initialize auth state from localStorage
    const initializeAuth = async () => {
        // Check auth status first
        await checkAuthStatus()

        // If auth is disabled, no need to check token
        if (isAuthDisabled.value) {
            return
        }

        // Check for existing token
        const storedToken = localStorage.getItem('binderdash_token')
        if (storedToken) {
            token.value = storedToken
            setAuthToken(storedToken) // Update webapi token
            // Verify token is still valid by fetching user info
            try {
                await fetchUserInfo()
            } catch (error) {
                // Token is invalid, clear it
                clearToken()
            }
        }
    }

    // Check if data loading is allowed (either auth disabled or user authenticated)
    const canLoadData = computed(() => {
        return isAuthDisabled.value || isAuthenticated.value
    })

    // Get authorization header for API requests
    const getAuthHeader = () => {
        if (!token.value) return {}
        return { 'Authorization': `Bearer ${token.value}` }
    }

    return {
        // State
        token,
        user,
        authStatus,
        isLoading,

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
        getAuthHeader,
    }
})
