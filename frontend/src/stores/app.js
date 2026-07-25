import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const showRecord = ref(false)
  const detailId = ref('')

  function openRecord() { showRecord.value = true }
  function closeRecord() { showRecord.value = false }
  function openDetail(id) { detailId.value = id }
  function closeDetail() { detailId.value = '' }

  return { showRecord, detailId, openRecord, closeRecord, openDetail, closeDetail }
})
