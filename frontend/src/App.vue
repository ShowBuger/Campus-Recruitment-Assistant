<script setup>
import { ref, onMounted, provide } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ChatModal from '@/components/ChatModal.vue'
import RecordModal from '@/components/RecordModal.vue'
import RecordDetailModal from '@/components/RecordDetailModal.vue'
import HelpModal from '@/components/HelpModal.vue'
import StatsModal from '@/components/StatsModal.vue'
import OfferCompareModal from '@/components/OfferCompareModal.vue'
import CalendarWidget from '@/components/CalendarWidget.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const showConfig = ref(false)
const showChat = ref(false)

// Modal state
const showRecord = ref(false)
const detailId = ref('')
const showHelp = ref(false)
const showStats = ref(false)
const showOffer = ref(false)

function openRecord() { showRecord.value = true }
function closeRecord() { showRecord.value = false }
function openDetail(id) { detailId.value = id }
function closeDetail() { detailId.value = '' }

provide('openRecord', openRecord)
provide('openDetail', openDetail)
provide('openStats', () => { showStats.value = true })
provide('openOffer', () => { showOffer.value = true })
provide('openHelp', () => { showHelp.value = true })

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
    <RecordModal v-if="showRecord" @close="closeRecord" @saved="closeRecord" />
    <RecordDetailModal v-if="detailId" :record-id="detailId" @close="closeDetail" @saved="closeDetail" />
    <HelpModal v-if="showHelp" @close="showHelp = false" />
    <StatsModal v-if="showStats" @close="showStats = false" />
    <OfferCompareModal v-if="showOffer" @close="showOffer = false" />
    <CalendarWidget />
  </div>
  <LoginModal v-else />
  <ToastContainer />
</template>
