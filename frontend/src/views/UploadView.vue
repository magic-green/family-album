<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useUploadStore } from '../stores/upload'
import CartoonStickers from '../components/CartoonStickers.vue'

const store = useUploadStore()

const dragging = ref(false)
const inputRef = ref(null)
const folderRef = ref(null)
// 微信照片模式：EXIF 被微信剥掉，可指定批次拍摄时间兜底
const wechatMode = ref(false)
// 默认当前月（YYYY-MM），下拉选最近 48 个月即可，不用再点日历
const now = new Date()
function monthValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
const batchDate = ref(monthValue(now))
const monthOptions = Array.from({ length: 48 }, (_, i) => {
  const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
  return { value: monthValue(d), label: `${d.getFullYear()}年${d.getMonth() + 1}月` }
})
// 压缩上传（默认关=原图）：图片压到长边 2048 的 JPEG，视频不受影响
const compress = ref(false)

// 缩略图预览：Vue 模板全局白名单里没有 URL，必须在 script 里生成并缓存
const previewUrls = new Map()
function previewUrl(file) {
  if (!previewUrls.has(file)) previewUrls.set(file, URL.createObjectURL(file))
  return previewUrls.get(file)
}

// 递归遍历拖拽目录（DataTransferItem.webkitGetAsEntry），收集全部文件
function traverseEntry(entry, out) {
  return new Promise((resolve) => {
    if (entry.isFile) {
      entry.file(
        (f) => {
          out.push(f)
          resolve()
        },
        () => resolve()
      )
    } else if (entry.isDirectory) {
      const reader = entry.createReader()
      const jobs = []
      const readBatch = () => {
        reader.readEntries((entries) => {
          if (!entries.length) {
            Promise.all(jobs).then(() => resolve())
            return
          }
          for (const en of entries) jobs.push(traverseEntry(en, out))
          readBatch() // readEntries 每次最多返回 100 条，读到空为止
        }, () => resolve())
      }
      readBatch()
    } else resolve()
  })
}

async function onDrop(e) {
  dragging.value = false
  const opts = { hint: wechatDate(), compress: compress.value }
  const items = e.dataTransfer?.items
  if (items && items.length && typeof items[0].webkitGetAsEntry === 'function') {
    const out = []
    const roots = []
    for (const it of items) {
      const en = it.webkitGetAsEntry()
      if (en) roots.push(en)
    }
    if (roots.length) {
      await Promise.all(roots.map((en) => traverseEntry(en, out)))
      if (out.length) {
        store.enqueue(out, opts)
        return
      }
    }
  }
  store.enqueue(e.dataTransfer.files, opts)
}

function onPick(e) {
  store.enqueue(e.target.files, { hint: wechatDate(), compress: compress.value })
  e.target.value = ''
}

function onFolderPick(e) {
  store.enqueue(e.target.files, { hint: wechatDate(), compress: compress.value })
  e.target.value = ''
}

function wechatDate() {
  return wechatMode.value ? batchDate.value : ''
}

function removeItem(item) {
  if (item.status === 'uploading') return
  const idx = store.items.indexOf(item)
  if (idx >= 0) store.items.splice(idx, 1)
}

function startUpload() {
  if (store.pendingCount === 0) return
  store.enqueue([], { hint: wechatDate(), compress: compress.value })
  store._run()
}

function fmtSize(bytes) {
  if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  return Math.ceil(bytes / 1024) + ' KB'
}

// 剪贴板粘贴上传：微信里 Ctrl+C 复制图片 → 本页 Ctrl+V 直接入队。
// 截图（PrtSc）、微信复制的图片都会以 image/png 形式出现在 clipboardData.files 里。
function onPaste(e) {
  const files = [...(e.clipboardData?.files || [])]
  const media = files.filter(
    (f) => f.type.startsWith('image/') || f.type.startsWith('video/') || f.type.startsWith('audio/')
  )
  if (media.length) {
    e.preventDefault() // 阻止浏览器默认行为（比如往输入框贴入路径文本）
    store.enqueue(media, { hint: wechatDate(), compress: compress.value })
  }
}
onMounted(() => window.addEventListener('paste', onPaste))
onUnmounted(() => window.removeEventListener('paste', onPaste))
</script>

<template>
  <div class="mx-auto max-w-lg px-4 pt-6 md:max-w-2xl md:px-8">
    <header class="mb-5">
      <h1 class="font-art text-2xl text-stone-700">上传照片</h1>
      <p class="text-xs text-stone-400">照片、视频、录音都可以，一次选一堆也没问题</p>
    </header>

    <!-- 微信照片模式 -->
    <div class="mb-4 rounded-2xl bg-white p-3 shadow-sm">
      <label class="flex cursor-pointer items-center gap-2 text-sm text-stone-600">
        <input type="checkbox" v-model="wechatMode" class="h-4 w-4 accent-blush-500" />
        <span>💬 微信照片模式</span>
        <span class="text-xs text-stone-400">（EXIF 已被微信剥掉，用文件名时间或批次日期恢复）</span>
      </label>
      <div v-if="wechatMode" class="mt-2 flex items-center gap-2 pl-6 text-sm">
        <label class="text-xs text-stone-400">这批大约拍摄于</label>
        <select
          v-model="batchDate"
          class="rounded-xl border border-honey-300/70 bg-cream-50 px-3 py-1.5 text-sm outline-none focus:border-blush-400"
        >
          <option v-for="op in monthOptions" :key="op.value" :value="op.value">{{ op.label }}</option>
        </select>
        <span class="text-xs text-stone-400">默认当前月，仅兜底用</span>
      </div>
      <label class="mt-2 flex cursor-pointer items-center gap-2 pl-6 text-xs text-stone-400">
        <input type="checkbox" v-model="compress" class="h-4 w-4 accent-blush-500" />
        压缩上传（省流量，默认不勾=传原图）
      </label>
    </div>

    <!-- 拖拽/点选区域 -->
    <div
      class="relative flex flex-col items-center justify-center rounded-3xl border-2 border-dashed px-6 py-12 text-center transition-colors"
      :class="dragging ? 'border-blush-400 bg-blush-100' : 'border-honey-300 bg-cream-100'"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
      @click="inputRef?.click()"
    >
      <CartoonStickers />
      <p class="text-4xl">🧺</p>
      <p class="mt-3 text-sm font-medium text-stone-500">把照片拖进小篮子，或点击挑选</p>
      <p class="mt-1 text-xs text-stone-400">电脑上也能直接 Ctrl+V 粘贴微信图片 / 截图</p>
      <input
        ref="inputRef"
        type="file"
        multiple
        accept="image/*,video/*,audio/*"
        class="hidden"
        @change="onPick"
      />
    </div>

    <!-- 电脑端：整文件夹导入 -->
    <div class="mt-2 text-center">
      <button
        type="button"
        class="text-xs text-stone-400 underline decoration-dotted hover:text-blush-500"
        @click="folderRef?.click()"
      >
        📁 从文件夹导入（电脑端，微信批量另存推荐）
      </button>
      <input
        ref="folderRef"
        type="file"
        multiple
        webkitdirectory
        class="hidden"
        @change="onFolderPick"
      />
    </div>

    <!-- 上传队列列表 -->
    <ul v-if="store.items.length" class="mt-5 space-y-2">
      <li
        v-for="item in store.items"
        :key="item.id"
        class="flex items-center gap-3 rounded-2xl bg-white p-3 shadow-sm"
      >
        <img v-if="!item.isVideo && !item.isAudio" :src="previewUrl(item.file)" class="h-12 w-12 rounded-xl object-cover" />
        <div v-else-if="item.isAudio" class="flex h-12 w-12 items-center justify-center rounded-xl bg-cream-100 text-xl">🎵</div>
        <div v-else class="flex h-12 w-12 items-center justify-center rounded-xl bg-cream-100 text-xl">🎬</div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm text-stone-600">{{ item.name }}</p>
          <p class="text-xs text-stone-400">
            {{ fmtSize(item.size) }}
            <span v-if="item.status === 'done'" class="text-green-500">· ✓ 已上传</span>
            <span v-else-if="item.status === 'skip' && item.dup" class="text-honey-500">
              · 与已上传的「{{ item.dup.orig_name }}」重复，已跳过
            </span>
            <span v-else-if="item.status === 'skip'" class="text-honey-500">· 重复，已跳过</span>
            <span v-else-if="item.status === 'fail'" class="text-blush-600">· 失败</span>
            <span v-else-if="item.status === 'uploading' && item.paused" class="text-honey-500">· 已暂停</span>
            <span v-else-if="item.status === 'uploading' && item.progress < 100" class="text-blush-500">· 传输中 {{ item.progress }}%</span>
            <span v-else-if="item.status === 'uploading' && item.progress >= 100" class="text-honey-500">· 处理中…</span>
          </p>
          <p v-if="item.status === 'skip' && item.dup" class="mt-0.5 text-[10px] text-stone-400">
            <router-link to="/" class="underline decoration-dotted hover:text-blush-500">
              相册里已有这张 → 去时间线查看
            </router-link>
          </p>
          <!-- 单文件进度条：真实传输阶段显示 -->
          <div v-if="item.status === 'uploading' && !item.paused && item.progress < 100" class="mt-1 h-1 overflow-hidden rounded-full bg-cream-100">
            <div class="h-full rounded-full bg-blush-400 transition-all" :style="{ width: item.progress + '%' }"></div>
          </div>
        </div>
        <!-- 操作：暂停/恢复/取消 -->
        <div class="flex shrink-0 items-center gap-1.5 text-sm">
          <template v-if="item.status === 'uploading'">
            <button class="w-6 text-stone-400 hover:text-blush-500" @click.stop="item.paused ? store.resumeItem(item) : store.pauseItem(item)">
              {{ item.paused ? '▶' : '⏸' }}
            </button>
            <button class="w-6 text-stone-300 hover:text-blush-600" @click.stop="store.cancelItem(item)">✕</button>
          </template>
          <button v-else-if="item.status === 'pending' || item.status === 'fail'" class="w-6 text-stone-300 hover:text-blush-600" @click.stop="store.cancelItem(item)">✕</button>
        </div>
      </li>
    </ul>

    <!-- 总进度（队列运行中） -->
    <div v-if="store.active" class="mt-4">
      <div class="h-2 overflow-hidden rounded-full bg-cream-100">
        <div class="h-full rounded-full bg-blush-500 transition-all" :style="{ width: store.overallPct + '%' }"></div>
      </div>
      <p class="mt-1 text-center text-xs text-stone-400">
        后台上传中 · 已完成 {{ store.finishedCount }} / {{ store.totalCount }} 张
        <span class="text-honey-500">（去逛时间线也照常传）</span>
      </p>
    </div>

    <!-- 结果汇总 -->
    <div v-if="!store.active && store.finishedCount > 0" class="mt-4 rounded-xl bg-cream-100 px-4 py-3 text-center text-sm text-stone-500">
      已上传 <span class="font-semibold text-green-500">{{ store.successCount }}</span> 个文件 🎉
      <span v-if="store.skipCount" class="block text-xs text-stone-400">跳过 {{ store.skipCount }} 张重复照片</span>
      <span v-if="store.failCount" class="block text-xs text-blush-600">失败 {{ store.failCount }} 份</span>
      <div class="mt-2 flex justify-center gap-2">
        <router-link to="/" class="rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-blush-500 shadow-sm">
          去时间线看看 →
        </router-link>
        <button v-if="store.failCount" class="rounded-full bg-blush-500 px-4 py-1.5 text-xs font-semibold text-white" @click="store.retryFailed()">
          重试失败项
        </button>
        <button class="rounded-full bg-white px-4 py-1.5 text-xs text-stone-400 shadow-sm" @click="store.clearFinished()">清空列表</button>
      </div>
    </div>
    <p v-if="store.lastError && !store.active" class="mt-2 rounded-xl bg-blush-100 px-4 py-2 text-center text-xs text-blush-600">{{ store.lastError }}</p>

    <!-- 上传按钮 -->
    <button
      v-if="store.pendingCount > 0"
      :disabled="store.active"
      class="mt-5 w-full rounded-full bg-blush-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-blush-600 disabled:opacity-60"
      @click="startUpload"
    >
      {{ store.active ? '放进相册中…' : `🌟 把 ${store.pendingCount} 份回忆放进相册` }}
    </button>
  </div>
</template>
