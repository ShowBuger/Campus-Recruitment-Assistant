<script setup>
import { onMounted, ref } from 'vue'
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
import RecommendationModal from '@/components/RecommendationModal.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import AppDialog from '@/components/AppDialog.vue'


const auth = useAuthStore()
const app = useAppStore()

// Error modal
const showError = ref(false)
const errorMsg = ref('')
const errorDetail = ref('')
window.__showError = (msg, detail) => { errorMsg.value = msg || '未知错误'; errorDetail.value = detail || ''; showError.value = true }
function copyError() { navigator.clipboard?.writeText(`${errorMsg.value}\n${errorDetail.value}`) }

// Card hover parallax
function onCardMouseMove(e) {
  const card = e.currentTarget; const rect = card.getBoundingClientRect()
  card.style.setProperty('--mx', `${((e.clientX-rect.left)/rect.width)*100}%`)
  card.style.setProperty('--my', `${((e.clientY-rect.top)/rect.height)*100}%`)
}
function onCardMouseLeave(e) { e.currentTarget.style.removeProperty('--mx'); e.currentTarget.style.removeProperty('--my') }
function bindCardHover() {
  document.querySelectorAll('.kpi-card,.metric').forEach(el => {
    el.addEventListener('mousemove', onCardMouseMove); el.addEventListener('mouseleave', onCardMouseLeave)
  })
}

onMounted(async () => {
  try { await auth.checkSession() } catch (e) {
    if (e?.message === '登录已过期') auth.clear()
  }
  if (auth.isLoggedIn) {
    const seen = localStorage.getItem('radar_help_seen')
    if (!seen) { setTimeout(() => { app.showHelp = true; localStorage.setItem('radar_help_seen', '1') }, 800) }
  }
  setTimeout(bindCardHover, 500)
  new MutationObserver(() => { setTimeout(bindCardHover, 100) }).observe(document.body, { childList: true, subtree: true })
})
</script>

<template>
  <div class="app" v-if="auth.isLoggedIn">
    <SidebarNav />
    <main class="main">
      <Topbar @open-config="app.toggleConfig()" @open-chat="app.toggleChat()" @open-help="app.toggleHelp()" />
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
    <RecommendationModal v-if="app.showRecommendation" @close="app.closeRecommendation()" />
    <div v-if="showError" class="error-overlay" @mousedown.self="showError = false">
      <div class="error-modal"><h3>&#9888; {{ errorMsg }}</h3><pre>{{ errorDetail }}</pre><div class="btn-row"><button class="btn" @click="copyError">复制详情</button><button class="btn" style="background:var(--blue);color:#fff" @click="showError = false">关闭</button></div></div>
    </div>
  </div>
  <LoginModal v-else />
  <AppDialog />
  <ToastContainer />
</template>
