<script setup>
import { onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import loginHeroUrl from '@/assets/login-campus-career.png'

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
    // The auth store handles success and App.vue reacts to isLoggedIn.
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
  <main class="login-home">
    <section class="login-visual" aria-label="校园求职场景">
      <img
        :src="loginHeroUrl"
        alt="学生在校园图书馆整理简历和求职资料"
        width="1536"
        height="1152"
        fetchpriority="high"
      >
      <div class="login-visual-shade"></div>
      <div class="login-brand">
        <div class="mark" aria-hidden="true"></div>
        <span>校招信息看板</span>
      </div>
      <div class="login-visual-copy">
        <p>从投递到 Offer</p>
        <h1>把每一次机会，<br>稳稳握在手里。</h1>
        <span>集中管理岗位、进度与面试准备，让校招节奏始终清晰。</span>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-panel-inner">
        <div class="login-mobile-brand">
          <div class="mark" aria-hidden="true"></div>
          <span>校招信息看板</span>
        </div>

        <header class="login-heading">
          <h2>{{ isRegister ? '创建你的账号' : '欢迎回来' }}</h2>
          <p>{{ isRegister ? '使用管理员提供的一次性邀请码完成注册。' : '登录后继续管理你的校招进程。' }}</p>
        </header>

        <form class="login-form" @submit.prevent="handleAuth(false)">
          <div class="login-field">
            <label for="login-username">用户名</label>
            <input
              id="login-username"
              v-model.trim="username"
              placeholder="请输入用户名"
              required
              minlength="2"
              maxlength="50"
              autocomplete="username"
            >
          </div>

          <div class="login-field">
            <label for="login-password">密码</label>
            <input
              id="login-password"
              v-model="password"
              type="password"
              placeholder="请输入密码"
              required
              minlength="4"
              maxlength="100"
              :autocomplete="isRegister ? 'new-password' : 'current-password'"
            >
          </div>

          <div v-if="isRegister" class="login-field">
            <label for="login-invite-code">邀请码</label>
            <input
              id="login-invite-code"
              v-model.trim="inviteCode"
              placeholder="CRA-XXXX-XXXX"
              required
              autocomplete="off"
              maxlength="32"
            >
            <small>邀请码由管理员提供，每个邀请码仅可使用一次。</small>
          </div>

          <div v-if="!isRegister" class="login-preferences">
            <label>
              <input v-model="rememberPassword" type="checkbox">
              <span>记住密码</span>
            </label>
            <label>
              <input v-model="autoLogin" type="checkbox">
              <span>自动登录</span>
            </label>
          </div>

          <div class="login-error" role="alert" aria-live="polite">{{ error }}</div>

          <button
            id="login-submit"
            class="login-submit"
            type="submit"
            :disabled="loading"
          >
            <span v-if="loading" class="login-spinner" aria-hidden="true"></span>
            {{ loading ? (isRegister ? '正在创建账号' : '正在登录') : (isRegister ? '注册并进入' : '登录') }}
          </button>
        </form>

        <div class="login-switch-row">
          <span>{{ isRegister ? '已经有账号？' : '第一次使用？' }}</span>
          <button id="login-toggle" type="button" @click="toggleAuthMode">
            {{ isRegister ? '返回登录' : '使用邀请码注册' }}
          </button>
        </div>
      </div>

      <footer class="login-footer">你的数据仅用于校招进度管理</footer>
    </section>
  </main>
</template>

<style scoped>
.login-home {
  --login-accent: var(--blue);
  --login-accent-strong: var(--blue2);
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(420px, .85fr);
  min-height: 100dvh;
  background: var(--panel);
  color: var(--ink);
}

.login-visual {
  position: relative;
  min-height: 100dvh;
  overflow: hidden;
  isolation: isolate;
  background: color-mix(in srgb, var(--login-accent) 72%, #18231f);
  color: #f7faf8;
}

.login-visual > img {
  position: absolute;
  inset: 0;
  z-index: -2;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: 52% center;
  animation: login-image-in .8s cubic-bezier(.16, 1, .3, 1) both;
}

.login-visual-shade {
  position: absolute;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(180deg, rgba(13, 28, 23, .16) 0%, rgba(13, 28, 23, .08) 38%, rgba(13, 28, 23, .84) 100%),
    linear-gradient(90deg, color-mix(in srgb, var(--login-accent) 32%, transparent), transparent 62%);
}

.login-brand,
.login-mobile-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  font-weight: 900;
  letter-spacing: .04em;
}

.login-brand {
  position: absolute;
  top: clamp(24px, 5vw, 56px);
  left: clamp(24px, 5vw, 64px);
}

.login-brand .mark,
.login-mobile-brand .mark {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
}

.login-visual-copy {
  position: absolute;
  right: clamp(26px, 6vw, 76px);
  bottom: clamp(42px, 8vh, 96px);
  left: clamp(26px, 6vw, 76px);
  max-width: 680px;
  animation: login-copy-in .65s .12s cubic-bezier(.16, 1, .3, 1) both;
}

.login-visual-copy p {
  margin: 0 0 15px;
  color: rgba(247, 250, 248, .78);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: .16em;
}

.login-visual-copy h1 {
  max-width: 620px;
  margin: 0;
  font-size: clamp(38px, 5vw, 68px);
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: -.045em;
  text-wrap: balance;
}

.login-visual-copy > span {
  display: block;
  max-width: 440px;
  margin-top: 22px;
  color: rgba(247, 250, 248, .82);
  font-size: 15px;
  line-height: 1.75;
}

.login-panel {
  display: flex;
  min-height: 100dvh;
  flex-direction: column;
  justify-content: center;
  padding: 56px clamp(34px, 6vw, 88px) 24px;
  background:
    radial-gradient(circle at 100% 0, var(--blueS), transparent 34%),
    var(--panel);
}

.login-panel-inner {
  width: 100%;
  max-width: 440px;
  margin: auto;
  animation: login-form-in .55s .08s cubic-bezier(.16, 1, .3, 1) both;
}

.login-mobile-brand {
  display: none;
  margin-bottom: 48px;
  color: var(--ink);
}

.login-heading h2 {
  margin: 0;
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1.15;
  letter-spacing: -.04em;
}

.login-heading p {
  margin: 12px 0 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}

.login-form {
  width: 100%;
  margin-top: 36px;
}

.login-field {
  margin-bottom: 19px;
  text-align: left;
}

.login-field label {
  display: block;
  margin-bottom: 8px;
  color: var(--ink);
  font-size: 13px;
  font-weight: 800;
}

.login-field input {
  width: 100%;
  height: 50px;
  margin: 0;
  padding: 0 15px;
  border: 1px solid var(--line2);
  border-radius: 12px;
  outline: none;
  background: var(--bg);
  box-shadow: none;
  color: var(--ink);
  font: 14px var(--font);
  transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;
}

.login-field input::placeholder { color: var(--sub); }
.login-field input:focus {
  border-color: var(--login-accent);
  background: var(--panel);
  box-shadow: 0 0 0 3px var(--blueS);
}

.login-field input#login-invite-code { text-transform: uppercase; }

.login-field small {
  display: block;
  margin-top: 7px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

.login-preferences {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: -2px;
}

.login-preferences label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.login-preferences input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--login-accent);
}

.login-preferences input:focus-visible {
  outline: 2px solid var(--login-accent);
  outline-offset: 2px;
}

.login-error {
  min-height: 38px;
  padding: 10px 0 6px;
  color: var(--red);
  font-size: 12px;
  line-height: 1.45;
}

.login-submit {
  display: inline-flex;
  width: 100%;
  height: 50px;
  align-items: center;
  justify-content: center;
  gap: 9px;
  border: 1px solid var(--login-accent);
  border-radius: 12px;
  background: var(--login-accent);
  color: #fff;
  box-shadow: 0 10px 24px color-mix(in srgb, var(--login-accent) 24%, transparent);
  font: 800 14px var(--font);
  cursor: pointer;
  transition: transform .18s ease, background .18s ease, box-shadow .18s ease;
}

.login-submit:hover:not(:disabled) {
  background: var(--login-accent-strong);
  transform: translateY(-1px);
  box-shadow: 0 13px 28px color-mix(in srgb, var(--login-accent) 28%, transparent);
}

.login-submit:active:not(:disabled) { transform: scale(.98); }
.login-submit:focus-visible { outline: 3px solid var(--blueS); outline-offset: 3px; }
.login-submit:disabled { cursor: wait; opacity: .72; }

.login-spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255,255,255,.42);
  border-top-color: #fff;
  border-radius: 50%;
  animation: login-spin .75s linear infinite;
}

.login-switch-row {
  display: flex;
  justify-content: center;
  gap: 5px;
  margin-top: 24px;
  color: var(--muted);
  font-size: 12px;
}

.login-switch-row button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--login-accent);
  font: 800 12px var(--font);
  cursor: pointer;
}

.login-switch-row button:hover { color: var(--login-accent-strong); text-decoration: underline; }
.login-switch-row button:focus-visible { outline: 2px solid var(--login-accent); outline-offset: 3px; }

.login-footer {
  margin-top: 40px;
  color: var(--sub);
  font-size: 11px;
  text-align: center;
}

@keyframes login-image-in { from { opacity: 0; transform: scale(1.025); } }
@keyframes login-copy-in { from { opacity: 0; transform: translateY(20px); } }
@keyframes login-form-in { from { opacity: 0; transform: translateY(14px); } }
@keyframes login-spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .login-home { grid-template-columns: minmax(0, 1fr); }
  .login-visual { min-height: 250px; }
  .login-brand { display: none; }
  .login-visual-copy { bottom: 28px; }
  .login-visual-copy p,
  .login-visual-copy > span { display: none; }
  .login-visual-copy h1 { max-width: 520px; font-size: clamp(30px, 7vw, 44px); }
  .login-panel { min-height: auto; padding: 44px 24px 28px; }
  .login-panel-inner { max-width: 520px; }
  .login-mobile-brand { display: flex; margin-bottom: 38px; }
}

@media (max-width: 560px) {
  .login-visual { min-height: 190px; }
  .login-visual > img { object-position: 48% 50%; }
  .login-visual-copy { right: 20px; bottom: 22px; left: 20px; }
  .login-visual-copy h1 { font-size: 29px; }
  .login-panel { padding: 32px 20px 24px; }
  .login-mobile-brand { margin-bottom: 32px; }
  .login-heading h2 { font-size: 30px; }
  .login-form { margin-top: 28px; }
}

@media (prefers-reduced-motion: reduce) {
  .login-visual > img,
  .login-visual-copy,
  .login-panel-inner,
  .login-spinner { animation: none; }
  .login-submit { transition: none; }
}
</style>
