<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const dockItems = computed(() => [
  { to: '/', label: '投递', icon: 'home' },
  { to: '/board', label: '看板', icon: 'board' },
  { to: '/records', label: '总表', icon: 'table' },
  { to: '/resumes', label: '简历', icon: 'resume' },
  { to: '/analysis', label: '分析', icon: 'spark' },
  ...(auth.isAdmin ? [{ to: '/admin', label: '管理', icon: 'admin' }] : []),
])
</script>

<template>
  <div class="desktop-skin-layer">
    <div class="liquid-backdrop" aria-hidden="true"><i></i><i></i><i></i></div>
    <div class="liquid-dock-glass">
      <nav class="liquid-dock" aria-label="桌面快捷导航">
        <router-link v-for="item in dockItems" :key="item.to" :to="item.to" :title="item.label">
          <svg v-if="item.icon === 'home'" viewBox="0 0 24 24"><path d="M3.5 10.7 12 3.8l8.5 6.9v9H15v-6H9v6H3.5v-9Z"/></svg>
          <svg v-else-if="item.icon === 'board'" viewBox="0 0 24 24"><path d="M4 4h6v16H4V4Zm10 0h6v9h-6V4Zm0 13h6v3h-6v-3Z"/></svg>
          <svg v-else-if="item.icon === 'table'" viewBox="0 0 24 24"><path d="M4 5h16v14H4V5Zm0 5h16M9 5v14"/></svg>
          <svg v-else-if="item.icon === 'resume'" viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6V3Zm9 0v4h3M9 11h6M9 15h6"/></svg>
          <svg v-else-if="item.icon === 'spark'" viewBox="0 0 24 24"><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Zm6 13 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z"/></svg>
          <svg v-else viewBox="0 0 24 24"><path d="M4 20v-2a5 5 0 0 1 5-5h6a5 5 0 0 1 5 5v2M12 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm6-5v4M16 7h4"/></svg>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
    </div>
  </div>
</template>
