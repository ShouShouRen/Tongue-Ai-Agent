import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: './', // 使用相对路径，确保在 Electron 中能正确加载资源
  build: {
    outDir: 'dist-react',
  },
  server: {
    // 如果需要代理 FastAPI 服務，可以在這裡配置
    // proxy: {
    //   '/api': {
    //     target: 'http://localhost:8000',
    //     changeOrigin: true,
    //   },
    // },
  },
})
