import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get, post, setToken } from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('rb_token') || '')

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_admin || user.value?.is_root)

  async function checkSession() {
    try {
      const data = await get('/api/auth/me', { silent: true })
      user.value = data.user
      token.value = localStorage.getItem('rb_token') || ''
    } catch (e) {
      // 网络错误不抛，避免误清 token
      if (e?.message === '登录已过期') throw e
      console.warn('checkSession network error:', e.message)
    }
  }

  async function login(username, password) {
    const data = await post('/api/auth/login', { username, password })
    setToken(data.token)
    token.value = data.token
    user.value = data.user
  }

  async function register(username, password, invite_code) {
    const data = await post('/api/auth/register', { username, password, invite_code })
    setToken(data.token)
    token.value = data.token
    user.value = data.user
  }

  async function logout() {
    await post('/api/auth/logout').catch(() => {})
    // 主动退出后不能在登录页再次自动提交已保存的密码。
    localStorage.setItem('rb_auto_login', '0')
    clear()
  }

  function clear() {
    setToken('')
    token.value = ''
    user.value = null
  }

  function setUser(nextUser) { user.value = { ...(user.value || {}), ...nextUser } }

  return { user, token, isLoggedIn, isAdmin, checkSession, login, register, logout, clear, setUser }
})
