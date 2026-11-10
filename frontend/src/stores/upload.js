// 全局上传队列：活在 Pinia 里，脱离上传页组件存活。
// 用户切到时间线/详情页随便逛，上传照常逐张进行；所有页面共享进度。
import { defineStore } from 'pinia'
import { mediaApi } from '../api'

const MEDIA_EXT =
  /\.(jpe?g|png|webp|gif|heic|heif|bmp|tiff?|mp4|mov|m4v|avi|webm|mp3|m4a|wav|aac|ogg|amr|flac|3gp)$/i
let uid = 0

/** 压缩图片：长边压到 2048、JPEG 质量 0.85。失败/非可解码格式回退原文件。 */
async function maybeCompress(file, enabled) {
  if (!enabled || !file.type.startsWith('image/') || file.type === 'image/gif') return file
  try {
    const bitmap = await createImageBitmap(file)
    const maxEdge = 2048
    const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height))
    if (scale >= 1 && file.size < 2 * 1024 * 1024) return file // 已够小不压
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.85))
    if (!blob || blob.size >= file.size) return file // 压完反而更大就用原图
    return new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file
  }
}

export const useUploadStore = defineStore('upload', {
  state: () => ({
    items: [], // {id, file, name, size, isVideo, status:'pending|uploading|done|skip|fail', progress, error}
    active: false, // 队列运行中
    hint: '', // 微信批次日期
    compress: false,
    lastError: '',
  }),

  getters: {
    totalCount: (s) => s.items.length,
    pendingCount: (s) => s.items.filter((i) => i.status === 'pending').length,
    successCount: (s) => s.items.filter((i) => i.status === 'done').length,
    skipCount: (s) => s.items.filter((i) => i.status === 'skip').length,
    failCount: (s) => s.items.filter((i) => i.status === 'fail').length,
    finishedCount: (s) =>
      s.items.filter((i) => ['done', 'skip', 'fail'].includes(i.status)).length,
    // 0-100 总进度（按完成张数比例）
    overallPct: (s) =>
      s.items.length ? Math.round((s.items.filter((i) => i.status !== 'pending').length / s.items.length) * 100) : 0,
  },

  actions: {
    /** 入队并自动开跑。hint=微信批次日期，compress=是否压缩 */
    enqueue(fileList, { hint = '', compress = false } = {}) {
      for (const f of fileList) {
        const isMedia =
          f.type.startsWith('image/') ||
          f.type.startsWith('video/') ||
          f.type.startsWith('audio/') ||
          MEDIA_EXT.test(f.name)
        if (isMedia) {
          this.items.push({
            id: ++uid,
            file: f,
            name: f.name,
            size: f.size,
            isVideo: f.type.startsWith('video/'),
            isAudio: f.type.startsWith('audio/') || /\.(mp3|m4a|wav|aac|ogg|amr|flac|3gp)$/i.test(f.name),
            status: 'pending',
            progress: 0,
            error: '',
            dup: null, // 与哪张已有照片重复 {id, orig_name, taken_at}
          })
        }
      }
      if (hint) this.hint = hint
      this.compress = compress
      if (!this.active) this._run()
    },

    async _run() {
      this.active = true
      this.lastError = ''
      // while + find：跑的过程中再入队也能接上
      for (;;) {
        const item = this.items.find((i) => i.status === 'pending')
        if (!item) break
        item.status = 'uploading'
        item.progress = 0
        item.paused = false
        item.cancelled = false
        try {
          const payload = await maybeCompress(item.file, this.compress)
          // 整文件级重试：分片内部已有 3 次重试，这里再兜底 2 轮
          let res = null
          let lastErr = null
          for (let attempt = 0; attempt < 2; attempt++) {
            try {
              res = await mediaApi.uploadChunked(
                payload,
                (pct) => {
                  item.progress = pct
                },
                {
                  takenAtHint: this.hint,
                  shouldPause: () => !!item.paused,
                  isCancelled: () => !!item.cancelled,
                }
              )
              lastErr = null
              break
            } catch (e) {
              if (item.cancelled || e.message === '已取消') {
                lastErr = e
                break
              }
              lastErr = e
              if (attempt < 1) await new Promise((r) => setTimeout(r, 1500))
            }
          }
          if (lastErr) {
            if (item.cancelled || lastErr.message === '已取消') {
              // 用户主动取消：从队列移除
              const idx = this.items.indexOf(item)
              if (idx >= 0) this.items.splice(idx, 1)
            } else {
              throw lastErr
            }
          } else if (res.skipped) {
            item.status = 'skip'
            // 记录与哪张重复：显示原文件名并支持跳转查看
            if (res.existing) {
              item.dup = {
                id: res.existing.id,
                orig_name: res.existing.orig_name,
                taken_at: res.existing.taken_at,
              }
            }
          } else {
            item.status = 'done'
            item.progress = 100
          }
        } catch (e) {
          if (item.cancelled || e.message === '已取消') {
            const idx = this.items.indexOf(item)
            if (idx >= 0) this.items.splice(idx, 1)
            continue
          }
          item.status = 'fail'
          item.error = e.message || '上传失败'
          this.lastError = item.error
        }
      }
      this.active = false
    },

    /** 暂停某项（当前片传完即停，已传分片保留） */
    pauseItem(item) {
      if (item.status === 'uploading') item.paused = true
    },

    /** 恢复某项 */
    resumeItem(item) {
      item.paused = false
    },

    /** 取消某项：中止传输并从队列移除 */
    cancelItem(item) {
      item.cancelled = true
      item.paused = false
      if (item.status !== 'uploading') {
        const idx = this.items.indexOf(item)
        if (idx >= 0) this.items.splice(idx, 1)
      }
    },

    /** 失败重试：把失败项重新排队 */
    retryFailed() {
      this.items.forEach((i) => {
        if (i.status === 'fail') {
          i.status = 'pending'
          i.progress = 0
        }
      })
      if (!this.active) this._run()
    },

    /** 清掉已完成的条目（队列空闲时可用） */
    clearFinished() {
      if (this.active) return
      this.items = this.items.filter((i) => i.status === 'pending')
    },
  },
})
