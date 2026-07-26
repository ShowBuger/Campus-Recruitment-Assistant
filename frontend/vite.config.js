import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8765',
      '/static': 'http://localhost:8765',
      '/guide': 'http://localhost:8765'
    }
  },
  base: '/dist/',
  build: {
    // Keep the build artifact inside the project so local startup and the
    // deployment script use the same output. setup.sh copies static/ to nginx.
    outDir: '../static/dist',
    emptyOutDir: true,
    rollupOptions: {
      // shader worker is loaded via new Worker(new URL(...)) at runtime —
      // prevent Rollup from trying to bundle it as a module import
      external: (id) => {
        if (id.includes('shader-worker')) return true
        return false
      }
    }
  }
})
