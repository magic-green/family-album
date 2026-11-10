// API 层：接口契约见 README.md
import { request } from './client'
import { sha256File } from '../utils/sha256'

// ---- Auth ----
export const authApi = {
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  login: (payload) => request('/api/auth/login', { method: 'POST', body: payload }),
  me: () => request('/api/auth/me'),
  refresh: () => request('/api/auth/refresh', { method: 'POST' }),
  users: () => request('/api/auth/users'),
  deleteUser: (id) => request(`/api/auth/users/${id}`, { method: 'DELETE' }),
  logs: (limit = 50) => request(`/api/auth/logs?limit=${limit}`),
}

// ---- 系统 ----
export const systemApi = {
  info: () => request('/api/system/info'),
  getSettings: () => request('/api/settings'),
  putSettings: (payload) => request('/api/settings', { method: 'PUT', body: payload }),
  uploadAvatar: (file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/system/avatar')
      const token = localStorage.getItem('family_album_token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      if (onProgress) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try { resolve(JSON.parse(xhr.responseText)) } catch { resolve(null) }
        } else {
          let msg = '头像上传失败'
          try {
            const d = JSON.parse(xhr.responseText)
            if (d.detail) msg = d.detail
          } catch { /* ignore */ }
          reject(new Error(msg))
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(form)
    })
  },
}

// ---- Media ----
// XHR 通用发送（带鉴权、上传进度回调、可选 AbortSignal）
function xhrSend(url, form, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    const token = localStorage.getItem('family_album_token')
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    if (signal) {
      if (signal.aborted) {
        reject(new Error('已取消'))
        return
      }
      signal.addEventListener('abort', () => {
        xhr.abort()
        reject(new Error('已取消'))
      })
    }
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded)
    }
    xhr.onload = () => {
      if (xhr.status === 401) {
        localStorage.removeItem('family_album_token')
        location.href = '/login'
        reject(new Error('未登录或登录已过期'))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) } catch { resolve(null) }
      } else {
        let msg = `请求失败 (${xhr.status})`
        try {
          const d = JSON.parse(xhr.responseText)
          if (d.detail) msg = typeof d.detail === 'string' ? d.detail : msg
        } catch { /* ignore */ }
        reject(new Error(msg))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误'))
    xhr.send(form)
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export const mediaApi = {
  list: ({ page = 1, pageSize = 30, tag = '' } = {}) =>
    request(`/api/media?page=${page}&page_size=${pageSize}${tag ? `&tag=${encodeURIComponent(tag)}` : ''}`),
  tagsAll: () => request('/api/media/tags/all'),
  aiRun: (id) => request(`/api/media/${id}/ai/run`, { method: 'POST' }),
  like: (id) => request(`/api/media/${id}/like`, { method: 'POST' }),
  removeTag: (id, tagId) => request(`/api/media/${id}/tags/${tagId}`, { method: 'DELETE' }),
  detail: (id) => request(`/api/media/${id}`),
  update: (id, payload) => request(`/api/media/${id}`, { method: 'PATCH', body: payload }),
  remove: (id) => request(`/api/media/${id}`, { method: 'DELETE' }),
  /**
   * 分片上传（3 片并行，弱网友好）：
   * - 每片失败自动重试 3 次（指数退避）
   * - onProgress(pct) 按整文件真实字节回调 0-99
   * - opts.shouldPause() 返回 true 时片间暂停（已传分片保留，恢复不重来）
   * - opts.isCancelled() 返回 true 时中止（抛 '已取消'）
   * 返回 { item: MediaOut|null, skipped: boolean }
   */
  async uploadChunked(file, onProgress, opts = {}) {
    // 秒传：先算哈希问服务器，已存在直接跳过（家人间互转的重复图 0 流量）
    const hash = await sha256File(file)
    if (hash) {
      try {
        const check = await request('/api/media/check', { method: 'POST', body: { content_hash: hash } })
        if (check?.exists) {
          if (onProgress) onProgress(100)
          return { item: check.item ?? null, skipped: true, existing: check.item ?? null }
        }
      } catch { /* 探测失败就走正常上传 */ }
    }
    const CHUNK = 1024 * 1024
    const PARALLEL = 3
    const total = Math.max(1, Math.ceil(file.size / CHUNK))
    const initForm = new FormData()
    initForm.append('total', String(total))
    const init = await xhrSend('/api/media/upload/init', initForm)
    const uploadId = init?.upload_id
    if (!uploadId) throw new Error('无法初始化上传')

    const isCancelled = () => !!(opts.isCancelled && opts.isCancelled())
    const shouldPause = () => !!(opts.shouldPause && opts.shouldPause())
    const completedBytes = { value: 0 }
    const inflight = new Map() // chunkIndex -> 已传字节
    const report = () => {
      if (!onProgress) return
      let bytes = completedBytes.value
      for (const v of inflight.values()) bytes += v
      onProgress(Math.min(99, Math.round((bytes / file.size) * 100)))
    }
    const waitWhilePaused = async () => {
      while (shouldPause() && !isCancelled()) await sleep(300)
      return !isCancelled()
    }

    let nextIndex = 0
    const worker = async () => {
      for (;;) {
        if (!(await waitWhilePaused())) return false
        const i = nextIndex++
        if (i >= total) return true
        const blob = file.slice(i * CHUNK, (i + 1) * CHUNK)
        let attempt = 0
        for (;;) {
          if (isCancelled()) return false
          const ctrl = new AbortController()
          inflight.set(i, 0)
          try {
            const form = new FormData()
            form.append('index', String(i))
            form.append('chunk', blob, `chunk_${i}`)
            await xhrSend(
              `/api/media/upload/${uploadId}/chunk`,
              form,
              (loaded) => {
                inflight.set(i, loaded)
                report()
              },
              ctrl.signal
            )
            break
          } catch (e) {
            if (isCancelled() || e.message === '已取消') return false
            attempt++
            if (attempt >= 4) throw e
            await sleep(800 * attempt)
          } finally {
            inflight.delete(i)
          }
        }
        completedBytes.value += blob.size
        report()
      }
    }

    const results = await Promise.all(Array.from({ length: Math.min(PARALLEL, total) }, worker))
    if (results.some((r) => r === false)) throw new Error('已取消')

    const finForm = new FormData()
    finForm.append('orig_name', file.name)
    if (opts.takenAtHint) finForm.append('taken_at_hint', opts.takenAtHint)
    const fin = await xhrSend(`/api/media/upload/${uploadId}/finalize`, finForm)
    const items = fin?.items ?? []
    return { item: items[0] ?? null, skipped: (fin?.skipped ?? 0) > 0, existing: fin?.existing ?? null }
  },
  /**
   * 单文件上传（上传页逐张串行调用，每张独立进度）
   * opts.takenAtHint：批次拍摄时间提示（微信照片模式用，如 "2025-03"）
   * onProgress(loadedPct) 回调 0-100
   * 返回 { item: MediaOut|null, skipped: boolean }
   */
  uploadOne(file, onProgress, opts = {}) {
    return new Promise((resolve, reject) => {
      const form = new FormData()
      form.append('files', file)
      if (opts.takenAtHint) form.append('taken_at_hint', opts.takenAtHint)
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/media/upload')
      const token = localStorage.getItem('family_album_token')
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }
      xhr.onload = () => {
        if (xhr.status === 401) {
          localStorage.removeItem('family_album_token')
          location.href = '/login'
          reject(new Error('未登录或登录已过期'))
          return
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          let data = null
          try { data = JSON.parse(xhr.responseText) } catch { /* ignore */ }
          const items = Array.isArray(data) ? data : data?.items ?? []
          const skipped = Array.isArray(data) ? 0 : data?.skipped ?? 0
          resolve({ item: items[0] ?? null, skipped: skipped > 0 })
        } else {
          let msg = `上传失败 (${xhr.status})`
          try {
            const d = JSON.parse(xhr.responseText)
            if (d.detail) msg = typeof d.detail === 'string' ? d.detail : msg
          } catch { /* ignore */ }
          reject(new Error(msg))
        }
      }
      xhr.onerror = () => reject(new Error('网络错误，上传失败'))
      xhr.send(form)
    })
  },
}

// ---- Comments ----
export const commentApi = {
  list: (targetType, targetId) =>
    request(`/api/comments?target_type=${encodeURIComponent(targetType)}&target_id=${encodeURIComponent(targetId)}`),
  create: (payload) => request('/api/comments', { method: 'POST', body: payload }),
  remove: (id) => request(`/api/comments/${id}`, { method: 'DELETE' }),
}
