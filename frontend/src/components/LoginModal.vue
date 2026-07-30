<script setup>
import { onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const REMEMBER_KEY = 'rb_remember_password'
const AUTO_LOGIN_KEY = 'rb_auto_login'
const USERNAME_KEY = 'rb_saved_username'
const PASSWORD_KEY = 'rb_saved_password'

const username = ref('')
const password = ref('')
const inviteCode = ref('')
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)
const rememberPassword = ref(localStorage.getItem(REMEMBER_KEY) === '1')
const autoLogin = ref(localStorage.getItem(AUTO_LOGIN_KEY) === '1')

if (rememberPassword.value) {
  username.value = localStorage.getItem(USERNAME_KEY) || ''
  password.value = localStorage.getItem(PASSWORD_KEY) || ''
}

watch(rememberPassword, (enabled) => {
  localStorage.setItem(REMEMBER_KEY, enabled ? '1' : '0')
  if (!enabled) {
    autoLogin.value = false
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(PASSWORD_KEY)
  }
})

watch(autoLogin, (enabled) => {
  localStorage.setItem(AUTO_LOGIN_KEY, enabled ? '1' : '0')
  if (enabled) rememberPassword.value = true
})

function toggleAuthMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function handleAuth(isAutomatic = false) {
  error.value = ''
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(username.value, password.value, inviteCode.value)
    } else {
      await auth.login(username.value, password.value)
      if (rememberPassword.value) {
        localStorage.setItem(USERNAME_KEY, username.value)
        localStorage.setItem(PASSWORD_KEY, password.value)
      }
    }
    // Success — auth store handles state, App.vue reacts to isLoggedIn
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '操作失败，请重试'
    if (isAutomatic) autoLogin.value = false
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (autoLogin.value && username.value && password.value) handleAuth(true)
})
</script>

<template>
  <div class="modal-mask login-overlay" style="display:flex">
    <div class="login-card">
      <div class="mark" style="margin:0 auto 16px;width:44px;height:44px"></div>
      <h2>{{ isRegister ? '注册账号' : '登录看板' }}</h2>
      <p>{{ isRegister ? '使用管理员提供的一次性邀请码注册' : '校招信息看板 · 多用户版' }}</p>
      <div class="login-error">{{ error }}</div>
      <form @submit.prevent="handleAuth(false)">
        <input
          id="login-username"
          v-model.trim="username"
          placeholder="用户名"
          required
          minlength="2"
          maxlength="50"
          autocomplete="username"
        >
        <input
          id="login-password"
          v-model="password"
          type="password"
          placeholder="密码"
          required
          minlength="4"
          maxlength="100"
          :autocomplete="isRegister ? 'new-password' : 'current-password'"
        >
        <input
          id="login-invite-code"
          v-if="isRegister"
          v-model.trim="inviteCode"
          placeholder="CRA-XXXX-XXXX"
          autocomplete="off"
          maxlength="32"
          style="text-transform:uppercase"
        >
        <div v-if="!isRegister" class="login-options">
          <label>
            <input v-model="rememberPassword" type="checkbox">
            <span>记住密码</span>
          </label>
          <label>
            <input v-model="autoLogin" type="checkbox">
            <span>自动登录</span>
          </label>
        </div>
        <button
          class="btn btn-primary"
          id="login-submit"
          type="submit"
          :disabled="loading"
        >
          {{ loading ? '...' : (isRegister ? '注 册' : '登 录') }}
        </button>
      </form>
      <button class="toggle" id="login-toggle" type="button" @click="toggleAuthMode">
        {{ isRegister ? '已有账号？点击登录' : '没有账号？点击注册' }}
      </button>
    </div>
  </div>
</template>
