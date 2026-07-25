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
  const detailId = ref('')

  function toggleConfig() { showConfig.value = !showConfig.value }
  function toggleChat() { showChat.value = !showChat.value }
  function toggleHelp() { showHelp.value = !showHelp.value }
  function openRecord() { showRecord.value = true }
  function closeRecord() { showRecord.value = false }
  function openDetail(id) { detailId.value = id }
  function closeDetail() { detailId.value = '' }
  function openStats() { showStats.value = true }
  function closeStats() { showStats.value = false }
  function openOffer() { showOffer.value = true }
  function closeOffer() { showOffer.value = false }
  function openManager() { showManager.value = true }
  function closeManager() { showManager.value = false }

  return { showConfig, showChat, showRecord, showHelp, showStats, showOffer, showManager, detailId,
    toggleConfig, toggleChat, toggleHelp, openRecord, closeRecord, openDetail, closeDetail,
    openStats, closeStats, openOffer, closeOffer, openManager, closeManager }
})
