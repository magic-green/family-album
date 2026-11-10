<script setup>
// 全屏看图模式 = 浏览 + 全部详情功能（小故事/AI建议/评论/元数据/删除）
// 桌面：图左 / 信息面板右；手机：图上 / 面板下滚动
// 切换：箭头常驻 + 触摸滑动 + 键盘←→/ESC（输入框内不触发）
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { commentApi, mediaApi } from '../api'

const props = defineProps({
  items: { type: Array, required: true },
  startIndex: { type: Number, default: 0 },
})
const emit = defineEmits(['close', 'deleted', 'updated'])

const idx = ref(Math.max(0, Math.min(props.startIndex, props.items.length - 1)))
const item = computed(() => props.items[idx.value] || null)
const imgLoading = ref(true)

// 拍摄日期编辑：年月日全下拉，默认带出该媒体当前日期（无日期则当天）
const editingDate = ref(false)
const savingDate = ref(false)
const thisYear = new Date().getFullYear()
const dateYear = ref(thisYear)
const dateMonth = ref(new Date().getMonth() + 1)
const dateDay = ref(new Date().getDate())
const yearOptions = computed(() => {
  const years = Array.from({ length: 21 }, (_, i) => thisYear - 15 + i)
  const cur = item.value?.taken_at ? new Date(item.value.taken_at).getFullYear() : null
  if (cur && Number.isFinite(cur) && !years.includes(cur)) years.push(cur)
  return years.sort((a, b) => b - a)
})
const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1)
const dayOptions = computed(() =>
  Array.from({ length: new Date(dateYear.value, dateMonth.value, 0).getDate() }, (_, i) => i + 1)
)
watch([dateYear, dateMonth], () => {
  if (dateDay.value > dayOptions.value.length) dateDay.value = dayOptions.value.length
})

function startEditDate() {
  if (!item.value) return
  const d = item.value.taken_at ? new Date(item.value.taken_at) : new Date()
  const base = Number.isNaN(d.getTime()) ? new Date() : d
  dateYear.value = base.getFullYear()
  dateMonth.value = base.getMonth() + 1
  dateDay.value = base.getDate()
  editingDate.value = true
}

async function saveDate() {
  if (!item.value) return
  // 只改日期，保留原时分秒（无效则默认 12:00:00）
  const orig = item.value.taken_at ? new Date(item.value.taken_at) : new Date()
  const base = Number.isNaN(orig.getTime()) ? new Date() : orig
  const p2 = (n) => String(n).padStart(2, '0')
  const iso = `${dateYear.value}-${p2(dateMonth.value)}-${p2(dateDay.value)}T${p2(base.getHours())}:${p2(base.getMinutes())}:${p2(base.getSeconds())}`
  savingDate.value = true
  try {
    const res = await mediaApi.update(item.value.id, { taken_at: iso })
    item.value.taken_at = res?.taken_at || iso
    item.value.taken_at_source = 'manual'
    editingDate.value = false
    emit('updated') // 日期变了，父组件重新分组加载时间线
  } catch (e) {
    alert(e.message || '日期保存失败')
  } finally {
    savingDate.value = false
  }
}

// 评论
const comments = ref([])
const loadingComments = ref(false)
const commentText = ref('')
const posting = ref(false)

// 小故事编辑
const editingCaption = ref(false)
const captionDraft = ref('')
const savingCaption = ref(false)

// AI
const aiLoading = ref(false)
const adopting = ref(false)

const deleting = ref(false)
// 点赞
const heartBurst = ref(false)
let touchX = 0
let lastTap = 0

async function toggleLike() {
  if (!item.value) return
  try {
    const res = await mediaApi.like(item.value.id)
    item.value.liked_by_me = res.liked
    item.value.likes_count = res.likes
    if (res.liked) {
      heartBurst.value = true
      setTimeout(() => (heartBurst.value = false), 900)
    }
  } catch (e) {
    alert(e.message || '点赞失败')
  }
}
/** 双击/双击触摸图片 = 点赞 */
function onImageActivate() {
  if (item.value && !item.value.liked_by_me) toggleLike()
}

watch(idx, () => {
  imgLoading.value = true
  editingDate.value = false
  loadComments()
})
watch(
  () => props.items.length,
  () => {
    if (!props.items.length) emit('close')
  }
)

function loadComments() {
  if (!item.value) return
  loadingComments.value = true
  commentApi
    .list('media', item.value.id)
    .then((list) => (comments.value = Array.isArray(list) ? list : list.items ?? []))
    .catch(() => (comments.value = []))
    .finally(() => (loadingComments.value = false))
}

function next() {
  if (idx.value < props.items.length - 1) idx.value++
}
function prev() {
  if (idx.value > 0) idx.value--
}
function close() {
  emit('close')
}
function viewOriginal() {
  if (item.value?.url) window.open(item.value.url, '_blank')
}

function onKey(e) {
  const tag = (e.target.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  if (e.key === 'ArrowRight') next()
  else if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'Escape') close()
}
onMounted(() => {
  window.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
  loadComments()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})

function touchStart(e) {
  touchX = e.changedTouches[0].clientX
}
function touchEnd(e) {
  const dx = e.changedTouches[0].clientX - touchX
  if (dx < -50) {
    next()
    return
  }
  if (dx > 50) {
    prev()
    return
  }
  // 双击触摸图片 = 点赞（双击判定：300ms 内两次点击）
  const now = Date.now()
  if (now - lastTap < 300) {
    lastTap = 0
    onImageActivate()
  } else {
    lastTap = now
  }
}

function cardTitle(m) {
  if (!m) return ''
  if (m.caption) return m.caption
  // 音频没有画面，用原文件名（去扩展名）当默认标题
  if (m.media_type === 'audio' && m.orig_name) {
    return m.orig_name.replace(/\.[^.]+$/, '')
  }
  const d = new Date(m.taken_at)
  if (Number.isNaN(d.getTime())) return '记录的瞬间'
  return `${d.getMonth() + 1}月${d.getDate()}日 的小瞬间`
}
function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ---- 评论 ----
async function postComment() {
  const text = commentText.value.trim()
  if (!text || !item.value) return
  posting.value = true
  try {
    const c = await commentApi.create({ target_type: 'media', target_id: item.value.id, body: text })
    comments.value.push(c)
    item.value.comment_count = (item.value.comment_count ?? 0) + 1
    commentText.value = ''
  } catch (e) {
    alert(e.message || '评论失败')
  } finally {
    posting.value = false
  }
}

// ---- 小故事 ----
function startEdit() {
  captionDraft.value = item.value?.caption || ''
  editingCaption.value = true
}
async function saveCaption() {
  if (!item.value) return
  savingCaption.value = true
  try {
    await mediaApi.update(item.value.id, { caption: captionDraft.value })
    item.value.caption = captionDraft.value
    editingCaption.value = false
  } catch (e) {
    alert(e.message || '保存失败')
  } finally {
    savingCaption.value = false
  }
}

// ---- AI ----
async function runAI() {
  if (!item.value) return
  aiLoading.value = true
  try {
    const updated = await mediaApi.aiRun(item.value.id)
    item.value.ai_caption = updated.ai_caption
    item.value.ai_tagged_at = updated.ai_tagged_at
    item.value.tags = updated.tags
  } catch (e) {
    alert(e.message || 'AI 生成失败')
  } finally {
    aiLoading.value = false
  }
}
async function adoptCaption() {
  if (!item.value?.ai_caption) return
  adopting.value = true
  try {
    await mediaApi.update(item.value.id, { caption: item.value.ai_caption })
    item.value.caption = item.value.ai_caption
  } catch (e) {
    alert(e.message || '采用失败')
  } finally {
    adopting.value = false
  }
}
async function removeTag(t) {
  if (!item.value) return
  try {
    await mediaApi.removeTag(item.value.id, t.id)
    item.value.tags = (item.value.tags || []).filter((x) => x.id !== t.id)
  } catch (e) {
    alert(e.message || '删除失败')
  }
}

// ---- 删除 ----
async function deleteMedia() {
  if (!item.value) return
  if (!confirm('确定要删除这张照片/视频吗？此操作不可恢复。')) return
  deleting.value = true
  try {
    await mediaApi.remove(item.value.id)
    emit('deleted', item.value.id)
  } catch (e) {
    alert(e.message || '删除失败')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex flex-col bg-stone-950/97 md:flex-row">
    <!-- 图区 -->
    <div class="relative flex h-[52vh] shrink-0 items-center justify-center md:h-auto md:min-w-0 md:flex-1" @touchstart.passive="touchStart" @touchend.passive="touchEnd">
      <!-- 顶栏（覆盖图上） -->
      <div class="absolute inset-x-0 top-0 z-20 flex items-center gap-2 bg-gradient-to-b from-black/60 to-transparent px-3 py-2.5">
        <span class="rounded-full bg-white/10 px-3 py-1 text-xs text-white">{{ idx + 1 }} / {{ items.length }}</span>
        <a
          v-if="item?.url"
          :href="item.url"
          target="_blank"
          rel="noopener"
          class="ml-auto rounded-full bg-white/10 px-3 py-1 text-xs text-white hover:bg-white/20"
        >
          🔍 查看原图
        </a>
        <button class="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-lg text-white hover:bg-white/20" @click="close">✕</button>
      </div>

      <!-- 箭头（常驻，边界置灰） -->
      <button
        class="absolute left-2 top-1/2 z-10 flex h-14 w-14 -translate-y-1/2 items-center justify-center rounded-full text-3xl md:left-6 md:h-16 md:w-16"
        :class="idx > 0 ? 'bg-white/25 text-white hover:bg-white/40' : 'cursor-default bg-white/5 text-white/20'"
        @click.stop="idx > 0 && prev()"
      >
        ‹
      </button>
      <button
        class="absolute right-2 top-1/2 z-10 flex h-14 w-14 -translate-y-1/2 items-center justify-center rounded-full text-3xl md:right-6 md:h-16 md:w-16"
        :class="idx < items.length - 1 ? 'bg-white/25 text-white hover:bg-white/40' : 'cursor-default bg-white/5 text-white/20'"
        @click.stop="idx < items.length - 1 && next()"
      >
        ›
      </button>

      <template v-if="item">
        <!-- 加载指示 -->
        <div v-if="imgLoading && item.media_type !== 'video' && item.media_type !== 'audio'" class="absolute flex flex-col items-center gap-2 text-white/60">
          <span class="h-10 w-10 animate-spin rounded-full border-4 border-white/20 border-t-blush-400"></span>
          <span class="text-xs">加载中…</span>
        </div>
        <!-- 双击点赞心形爆闪 -->
        <div v-if="heartBurst" class="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span class="heart-burst text-8xl">❤️</span>
        </div>
        <video
          v-if="item.media_type === 'video'"
          :src="item.url || item.thumbnail_url"
          controls
          class="max-h-full max-w-full"
          @loadeddata="imgLoading = false"
          @dblclick="onImageActivate"
        />
        <!-- 音频：封面占位 + 播放器 -->
        <div
          v-else-if="item.media_type === 'audio'"
          class="flex w-full max-w-sm flex-col items-center gap-4 rounded-3xl bg-white/10 p-6 backdrop-blur"
        >
          <img
            :src="item.thumbnail_url"
            alt=""
            class="h-32 w-32 rounded-2xl object-cover shadow-lg"
            @load="imgLoading = false"
          />
          <p class="max-w-full truncate text-center text-sm font-medium text-white">{{ cardTitle(item) }}</p>
          <audio
            :src="item.url"
            controls
            class="w-full"
            @canplay="imgLoading = false"
          ></audio>
        </div>
        <img
          v-else
          :src="item.thumbnail_url"
          :alt="item.caption || ''"
          class="max-h-full max-w-full select-none object-contain transition-opacity"
          :class="imgLoading ? 'opacity-0' : 'opacity-100'"
          draggable="false"
          @load="imgLoading = false"
          @dblclick="onImageActivate"
        />
      </template>
    </div>

    <!-- 信息面板 -->
    <div class="min-h-0 flex-1 overflow-y-auto bg-white md:w-96 md:flex-none md:rounded-l-2xl">
      <div v-if="item" class="p-4">
        <!-- 标题 + 点赞 + 元数据 -->
        <p class="font-art text-lg text-stone-700">{{ cardTitle(item) }}</p>
        <div class="mt-1.5 flex items-center gap-3">
          <button
            class="flex items-center gap-1 rounded-full px-2.5 py-1 text-sm transition-transform active:scale-90"
            :class="item.liked_by_me ? 'bg-blush-50 text-blush-500' : 'bg-cream-100 text-stone-400'"
            :title="item.liked_by_me ? '取消点赞' : '点赞'"
            @click="toggleLike"
          >
            <span class="text-base">{{ item.liked_by_me ? '❤️' : '🤍' }}</span>
            <span class="text-xs">{{ item.likes_count ?? 0 }}</span>
          </button>
          <span class="text-xs text-stone-400">💬 {{ item.comment_count ?? 0 }}</span>
        </div>
        <div class="mt-1.5 flex items-center gap-2">
          <p class="text-xs text-stone-400">📅 {{ fmtDate(item.taken_at) }}</p>
          <button v-if="!editingDate" class="text-xs text-blush-500" @click="startEditDate">修改日期</button>
        </div>
        <div v-if="editingDate" class="mt-2 rounded-xl bg-cream-50 p-2.5">
          <div class="flex items-center gap-1.5 text-sm text-stone-600">
            <select v-model.number="dateYear" class="rounded-lg border border-honey-300/70 bg-white px-2 py-1 outline-none focus:border-blush-400">
              <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
            </select>
            <span>年</span>
            <select v-model.number="dateMonth" class="rounded-lg border border-honey-300/70 bg-white px-2 py-1 outline-none focus:border-blush-400">
              <option v-for="m in monthOptions" :key="m" :value="m">{{ m }}</option>
            </select>
            <span>月</span>
            <select v-model.number="dateDay" class="rounded-lg border border-honey-300/70 bg-white px-2 py-1 outline-none focus:border-blush-400">
              <option v-for="d in dayOptions" :key="d" :value="d">{{ d }}</option>
            </select>
            <span>日</span>
          </div>
          <p class="mt-1.5 text-[10px] text-stone-400">只改日期，时分秒保持原样；保存后时间线按新日期重排</p>
          <div class="mt-2 flex justify-end gap-2">
            <button class="rounded-full px-4 py-1.5 text-xs text-stone-400" @click="editingDate = false">取消</button>
            <button
              class="rounded-full bg-blush-500 px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
              :disabled="savingDate"
              @click="saveDate"
            >
              {{ savingDate ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
        <p v-if="item.orig_name || item.camera_model || item.location_name" class="mt-1 text-xs text-stone-400">
          <span v-if="item.orig_name" class="font-mono">📄 {{ item.orig_name }}</span>
          <span v-if="item.orig_name && (item.camera_model || item.location_name)" class="mx-1">·</span>
          <span v-if="item.camera_make || item.camera_model">📷 {{ [item.camera_make, item.camera_model].filter(Boolean).join(' ') }}</span>
          <span v-if="item.camera_model && item.location_name" class="mx-1">·</span>
          <span v-if="item.location_name">📍 {{ item.location_name }}</span>
        </p>

        <!-- 小故事 -->
        <section class="mt-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold text-stone-500">📝 小故事</h2>
            <button v-if="!editingCaption" class="text-xs text-blush-500" @click="startEdit">编辑</button>
          </div>
          <p v-if="!editingCaption" class="mt-2 text-sm text-stone-600">
            {{ item.caption || '这一刻的小故事还没写，点"编辑"写下来吧' }}
          </p>
          <div v-else class="mt-2 space-y-2">
            <textarea
              v-model="captionDraft"
              rows="3"
              class="w-full rounded-xl border border-honey-300/70 bg-cream-50 px-3 py-2 text-sm outline-none focus:border-blush-400"
              placeholder="记录这一刻的小故事…"
            ></textarea>
            <div class="flex justify-end gap-2">
              <button class="rounded-full px-4 py-1.5 text-xs text-stone-400" @click="editingCaption = false">取消</button>
              <button class="rounded-full bg-blush-500 px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-60" :disabled="savingCaption" @click="saveCaption">
                {{ savingCaption ? '保存中…' : '保存' }}
              </button>
            </div>
          </div>
        </section>

        <!-- AI 建议 -->
        <section class="mt-4 border-t border-cream-100 pt-4">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold text-stone-500">✨ AI 建议</h2>
            <button
              v-if="!item.ai_tagged_at && item.media_type === 'photo'"
              :disabled="aiLoading"
              class="text-xs text-blush-500 disabled:opacity-50"
              @click="runAI"
            >
              {{ aiLoading ? '生成中…（约半分钟）' : '生成 AI 标记' }}
            </button>
          </div>
          <div v-if="item.ai_caption" class="mt-2 flex items-start justify-between gap-2 rounded-xl bg-cream-50 p-2.5">
            <p class="text-sm text-stone-600">💡 {{ item.ai_caption }}</p>
            <button class="shrink-0 rounded-full bg-blush-500 px-3 py-1 text-[10px] font-semibold text-white disabled:opacity-50" :disabled="adopting" @click="adoptCaption">
              {{ adopting ? '…' : '采用为标题' }}
            </button>
          </div>
          <p v-else-if="item.ai_tagged_at" class="mt-2 text-xs text-stone-400">AI 没想出合适的标题，先看看标签吧</p>
          <div v-if="item.tags?.length" class="mt-2 flex flex-wrap gap-1.5">
            <span v-for="t in item.tags" :key="t.id" class="flex items-center gap-1 rounded-full bg-honey-300/30 px-2.5 py-1 text-xs text-stone-600">
              #{{ t.name }}
              <button class="text-stone-400 hover:text-blush-600" @click="removeTag(t)">✕</button>
            </span>
          </div>
          <p v-else-if="item.ai_tagged_at" class="mt-2 text-xs text-stone-400">还没有标签</p>
        </section>

        <!-- 评论 -->
        <section class="mt-4 border-t border-cream-100 pt-4">
          <h2 class="text-sm font-semibold text-stone-500">💬 成员留言 ({{ comments.length }})</h2>
          <ul v-if="comments.length" class="mt-3 space-y-3">
            <li v-for="c in comments" :key="c.id" class="flex gap-3">
              <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blush-100 text-xs font-semibold text-blush-600">
                {{ (c.author_name || '成员').slice(0, 1) }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs text-stone-400">{{ c.author_name || '成员' }} · {{ fmtDate(c.created_at) }}</p>
                <p class="mt-0.5 break-words text-sm text-stone-600">{{ c.body }}</p>
              </div>
            </li>
          </ul>
          <p v-else class="mt-3 text-xs text-stone-400">还没有留言，来说点什么吧～</p>

          <form class="mt-4 flex gap-2" @submit.prevent="postComment">
            <input
              v-model="commentText"
              type="text"
              placeholder="对这瞬间说点什么…"
              class="min-w-0 flex-1 rounded-full border border-honey-300/70 bg-cream-50 px-4 py-2 text-sm outline-none placeholder:text-stone-300 focus:border-blush-400"
            />
            <button
              type="submit"
              :disabled="posting || !commentText.trim()"
              class="shrink-0 rounded-full bg-blush-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              发送
            </button>
          </form>
        </section>

        <!-- 删除 -->
        <button class="mt-6 w-full rounded-full border border-blush-200 py-2 text-xs text-blush-600 hover:bg-blush-50" :disabled="deleting" @click="deleteMedia">
          删除这张{{ item.media_type === 'video' ? '视频' : item.media_type === 'audio' ? '录音' : '照片' }}
        </button>
      </div>
    </div>
  </div>
</template>
