import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      // 前端走同源 /api，由 Vite 代理到后端，避免跨域 Failed to fetch
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/model-health/cosyvoice': {
          target: 'http://127.0.0.1:8002',
          changeOrigin: true,
          rewrite: () => '/health',
        },
        '/model-health/heygem': {
          target: 'http://127.0.0.1:8003',
          changeOrigin: true,
          rewrite: () => '/health',
        },
        '/model-health/tuilionnx': {
          target: 'http://127.0.0.1:8004',
          changeOrigin: true,
          rewrite: () => '/health',
        },
      },
    },
  }
})
