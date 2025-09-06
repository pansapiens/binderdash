import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'

// PrimeVue imports
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import ToastService from 'primevue/toastservice'
import Toast from 'primevue/toast'
import 'primeicons/primeicons.css'

const app = createApp(App)

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

// Register global components
app.component('Toast', Toast)

app.mount('#app')
