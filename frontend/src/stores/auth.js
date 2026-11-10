import { defineStore } from 'pinia'
import { authApi } from '../api'
import { getToken, setToken, clearToken } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken(),
    user: null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
  },
  actions: {
    async login(payload) {
      const data = await authApi.login(payload)
      if (data?.access_token) {
        this.token = data.access_token
        setToken(data.access_token)
      }
      await this.fetchMe()
    },
    async register(payload) {
      const data = await authApi.register(payload)
      // 注册成功若直接返回 token 则自动登录
      if (data?.access_token) {
        this.token = data.access_token
        setToken(data.access_token)
        await this.fetchMe()
      }
      return data
    },
    async fetchMe() {
      try {
        this.user = await authApi.me()
        // 静默续期：每次打开应用换 30 天新 token，家人基本免重复登录
        try {
          const fresh = await authApi.refresh()
          if (fresh?.access_token) {
            this.token = fresh.access_token
            setToken(fresh.access_token)
          }
        } catch { /* 续期失败不影响使用，token 仍有效期内 */ }
      } catch {
        this.user = null
      }
    },
    logout() {
      this.token = null
      this.user = null
      clearToken()
    },
  },
})
