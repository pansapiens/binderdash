import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'

// PrimeVue imports
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Toast from 'primevue/toast'
import 'primeicons/primeicons.css'

const app = createApp(App)

// Use PrimeVue
app.use(PrimeVue)
app.use(ToastService)

// Register global components
app.component('Toast', Toast)

app.mount('#app')
