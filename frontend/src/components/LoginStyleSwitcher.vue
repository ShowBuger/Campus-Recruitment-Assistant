<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import {
  restoreAnimeResource,
  restoreAuroraResource,
  restoreCyberResource,
  restoreShuimoResource,
} from '@/utils/skinResources'

const styles = [
  { value: 'classic', label: '清简原境' },
  { value: 'pixelium', label: '像素矩阵' },
  { value: 'aurora', label: '雨幕流光', resource: 'aurora' },
  { value: 'cyber', label: '霓虹终端', resource: 'cyber' },
  { value: 'anime', label: '樱愿手账', resource: 'anime' },
  { value: 'journal', label: '纸页档案' },
  { value: 'shuimo', label: '云水墨境', resource: 'shuimo' },
]

const currentStyle = ref(document.documentElement.dataset.style || 'pixelium')
const checking = ref(true)
const open = ref(false)
const ready = ref({ aurora: false, anime: false, shuimo: false, cyber: false })
const useDefaultFont = computed(() => document.documentElement.dataset.styleFont === 'default')

function enableSheet(id, enabled) {
  const sheet = document.getElementById(id)
  if (!sheet) return
  if (enabled) sheet.removeAttribute('disabled')
  else sheet.setAttribute('disabled', '')
}

function isAvailable(style) {
  if (!style.resource) return true
  if (style.resource !== 'aurora' && useDefaultFont.value) return true
  return ready.value[style.resource]
}

function applyStyle(name) {
  const selected = styles.find(style => style.value === name)
  if (!selected || !isAvailable(selected)) return

  const previous = currentStyle.value
  if (name === 'aurora' && previous !== 'aurora') {
    localStorage.setItem('radar_non_aurora_theme', document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
  }
  currentStyle.value = name
  document.documentElement.dataset.style = name
  localStorage.setItem('radar_style', name)

  if (name === 'aurora') {
    document.documentElement.dataset.theme = 'dark'
    localStorage.setItem('radar_theme', 'dark')
  } else if (previous === 'aurora') {
    const theme = localStorage.getItem('radar_non_aurora_theme') === 'dark' ? 'dark' : 'light'
    document.documentElement.dataset.theme = theme
    localStorage.setItem('radar_theme', theme)
  }

  for (const id of ['css-pixelium', 'css-pixelfont', 'css-pixelvue']) enableSheet(id, name === 'pixelium')
  window.electronAPI?.setSkin?.(name)
  open.value = false
}

function toggle(event) {
  event.stopPropagation()
  open.value = !open.value
  if (open.value) nextTick(() => document.querySelector('.login-style-option.active')?.focus())
}

function closeFromOutside(event) {
  if (!event.target.closest('.login-style-switcher')) open.value = false
}

onMounted(async () => {
  const [aurora, anime, shuimo, cyber] = await Promise.all([
    restoreAuroraResource(),
    restoreAnimeResource(),
    restoreShuimoResource(),
    restoreCyberResource(),
  ])
  ready.value = { aurora, anime, shuimo, cyber }
  checking.value = false
  document.addEventListener('click', closeFromOutside)
})

onUnmounted(() => document.removeEventListener('click', closeFromOutside))
</script>

<template>
  <div class="login-style-switcher" @click.stop>
    <button class="login-style-trigger" type="button" :disabled="checking" :aria-expanded="open" aria-haspopup="menu" title="切换界面风格" @click="toggle">
      <span class="login-style-icon" aria-hidden="true"><i></i><i></i><i></i></span>
      <span>风格</span>
    </button>
    <div v-if="open" class="login-style-menu" role="menu" aria-label="界面风格">
      <header><div><b>选择界面风格</b><small>登录后将继续使用</small></div><span>{{ styles.find(item => item.value === currentStyle)?.label }}</span></header>
      <div class="login-style-options">
        <button
          v-for="style in styles"
          :key="style.value"
          type="button"
          class="login-style-option"
          :class="[{ active: currentStyle === style.value }, 'style-' + style.value]"
          :disabled="!isAvailable(style)"
          role="menuitemradio"
          :aria-checked="currentStyle === style.value"
          @click="applyStyle(style.value)"
        >
          <i class="login-style-swatch" aria-hidden="true"></i>
          <span><b>{{ style.label }}</b><small>{{ !isAvailable(style) ? '需先在主界面下载' : (currentStyle === style.value ? '当前风格' : '点击预览') }}</small></span>
          <i class="login-style-check" aria-hidden="true"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-style-switcher{position:fixed;z-index:40;top:22px;right:24px;color:var(--ink);font-family:var(--font)}
.login-style-trigger{display:flex;height:38px;align-items:center;gap:8px;padding:0 12px;border:1px solid color-mix(in srgb,var(--line2) 75%,transparent);border-radius:9px;background:color-mix(in srgb,var(--panel) 88%,transparent);color:var(--ink);box-shadow:0 5px 18px color-mix(in srgb,var(--ink) 9%,transparent);font:800 11px var(--font);cursor:pointer;backdrop-filter:blur(16px);transition:transform .16s ease,border-color .16s ease,background .16s ease}
.login-style-trigger:hover{border-color:var(--blue);background:var(--panel);transform:translateY(-1px)}.login-style-trigger:active{transform:scale(.97)}.login-style-trigger:disabled{cursor:wait;opacity:.6}
.login-style-icon{position:relative;display:block;width:18px;height:18px;border:1px solid var(--line2);border-radius:50%;background:var(--panel)}.login-style-icon i{position:absolute;width:5px;height:5px;border-radius:50%}.login-style-icon i:nth-child(1){top:3px;left:4px;background:var(--blue)}.login-style-icon i:nth-child(2){top:4px;right:3px;background:var(--amber)}.login-style-icon i:nth-child(3){right:5px;bottom:3px;background:var(--green)}
.login-style-menu{position:absolute;top:46px;right:0;width:min(360px,calc(100vw - 28px));padding:8px;border:1px solid var(--line);border-radius:12px;background:color-mix(in srgb,var(--panel) 96%,transparent);box-shadow:0 18px 55px color-mix(in srgb,var(--ink) 18%,transparent);backdrop-filter:blur(24px);animation:style-menu-in .18s cubic-bezier(.2,.8,.2,1)}
.login-style-menu header{display:flex;align-items:center;justify-content:space-between;padding:8px 9px 12px}.login-style-menu header>div{display:flex;flex-direction:column;gap:2px}.login-style-menu header b{font-size:12px}.login-style-menu header small{color:var(--muted);font-size:9px}.login-style-menu header>span{color:var(--blue);font-size:9px;font-weight:800}
.login-style-options{display:grid;grid-template-columns:1fr 1fr;gap:5px}.login-style-option{position:relative;display:grid;grid-template-columns:30px 1fr 8px;align-items:center;gap:8px;min-height:52px;padding:7px 8px;border:1px solid transparent;border-radius:8px;background:transparent;color:var(--ink);text-align:left;cursor:pointer}.login-style-option:hover:not(:disabled){border-color:var(--line);background:var(--bg)}.login-style-option.active{border-color:color-mix(in srgb,var(--blue) 40%,var(--line));background:var(--blueS)}.login-style-option:disabled{cursor:not-allowed;opacity:.42}.login-style-option>span{display:flex;min-width:0;flex-direction:column;gap:2px}.login-style-option b{overflow:hidden;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.login-style-option small{overflow:hidden;color:var(--muted);font-size:8px;text-overflow:ellipsis;white-space:nowrap}
.login-style-swatch{width:30px;height:30px;border:1px solid color-mix(in srgb,var(--ink) 18%,transparent);border-radius:7px;box-shadow:inset 0 0 0 3px rgba(255,255,255,.38)}.style-classic .login-style-swatch{background:linear-gradient(135deg,#edf5ff 0 52%,#2563a6 53%)}.style-pixelium .login-style-swatch{border-radius:2px;background:linear-gradient(135deg,#e8f0eb 0 48%,#386a57 49% 72%,#e5a84b 73%)}.style-aurora .login-style-swatch{background:linear-gradient(135deg,#7358e8,#4da6cf 55%,#47b59c)}.style-cyber .login-style-swatch{border-radius:2px;background:linear-gradient(145deg,#f8e71c 0 48%,#111923 49% 70%,#00d9f5 71%)}.style-anime .login-style-swatch{background:linear-gradient(145deg,#fff0f4 0 50%,#526dc7 51% 72%,#df6279 73%)}.style-journal .login-style-swatch{border-radius:3px;background:linear-gradient(145deg,#f8f6ed 0 55%,#2f6756 56% 78%,#b95746 79%)}.style-shuimo .login-style-swatch{border-radius:6px 2px 6px 2px;background:radial-gradient(circle at 72% 25%,#a33a32 0 7%,transparent 8%),linear-gradient(145deg,#f4f1e8 0 52%,#344b4a 53% 72%,#232521 73%)}
.login-style-check{width:7px;height:7px;border-radius:50%;background:transparent}.login-style-option.active .login-style-check{background:var(--blue);box-shadow:0 0 0 3px var(--blueS)}
@keyframes style-menu-in{from{opacity:0;transform:translateY(-6px) scale(.98)}}
@media(max-width:560px){.login-style-switcher{top:14px;right:14px}.login-style-trigger{width:38px;padding:0;justify-content:center}.login-style-trigger>span:last-child{display:none}.login-style-menu{top:44px}.login-style-options{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.login-style-trigger{transition:none}.login-style-menu{animation:none}}
</style>
