<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h2>Login to Binderdash</h2>
        <p v-if="showPasswordLogin && showGoogleLogin">Choose a sign-in method</p>
        <p v-else-if="showPasswordLogin">Enter your credentials to access the application</p>
        <p v-else-if="showGoogleLogin">Sign in with your Google account</p>
        <p v-else class="p-error">No sign-in methods are enabled on the server.</p>
      </div>

      <form
        v-if="showPasswordLogin"
        @submit.prevent="handleLogin"
        class="login-form"
      >
        <div class="form-group">
          <label for="username">Username</label>
          <InputText
            id="username"
            v-model="loginForm.username"
            placeholder="Enter your username"
            :class="{ 'p-invalid': errors.username }"
            required
          />
          <small v-if="errors.username" class="p-error">{{ errors.username }}</small>
        </div>

        <div class="form-group">
          <label for="password">Password</label>
          <Password
            id="password"
            v-model="loginForm.password"
            placeholder="Enter your password"
            :class="{ 'p-invalid': errors.password }"
            :feedback="false"
            toggleMask
            required
          />
          <small v-if="errors.password" class="p-error">{{ errors.password }}</small>
        </div>

        <Button
          type="submit"
          label="Sign in"
          :loading="isLoading"
          :disabled="isLoading"
          class="login-button"
        />
      </form>

      <div v-if="showPasswordLogin && showGoogleLogin" class="divider">
        <span>or</span>
      </div>

      <div v-if="showGoogleLogin" class="google-block">
        <Button
          type="button"
          label="Sign in with Google"
          icon="pi pi-google"
          severity="secondary"
          class="google-button"
          @click="goGoogle"
        />
      </div>

      <div v-if="loginError" class="error-message">
        <Message severity="error" :closable="false">
          {{ loginError }}
        </Message>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const showPasswordLogin = computed(() => {
  const p = authStore.authStatus?.providers
  if (!p) return true
  return p.local.enabled || p.pam.enabled
})

const showGoogleLogin = computed(
  () => authStore.authStatus?.providers?.google?.enabled ?? false
)

const googleLoginHref = computed(
  () => authStore.authStatus?.providers?.google?.login_url ?? '/api/auth/google/login'
)

const loginForm = reactive({
  username: '',
  password: ''
})

const isLoading = ref(false)
const loginError = ref('')
const errors = reactive({
  username: '',
  password: ''
})

const validateForm = () => {
  errors.username = ''
  errors.password = ''

  if (!loginForm.username.trim()) {
    errors.username = 'Username is required'
    return false
  }

  if (!loginForm.password) {
    errors.password = 'Password is required'
    return false
  }

  return true
}

const handleLogin = async () => {
  if (!validateForm()) {
    return
  }

  isLoading.value = true
  loginError.value = ''

  try {
    await authStore.login(loginForm.username, loginForm.password)
  } catch (error: any) {
    loginError.value = error.message || 'Login failed. Please check your credentials.'
  } finally {
    isLoading.value = false
  }
}

const goGoogle = () => {
  window.location.href = googleLoginHref.value
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem;
}

.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  padding: 2.5rem;
  width: 100%;
  max-width: 400px;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-header h2 {
  color: #495057;
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
}

.login-header p {
  color: #6c757d;
  margin: 0;
  font-size: 0.95rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  color: #495057;
  font-weight: 500;
  font-size: 0.9rem;
}

.login-button {
  width: 100%;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 600;
  background: #667eea !important;
  border-color: #667eea !important;
  color: white !important;
}

.login-button:hover {
  background: #5a6fd8 !important;
  border-color: #5a6fd8 !important;
}

.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1.5rem 0;
  color: #6c757d;
  font-size: 0.85rem;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid #dee2e6;
}

.divider span {
  padding: 0 1rem;
}

.google-block {
  display: flex;
  flex-direction: column;
}

.google-button {
  width: 100%;
  justify-content: center;
}

.error-message {
  margin-top: 1.5rem;
}

:deep(.p-inputtext) {
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid #dee2e6;
  font-size: 0.95rem;
}

:deep(.p-inputtext:focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
}

:deep(.p-password) {
  width: 100%;
}

:deep(.p-password .p-inputtext) {
  width: 100%;
}

:deep(.p-password .p-password-toggle-mask) {
  color: #6c757d;
}

:deep(.p-password .p-password-toggle-mask:hover) {
  color: #495057;
}

:deep(.p-invalid) {
  border-color: #dc3545 !important;
}

:deep(.p-invalid:focus) {
  border-color: #dc3545 !important;
  box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25) !important;
}

.p-error {
  color: #dc3545;
  font-size: 0.85rem;
  margin-top: 0.25rem;
}
</style>
