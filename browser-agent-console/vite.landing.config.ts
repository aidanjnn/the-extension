import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  resolve: {
    alias: {
      '@': `${path.resolve(__dirname, 'src')}`,
    },
  },
  plugins: [react()],
  build: {
    outDir: 'dist-landing',
    rollupOptions: {
      input: path.resolve(__dirname, 'index.html'),
    },
  },
})
