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
import RecordManagerModal from '@/components/RecordManagerModal.vue'
import HelpModal from '@/components/HelpModal.vue'
import StatsModal from '@/components/StatsModal.vue'
import OfferCompareModal from '@/components/OfferCompareModal.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const app = useAppStore()

onMounted(async () => {
  try { await auth.checkSession() } catch { auth.clear() }
})
</script>

<template>
  <div class="app" v-if="auth.isLoggedIn">
    <SidebarNav />
    <main class="main">
      <Topbar
        @open-config="app.toggleConfig()"
        @open-chat="app.toggleChat()"
        @open-help="app.toggleHelp()"
      />
      <router-view />
    </main>
    <ConfigModal v-if="app.showConfig" @close="app.showConfig = false" />
    <ChatModal v-if="app.showChat" @close="app.showChat = false" />
    <RecordModal v-if="app.showRecord" @close="app.closeRecord()" @saved="app.closeRecord()" />
    <RecordDetailModal v-if="app.detailId" :record-id="app.detailId" @close="app.closeDetail()" @saved="app.closeDetail()" />
    <RecordManagerModal v-if="app.showManager" @close="app.closeManager()" />
    <HelpModal v-if="app.showHelp" @close="app.showHelp = false" />
    <StatsModal v-if="app.showStats" @close="app.closeStats()" />
    <OfferCompareModal v-if="app.showOffer" @close="app.closeOffer()" />
  </div>
  <LoginModal v-else />
  <ToastContainer />
</template>
