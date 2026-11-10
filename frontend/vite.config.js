import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8020',
        changeOrigin: true,
      },
      // 后端静态媒体文件（url/thumbnail_url 形如 /data/originals/xxx、/data/thumbnails/xxx）
      '/data': {
        target: 'http://localhost:8020',
        changeOrigin: true,
      },
    },
  },
})
