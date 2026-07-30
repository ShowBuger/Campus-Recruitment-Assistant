<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const maximized = ref(false)
let removeStateListener = null

async function control(action) {
  const state = await window.electronAPI?.windowControl?.(action)
  if (state) maximized.value = Boolean(state.maximized)
}

onMounted(async () => {
  const state = await window.electronAPI?.windowControl?.('state')
  maximized.value = Boolean(state?.maximized)
  removeStateListener = window.electronAPI?.onWindowState?.(state => {
    maximized.value = Boolean(state?.maximized)
  }) || null
})

onUnmounted(() => removeStateListener?.())
</script>

<template>
  <header class="desktop-titlebar">
    <div class="desktop-titlebar-brand">
      <span class="desktop-titlebar-pixel" aria-hidden="true"></span>
      <b>校招信息看板</b>
      <small>DESKTOP / CAMPUS_BOARD</small>
    </div>
    <div class="desktop-window-controls">
      <button type="button" title="最小化" aria-label="最小化" @click="control('minimize')">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 11h10v2H3z"/></svg>
      </button>
      <button type="button" :title="maximized ? '还原' : '最大化'" :aria-label="maximized ? '还原' : '最大化'" @click="control('toggle-maximize')">
        <svg v-if="!maximized" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 2h12v12H2V2Zm2 3v7h8V5H4Z"/></svg>
        <svg v-else viewBox="0 0 16 16" aria-hidden="true"><path d="M5 2h9v9h-2V4H5V2ZM2 5h9v9H2V5Zm2 2v5h5V7H4Z"/></svg>
      </button>
      <button type="button" class="desktop-window-close" title="关闭到托盘" aria-label="关闭到托盘" @click="control('close')">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 2h2v2h2v2h2V4h2V2h2v2h-2v2H9v2h2v2h2v2h-2v-2H9V8H7v2H5v2H3v-2h2V8h2V6H5V4H3V2Z"/></svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.desktop-titlebar{
  -webkit-app-region:drag;
  position:relative;
  z-index:10002;
  display:flex;
  align-items:center;
  justify-content:space-between;
  min-width:0;
  border-bottom:3px solid var(--ink);
  background:
    repeating-linear-gradient(135deg,var(--blue) 0 8px,color-mix(in srgb,var(--blue) 82%,#fff) 8px 16px);
  color:#fff;
  user-select:none;
}
.desktop-titlebar-brand{display:flex;align-items:center;min-width:0;gap:9px;padding:0 12px;text-shadow:2px 2px 0 var(--ink)}
.desktop-titlebar-brand b{font-size:12px;letter-spacing:.08em;white-space:nowrap}
.desktop-titlebar-brand small{color:rgba(255,255,255,.72);font:900 8px var(--mono);letter-spacing:.1em;white-space:nowrap}
.desktop-titlebar-pixel{width:11px;height:11px;border:2px solid #fff;background:var(--amber);box-shadow:2px 2px 0 var(--ink)}
.desktop-window-controls{-webkit-app-region:no-drag;align-self:stretch;display:flex}
.desktop-window-controls{border:0}
.desktop-window-controls button{display:grid;width:43px;height:100%;place-items:center;padding:0;border:0;border-radius:0;background:transparent;color:#fff;box-shadow:none;cursor:pointer;text-shadow:none;transform:none}
.desktop-window-controls button:hover{background:rgba(255,255,255,.16);color:#fff;box-shadow:none;text-shadow:none}
.desktop-window-controls button:active{background:rgba(255,255,255,.22);box-shadow:none;text-shadow:none;transform:none}
.desktop-window-controls .desktop-window-close:hover{background:var(--red);color:#fff}
.desktop-window-controls svg{width:14px;height:14px;fill:currentColor;shape-rendering:crispEdges}
@media(max-width:720px){.desktop-titlebar-brand small{display:none}}
</style>
