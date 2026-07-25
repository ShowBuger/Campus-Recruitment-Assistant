import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get, post, setToken } from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('rb_token') || '')

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.is_admin || user.value?.is_root)

  async function checkSession() {
    const data = await get('/api/auth/me', { silent: true })
    user.value = data.user
    token.value = localStorage.getItem('rb_token') || ''
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
    clear()
  }

  function clear() {
    setToken('')
    token.value = ''
    user.value = null
  }

  return { user, token, isLoggedIn, isAdmin, checkSession, login, register, logout, clear }
})
