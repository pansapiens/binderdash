<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import Toast from 'primevue/toast'
import Button from 'primevue/button'
import RunsView from './components/DesignsView.vue'
import PlotsView from './components/PlotsView.vue'
import FolderBrowser from './components/FolderBrowser.vue'
import LoginView from './components/LoginView.vue'
import { useDesignsStore, usePlotsStore, useRunsStore, useAuthStore } from './stores'

// Use Pinia stores
const designsStore = useDesignsStore()
const plotsStore = usePlotsStore()
const runsStore = useRunsStore()
const authStore = useAuthStore()

// Create refs to components so we can call their methods
const runsViewRef = ref<any>(null)
const plotsViewRef = ref<any>(null)

// Handle runs scanned event from FolderBrowser
const handleRunsScanned = (): void => {
  // Refresh designs data when new runs are scanned
  designsStore.fetchDesigns()
}

// Handle tab change to refresh data when switching to Plots tab
const handleTabChange = (event: any): void => {
  // Check if the Plots tab is being activated (index 1)
  if (event.index === 1) {
    // Refresh runs data for plots
    runsStore.fetchRuns()
  }
}

// Track if authentication has been initialized
const authInitialized = ref(false)

// Initialize authentication on app start
onMounted(async () => {
  await authStore.initializeAuth()
  authInitialized.value = true
})

// Computed property to check if we should show the main app
const shouldShowMainApp = computed(() => {
  // Show main app if auth is disabled or user is authenticated
  return authStore.isAuthDisabled || authStore.isAuthenticated
})

// Computed property to check if we should show loading state
const shouldShowLoading = computed(() => {
  // Show loading if auth hasn't been initialized yet
  return !authInitialized.value
})
</script>

<template>
  <div id="app">
    <!-- Show loading state while authentication is being initialized -->
    <div v-if="shouldShowLoading" class="loading-container">
      <div class="loading-content">
        <i class="pi pi-spinner pi-spin" style="font-size: 2rem; color: #667eea;"></i>
        <p>Initializing...</p>
      </div>
    </div>
    
    <!-- Show login page if authentication is required and user is not authenticated -->
    <LoginView v-else-if="authStore.shouldShowLogin" />
    
    <!-- Show main app if authentication is disabled or user is authenticated -->
    <template v-else-if="shouldShowMainApp">
      <header class="app-header">
        <!-- Show logout button if authenticated -->
        <Button 
          v-if="authStore.isAuthenticated"
          label="Logout" 
          severity="primary" 
          size="small" 
          @click="authStore.logout"
          class="logout-button"
        />
        <div class="banner-overlay">
          <h1>Binderdash</h1>
          <p>De novo protein binder design results viewer</p>
        </div>
      </header>

      <main class="app-main">
        <TabView @tab-change="handleTabChange">
          <TabPanel header="Designs" value="designs">
            <RunsView ref="runsViewRef" />
          </TabPanel>
          <TabPanel header="Plots" value="plots">
            <PlotsView ref="plotsViewRef" />
          </TabPanel>
          <TabPanel header="Select Projects/Runs" value="folders">
            <FolderBrowser @runs-scanned="handleRunsScanned" />
          </TabPanel>
        </TabView>
      </main>
    </template>

    <Toast />
  </div>
</template>

<style>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  min-height: 100vh;
  background-color: #f8f9fa;
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}

body {
  margin: 0 !important;
  padding: 0 !important;
  width: 100% !important;
  max-width: none !important;
}

.app-header {
  background-image: url('./assets/banner.webp');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  position: relative;
  padding: 1rem 2rem;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  width: 100%;
  box-sizing: border-box;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.app-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(102, 51, 153, 0.7); /* Purple filter at 70% opacity */
  z-index: 1;
}

.banner-overlay {
  position: relative;
  z-index: 2;
  color: white;
}

.banner-overlay h1 {
  margin: 0;
  font-size: 2rem;
  font-weight: 600;
  color: white;
  text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.banner-overlay p {
  margin: 0.5rem 0 0 0;
  opacity: 0.9;
  font-size: 1rem;
  color: white;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.logout-button {
  position: absolute !important;
  top: 1rem;
  right: 1rem;
  z-index: 1000;
  font-size: 0.8rem !important;
  padding: 0.4rem 0.8rem !important;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f8f9fa;
}

.loading-content {
  text-align: center;
  color: #6c757d;
}

.loading-content p {
  margin: 1rem 0 0 0;
  font-size: 1rem;
}

.app-main {
  padding: 2rem;
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  box-sizing: border-box !important;
}

/* Global text color overrides - HIGH PRIORITY */
* {
  color: #495057 !important;
}

/* Ensure all text elements have proper contrast */
p, span, div, label, input, textarea, select, button, a, h1, h2, h3, h4, h5, h6 {
  color: #495057 !important;
}

/* App header override - keep white text on dark background */
.app-header, .app-header * {
  color: white !important;
}

.banner-overlay, .banner-overlay * {
  color: white !important;
}

.banner-overlay h1, .banner-overlay p {
  color: white !important;
}

/* PrimeVue TabView - COMPREHENSIVE OVERRIDE */
.p-tabview {
  width: 100% !important;
  max-width: 100% !important;
}

.p-tabview .p-tabview-nav {
  border-bottom: 2px solid #e9ecef !important;
  background: white !important;
  border-radius: 8px 8px 0 0 !important;
}

.p-tabview .p-tabview-nav .p-tabview-nav-link {
  padding: 1rem 1.5rem !important;
  font-weight: 500 !important;
  color: #495057 !important;
  background: #f8f9fa !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  transition: all 0.2s ease !important;
}

.p-tabview .p-tabview-nav .p-tabview-nav-link:hover {
  background: #e9ecef !important;
  color: #212529 !important;
}

.p-tabview .p-tabview-nav .p-tabview-nav-link.p-highlight {
  background: white !important;
  color: #667eea !important;
  border-bottom: 2px solid #667eea !important;
  font-weight: 600 !important;
}

.p-tabview .p-tabview-panels {
  background: white !important;
  border-radius: 0 0 8px 8px !important;
  padding: 2rem !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
}

.p-tabview .p-tabview-panels .p-tabview-panel {
  padding: 0 !important;
  width: 100% !important;
}

.p-tabview .p-tabview-panels {
  background: white !important;
  border-radius: 0 0 8px 8px !important;
  padding: 2rem !important;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
  width: 100% !important;
  box-sizing: border-box !important;
}

/* Button styling - COMPREHENSIVE OVERRIDE */
.p-button {
  color: #495057 !important;
  background: #ffffff !important;
  border: 1px solid #dee2e6 !important;
  font-weight: 500 !important;
}

.p-button:hover {
  background: #f8f9fa !important;
  border-color: #adb5bd !important;
  color: #212529 !important;
}

.p-button.p-button-secondary {
  background: #6c757d !important;
  border-color: #6c757d !important;
  color: white !important;
}

.p-button.p-button-secondary:hover {
  background: #5a6268 !important;
  border-color: #545b62 !important;
}

.p-button.p-button-danger {
  background: #dc3545 !important;
  border-color: #dc3545 !important;
  color: white !important;
}

.p-button.p-button-danger:hover {
  background: #c82333 !important;
  border-color: #bd2130 !important;
}

/* DataTable styling - COMPREHENSIVE OVERRIDE */
.p-datatable .p-datatable-thead > tr > th {
  background: #f8f9fa !important;
  color: #495057 !important;
  font-weight: 600 !important;
  border-bottom: 1px solid #dee2e6 !important;
}

.p-datatable .p-datatable-tbody > tr > td {
  color: #495057 !important;
  border-bottom: 1px solid #f1f3f4 !important;
}

.p-datatable .p-datatable-tbody > tr:hover > td {
  background: #f8f9fa !important;
}

/* TreeTable styling - COMPREHENSIVE OVERRIDE */
.p-treetable .p-treetable-thead > tr > th {
  background: #f8f9fa !important;
  color: #495057 !important;
  font-weight: 600 !important;
  border-bottom: 1px solid #dee2e6 !important;
}

.p-treetable .p-treetable-tbody > tr > td {
  color: #495057 !important;
  border-bottom: 1px solid #f1f3f4 !important;
}

.p-treetable .p-treetable-tbody > tr:hover > td {
  background: #f8f9fa !important;
}

/* Pagination styling - COMPREHENSIVE OVERRIDE */
.p-paginator {
  background: #f8f9fa !important;
  border-top: 1px solid #dee2e6 !important;
}

.p-paginator .p-paginator-current {
  color: #495057 !important;
  font-weight: 500 !important;
}

.p-paginator .p-paginator-pages .p-paginator-page {
  color: #495057 !important;
  background: white !important;
  border: 1px solid #dee2e6 !important;
}

.p-paginator .p-paginator-pages .p-paginator-page:hover {
  background: #e9ecef !important;
  color: #212529 !important;
}

.p-paginator .p-paginator-pages .p-paginator-page.p-highlight {
  background: #667eea !important;
  color: white !important;
  border-color: #667eea !important;
}

/* Dropdown styling - COMPREHENSIVE OVERRIDE */
.p-dropdown {
  background: white !important;
  border: 1px solid #dee2e6 !important;
  color: #495057 !important;
}

.p-dropdown:hover {
  border-color: #adb5bd !important;
}

.p-dropdown .p-dropdown-trigger {
  color: #6c757d !important;
}

.p-dropdown .p-dropdown-label {
  color: #495057 !important;
}

/* Tag styling - COMPREHENSIVE OVERRIDE */
.p-tag {
  font-weight: 500 !important;
}

.p-tag.p-tag-success {
  background: #d4edda !important;
  color: #155724 !important;
  border: 1px solid #c3e6cb !important;
}

.p-tag.p-tag-info {
  background: #d1ecf1 !important;
  color: #0c5460 !important;
  border: 1px solid #bee5eb !important;
}

.p-tag.p-tag-warning {
  background: #fff3cd !important;
  color: #856404 !important;
  border: 1px solid #ffeaa7 !important;
}

/* Badge styling - COMPREHENSIVE OVERRIDE */
.p-badge {
  font-weight: 500 !important;
}

.p-badge.p-badge-info {
  background: #17a2b8 !important;
  color: white !important;
}

/* Toast styling - COMPREHENSIVE OVERRIDE */
.p-toast .p-toast-message {
  border-radius: 6px !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
}

.p-toast .p-toast-message .p-toast-message-content {
  padding: 1rem !important;
}

.p-toast .p-toast-message .p-toast-summary {
  font-weight: 600 !important;
  color: #495057 !important;
}

.p-toast .p-toast-message .p-toast-detail {
  color: #6c757d !important;
  margin-top: 0.25rem !important;
}

/* Chip styling - COMPREHENSIVE OVERRIDE */
.p-chip {
  background: #e9ecef !important;
  color: #495057 !important;
  border: 1px solid #dee2e6 !important;
}

.p-chip .p-chip-text {
  color: #495057 !important;
}

/* Input styling - COMPREHENSIVE OVERRIDE */
.p-inputtext {
  color: #495057 !important;
  background: white !important;
  border: 1px solid #dee2e6 !important;
}

.p-inputtext:focus {
  border-color: #667eea !important;
  box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25) !important;
}

/* Label styling - COMPREHENSIVE OVERRIDE */
.p-component {
  color: #495057 !important;
}

/* Override any remaining light text */
.p-component * {
  color: #495057 !important;
}

/* Ensure icons don't inherit text color */
.pi {
  color: inherit !important;
}

/* Override any PrimeVue default text colors */
[class*="p-"] {
  color: #495057 !important;
}

/* Specific overrides for common PrimeVue text elements */
.p-component, .p-component * {
  color: #495057 !important;
}

/* Force readable text on all interactive elements */
button, input, select, textarea, a, .p-button, .p-dropdown, .p-inputtext {
  color: #495057 !important;
}

/* Override any remaining light grey text */
*[style*="color: rgb(108, 117, 125)"], 
*[style*="color: #6c757d"],
*[style*="color: rgb(173, 181, 189)"],
*[style*="color: #adb5bd"] {
  color: #495057 !important;
}

/* Comprehensive checkbox styling for TreeTable */
.p-treetable .p-checkbox {
  display: inline-block !important;
  visibility: visible !important;
  opacity: 1 !important;
  margin-right: 0.5rem !important;
  position: relative !important;
  z-index: 1 !important;
}

.p-treetable .p-checkbox .p-checkbox-box {
  display: inline-block !important;
  visibility: visible !important;
  opacity: 1 !important;
  width: 16px !important;
  height: 16px !important;
  border: 2px solid #dee2e6 !important;
  background: white !important;
  border-radius: 3px !important;
  position: relative !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
}

.p-treetable .p-checkbox .p-checkbox-box:hover {
  border-color: #667eea !important;
  background: #f8f9fa !important;
}

.p-treetable .p-checkbox .p-checkbox-box.p-highlight {
  background: #667eea !important;
  border-color: #667eea !important;
}

.p-treetable .p-checkbox .p-checkbox-box.p-highlight .p-checkbox-icon {
  color: white !important;
  font-size: 12px !important;
  font-weight: bold !important;
}

.p-treetable .p-checkbox .p-checkbox-box .p-checkbox-icon {
  display: block !important;
  visibility: visible !important;
  opacity: 1 !important;
  color: white !important;
  font-size: 12px !important;
  font-weight: bold !important;
  text-align: center !important;
  line-height: 12px !important;
}

/* Ensure checkbox is clickable */
.p-treetable .p-checkbox input[type="checkbox"] {
  position: absolute !important;
  opacity: 0 !important;
  pointer-events: none !important;
}

/* TreeTable row styling to accommodate checkboxes */
.p-treetable .p-treetable-tbody > tr > td:first-child {
  padding-left: 0.5rem !important;
  position: relative !important;
}

.p-treetable .p-treetable-tbody > tr > td:first-child .folder-node {
  display: flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
  padding-left: 0 !important;
}

/* Button styling improvements for better visibility */
.p-button {
  color: #495057 !important;
  background: #ffffff !important;
  border: 1px solid #dee2e6 !important;
  font-weight: 500 !important;
  padding: 0.5rem 1rem !important;
  border-radius: 6px !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 0.5rem !important;
}

.p-button:hover {
  background: #f8f9fa !important;
  border-color: #adb5bd !important;
  color: #212529 !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
}

.p-button:disabled {
  opacity: 0.6 !important;
  cursor: not-allowed !important;
  transform: none !important;
  box-shadow: none !important;
}

/* Toast styling improvements - GLOBAL OVERRIDE */
.p-toast {
  opacity: 1 !important;
}

.p-toast .p-toast-message {
  background: white !important;
  border: 1px solid #e9ecef !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
  opacity: 1 !important;
  color: #495057 !important;
}

.p-toast .p-toast-message-content {
  background: white !important;
  opacity: 1 !important;
  color: #495057 !important;
}

.p-toast .p-toast-message-text {
  color: #495057 !important;
  opacity: 1 !important;
}

.p-toast .p-toast-message-icon {
  opacity: 1 !important;
}

.p-toast .p-toast-icon-close {
  opacity: 1 !important;
  color: #6c757d !important;
}

.p-toast .p-toast-icon-close:hover {
  color: #495057 !important;
}

/* Toast severity-specific styling */
.p-toast .p-toast-message.p-toast-message-success {
  background: #d4edda !important;
  border-color: #c3e6cb !important;
  color: #155724 !important;
}

.p-toast .p-toast-message.p-toast-message-error {
  background: #f8d7da !important;
  border-color: #f5c6cb !important;
  color: #721c24 !important;
}

.p-toast .p-toast-message.p-toast-message-warn {
  background: #fff3cd !important;
  border-color: #ffeaa7 !important;
  color: #856404 !important;
}

.p-toast .p-toast-message.p-toast-message-info {
  background: #d1ecf1 !important;
  border-color: #bee5eb !important;
  color: #0c5460 !important;
}
</style>
