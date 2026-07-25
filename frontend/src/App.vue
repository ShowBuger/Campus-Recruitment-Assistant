<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ChatModal from '@/components/ChatModal.vue'
import RecordModal from '@/components/RecordModal.vue'
import RecordDetailModal from '@/components/RecordDetailModal.vue'
import CalendarWidget from '@/components/CalendarWidget.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { ref } from 'vue'

const auth = useAuthStore()
const app = useAppStore()
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
    <RecordModal v-if="app.showRecord" @close="app.closeRecord()" @saved="app.closeRecord()" />
    <RecordDetailModal v-if="app.detailId" :record-id="app.detailId" @close="app.closeDetail()" @saved="app.closeDetail()" />
    <CalendarWidget />
  </div>
  <LoginModal v-else />
  <ToastContainer />
</template>
