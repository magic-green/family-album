<script setup>
// 示例吉祥物：圆脸小萌宝（纯 SVG，可任意缩放）
defineProps({
  size: { type: Number, default: 96 },
})
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 120 120"
    fill="none"
    aria-label="示例吉祥物"
  >
    <!-- 外圈光环 -->
    <circle cx="60" cy="60" r="58" fill="#FFF3E4" />
    <circle cx="60" cy="60" r="52" fill="#FFE9E0" />

    <!-- 小耳朵 -->
    <circle cx="16" cy="62" r="10" fill="#FFD9BC" />
    <circle cx="104" cy="62" r="10" fill="#FFD9BC" />
    <circle cx="16" cy="62" r="5" fill="#FFC7A3" />
    <circle cx="104" cy="62" r="5" fill="#FFC7A3" />

    <!-- 脸蛋 -->
    <circle cx="60" cy="62" r="42" fill="#FFE3C9" />

    <!-- 呆毛（水滴形呆毛） -->
    <path
      d="M60 22c-2-9 4-14 12-13-5 3-6 6-4 10 3-2 7-1 8 2-4 0-6 2-6 5-4-3-8-4-10-4z"
      fill="#C98A5B"
    />
    <path d="M58 21c-6-4-6-9-2-13 1 5 4 8 8 9-4 1-6 2-6 4z" fill="#C98A5B" />

    <!-- 眼睛（大圆眼 + 高光） -->
    <circle cx="44" cy="60" r="6.5" fill="#5B4636" />
    <circle cx="76" cy="60" r="6.5" fill="#5B4636" />
    <circle cx="46.2" cy="57.6" r="2.2" fill="#fff" />
    <circle cx="78.2" cy="57.6" r="2.2" fill="#fff" />

    <!-- 腮红 -->
    <ellipse cx="32" cy="72" rx="7" ry="4.5" fill="#FFB4A0" opacity="0.8" />
    <ellipse cx="88" cy="72" rx="7" ry="4.5" fill="#FFB4A0" opacity="0.8" />

    <!-- 微笑 -->
    <path
      d="M52 74c2.5 4 13.5 4 16 0"
      stroke="#5B4636"
      stroke-width="3"
      stroke-linecap="round"
    />

    <!-- 小下巴 -->
    <ellipse cx="60" cy="86" rx="10" ry="6" fill="#FFD9BC" opacity="0.6" />
  </svg>
</template>
