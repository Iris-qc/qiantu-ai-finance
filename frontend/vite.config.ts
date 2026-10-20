import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发环境：/api 代理到本地 FastAPI（默认 8000 端口）
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
})
