import './assets/main.css'

import { createApp } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import App from './App.vue'
import { hydratePersistedState } from './persistence/hydrate'

// PrimeVue imports
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import ToastService from 'primevue/toastservice'
import Toast from 'primevue/toast'
import Password from 'primevue/password'
import Tooltip from 'primevue/tooltip'
import 'primeicons/primeicons.css'

const app = createApp(App)

// Use Pinia
const pinia = createPinia()
setActivePinia(pinia)
app.use(pinia)

// Use PrimeVue
app.use(PrimeVue, {
    // Default theme configuration
    theme: {
        preset: Aura,
        options: {
            prefix: 'p',
            //darkModeSelector: 'system',
            darkModeSelector: false || 'none',
            cssLayer: false
        }
    }
});

app.use(ToastService)

app.directive('tooltip', Tooltip)

// Register global components
app.component('Toast', Toast)
app.component('Password', Password)

void hydratePersistedState().finally(() => {
    app.mount('#app')
})
