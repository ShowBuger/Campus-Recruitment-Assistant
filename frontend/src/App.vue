<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'

const auth = useAuthStore()

onMounted(async () => {
  try { await auth.checkSession() } catch { auth.clear() }
})
</script>

<template>
  <div class="app" v-if="auth.isLoggedIn">
    <SidebarNav />
    <main class="main">
      <Topbar />
      <router-view />
    </main>
  </div>
  <div class="login-overlay" v-else>
    <slot name="login"><div class="center">请登录</div></slot>
  </div>
</template>

<style>
@import '@/styles/global.css';
</style>
