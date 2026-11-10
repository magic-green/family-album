<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BabyMascot from '../components/BabyMascot.vue'
import { ageText, daysText, BABY } from '../baby'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref('login') // login | register
const username = ref('')
const password = ref('')
const inviteCode = ref('')
const loading = ref(false)
const error = ref('')

function switchMode(m) {
  mode.value = m
  error.value = ''
}

async function submit() {
  if (!username.value.trim() || !password.value) {
    error.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const payload = { username: username.value.trim(), password: password.value }
    if (mode.value === 'register') payload.invite_code = inviteCode.value.trim()
    if (mode.value === 'register') {
      const data = await auth.register(payload)
      // 若注册接口不返回 token，则注册成功后自动登录
      if (!data?.access_token) await auth.login(payload)
    } else {
      await auth.login(payload)
    }
    router.replace(route.query.redirect || '/')
  } catch (e) {
    error.value = e.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="relative flex min-h-full flex-col items-center justify-center overflow-hidden px-6 py-10">
    <!-- 漂浮装饰 -->
    <div class="pointer-events-none absolute inset-0 select-none">
      <span class="absolute left-6 top-10 text-2xl opacity-60">☁️</span>
      <span class="absolute right-8 top-24 text-xl opacity-50">☁️</span>
      <span class="absolute left-12 bottom-24 text-xl opacity-50">🌟</span>
      <span class="absolute right-10 bottom-40 text-lg opacity-60">🧸</span>
      <span class="absolute left-1/4 top-6 text-base opacity-40">✨</span>
    </div>

    <div class="w-full max-w-sm">
      <!-- 顶部卡通 banner（和首页同一张插画） -->
      <div class="login-banner mb-6 h-24 rounded-3xl shadow-sm"></div>
      <!-- 头部：示例形象 -->
      <div class="mb-8 text-center">
        <div class="relative mx-auto mb-4 inline-block">
          <BabyMascot :size="112" class="drop-shadow-md" />
          <span class="absolute -right-1 -top-1 text-2xl">🍼</span>
        </div>
        <h1 class="font-art text-3xl text-stone-700 drop-shadow-sm">拾光相册</h1>
        <p class="font-elegance mt-2 text-sm text-stone-400">记录家庭的每一天</p>
        <div class="mt-3 inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-xs text-stone-500 shadow-sm">
          <span class="text-base">🎂</span>
          <span class="font-semibold text-blush-500">{{ BABY.nickname }} {{ ageText() }}</span>
          <span class="text-honey-300">|</span>
          <span>{{ daysText() }}</span>
        </div>
      </div>

      <!-- 切换 -->
      <div class="mb-6 grid grid-cols-2 rounded-full bg-cream-100 p-1 text-sm font-medium">
        <button
          class="rounded-full py-2 transition-all"
          :class="mode === 'login' ? 'bg-white text-blush-600 shadow' : 'text-stone-400'"
          @click="switchMode('login')"
        >
          登录
        </button>
        <button
          class="rounded-full py-2 transition-all"
          :class="mode === 'register' ? 'bg-white text-blush-600 shadow' : 'text-stone-400'"
          @click="switchMode('register')"
        >
          注册
        </button>
      </div>

      <form class="space-y-4" @submit.prevent="submit">
        <input
          v-model="username"
          type="text"
          placeholder="用户名"
          autocomplete="username"
          class="w-full rounded-2xl border border-honey-300/70 bg-white px-4 py-3 text-sm outline-none placeholder:text-stone-300 focus:border-blush-400"
        />
        <input
          v-model="password"
          type="password"
          placeholder="密码"
          :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          class="w-full rounded-2xl border border-honey-300/70 bg-white px-4 py-3 text-sm outline-none placeholder:text-stone-300 focus:border-blush-400"
        />
        <input
          v-if="mode === 'register'"
          v-model="inviteCode"
          type="text"
          placeholder="邀请码"
          class="w-full rounded-2xl border border-honey-300/70 bg-white px-4 py-3 text-sm outline-none placeholder:text-stone-300 focus:border-blush-400"
        />
        <p v-if="mode === 'register'" class="text-xs text-stone-400">
          邀请码由部署方在服务端 .env 中配置，请向管理员索取
        </p>

        <p v-if="error" class="rounded-xl bg-blush-100 px-4 py-2 text-sm text-blush-600">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-full bg-blush-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-blush-600 disabled:opacity-60"
        >
          {{ loading ? '请稍候…' : mode === 'login' ? '进入相册' : '创建账号' }}
        </button>
      </form>
    </div>
  </div>
</template>
