<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BottomNav from './components/BottomNav.vue'
import UploadIndicator from './components/UploadIndicator.vue'
import { useUploadStore } from './stores/upload'
import { systemApi } from './api'
import { setBirthDate, BABY } from './baby'

const route = useRoute()
const router = useRouter()
const uploadStore = useUploadStore()

// 应用启动：拉取全局设置（生日/头像），并在上传进行中拦截页面刷新
async function loadGlobalSettings() {
  try {
    const s = await systemApi.getSettings()
    if (s.birth_date) setBirthDate(s.birth_date)
    if (s.avatar_url) BABY.avatar = s.avatar_url
  } catch { /* 未登录时静默跳过，登录后各页面会再拉 */ }
}

function beforeUnloadGuard(e) {
  if (uploadStore.active) {
    e.preventDefault()
    e.returnValue = ''
  }
}

// Web Share Target：SW 把系统分享的文件暂存在 Cache 里，这里取走并入队上传
async function consumeSharedFiles() {
  if (!('caches' in window)) return
  try {
    const cache = await caches.open('share-target')
    const countRes = await cache.match('share-count')
    if (!countRes) return
    const count = parseInt(await countRes.text(), 10)
    if (!count || count < 1) return
    const files = []
    for (let i = 0; i < count; i++) {
      const res = await cache.match(`share-file-${i}`)
      if (!res) continue
      const blob = await res.blob()
      const name = decodeURIComponent(res.headers.get('X-File-Name') || `shared_${i}.jpg`)
      files.push(new File([blob], name, { type: res.headers.get('Content-Type') || blob.type }))
    }
    await cache.delete('share-count')
    for (let i = 0; i < count; i++) await cache.delete(`share-file-${i}`)
    if (files.length) {
      uploadStore.enqueue(files)
      if (route.path !== '/upload') router.push('/upload')
    }
  } catch { /* 无分享内容或 Cache 不可用，静默跳过 */ }
}

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnloadGuard)
  if (route.query['from-share'] !== undefined) {
    // 清掉查询参数避免刷新重复触发
    router.replace({ query: {} })
  }
  loadGlobalSettings()
  consumeSharedFiles()
})
</script>

<template>
  <div class="flex min-h-full flex-col">
    <main class="flex-1 pb-16">
      <router-view />
    </main>
    <!-- 登录页不显示底部导航 -->
    <BottomNav v-if="route.name !== 'login'" />
    <!-- 后台上传悬浮条（上传页自带完整界面，不重复挂） -->
    <UploadIndicator v-if="route.name !== 'login' && route.name !== 'upload'" />
  </div>
</template>
