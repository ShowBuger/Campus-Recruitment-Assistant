<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['close'])

const auth = useAuthStore()

const username = ref('')
const password = ref('')
const inviteCode = ref('')
const error = ref('')
const loading = ref(false)
const isRegister = ref(false)

function toggleMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    if (isRegister.value) {
      await auth.register(username.value, password.value, inviteCode.value)
    } else {
      await auth.login(username.value, password.value)
    }
    emit('close')
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="login-card">
      <h2>{{ isRegister ? '注册账号' : '登录看板' }}</h2>
      <p>{{ isRegister ? '使用管理员提供的一次性邀请码注册' : '校招信息看板 · 多用户版' }}</p>
      <form @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input
            v-model="username"
            required
            minlength="2"
            maxlength="50"
            autocomplete="username"
          >
        </div>
        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            required
            minlength="4"
            maxlength="100"
            :autocomplete="isRegister ? 'new-password' : 'current-password'"
          >
        </div>
        <div class="form-group" v-if="isRegister">
          <label>邀请码</label>
          <input
            v-model="inviteCode"
            required
            placeholder="CRA-XXXX-XXXX"
            style="text-transform:uppercase"
          >
        </div>
        <p class="login-error" v-if="error">{{ error }}</p>
        <button
          class="btn btn-primary"
          type="submit"
          :disabled="loading"
        >
          {{ loading ? '...' : (isRegister ? '注 册' : '登 录') }}
        </button>
      </form>
      <button class="toggle" @click="toggleMode">
        {{ isRegister ? '已有账号？点击登录' : '没有账号？点击注册' }}
      </button>
    </div>
  </div>
</template>
