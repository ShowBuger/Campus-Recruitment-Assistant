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

watch(rememberPassword, enabled => {
  localStorage.setItem(REMEMBER_KEY, enabled ? '1' : '0')
  if (!enabled) {
    autoLogin.value = false
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(PASSWORD_KEY)
  }
})

watch(autoLogin, enabled => {
  localStorage.setItem(AUTO_LOGIN_KEY, enabled ? '1' : '0')
  if (enabled) rememberPassword.value = true
})

function toggleMode() {
  isRegister.value = !isRegister.value
  error.value = ''
}

async function submit(isAutomatic = false) {
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
  } catch (e) {
    error.value = e?.message || '操作失败，请重试'
    if (isAutomatic) autoLogin.value = false
  } finally {
    loading.value = false
  }
}

function control(action) {
  window.electronAPI?.windowControl?.(action)
}

onMounted(() => {
  control('login-size')
  if (!auth.token && autoLogin.value && username.value && password.value) submit(true)
})
</script>

<template>
  <main class="desktop-login">
    <header class="desktop-login-titlebar">
      <div><span></span><b>CAMPUS_BOARD</b></div>
      <nav>
        <button type="button" title="最小化" @click="control('minimize')">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 11h10v2H3z"/></svg>
        </button>
        <button type="button" title="关闭到托盘" @click="control('close')">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2h2v2h2v2h2V4h2V2h2v2h-2v2H9v2h2v2h2v2h-2v-2H9V8H7v2H5v2H3v-2h2V8h2V6H5V4H3V2Z"/></svg>
        </button>
      </nav>
    </header>

    <section class="desktop-login-content">
      <div class="desktop-login-avatar"><span></span></div>
      <div class="desktop-login-copy">
        <small>{{ isRegister ? 'NEW / ACCOUNT' : 'WELCOME / BACK' }}</small>
        <h1>{{ isRegister ? '注册账号' : '校招信息看板' }}</h1>
        <p>{{ isRegister ? '使用管理员提供的一次性邀请码' : '登录后继续管理你的校招投递' }}</p>
      </div>

      <form @submit.prevent="submit(false)">
        <label>
          <span>用户名</span>
          <input v-model.trim="username" required minlength="2" maxlength="50" autocomplete="username" placeholder="请输入用户名">
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" required minlength="4" maxlength="100" type="password" :autocomplete="isRegister ? 'new-password' : 'current-password'" placeholder="请输入密码">
        </label>
        <label v-if="isRegister">
          <span>邀请码</span>
          <input v-model.trim="inviteCode" required maxlength="32" autocomplete="off" placeholder="CRA-XXXX-XXXX">
        </label>

        <div v-if="!isRegister" class="desktop-login-options">
          <label><input v-model="rememberPassword" type="checkbox"><span>记住密码</span></label>
          <label><input v-model="autoLogin" type="checkbox"><span>自动登录</span></label>
        </div>

        <div class="desktop-login-error" aria-live="polite">{{ error }}</div>
        <button class="desktop-login-submit" type="submit" :disabled="loading">
          {{ loading ? '连接中…' : (isRegister ? '注册并进入' : '登录') }}
        </button>
      </form>

      <button class="desktop-login-switch" type="button" @click="toggleMode">
        {{ isRegister ? '已有账号？返回登录' : '没有账号？使用邀请码注册' }}
      </button>
    </section>
    <footer><span>CRA / DESKTOP</span><span>SECURE SESSION</span></footer>
  </main>
</template>

<style scoped>
.desktop-login{display:flex;width:100vw;height:100vh;flex-direction:column;overflow:hidden;border:3px solid var(--ink);background-color:var(--bg);background-image:linear-gradient(rgba(56,106,87,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(56,106,87,.07) 1px,transparent 1px);background-size:12px 12px;color:var(--ink);font-family:var(--font)}
.desktop-login-titlebar{-webkit-app-region:drag;display:flex;min-height:38px;align-items:center;justify-content:space-between;border-bottom:3px solid var(--ink);background:repeating-linear-gradient(135deg,var(--blue) 0 8px,color-mix(in srgb,var(--blue) 82%,#fff) 8px 16px);color:#fff}
.desktop-login-titlebar>div{display:flex;align-items:center;gap:8px;padding-left:11px;text-shadow:2px 2px 0 var(--ink)}.desktop-login-titlebar>div span{width:10px;height:10px;border:2px solid #fff;background:var(--amber);box-shadow:2px 2px 0 var(--ink)}.desktop-login-titlebar b{font:900 9px var(--mono);letter-spacing:.12em}
.desktop-login-titlebar nav{-webkit-app-region:no-drag;align-self:stretch;display:flex}.desktop-login-titlebar nav button{display:grid;width:38px;height:100%;place-items:center;border:0;background:transparent;color:#fff;cursor:pointer}.desktop-login-titlebar nav button:hover{background:rgba(255,255,255,.16)}.desktop-login-titlebar nav button:last-child:hover{background:var(--red)}.desktop-login-titlebar svg{width:13px;height:13px;fill:currentColor;shape-rendering:crispEdges}
.desktop-login-content{display:flex;min-height:0;flex:1;flex-direction:column;align-items:center;padding:24px 38px 14px}.desktop-login-avatar{display:grid;width:72px;height:72px;place-items:center;border:3px solid var(--ink);background:var(--panel);box-shadow:6px 6px 0 var(--ink)}.desktop-login-avatar span{width:30px;height:30px;border:5px solid var(--ink);background:var(--blue);box-shadow:5px 5px 0 var(--amber)}
.desktop-login-copy{margin:18px 0 15px;text-align:center}.desktop-login-copy small{color:var(--blue);font:900 9px var(--mono);letter-spacing:.14em}.desktop-login-copy h1{margin:5px 0 4px;font-size:20px;letter-spacing:.04em}.desktop-login-copy p{margin:0;color:var(--muted);font-size:11px}
form{width:100%}form>label{display:block;margin-bottom:10px}form>label>span{display:block;margin-bottom:5px;font-size:10px;font-weight:900}input{width:100%;height:38px;padding:0 11px;border:2px solid var(--ink);border-radius:0;background:var(--panel);color:var(--ink);font:12px var(--font);outline:none;box-shadow:2px 2px 0 var(--line2)}input:focus{background:var(--blueS);box-shadow:3px 3px 0 var(--ink)}
.desktop-login-options{display:flex;justify-content:space-between;margin:3px 0 0}.desktop-login-options label{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:10px;cursor:pointer}.desktop-login-options input{width:14px;height:14px;margin:0;padding:0;box-shadow:none;accent-color:var(--blue)}
.desktop-login-error{min-height:25px;padding-top:7px;color:var(--red);font-size:10px;text-align:center}.desktop-login-submit{width:100%;height:39px;border:2px solid var(--ink);border-radius:0;background:var(--blue);color:#fff;box-shadow:3px 3px 0 var(--ink);font:900 12px var(--font);cursor:pointer}.desktop-login-submit:hover{transform:translate(-1px,-1px);box-shadow:4px 4px 0 var(--ink)}.desktop-login-submit:disabled{cursor:wait;opacity:.65}
.desktop-login-switch{margin-top:15px;border:0;background:transparent;color:var(--blue);font:900 10px var(--font);cursor:pointer}.desktop-login-switch:hover{text-decoration:underline}
.desktop-login>footer{display:flex;justify-content:space-between;padding:7px 10px;border-top:2px solid var(--ink);background:var(--panel);color:var(--muted);font:900 8px var(--mono);letter-spacing:.08em}
</style>
