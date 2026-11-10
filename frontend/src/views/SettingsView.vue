<script setup>
import { ref, onMounted } from 'vue'
import { authApi, systemApi } from '../api'
import { setBirthDate, BABY } from '../baby'

const info = ref(null)
const users = ref([])
const logs = ref([])
const birthDate = ref(BABY.birth)
const savingBirth = ref(false)
const birthSaved = ref(false)
const loading = ref(true)
const error = ref('')
const avatarInput = ref(null)
const uploadingAvatar = ref(false)

function fmt(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function load() {
  loading.value = true
  try {
    const [i, u, l, s] = await Promise.all([
      systemApi.info(),
      authApi.users(),
      authApi.logs(50),
      systemApi.getSettings(),
    ])
    info.value = i
    users.value = u
    logs.value = l
    if (s.birth_date) {
      birthDate.value = s.birth_date
      setBirthDate(s.birth_date)
    }
    if (s.avatar_url) BABY.avatar = s.avatar_url
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function saveBirth() {
  savingBirth.value = true
  birthSaved.value = false
  try {
    await systemApi.putSettings({ birth_date: birthDate.value })
    setBirthDate(birthDate.value)
    birthSaved.value = true
    setTimeout(() => (birthSaved.value = false), 2500)
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    savingBirth.value = false
  }
}

async function uploadAvatar(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  uploadingAvatar.value = true
  error.value = ''
  try {
    const res = await systemApi.uploadAvatar(file)
    if (res?.avatar_url) BABY.avatar = res.avatar_url
  } catch (err) {
    error.value = err.message || '头像上传失败'
  } finally {
    uploadingAvatar.value = false
  }
}

async function deleteUser(u) {
  if (!confirm(`确定删除账号「${u.username}」吗？此操作不可恢复。`)) return
  try {
    await authApi.deleteUser(u.id)
    users.value = users.value.filter((x) => x.id !== u.id)
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-lg px-4 pt-6 md:max-w-3xl">
    <header class="mb-5">
      <h1 class="font-art text-2xl text-stone-700">系统设置</h1>
      <p class="font-elegance text-xs text-stone-400">家庭相册，由家庭成员共同珍藏</p>
    </header>

    <p v-if="error" class="mb-4 rounded-xl bg-blush-100 px-4 py-3 text-sm text-blush-600">{{ error }}</p>
    <p v-if="loading" class="py-16 text-center text-sm text-stone-400">加载中…</p>

    <template v-else>
      <!-- 头像与宝宝信息 -->
      <section class="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <h2 class="mb-3 text-sm font-semibold text-stone-500">👤 档案信息</h2>
        <div class="flex items-start gap-4">
          <!-- 头像上传 -->
          <div class="flex shrink-0 flex-col items-center gap-1.5">
            <button class="group relative block" @click="avatarInput?.click()">
              <img v-if="BABY.avatar" :src="BABY.avatar" alt="头像" class="h-20 w-20 rounded-full object-cover shadow-sm" />
              <span v-else class="flex h-20 w-20 items-center justify-center rounded-full bg-blush-100 text-3xl">🐣</span>
              <span class="absolute inset-0 flex items-center justify-center rounded-full bg-black/0 text-xs text-white opacity-0 transition-all group-hover:bg-black/40 group-hover:opacity-100">
                {{ uploadingAvatar ? '…' : '更换' }}
              </span>
            </button>
            <span class="text-[10px] text-stone-400">点击更换头像</span>
            <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="uploadAvatar" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-end gap-3">
              <label class="text-xs text-stone-400">
                <span class="mb-1 block">出生日期</span>
                <input
                  v-model="birthDate"
                  type="date"
                  class="rounded-xl border border-honey-300/70 bg-cream-50 px-3 py-1.5 text-sm outline-none focus:border-blush-400"
                />
              </label>
              <button
                class="rounded-full bg-blush-500 px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
                :disabled="savingBirth"
                @click="saveBirth"
              >
                {{ savingBirth ? '保存中…' : '保存' }}
              </button>
              <span v-if="birthSaved" class="pb-1.5 text-xs text-green-500">✓ 已保存，全站生效</span>
            </div>
            <p class="mt-2 text-xs text-stone-400">示例档案「{{ BABY.name }}」· 出生日期：{{ BABY.birth }}</p>
          </div>
        </div>
      </section>

      <!-- 系统信息 -->
      <section v-if="info" class="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <h2 class="mb-3 text-sm font-semibold text-stone-500">📊 相册概况</h2>
        <div class="grid grid-cols-2 gap-2 text-center text-xs md:grid-cols-4">
          <div class="rounded-xl bg-cream-100 p-3">
            <p class="text-lg font-bold text-blush-500">{{ info.photos }}</p>
            <p class="text-stone-400">照片</p>
          </div>
          <div class="rounded-xl bg-cream-100 p-3">
            <p class="text-lg font-bold text-honey-500">{{ info.videos }}</p>
            <p class="text-stone-400">视频</p>
          </div>
          <div class="rounded-xl bg-cream-100 p-3">
            <p class="text-lg font-bold text-stone-600">{{ info.ai_tagged }}</p>
            <p class="text-stone-400">已 AI 标记</p>
          </div>
          <div class="rounded-xl bg-cream-100 p-3">
            <p class="text-lg font-bold text-stone-600">{{ info.tags }}</p>
            <p class="text-stone-400">标签</p>
          </div>
        </div>
        <p class="mt-3 text-xs text-stone-400">
          存储占用：原图 {{ info.storage_originals_mb }} MB · 缩略图 {{ info.storage_thumbs_mb }} MB
          ｜ AI 模型：{{ info.ai_model }}
          <span class="ml-1" :class="info.ollama_ok ? 'text-green-500' : 'text-blush-600'">
            （{{ info.ollama_ok ? '在线' : '离线' }}）
          </span>
        </p>
      </section>

      <!-- 账号管理 -->
      <section class="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <h2 class="mb-3 text-sm font-semibold text-stone-500">👨‍👩‍👧 账号管理（{{ users.length }}）</h2>
        <ul class="divide-y divide-cream-100">
          <li v-for="u in users" :key="u.id" class="flex items-center gap-3 py-2.5">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blush-100 text-sm font-semibold text-blush-600">
              {{ u.username.slice(0, 1).toUpperCase() }}
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-sm text-stone-600">{{ u.username }}</p>
              <p class="text-xs text-stone-400">加入于 {{ fmt(u.created_at) }} · 上传 {{ u.media_count }} 个</p>
            </div>
            <button
              class="shrink-0 text-xs text-stone-300 hover:text-blush-600"
              @click="deleteUser(u)"
            >
              删除
            </button>
          </li>
        </ul>
        <p class="mt-2 text-xs text-stone-400">新成员？请向管理员索取邀请码（由部署方在服务端 .env 中配置），在登录页注册即可</p>
      </section>

      <!-- 访问记录 -->
      <section class="mb-4 rounded-2xl bg-white p-4 shadow-sm">
        <h2 class="mb-3 text-sm font-semibold text-stone-500">🕐 最近访问记录</h2>
        <ul class="divide-y divide-cream-100">
          <li v-for="l in logs" :key="l.id" class="flex items-center gap-3 py-2 text-xs">
            <span class="w-20 shrink-0 font-semibold" :class="l.ok ? 'text-stone-600' : 'text-blush-600'">
              {{ l.username }}
            </span>
            <span :class="l.ok ? 'text-green-500' : 'text-blush-600'">{{ l.ok ? '登录成功' : '登录失败' }}</span>
            <span class="ml-auto text-stone-400">{{ fmt(l.created_at) }}</span>
          </li>
          <li v-if="!logs.length" class="py-4 text-center text-xs text-stone-400">还没有记录</li>
        </ul>
      </section>
    </template>
  </div>
</template>
