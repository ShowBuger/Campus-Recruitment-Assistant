import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { get, post } from '@/utils/api'

export const useDashboardStore = defineStore('dashboard', () => {
  const data = ref(null)
  const loading = ref(false)
  const error = ref('')

  const records = computed(() => data.value?.main?.records || [])
  const recentRecords = computed(() => records.value.filter(r => {
    const p = (r.progress || [])[0]
    return p && p !== '未投递'
  }))
  const kpi = computed(() => ({
    total_companies: data.value?.main?.total_companies || 0,
    exam_count: data.value?.main?.exam_count || 0,
    interview_count: data.value?.main?.interview_count || 0,
    offer_count: data.value?.main?.offer_count || 0,
  }))
  const stats = computed(() => ({
    directions: data.value?.main?.directions || [],
    ctypes: data.value?.main?.ctypes || [],
  }))
  const deadlines = computed(() => data.value?.main?.deadlines || [])
  const lastUpdated = computed(() => data.value?.now || '')

  async function fetch() {
    loading.value = true; error.value = ''
    try { data.value = await get('/api/dashboard') }
    catch (e) { error.value = e.message }
    finally { loading.value = false }
  }

  async function refresh() {
    await post('/api/dashboard/refresh')
    await fetch()
  }

  let pollTimer = null
  function startPolling(ms = 30000) { stopPolling(); pollTimer = setInterval(() => { get('/api/dashboard').then(d => { if (d) data.value = d }).catch(() => {}) }, ms) }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
  return { data, loading, error, records, recentRecords, kpi, stats, deadlines, lastUpdated, fetch, refresh, startPolling, stopPolling }
})
