<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { name: 'timeline', label: '时间线', to: '/', emoji: '🖼️' },
  { name: 'upload', label: '上传', to: '/upload', emoji: '📤' },
  { name: 'settings', label: '设置', to: '/settings', emoji: '⚙️' },
]
</script>

<template>
  <nav class="fixed inset-x-0 bottom-0 z-40 border-t border-honey-300/60 bg-cream-100/95 backdrop-blur" style="padding-bottom: env(safe-area-inset-bottom)">
    <div class="mx-auto flex max-w-lg items-stretch justify-around">
      <router-link
        v-for="t in tabs"
        :key="t.name"
        :to="t.to"
        class="flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors"
        :class="route.name === t.name ? 'text-blush-600 font-semibold' : 'text-stone-400'"
      >
        <span class="text-xl transition-transform" :class="route.name === t.name ? 'scale-110' : 'opacity-60 grayscale'">{{ t.emoji }}</span>
        {{ t.label }}
      </router-link>
    </div>
  </nav>
</template>
