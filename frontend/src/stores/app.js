import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const showConfig = ref(false)
  const showChat = ref(false)
  const showRecord = ref(false)
  const showHelp = ref(false)
  const showStats = ref(false)
  const showOffer = ref(false)
  const showManager = ref(false)
  const showRecommendation = ref(false)
  const detailId = ref('')
  const recordShared = ref(false)
  const managerShared = ref(false)
  const managerScope = ref('records')

  function toggleConfig() { showConfig.value = !showConfig.value }
  function toggleChat() { showChat.value = !showChat.value }
  function toggleHelp() { showHelp.value = !showHelp.value }
  function openRecord(shared) { recordShared.value = !!shared; showRecord.value = true }
  function closeRecord() { showRecord.value = false; recordShared.value = false }
  function openDetail(id) { detailId.value = id }
  function closeDetail() { detailId.value = '' }
  function openStats() { showStats.value = true }
  function closeStats() { showStats.value = false }
  function openOffer() { showOffer.value = true }
  function closeOffer() { showOffer.value = false }
  function openManager(scope = 'records') {
    managerShared.value = scope === true || scope === 'shared'
    managerScope.value = scope === 'applications' ? 'applications' : 'records'
    showManager.value = true
  }
  function closeManager() { showManager.value = false; managerShared.value = false; managerScope.value = 'records' }
  function openRecommendation() { showRecommendation.value = true }
  function closeRecommendation() { showRecommendation.value = false }

  // Chat unread count (shared between ChatModal & Topbar)
  const chatUnread = ref(0)
  function setChatUnread(n) { chatUnread.value = n || 0 }

  // Tracker pending events (shared between DashboardPage & TrackerSettings)
  const trackerPending = ref([])
  function setTrackerPending(events) { trackerPending.value = events || [] }
  function clearTrackerPending() { trackerPending.value = [] }

  return { showConfig, showChat, showRecord, showHelp, showStats, showOffer, showManager, showRecommendation, detailId, recordShared, managerShared, managerScope,
    toggleConfig, toggleChat, toggleHelp, openRecord, closeRecord, openDetail, closeDetail,
    openStats, closeStats, openOffer, closeOffer, openManager, closeManager, openRecommendation, closeRecommendation,
    trackerPending, setTrackerPending, clearTrackerPending, chatUnread, setChatUnread }
})
