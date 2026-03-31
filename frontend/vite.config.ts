import path from 'node:path'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const molstarPackageRoot = path.resolve(__dirname, 'node_modules/molstar')

// https://vite.dev/config/
export default defineConfig({
    plugins: [
        vue(),
        vueDevTools(),
    ],
    resolve: {
        dedupe: ['molstar'],
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url)),
            // pdbe-molstar (CJS) and our code (ESM) must resolve molstar to the same on-disk package
            // so PluginStateObject types match (otherwise membrane StateTransforms throw "No suitable parent").
            molstar: molstarPackageRoot,
        },
    },
    optimizeDeps: {
        include: ['pdbe-molstar/lib/viewer'],
    },
    server: {
        proxy: {
            '/api': {
                target: process.env.API_BASE || 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
    build: {
        outDir: '../backend/static',
        emptyOutDir: true,
        rollupOptions: {
            output: {
                manualChunks(id) {
                    if (id.includes('/node_modules/molstar/')) {
                        return 'molstar'
                    }
                    return undefined
                },
            },
        },
    },
})
