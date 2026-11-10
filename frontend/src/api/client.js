const TOKEN_KEY = 'family_album_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * 基础请求封装：自动带 Authorization: Bearer <token>
 * 401 时清除 token 并跳登录页
 */
export async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!isForm) headers['Content-Type'] = 'application/json'

  const res = await fetch(path, {
    method,
    headers,
    body: isForm ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    clearToken()
    if (!location.pathname.startsWith('/login')) {
      location.href = '/login'
    }
    throw new Error('未登录或登录已过期')
  }
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      if (data.detail) msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  if (res.status === 204) return null
  return res.json()
}
