<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { mediaApi } from '../api'
import { useAuthStore } from '../stores/auth'
import BabyMascot from '../components/BabyMascot.vue'
import LightboxViewer from '../components/LightboxViewer.vue'
import CartoonStickers from '../components/CartoonStickers.vue'
import { ageText, daysText, setBirthDate, BABY } from '../baby'
import { systemApi } from '../api'

const auth = useAuthStore()

const groups = ref([]) // [{ date:'YYYY年M月D日', items: [...] }]
const total = ref(0)
const page = ref(0)
const pageSize = 30
const loading = ref(false)
const done = ref(false)
const error = ref('')
const sentinel = ref(null)
// 标签筛选（小红书风）
const selectedTag = ref('')
const allTags = ref([])
// 看图模式
const viewerOpen = ref(false)
const viewerStart = ref(0)

const flatItems = computed(() => groups.value.flatMap((g) => g.items))

function openViewer(m) {
  const idx = flatItems.value.findIndex((x) => x.id === m.id)
  viewerStart.value = Math.max(0, idx)
  viewerOpen.value = true
}

function onDeleted(id) {
  for (const g of groups.value) g.items = g.items.filter((x) => x.id !== id)
}

function fmtDate(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

// 列数跟随屏宽：手机 2 列 / 平板 3 列 / 桌面 4 列；轮流分配保证"先左后右"
const colCount = ref(window.innerWidth >= 1024 ? 4 : window.innerWidth >= 768 ? 3 : 2)
function onResize() {
  const w = window.innerWidth
  colCount.value = w >= 1024 ? 4 : w >= 768 ? 3 : 2
}

function colsOf(items) {
  const cols = Array.from({ length: colCount.value }, () => [])
  items.forEach((m, i) => cols[i % colCount.value].push(m))
  return cols
}

function cardTitle(m) {
  if (m.caption) return m.caption
  // 音频没有画面，用原文件名（去扩展名）当默认标题，家人好识别
  if (m.media_type === 'audio' && m.orig_name) {
    return m.orig_name.replace(/\.[^.]+$/, '')
  }
  const d = new Date(m.taken_at)
  if (Number.isNaN(d.getTime())) return '记录的瞬间'
  return `${d.getMonth() + 1}月${d.getDate()}日 的小瞬间`
}

function cardRatio(m) {
  if (m.media_type === 'audio') return '1 / 1' // 音频占位缩略图是方形
  if (m.width && m.height) return `${m.width} / ${m.height}`
  return '3 / 4'
}

function pushToGroups(list, it) {
  const key = it.taken_at ? fmtDate(it.taken_at) : '未记录日期'
  let g = list.find((g) => g.date === key)
  if (!g) {
    g = { date: key, items: [] }
    list.push(g)
  }
  g.items.push(it)
}

async function loadMore() {
  if (loading.value || done.value) return
  loading.value = true
  error.value = ''
  try {
    const next = page.value + 1
    const data = await mediaApi.list({ page: next, pageSize, tag: selectedTag.value })
    total.value = data.total ?? 0
    const items = data.items ?? []
    for (const it of items) pushToGroups(groups.value, it)
    page.value = next
    if (items.length < pageSize) done.value = true
  } catch (e) {
    error.value = e.message || '加载失败'
    // 避免出错时无限重试
    done.value = true
  } finally {
    loading.value = false
  }
}

async function loadTags() {
  try {
    allTags.value = await mediaApi.tagsAll()
  } catch { /* 标签栏非关键功能 */ }
}

async function loadAvatar() {
  // 先拉轻量 settings（生日+头像，毫秒级），再拉系统概况（含 ollama 检测，较慢）
  try {
    const s = await systemApi.getSettings()
    if (s.birth_date) setBirthDate(s.birth_date)
    if (s.avatar_url) BABY.avatar = s.avatar_url
  } catch { /* 非关键 */ }
  try {
    const info = await systemApi.info()
    if (info.avatar_url && !BABY.avatar) BABY.avatar = info.avatar_url
  } catch { /* 非关键 */ }
}

async function resetAndLoad(tag) {
  if (selectedTag.value === tag) return
  selectedTag.value = tag
  groups.value = []
  page.value = 0
  done.value = false
  await loadMore()
}

// 拍摄日期被修改后按新日期重新分组（保持当前标签筛选）。
// 先在内存里重新拉好，再一次性替换 groups —— 不看图模式道具数组清成 0 导致看图模式自动关闭。
async function reloadTimeline() {
  const maxPage = Math.max(1, page.value)
  const fresh = []
  let loadedPages = 0
  let hitEnd = false
  try {
    for (let p = 1; p <= maxPage; p++) {
      const data = await mediaApi.list({ page: p, pageSize, tag: selectedTag.value })
      const items = data.items ?? []
      for (const it of items) pushToGroups(fresh, it)
      loadedPages = p
      total.value = data.total ?? total.value
      if (items.length < pageSize) {
        hitEnd = true
        break
      }
    }
    groups.value = fresh
    page.value = loadedPages
    done.value = hitEnd
  } catch (e) {
    error.value = e.message || '刷新时间线失败'
  }
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  await auth.fetchMe()
  await loadMore()
  loadTags()
  loadAvatar()

  // 无限滚动
  const io = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) loadMore()
  }, { rootMargin: '400px' })
  if (sentinel.value) io.observe(sentinel.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="mx-auto max-w-lg px-4 pt-6 md:max-w-3xl md:px-8 lg:max-w-6xl">
    <!-- 头部：品牌 + 示例名片（渐变英雄区） -->
    <header class="hero-banner relative mb-6 overflow-hidden rounded-3xl bg-gradient-to-br from-blush-100 via-cream-100 to-honey-300/40 p-5 shadow-sm">
      <div class="mb-4 flex items-baseline justify-between">
        <h1 class="font-art text-3xl text-stone-700 drop-shadow-sm">
          拾光相册<span class="ml-1 align-top text-xs text-honey-500">✦</span>
        </h1>
        <button
          class="rounded-full bg-white/80 px-3 py-1.5 text-xs text-stone-400 hover:text-blush-500"
          @click="auth.logout(); $router.push('/login')"
        >
          退出
        </button>
      </div>
      <div class="flex items-center gap-4">
        <div class="rounded-full bg-white/80 p-1.5 shadow-sm">
          <img v-if="BABY.avatar" :src="BABY.avatar" alt="头像" class="h-16 w-16 rounded-full object-cover" />
          <BabyMascot v-else :size="64" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="font-elegance text-base text-stone-600">{{ BABY.name }}的家庭相册</p>
          <p class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500">
            <span class="rounded-full bg-white/90 px-2 py-0.5 font-semibold text-blush-500 shadow-sm">{{ ageText() }}</span>
            <span class="rounded-full bg-white/90 px-2 py-0.5 shadow-sm">{{ daysText() }}</span>
          </p>
        </div>
      </div>
      <div class="mt-4 flex items-center gap-2 text-xs text-stone-500">
        <span class="rounded-full bg-white/80 px-3 py-1 shadow-sm">📷 共 {{ total }} 个瞬间</span>
        <span class="rounded-full bg-white/80 px-3 py-1 shadow-sm">🍼 成员共同记录</span>
        <router-link to="/settings" class="ml-auto rounded-full bg-white/80 px-3 py-1 shadow-sm hover:text-blush-500">⚙️ 设置</router-link>
      </div>
    </header>

    <!-- 标签筛选栏 -->
    <div v-if="allTags.length" class="mb-5 flex gap-2 overflow-x-auto no-scrollbar pb-1">
      <button
        class="shrink-0 rounded-full px-3.5 py-1.5 text-xs shadow-sm transition-colors"
        :class="!selectedTag ? 'bg-blush-500 font-semibold text-white' : 'bg-white text-stone-500'"
        @click="resetAndLoad('')"
      >
        全部
      </button>
      <button
        v-for="t in allTags"
        :key="t.id"
        class="shrink-0 rounded-full px-3.5 py-1.5 text-xs shadow-sm transition-colors"
        :class="selectedTag === t.name ? 'bg-blush-500 font-semibold text-white' : 'bg-white text-stone-500'"
        @click="resetAndLoad(t.name)"
      >
        #{{ t.name }} <span class="opacity-60">{{ t.count }}</span>
      </button>
    </div>

    <p v-if="error" class="mb-4 rounded-xl bg-blush-100 px-4 py-3 text-sm text-blush-600">{{ error }}</p>

    <!-- 日期分组（瀑布流：轮流分配，先左后右；列数跟随屏宽 2/3/4） -->
    <div v-for="g in groups" :key="g.date" class="mb-8">
      <h2 class="sticky top-0 z-10 mb-3 flex items-center gap-2 bg-cream-50/90 py-2 text-sm font-semibold text-stone-500 backdrop-blur">
        <span class="flex h-7 w-7 items-center justify-center rounded-full bg-white text-sm shadow-sm">🌸</span>
        {{ g.date }}
        <span class="rounded-full bg-white px-2 py-0.5 text-[10px] font-normal text-stone-400 shadow-sm">{{ g.items.length }} 张</span>
        <span class="h-px flex-1 bg-honey-300/50"></span>
      </h2>
      <div class="flex gap-2.5 md:gap-3">
        <div v-for="(col, ci) in colsOf(g.items)" :key="ci" class="flex min-w-0 flex-1 flex-col gap-2.5 md:gap-3">
          <a
            v-for="m in col"
            :key="m.id"
            href="#"
            class="group block overflow-hidden rounded-2xl bg-white shadow-sm transition-shadow hover:shadow-md"
            @click.prevent="openViewer(m)"
          >
          <div class="relative w-full overflow-hidden bg-cream-100" :style="{ aspectRatio: cardRatio(m) }">
            <img
              :src="m.thumbnail_url"
              :alt="m.caption || ''"
              loading="lazy"
              class="h-full w-full object-cover transition-transform group-hover:scale-105"
            />
            <span
              v-if="m.media_type === 'video'"
              class="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/45 text-white"
            >
              <svg class="h-3 w-3" viewBox="0 0 12 12" fill="currentColor"><path d="M3 1.5v9l8-4.5-8-4.5z" /></svg>
            </span>
            <span
              v-else-if="m.media_type === 'audio'"
              class="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-black/45 text-xs text-white"
            >🎵</span>
          </div>
          <div class="p-2">
            <p class="line-clamp-2 text-xs font-medium leading-snug text-stone-600">{{ cardTitle(m) }}</p>
            <div v-if="m.tags?.length" class="mt-1 flex flex-wrap gap-1">
              <span v-for="t in m.tags.slice(0, 3)" :key="t.id" class="rounded-full bg-honey-300/25 px-1.5 py-0.5 text-[10px] text-stone-500">#{{ t.name }}</span>
            </div>
            <p class="mt-1 flex items-center gap-2 text-[10px] text-stone-400">
              <span v-if="m.location_name" class="truncate">📍 {{ m.location_name }}</span>
              <span class="ml-auto flex shrink-0 items-center gap-1.5">
                <span>❤️ {{ m.likes_count ?? 0 }}</span>
                <span>💬 {{ m.comment_count ?? 0 }}</span>
              </span>
            </p>
          </div>
          </a>
        </div>
      </div>
    </div>

    <!-- 看图模式 -->
    <LightboxViewer
      v-if="viewerOpen"
      :items="flatItems"
      :start-index="viewerStart"
      @close="viewerOpen = false"
      @deleted="onDeleted"
      @updated="reloadTimeline"
    />

    <!-- 空状态 -->
    <div v-if="!loading && groups.length === 0" class="relative py-20 text-center">
      <CartoonStickers />
      <p class="text-6xl">🦆</p>
      <p class="mt-4 text-sm text-stone-500">还没有照片，快来上传第一张吧～</p>
      <p class="mt-1 text-xs text-stone-400">快把照片上传进来吧 ✨</p>
      <router-link to="/upload" class="mt-4 inline-block rounded-full bg-blush-500 px-6 py-2 text-sm font-semibold text-white shadow-sm transition-transform active:scale-95">
        📷 上传照片
      </router-link>
    </div>

    <p v-if="loading" class="py-6 text-center text-xs text-stone-400">加载中…</p>

    <!-- 无限滚动哨兵 -->
    <div ref="sentinel" class="h-1"></div>
  </div>
</template>
