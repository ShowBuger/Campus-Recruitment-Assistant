<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import UserProfileModal from '@/components/UserProfileModal.vue'
import { isDesktopRuntime } from '@/utils/runtime'
import UserAvatar from '@/components/UserAvatar.vue'
const auth = useAuthStore()
const version = ref('')
const collapsed = ref(false)
const showProfile = ref(false)
let styleObserver = null
const navItems = computed(() => [
  { to: '/', label: '投递信息', icon: 'home' },
  { to: '/board', label: '投递看板', icon: 'board' },
  { to: '/records', label: '总表信息', icon: 'table' },
  { to: '/resumes', label: '简历管理', icon: 'resume' },
  { to: '/analysis', label: '简历分析', icon: 'analysis' },
  ...(auth.isAdmin ? [{ to: '/admin', label: '管理页面', icon: 'admin' }] : []),
])

function syncCollapsedLayout() {
  const app = document.querySelector('.app')
  const root = document.documentElement
  const style = root.dataset.style
  const desktop = root.classList.contains('desktop-main-mode')
  const wide = window.matchMedia('(min-width: 1081px)').matches
  const width = style === 'anime' ? 80 : style === 'journal' ? 72 : style === 'cyber' ? 76 : ['aurora', 'shuimo'].includes(style) ? 76 : ['classic', 'pixelium'].includes(style) ? 72 : 0
  const enabled = Boolean(width) && (style === 'journal' || wide) && (!desktop || ['classic', 'pixelium', 'anime', 'journal', 'cyber'].includes(style))
  const active = collapsed.value && enabled
  root.classList.toggle('sidebar-collapse-enabled', enabled)
  app?.classList.toggle('sidebar-is-collapsed', active)
  if (app) app.style.gridTemplateColumns = active ? `${width}px minmax(0, 1fr)` : ''
}

function applyCollapsed(value) {
  collapsed.value = value
  document.documentElement.classList.toggle('sidebar-collapsed', value)
  syncCollapsedLayout()
  try { localStorage.setItem('radar_sidebar_collapsed', value ? '1' : '0') } catch (_) {}
}

function toggleSidebar() { applyCollapsed(!collapsed.value) }

onMounted(async () => {
  try { applyCollapsed(localStorage.getItem('radar_sidebar_collapsed') === '1') } catch (_) {}
  styleObserver = new MutationObserver(syncCollapsedLayout)
  styleObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-style'] })
  window.addEventListener('resize', syncCollapsedLayout)
  try {
    if (isDesktopRuntime()) {
      version.value = await window.electronAPI.getAppVersion()
      return
    }
    const r = await fetch('/api/version')
    const d = await r.json()
    version.value = d.version || ''
  } catch {}
})

onUnmounted(() => {
  styleObserver?.disconnect()
  window.removeEventListener('resize', syncCollapsedLayout)
})
</script>

<template>
  <aside id="primary-sidebar" class="sidebar">
    <div class="brand">
      <div class="mark"></div>
      <div class="brand-copy"><b>校招信息看板</b><span>投递进度工作台</span></div>
      <button type="button" class="sidebar-collapse" :title="collapsed ? '展开侧边栏' : '折叠侧边栏'" :aria-label="collapsed ? '展开侧边栏' : '折叠侧边栏'" :aria-expanded="!collapsed" aria-controls="primary-sidebar" @click="toggleSidebar">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3.5" y="4" width="17" height="16" rx="2.5"/>
          <path d="M9 4v16M14.5 8.5 11.5 12l3 3.5"/>
        </svg>
      </button>
    </div>
    <div class="nav-sec">工作台</div>
    <router-link v-for="item in navItems" :key="item.to" :to="item.to" :title="collapsed ? item.label : undefined">
      <svg class="sidebar-nav-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path v-if="item.icon === 'home'" d="M4 10.5 12 4l8 6.5V20h-5v-6H9v6H4v-9.5Z"/>
        <path v-else-if="item.icon === 'board'" d="M4 4h6v16H4V4Zm10 0h6v9h-6V4Zm0 13h6v3h-6v-3Z"/>
        <path v-else-if="item.icon === 'table'" d="M4 5h16v14H4V5Zm0 5h16M9 5v14"/>
        <path v-else-if="item.icon === 'resume'" d="M6 3h9l3 3v15H6V3Zm9 0v4h3M9 11h6M9 15h6"/>
        <path v-else-if="item.icon === 'analysis'" d="M4 19V9m5 10V5m5 14v-7m5 7V3"/>
        <path v-else d="M4 20v-2a5 5 0 0 1 5-5h6a5 5 0 0 1 5 5v2M12 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm6-5v4M16 7h4"/>
      </svg>
      <span class="sidebar-nav-label">{{ item.label }}</span>
    </router-link>
    <div class="sidebar-foot">
      <div class="sidebar-user">
        <button class="sidebar-profile-avatar" type="button" title="用户信息" aria-label="打开用户信息" @click="showProfile = true"><UserAvatar :avatar-key="auth.user?.avatar_key" :avatar-url="auth.user?.avatar_url" :label="auth.user?.nickname || auth.user?.username"/></button>
        <button class="btn sidebar-logout" title="退出登录" @click="auth.logout()">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 5H5v14h5M14 8l4 4-4 4m4-4H9"/></svg>
          <span>退出</span>
        </button>
      </div>
      <div class="conn sidebar-connection">
        <span class="pulse"></span><span>云端存储</span>
        <span v-if="version" class="sidebar-version">v{{ version }}</span>
      </div>
    </div>
    <UserProfileModal v-if="showProfile" @close="showProfile = false" />
  </aside>
</template>
