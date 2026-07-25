<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ChatModal from '@/components/ChatModal.vue'
import RecordModal from '@/components/RecordModal.vue'
import RecordDetailModal from '@/components/RecordDetailModal.vue'
import CalendarWidget from '@/components/CalendarWidget.vue'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const showConfig = ref(false)
const showChat = ref(false)
const showRecord = ref(false)
const detailId = ref('')

function openDetail(id) { detailId.value = id }
function closeDetail() { detailId.value = '' }
</script>

<template>
  <div class="app" v-if="auth.isLoggedIn">
    <SidebarNav />
    <main class="main">
      <Topbar
        @open-config="showConfig = true"
        @open-chat="showChat = true"
      />
      <router-view
        @open-detail="openDetail"
        @open-record="showRecord = true"
      />
    </main>
    <ConfigModal v-if="showConfig" @close="showConfig = false" />
    <ChatModal v-if="showChat" @close="showChat = false" />
    <RecordModal v-if="showRecord" @close="showRecord = false" @saved="showRecord = false" />
    <RecordDetailModal v-if="detailId" :record-id="detailId" @close="closeDetail" @saved="closeDetail" />
    <CalendarWidget />
  </div>
  <LoginModal v-else />
  <ToastContainer />
</template>
