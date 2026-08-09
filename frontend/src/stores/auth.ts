import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import { authApi, setCsrfToken, ApiError } from '../webapi'
import type { AuthUserDto } from '../webapi'

interface AuthStatus {
    auth_disabled: boolean
    desktop_mode?: boolean
    providers: {
        local: { enabled: boolean }
        pam: { enabled: boolean }
        google: { enabled: boolean; login_url: string }
    }
    api_keys: { enabled: boolean; reason?: string }
}

export const useAuthStore = defineStore('auth', () => {
    // State
    const user = ref<AuthUserDto | null>(null)
    const authStatus = ref<AuthStatus | null>(null)
    const isLoading = ref(false)
    const csrfToken = ref<string | null>(null)
    const authPollingInterval = ref<number | null>(null)

    // Getters
    const isAuthenticated = computed(() => !!user.value)
    const isAuthEnabled = computed(() => {
        // If authStatus is unknown, assume auth is enabled (show login by default)
        if (authStatus.value === null) {
            return true
        }
        return !authStatus.value.auth_disabled
    })
    const isAuthDisabled = computed(() => {
        // If authStatus is not loaded yet, assume auth is enabled (not disabled)
        if (authStatus.value === null) {
            return false
        }
        return authStatus.value.auth_disabled
    })
    const shouldShowLogin = computed(() => isAuthEnabled.value && !isAuthenticated.value)

    // Fail closed: hide the API-keys UI unless the server has confirmed it's enabled.
    const canManageApiKeys = computed(() => {
        return isAuthenticated.value && authStatus.value?.api_keys?.enabled === true
    })
    const canShowAccountUi = computed(() => isAuthenticated.value)

    // Actions
    const setCsrfTokenLocal = (token: string) => {
        csrfToken.value = token
        setCsrfToken(token) // Update webapi token
    }

    const clearAuth = () => {
        user.value = null
        csrfToken.value = null
        setCsrfToken(null) // Clear webapi token
        stopAuthPolling()
    }

    const setUser = (userData: AuthUserDto) => {
        user.value = userData
    }

    const setAuthStatus = (status: AuthStatus) => {
        authStatus.value = status
    }

    // Start polling for auth status every minute
    const startAuthPolling = () => {
        // Only start polling if auth is enabled and user is authenticated
        if (!isAuthEnabled.value || !isAuthenticated.value) {
            return
        }

        // Clear any existing interval
        stopAuthPolling()

        // Poll every minute (60000ms)
        authPollingInterval.value = window.setInterval(async () => {
            try {
                await authApi.getMe()
                // If successful, user is still authenticated
            } catch (error: unknown) {
                // If we get a 401, the session has expired - logout
                if (error instanceof ApiError && error.status === 401) {
                    console.log('Session expired, logging out...')
                    clearAuth()
                }
            }
        }, 60000)
    }

    // Stop polling for auth status
    const stopAuthPolling = () => {
        if (authPollingInterval.value) {
            clearInterval(authPollingInterval.value)
            authPollingInterval.value = null
        }
    }

    // Check auth status from server
    const checkAuthStatus = async () => {
        try {
            const status = await authApi.getStatus()
            setAuthStatus(status)
            return status
        } catch (error) {
            console.error('Failed to check auth status:', error)
            const fallback: AuthStatus = {
                auth_disabled: false,
                desktop_mode: false,
                providers: {
                    local: { enabled: false },
                    pam: { enabled: false },
                    google: { enabled: false, login_url: '/api/auth/google/login' }
                },
                // Fail closed on a status fetch failure — never assume keys are available.
                api_keys: { enabled: false, reason: 'status_unavailable' }
            }
            setAuthStatus(fallback)
            return fallback
        }
    }

    // Login
    const login = async (username: string, password: string): Promise<void> => {
        isLoading.value = true

        try {
            const data = await authApi.login(username, password)
            setUser(data.user)
            setCsrfTokenLocal(data.csrf_token)

            // Start polling after successful login
            startAuthPolling()

        } catch (error: any) {
            clearAuth()
            throw error
        } finally {
            isLoading.value = false
        }
    }

    // Get user info
    const fetchUserInfo = async (skipAuthCheck = false) => {
        // Skip auth check during initialization to allow session restoration
        if (!skipAuthCheck && !isAuthenticated.value) return

        try {
            const userData = await authApi.getMe()
            setUser(userData)

            // Start polling after successful user info fetch
            startAuthPolling()

        } catch (error: unknown) {
            console.error('Failed to fetch user info:', error)
            // If we get a 401, the session is invalid - clear auth
            if (error instanceof ApiError && error.status === 401) {
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
        try {
            // Check auth status first
            await checkAuthStatus()

            // Restore CSRF token from cookie on startup so POSTs can include header after reload
            try {
                const cookieEntry = document.cookie.split('; ').find(row => row.startsWith('binderdash_csrf='))
                if (cookieEntry) {
                    const token = decodeURIComponent(cookieEntry.split('=')[1])
                    if (token) {
                        setCsrfTokenLocal(token)
                    }
                }
            } catch (e) {
                // ignore cookie parsing issues
            }

            // If auth is disabled, no need to check session
            if (isAuthDisabled.value) {
                return
            }

            // Try to fetch user info to check if session is valid
            // Skip auth check during initialization to allow session restoration
            try {
                await fetchUserInfo(true)
            } catch (error) {
                // Session is invalid or doesn't exist, clear auth
                clearAuth()
            }
        } catch (error) {
            console.error('Auth initialization failed:', error)
            throw error
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
        authPollingInterval,

        // Getters
        isAuthenticated,
        isAuthEnabled,
        isAuthDisabled,
        shouldShowLogin,
        canLoadData,
        canManageApiKeys,
        canShowAccountUi,

        // Actions
        login,
        logout,
        initializeAuth,
        checkAuthStatus,
        fetchUserInfo,
        getCsrfHeader,
        clearAuth,
        startAuthPolling,
        stopAuthPolling,
    }
})
