<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ChatModal from '@/components/ChatModal.vue'
import CalendarWidget from '@/components/CalendarWidget.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const showConfig = ref(false)
const showChat = ref(false)

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
        @open-chat="showChat = true"
      />
      <router-view />
    </main>
    <ConfigModal v-if="showConfig" @close="showConfig = false" />
    <ChatModal v-if="showChat" @close="showChat = false" />
    <CalendarWidget />
  </div>
  <LoginModal v-else @close="() => {}" />
  <ToastContainer />
</template>

<style>
@import '@/styles/global.css';
</style>
