<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const showConfig = ref(false)
const showHelp = ref(false)

onMounted(async () => {
  try { await auth.checkSession() } catch { auth.clear() }
})
</script>

<template>
  <div class="app" v-if="auth.isLoggedIn">
    <SidebarNav />
    <main class="main">
      <Topbar
        @open-config="showConfig = true"
        @open-help="showHelp = true"
      />
      <router-view />
    </main>
    <ConfigModal v-if="showConfig" @close="showConfig = false" />
  </div>
  <LoginModal v-else @close="() => {}" />
  <ToastContainer />
</template>

<style>
@import '@/styles/global.css';
</style>
