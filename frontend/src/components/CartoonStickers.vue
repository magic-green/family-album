<script setup>
// 卡通贴纸：纯 SVG 小元素，铺在相对定位容器里做点缀（不吃点击、不挡内容）
</script>

<template>
  <div class="pointer-events-none absolute inset-0 select-none overflow-hidden" aria-hidden="true">
    <!-- 左上：小云朵 -->
    <svg class="cartoon-float absolute -left-1 -top-2 h-10 w-14 opacity-80" viewBox="0 0 84 52" fill="none">
      <path d="M18 40C8 40 3 33 5 26c2-7 10-10 17-8 2-9 10-15 20-15 9 0 16 5 19 12 8-1 15 4 15 12 0 8-6 13-16 13H18z" fill="#fff" stroke="#FFD9BC" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="28" cy="27" r="2.2" fill="#5B4636"/>
      <circle cx="49" cy="27" r="2.2" fill="#5B4636"/>
      <path d="M34 32c2 2 5 2 7 0" stroke="#5B4636" stroke-width="2" stroke-linecap="round"/>
      <circle cx="22" cy="32" r="3" fill="#FFC7A3" opacity=".8"/>
      <circle cx="55" cy="32" r="3" fill="#FFC7A3" opacity=".8"/>
    </svg>
    <!-- 右上：星星 -->
    <svg class="cartoon-float-slow absolute right-3 -top-1 h-8 w-8 opacity-75" viewBox="0 0 40 40" fill="none">
      <path d="M20 3l4.6 10.6L36 15l-8.3 8 2.1 11.6L20 28.9 10.2 34.6l2.1-11.6L4 15l11.4-1.4L20 3z" fill="#FFD591" stroke="#FFB347" stroke-width="2" stroke-linejoin="round"/>
      <circle cx="15" cy="18" r="1.5" fill="#5B4636"/>
      <circle cx="24" cy="18" r="1.5" fill="#5B4636"/>
    </svg>
    <!-- 右下：小花 -->
    <svg class="cartoon-float absolute -bottom-2 right-6 h-9 w-9 opacity-75" viewBox="0 0 48 48" fill="none">
      <path d="M24 24c-4-3-5-9-2-12 3-3 8-1 8 3 4-2 9 0 9 4 0 4-5 6-9 5 1 4-2 8-6 8-4 0-6-4-4-8-4 1-8-2-8-6 0-4 5-6 9-4-3-3-2-8 2-10" fill="#FFE9E0" stroke="#FFB4A0" stroke-width="2" stroke-linejoin="round"/>
      <circle cx="24" cy="24" r="6" fill="#FFD591"/>
      <circle cx="22" cy="23" r="1.2" fill="#5B4636"/>
      <circle cx="26" cy="23" r="1.2" fill="#5B4636"/>
    </svg>
  </div>
</template>
