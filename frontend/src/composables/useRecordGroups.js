import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const selectedByCompany = ref({})

function companyKey(record) {
  return String(record?.company || '').trim().toLocaleLowerCase('zh-CN') || `record:${record?.record_id || ''}`
}

function groupRecords(records) {
  const groups = new Map()
  for (const record of records || []) {
    const key = companyKey(record)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(record)
  }
  return [...groups.entries()].map(([key, positions]) => {
    const selectedId = selectedByCompany.value[key]
    const selected = positions.find(item => item.record_id === selectedId) || positions[0]
    return { ...selected, _companyKey: key, _positions: positions }
  })
}

export function useRecordGroups(source) {
  const auth = useAuthStore()
  const expandedCompanies = ref(new Set())
  const groupedRecords = computed(() => groupRecords(source.value))
  const userIdentity = computed(() => auth.user?.id || auth.user?.user_id || auth.user?.username || '')

  function storageKey() {
    return userIdentity.value ? `rb_record_primary:${userIdentity.value}` : ''
  }

  function loadSelection() {
    const key = storageKey()
    if (!key) {
      selectedByCompany.value = {}
      return
    }
    try {
      const value = JSON.parse(localStorage.getItem(key) || '{}')
      selectedByCompany.value = value && typeof value === 'object' && !Array.isArray(value) ? value : {}
    } catch (_) {
      selectedByCompany.value = {}
    }
  }

  function saveSelection() {
    const key = storageKey()
    if (key) localStorage.setItem(key, JSON.stringify(selectedByCompany.value))
  }

  watch(userIdentity, loadSelection, { immediate: true })

  function selectPosition(group, position) {
    selectedByCompany.value = {
      ...selectedByCompany.value,
      [group._companyKey || companyKey(group)]: position.record_id,
    }
    saveSelection()
  }

  function selectPositionById(group, recordId) {
    const position = group?._positions?.find(item => item.record_id === recordId)
    if (position) selectPosition(group, position)
  }

  function toggleExpanded(group) {
    if (!group?._positions || group._positions.length < 2) return
    const next = new Set(expandedCompanies.value)
    if (next.has(group._companyKey)) next.delete(group._companyKey)
    else next.add(group._companyKey)
    expandedCompanies.value = next
  }

  function isExpanded(group) {
    return expandedCompanies.value.has(group?._companyKey)
  }

  return { groupedRecords, selectPosition, selectPositionById, toggleExpanded, isExpanded }
}
