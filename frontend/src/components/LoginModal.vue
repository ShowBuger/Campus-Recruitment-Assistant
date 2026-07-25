<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toast = useToastStore()

const username = ref('')
const password = ref('')
const inviteCode = ref('')
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)

function toggleAuthMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function handleAuth() {
  error.value = ''
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(username.value, password.value, inviteCode.value)
    } else {
      await auth.login(username.value, password.value)
    }
    // Success — auth store handles state, App.vue reacts to isLoggedIn
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-mask login-overlay" style="display:flex">
    <div class="login-card">
      <div class="mark" style="margin:0 auto 16px;width:44px;height:44px"></div>
      <h2>{{ isRegister ? '注册账号' : '登录看板' }}</h2>
      <p>{{ isRegister ? '使用管理员提供的一次性邀请码注册' : '校招信息看板 · 多用户版' }}</p>
      <div class="login-error">{{ error }}</div>
      <form @submit.prevent="handleAuth">
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
