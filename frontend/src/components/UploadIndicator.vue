<script setup>
// 全局上传悬浮条：队列在跑时出现在所有页面（上传页除外），点击回到上传页
import { useRouter } from 'vue-router'
import { useUploadStore } from '../stores/upload'

const store = useUploadStore()
const router = useRouter()
</script>

<template>
  <div v-if="store.active" class="pointer-events-none fixed inset-x-0 bottom-16 z-50 px-3" style="padding-bottom: 0">
    <div class="pointer-events-auto mx-auto max-w-lg">
      <button
        class="flex w-full items-center gap-3 rounded-2xl bg-white/95 p-3 text-left shadow-lg backdrop-blur transition-transform active:scale-[0.98]"
        @click="router.push('/upload')"
      >
        <span class="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blush-100 text-lg">
          🍼
          <span class="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 animate-ping rounded-full bg-blush-400"></span>
          <span class="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-blush-500"></span>
        </span>
        <span class="min-w-0 flex-1">
          <span class="flex items-baseline justify-between gap-2">
            <span class="truncate text-xs font-semibold text-stone-600">
              后台上传中 · {{ store.finishedCount }}/{{ store.totalCount }} 张
            </span>
            <span class="shrink-0 text-[10px] text-stone-400">去查看 ›</span>
          </span>
          <span class="mt-1 block h-1.5 overflow-hidden rounded-full bg-cream-100">
            <span
              class="block h-full rounded-full bg-blush-500 transition-all"
              :style="{ width: store.overallPct + '%' }"
            ></span>
          </span>
        </span>
      </button>
    </div>
  </div>
</template>
