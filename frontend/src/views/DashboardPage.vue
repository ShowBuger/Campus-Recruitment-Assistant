<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import { useDialogStore } from '@/stores/dialog'
import ProgressBadge from '@/components/ProgressBadge.vue'
import TooltipCell from '@/components/TooltipCell.vue'
import { fmtDateChina, fmtDateFullChina, inputDateChina, inputDateTimeChina, chinaDateTimeMs, calendarDateChina } from '@/utils/date'
import { externalHttpUrl } from '@/utils/externalUrl'

const store = useDashboardStore()
const app = useAppStore()
const dialog = useDialogStore()
const showFilter = ref(false)
const calendarCollapsed = ref(false)
const activeFilter = ref([])
const draftFilter = ref(null)
const FILTER_OPERATORS = [
  { value: 'equals', label: '等于' }, { value: 'not_equals', label: '不等于' },
  { value: 'contains', label: '包含' }, { value: 'not_contains', label: '不包含' },
]
const FILTER_COLUMNS = [
  { value: 'company', label: '公司', type: 'text' },
  { value: 'job', label: '目标岗位', type: 'text' },
  { value: 'city', label: '城市', type: 'text' },
  { value: 'batch', label: '批次', type: 'select', options: ['秋招', '提前批'] },
  { value: 'apply_date', label: '投递时间', type: 'date' },
  { value: 'exam_date', label: '机考时间', type: 'date' },
  { value: 'interview1', label: '一面时间', type: 'date' },
  { value: 'interview2', label: '二面时间', type: 'date' },
  { value: 'interview3', label: '三面时间', type: 'date' },
  { value: 'warm', label: '保温时间', type: 'date' },
  { value: 'result', label: '结果时间', type: 'date' },
  { value: 'deadline', label: '截止时间', type: 'date' },
  { value: 'progress', label: '进展', type: 'select', options: ['未投递', '已投递', '机考', '面试', 'OC', '已挂', '放弃'] },
]
let filterConditionId = 0

// Tracker pending events (shared via store, updated by TrackerSettings on sync complete)
const showTrackerModal = ref(false)
const trackerModalTitle = ref('')
const trackerModalSummary = ref('')
const trackerModalEvents = ref([])

async function loadTrackerPending() {
  try {
    const { get } = await import('@/utils/api')
    const data = await get('/api/progress-tracker')
    app.setTrackerPending((data?.events || []).filter(e => e.status === 'pending'))
  } catch (_) { app.clearTrackerPending() }
}

function openTrackerPendingModal() {
  const pending = app.trackerPending || []
  if (!pending.length) return
  trackerModalTitle.value = '待确认更新'
  trackerModalSummary.value = `发现 ${pending.length} 条待确认进度，可以现在处理或稍后再看`
  trackerModalEvents.value = [...pending]
  showTrackerModal.value = true
}

async function actTrackerPopupEvent(id, action) {
  const payload = { action }
  const roundEl = document.getElementById('tracker-round-' + id)
  if ((action === 'confirm' || action === 'create') && roundEl?.value) {
    payload.interview_round = Number(roundEl.value)
  }
  const timeEl = document.getElementById('tracker-time-' + id)
  if ((action === 'confirm' || action === 'create') && timeEl?.value) {
    payload.event_ms = chinaDateTimeMs(timeEl.value)
  }
  const { post } = await import('@/utils/api')
  const { useToastStore } = await import('@/stores/toast')
  const toast = useToastStore()
  try {
    const result = await post(`/api/progress-tracker/events/${id}`, payload)
    // Remove from local list only after successful API call
    const updated = trackerModalEvents.value.filter(e => Number(e.id) !== Number(id))
    trackerModalEvents.value = updated
    app.setTrackerPending(app.trackerPending.filter(e => Number(e.id) !== Number(id)))
    const left = updated.length
    trackerModalSummary.value = left ? `还有 ${left} 条待确认进度` : '处理完成，没有待确认进度'
    // Refresh dashboard if confirmed
    if (action === 'confirm' || action === 'create') await store.fetch()
    toast.success(result.message || '已处理')
    // Reload from server to sync
    await loadTrackerPending()
  } catch (e) {
    toast.error('处理失败: ' + e.message)
  }
}

function formatTrackerTime(value) {
  if (!value) return ''
  const d = new Date(String(value).replace(' ', 'T') + 'Z')
  return isNaN(d) ? value : d.toLocaleString('zh-CN', { hour12: false })
}

function formatTrackerEventTime(value) {
  if (!value) return ''
  const d = new Date(Number(value))
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('zh-CN', { hour12: false })
}

function trackerEventTime(item) {
  return item.progress === '机考'
    ? (item.deadline_ms || item.scheduled_ms || item.received_ms)
    : (item.scheduled_ms || item.received_ms)
}

// ---- calendar event modal ----
const showEventModal = ref(false)
const calEventDate = ref('')
const calEventLabel = ref('')

const editDateRecord = ref(null)
const editDateType = ref('')
const editDateValue = ref('')
const editDateSaving = ref(false)
const DATE_FIELD_LABELS = {
  apply: '投递时间', exam: '机考时间', interview1: '一面时间', interview2: '二面时间',
  interview3: '三面时间', warm: '保温时间', result: '结果时间', deadline: '截止时间',
}

function openDateEditor(record, eventType, timestamp) {
  editDateRecord.value = record
  editDateType.value = eventType
  editDateValue.value = inputDateChina(timestamp)
}

function closeDateEditor() {
  if (editDateSaving.value) return
  editDateRecord.value = null
  editDateType.value = ''
  editDateValue.value = ''
}

async function saveRecordDate(clear = false) {
  const record = editDateRecord.value
  if (!record || (!clear && !editDateValue.value)) return
  editDateSaving.value = true
  try {
    const { post } = await import('@/utils/api')
    const path = clear ? '/api/dashboard/calendar/event/delete' : '/api/dashboard/calendar/event'
    const payload = { record_id: record.record_id, event_type: editDateType.value }
    if (!clear) payload.date = editDateValue.value
    await post(path, payload)
    await store.fetch()
    editDateRecord.value = null
    editDateType.value = ''
    editDateValue.value = ''
  } finally {
    editDateSaving.value = false
  }
}

// ---- application records (original: _lastData.main.recent) ----
const records = computed(() => store.data?.main?.recent || [])

function newFilterCondition() {
  return { id: ++filterConditionId, column: 'company', operator: 'contains', value: '', from: '', to: '' }
}
function filterColumn(condition) {
  return FILTER_COLUMNS.find(column => column.value === condition.column) || FILTER_COLUMNS[0]
}
function validFilterConditions(conditions) {
  return (conditions || []).filter(condition => filterColumn(condition).type === 'date'
    ? Boolean(condition.from || condition.to)
    : Boolean(String(condition.value || '').trim()))
}
function recordMatchesCondition(record, condition) {
  const column = filterColumn(condition)
  if (column.type === 'date') {
    const value = inputDateChina(record[condition.column])
    if (!value) return false
    const from = condition.from && condition.to && condition.from > condition.to ? condition.to : condition.from
    const to = condition.from && condition.to && condition.from > condition.to ? condition.from : condition.to
    return (!from || value >= from) && (!to || value <= to)
  }
  const sourceValue = condition.column === 'progress' ? (record.progress || [])[0] : record[condition.column]
  const source = String(sourceValue || '').trim().toLocaleLowerCase('zh-CN')
  const target = String(condition.value || '').trim().toLocaleLowerCase('zh-CN')
  if (condition.operator === 'equals') return source === target
  if (condition.operator === 'not_equals') return source !== target
  if (condition.operator === 'not_contains') return !source.includes(target)
  return source.includes(target)
}
function filterRecords(source, conditions) {
  const valid = validFilterConditions(conditions)
  return valid.length ? source.filter(record => valid.every(condition => recordMatchesCondition(record, condition))) : source
}

function serializableFilters(conditions) {
  return validFilterConditions(conditions).slice(0, 20).map(condition => ({
    column: condition.column,
    operator: filterColumn(condition).type === 'date' ? 'range' : condition.operator,
    value: filterColumn(condition).type === 'date' ? '' : String(condition.value || '').trim(),
    from: condition.from || null,
    to: condition.to || null,
  }))
}

async function loadSavedFilters() {
  try {
    const { get } = await import('@/utils/api')
    const data = await get('/api/config/dashboard-filters', { silent: true })
    const allowedColumns = new Set(FILTER_COLUMNS.map(column => column.value))
    const allowedOperators = new Set(FILTER_OPERATORS.map(operator => operator.value).concat('range'))
    activeFilter.value = (Array.isArray(data?.conditions) ? data.conditions : [])
      .filter(condition => allowedColumns.has(condition.column) && allowedOperators.has(condition.operator))
      .map(condition => ({ ...condition, id: ++filterConditionId, from: condition.from || '', to: condition.to || '' }))
  } catch (_) {
    activeFilter.value = []
  }
}

async function saveActiveFilters() {
  try {
    const { post } = await import('@/utils/api')
    await post('/api/config/dashboard-filters', { conditions: serializableFilters(activeFilter.value) }, { silent: true })
  } catch (_) {}
}

const filteredRecords = computed(() => filterRecords(records.value, activeFilter.value))
const draftFilteredCount = computed(() => {
  return filterRecords(records.value, draftFilter.value).length
})

const filterSummary = computed(() => {
  if (!showFilter.value) return ''
  const count = validFilterConditions(draftFilter.value).length
  if (!count) return '添加条件后应用筛选'
  return `${count} 个条件 · ${draftFilteredCount.value} / ${records.value.length} 条`
})

function openFilter() {
  draftFilter.value = activeFilter.value.length
    ? activeFilter.value.map(condition => ({ ...condition, id: ++filterConditionId }))
    : [newFilterCondition()]
  showFilter.value = true
}
function applyFilter() {
  if (draftFilter.value !== null) activeFilter.value = validFilterConditions(draftFilter.value).map(condition => ({ ...condition }))
  draftFilter.value = null
  showFilter.value = false
  void saveActiveFilters()
}
function clearFilter() {
  draftFilter.value = [newFilterCondition()]
}
function addFilterCondition() {
  draftFilter.value.push(newFilterCondition())
}
function removeFilterCondition(id) {
  draftFilter.value = draftFilter.value.filter(condition => condition.id !== id)
  if (!draftFilter.value.length) draftFilter.value.push(newFilterCondition())
}
function changeFilterColumn(condition) {
  condition.operator = filterColumn(condition).type === 'date' ? 'range' : 'contains'
  condition.value = ''
  condition.from = ''
  condition.to = ''
}

function toggleCalendarFromRecordHeader(event) {
  if (event.target.closest('button, input, select, label, a, [role="dialog"]')) return
  calendarCollapsed.value = !calendarCollapsed.value
}

function formatDate(ts) { return fmtDateChina(ts) }
function formatDateFull(ts) { return fmtDateFullChina(ts) }

// ---- Calendar (exact replica of original renderCalendar) ----
const calendarMonth = ref(new Date())
const localEvents = ref([])
const DAY = 86400000

function calendarKey(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }

function calendarDate(ts) { return calendarDateChina(ts) }

function calendarEvents() {
  const groups = {}
  function add(ts, type, label, r, extra) {
    const date = calendarDate(ts); if (!date) return
    const key = calendarKey(date)
    if (!groups[key]) groups[key] = []
    groups[key].push({ date, type, label, company: r.company || '-', job: r.job || '', ...(extra || {}) })
  }
	  records.value.forEach(r => {
	    add(r.exam_date, 'exam', '机考/笔试', r, { rid: r.record_id, etype: 'exam' })
	    add(r.interview1, 'interview', '一面', r, { rid: r.record_id, etype: 'interview1' })
	    add(r.interview2, 'interview', '二面', r, { rid: r.record_id, etype: 'interview2' })
	    add(r.interview3, 'interview', '三面', r, { rid: r.record_id, etype: 'interview3' })
	    add(r.deadline, 'deadline', '截止', r, { rid: r.record_id, etype: 'deadline' })
  })
  localEvents.value.forEach(e => { add(e.date, 'other', e.label, { company: '', job: '' }, { lid: e.id }) })
  return groups
}

const events = computed(() => calendarEvents())

const calendarTitle = computed(() => {
  const y = calendarMonth.value.getFullYear(), m = calendarMonth.value.getMonth()
  return y + ' 年 ' + (m + 1) + ' 月'
})

const calendarDays = computed(() => {
  const year = calendarMonth.value.getFullYear(), month = calendarMonth.value.getMonth()
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7 // Monday-first
  const start = new Date(year, month, 1 - offset)
  const days = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    const key = calendarKey(d)
    const items = events.value[key] || []
    const other = d.getMonth() !== month
    const today = calendarKey(new Date()) === key
    days.push({ date: d, key, items, other, today, visible: items.slice(0, 2), more: Math.max(0, items.length - 2) })
  }
  return days
})

const countdownItems = computed(() => {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const upcoming = []
  Object.entries(events.value).forEach(([key, items]) => {
    items.forEach(item => {
      const days = Math.round((new Date(item.date.getFullYear(), item.date.getMonth(), item.date.getDate()) - today) / DAY)
      if (days >= 0 && days <= 15) upcoming.push({ item, days, key })
    })
  })
  upcoming.sort((a, b) => a.item.date - b.item.date || (a.item.company || '').localeCompare(b.item.company || ''))
  return upcoming.slice(0, 30)
})

function changeMonth(delta) { const d = new Date(calendarMonth.value); d.setMonth(d.getMonth() + delta); calendarMonth.value = d }
function goToday() { calendarMonth.value = new Date() }

function inputDate(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }

function openCalendarEventModal(dateStr) {
  calEventDate.value = dateStr || inputDate(new Date())
  calEventLabel.value = ''
  showEventModal.value = true
}

async function submitCalendarEvent() {
  if (!calEventDate.value || !calEventLabel.value.trim()) return
  try {
    const response = await fetch('/api/dashboard/calendar/local-event', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
      body: JSON.stringify({ date: calEventDate.value, label: calEventLabel.value.trim() })
    })
    if (!response.ok) return
    await loadLocalEvents()
    showEventModal.value = false
  } catch {}
}

async function loadLocalEvents() {
  try {
    const r = await fetch('/api/dashboard/calendar/local-events', { headers: { Authorization: `Bearer ${localStorage.getItem('rb_token')}` } })
    localEvents.value = (await r.json()).events || []
  } catch { localEvents.value = [] }
}

async function deleteEvent(id, etype) {
  const confirmed = await dialog.confirm(
    '确定删除这个日程吗？',
    { title: '删除日程', tone: 'danger', confirmText: '删除日程' },
  )
  if (!confirmed) return
  try {
    if (etype) {
      await fetch('/api/dashboard/calendar/event/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
        body: JSON.stringify({ record_id: id, event_type: etype })
      })
    } else {
      await fetch(`/api/dashboard/calendar/local-event/${id}/delete`, {
        method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('rb_token')}` }
      })
    }
    await store.fetch()
    await loadLocalEvents()
  } catch {}
}

// Day detail modal
const dayDetailKey = ref('')
const dayDetailItems = computed(() => dayDetailKey.value ? (events.value[dayDetailKey.value] || []) : [])
function openDayDetail(key) { dayDetailKey.value = key }
function closeDayDetail() { dayDetailKey.value = '' }

const EVENT_TYPE_MAP = { apply: '投递', exam: '机考/笔试', interview: '面试', warm: '保温', result: '结果', deadline: '截止', other: '自定义' }
const EVENT_BADGE_MAP = { other: 'bdg-a', deadline: 'bdg-r', exam: 'bdg-a', warm: 'bdg-a' }
function eventBadgeClass(type) { return EVENT_BADGE_MAP[type] || 'bdg-b' }
function eventTypeName(type) { return EVENT_TYPE_MAP[type] || type }

async function deleteCalendarEvent(id, etype) {
  const confirmed = await dialog.confirm(
    '确定删除这个日程吗？',
    { title: '删除日程', tone: 'danger', confirmText: '删除日程' },
  )
  if (!confirmed) return
  try {
    if (etype) {
      await fetch('/api/dashboard/calendar/event/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
        body: JSON.stringify({ record_id: id, event_type: etype })
      })
    } else {
      await fetch(`/api/dashboard/calendar/local-event/${id}/delete`, {
        method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('rb_token')}` }
      })
    }
    await store.fetch(); await loadLocalEvents()
    // Re-render the day detail
    if (dayDetailKey.value) {
      const key = dayDetailKey.value
      dayDetailKey.value = ''
      await nextTick()
      dayDetailKey.value = key
    }
  } catch {}
}

function onKeydown(e) { if (e.key === 'Escape' && showFilter.value) applyFilter() }

let trackerPollTimer = null
onMounted(() => { store.fetch(); loadSavedFilters(); loadLocalEvents(); loadTrackerPending(); store.startPolling(); trackerPollTimer = setInterval(loadTrackerPending, 30000); document.addEventListener('keydown', onKeydown) })
onUnmounted(() => { store.stopPolling(); if (trackerPollTimer) clearInterval(trackerPollTimer); document.removeEventListener('keydown', onKeydown) })
</script>

<template>
  <div class="page active dashboard-page" :class="{ 'calendar-collapsed': calendarCollapsed }">
    <!-- KPI Cards (exact original structure) -->
    <div class="kpis">
      <div class="kpi b"><i class="kpi-koi" aria-hidden="true"></i><div class="kpi-label">投递岗位</div><div class="kpi-value">{{ store.kpi.total_companies }}</div><div class="kpi-sub">已进入投递流程</div></div>
      <div class="kpi a"><i class="kpi-koi" aria-hidden="true"></i><div class="kpi-label">笔试 / 机考</div><div class="kpi-value">{{ store.kpi.exam_count }}</div><div class="kpi-sub">有笔试或机考记录</div></div>
      <div class="kpi c"><i class="kpi-koi" aria-hidden="true"></i><div class="kpi-label">面试</div><div class="kpi-value">{{ store.kpi.interview_count }}</div><div class="kpi-sub">进入面试流程</div></div>
      <div class="kpi g"><i class="kpi-koi" aria-hidden="true"></i><div class="kpi-label">Offer</div><div class="kpi-value">{{ store.kpi.offer_count }}</div><div class="kpi-sub">OC 或已录用</div></div>
    </div>

    <!-- Calendar Card (exact original structure) -->
    <div v-show="!calendarCollapsed" class="card dashboard-calendar">
      <div class="card-hd"><span class="dot a"></span><div class="card-title">校招日历</div><div class="card-sub">日程、投递节点与截止日期</div></div>
      <div class="card-body">
        <div class="calendar-toolbar">
          <button class="icon-btn" @click="changeMonth(-1)" title="上个月">&#8249;</button>
          <h2>{{ calendarTitle }}</h2>
          <button class="icon-btn" @click="changeMonth(1)" title="下个月">&#8250;</button>
          <button class="btn" @click="goToday">今天</button>
          <button class="btn btn-primary" @click="openCalendarEventModal()">新建日程</button>
          <div class="calendar-legend">
            <span class="lg-apply">投递</span><span class="lg-exam">机考/笔试</span><span>面试</span><span class="lg-warm">保温</span><span class="lg-result">结果</span><span class="lg-deadline">截止</span><span class="lg-other">其他</span>
          </div>
        </div>
        <div class="calendar-layout">
          <div class="calendar-scroll">
            <div class="calendar-grid">
              <div v-for="d in ['一','二','三','四','五','六','日']" :key="d" class="calendar-weekday">周{{ d }}</div>
              <div v-for="day in calendarDays" :key="day.key" class="calendar-day" :class="{ other: day.other, today: day.today }" @click="!day.other && openDayDetail(day.key)">
                <div class="calendar-date"><span>{{ day.date.getDate() }}</span></div>
                <div class="calendar-events">
                  <div v-for="e in day.visible" :key="e.rid || e.lid || e.label" class="calendar-event" :class="e.type" :title="e.label + (e.company ? ' · ' + e.company : '') + (e.job ? ' · ' + e.job : '')">
                    {{ e.label }}{{ e.company ? ' · ' + e.company : '' }}
                  </div>
                  <div v-if="day.more" class="calendar-more">+{{ day.more }} 项</div>
                </div>
              </div>
            </div>
          </div>
          <aside class="countdown-panel">
            <h3>近期安排</h3>
            <div class="countdown-list">
              <div v-if="!countdownItems.length" class="center">暂无未来安排</div>
              <div v-for="x in countdownItems" :key="x.key + x.item.label + x.item.company" class="countdown-item">
                <div>
                  <b>{{ x.item.company ? x.item.company + ' · ' : '' }}{{ x.item.label }}</b>
                  <span>{{ x.key }}{{ x.item.job ? ' · ' + x.item.job : '' }}</span>
                </div>
                <div class="countdown-days" :class="{ urgent: x.days <= 3 }">
                  {{ x.days === 0 ? '今天' : x.days === 1 ? '明天' : '还有 ' + x.days + ' 天' }}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>

    <!-- Records Table Card (exact original structure) -->
    <div class="card data-table-card" :class="{ 'filter-open': showFilter }">
      <div class="card-hd record-card-hd" :title="calendarCollapsed ? '双击恢复日历' : '双击隐藏日历并展开投递记录'" @dblclick="toggleCalendarFromRecordHeader">
        <span class="dot"></span>
        <div class="card-title">投递记录</div>
        <span class="record-expand-hint" aria-hidden="true">{{ calendarCollapsed ? '双击恢复' : '双击扩展' }}</span>
        <button v-if="app.trackerPending.length" class="tracker-pending-btn" @click="openTrackerPendingModal">待确认更新 <span>{{ app.trackerPending.length }}</span></button>
        <div class="record-hd-spacer"></div>
        <div class="progress-filter" :class="{ active: showFilter }">
          <button class="progress-filter-toggle" :class="{ 'has-filter': activeFilter.length > 0 }" @click="showFilter ? applyFilter() : openFilter()" aria-haspopup="dialog" :aria-expanded="showFilter">
            <span>{{ activeFilter.length ? activeFilter.length + ' 个条件' : '筛选记录' }}</span>
          </button>
          <div class="progress-filter-backdrop" @click="applyFilter" v-if="showFilter"></div>
          <div class="progress-filter-menu" v-if="showFilter" role="dialog" aria-modal="true">
            <div class="progress-filter-menu-hd">
              <div><b>筛选投递记录</b><span>{{ filterSummary }}</span></div>
              <div class="progress-filter-dialog-actions">
                <button type="button" class="progress-filter-clear" :disabled="!validFilterConditions(draftFilter).length" @click="clearFilter">重置</button>
                <button type="button" class="progress-filter-close" @click="applyFilter" aria-label="关闭筛选">&times;</button>
              </div>
            </div>
            <div class="filter-builder">
              <div v-for="(condition, index) in draftFilter" :key="condition.id" class="filter-condition">
                <div class="filter-condition-head"><span>条件 {{ String(index + 1).padStart(2, '0') }}</span><button type="button" class="filter-condition-remove" @click="removeFilterCondition(condition.id)">删除</button></div>
                <div class="filter-condition-fields">
                  <label class="filter-field filter-field-column"><span>筛选列</span><select v-model="condition.column" aria-label="筛选列" @change="changeFilterColumn(condition)"><option v-for="column in FILTER_COLUMNS" :key="column.value" :value="column.value">{{ column.label }}</option></select></label>
                  <template v-if="filterColumn(condition).type === 'date'">
                    <div class="filter-field filter-field-operator"><span>关系</span><strong>时间区间</strong></div>
                    <label class="filter-field filter-field-value"><span>日期范围</span><div class="filter-date-range"><input v-model="condition.from" type="date" aria-label="开始日期"><i>至</i><input v-model="condition.to" type="date" aria-label="结束日期"></div></label>
                  </template>
                  <template v-else>
                    <label class="filter-field filter-field-operator"><span>关系</span><select v-model="condition.operator" aria-label="筛选关系"><option v-for="operator in FILTER_OPERATORS" :key="operator.value" :value="operator.value">{{ operator.label }}</option></select></label>
                    <label class="filter-field filter-field-value"><span>值</span><select v-if="filterColumn(condition).type === 'select'" v-model="condition.value" aria-label="筛选值"><option value="">请选择</option><option v-for="option in filterColumn(condition).options" :key="option" :value="option">{{ option }}</option></select><input v-else v-model.trim="condition.value" type="text" maxlength="100" aria-label="筛选值" placeholder="输入筛选值"></label>
                  </template>
                </div>
              </div>
              <button type="button" class="filter-add-condition" @click="addFilterCondition">添加条件</button>
            </div>
            <div class="filter-builder-footer">
              <span>多个条件同时满足</span>
              <button type="button" class="btn btn-primary" @click="applyFilter">应用筛选</button>
            </div>
          </div>
        </div>
<div class="card-sub">{{ filteredRecords.length }} 条</div>
      </div>

      <div class="tbl records-table-scroll">
        <table class="data-table records-table">
          <colgroup>
            <col style="width:120px"><col style="width:145px"><col style="width:68px"><col style="width:88px">
            <col style="width:68px"><col style="width:58px"><col style="width:58px"><col style="width:58px"><col style="width:58px">
            <col style="width:58px"><col style="width:58px"><col style="width:68px"><col style="width:76px"><col style="width:58px">
          </colgroup>
          <thead>
            <tr>
              <th>公司</th><th>目标岗位</th><th>城市</th><th>批次</th>
              <th>投递</th><th>机考</th><th>一面</th><th>二面</th><th>三面</th>
              <th>保温</th><th>结果</th><th>截止</th><th>进展</th><th>入口</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="store.loading"><td colspan="14" class="center">加载中…</td></tr>
            <tr v-else-if="store.error"><td colspan="14" class="center" style="color:var(--red)">{{ store.error }}</td></tr>
            <tr v-else-if="!filteredRecords.length"><td colspan="14" class="center">暂无记录</td></tr>
            <tr v-for="(r, i) in filteredRecords.slice(0, 40)" :key="r.record_id">
              <td class="company"><button class="company-link" @click="app.openDetail(r.record_id)">{{ r.company || '-' }}</button></td>
              <td class="job"><TooltipCell :text="r.job || '-'" /></td>
              <td><TooltipCell :text="r.city || '-'" /></td>
              <td><span class="badge bdg-b">{{ r.batch || '-' }}</span></td>
              <td><button class="table-date date-edit" :title="'修改投递时间：' + (formatDateFull(r.apply_date) || '未填写')" @click="openDateEditor(r, 'apply', r.apply_date)">{{ formatDate(r.apply_date) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改机考时间：' + (formatDateFull(r.exam_date) || '未填写')" @click="openDateEditor(r, 'exam', r.exam_date)">{{ formatDate(r.exam_date) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改一面时间：' + (formatDateFull(r.interview1) || '未填写')" @click="openDateEditor(r, 'interview1', r.interview1)">{{ formatDate(r.interview1) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改二面时间：' + (formatDateFull(r.interview2) || '未填写')" @click="openDateEditor(r, 'interview2', r.interview2)">{{ formatDate(r.interview2) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改三面时间：' + (formatDateFull(r.interview3) || '未填写')" @click="openDateEditor(r, 'interview3', r.interview3)">{{ formatDate(r.interview3) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改保温时间：' + (formatDateFull(r.warm) || '未填写')" @click="openDateEditor(r, 'warm', r.warm)">{{ formatDate(r.warm) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改结果时间：' + (formatDateFull(r.result) || '未填写')" @click="openDateEditor(r, 'result', r.result)">{{ formatDate(r.result) }}</button></td>
              <td><button class="table-date date-edit" :title="'修改截止时间：' + (formatDateFull(r.deadline) || '未填写')" @click="openDateEditor(r, 'deadline', r.deadline)">{{ formatDate(r.deadline) }}</button></td>
              <td><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td><a v-if="externalHttpUrl(r.url)" :href="externalHttpUrl(r.url)" target="_blank" rel="noopener noreferrer">查看</a><span v-else class="table-date">-</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="table-actions">
        <button class="btn btn-primary" @click="app.openRecord()">新增记录</button>
        <button class="btn" @click="app.openManager('applications')">管理记录</button>
        <button class="btn" @click="app.openStats()">统计信息</button>
        <button class="btn" @click="app.openOffer()">Offer 对比</button>
      </div>
    </div>

    <!-- Inline record date editor -->
    <div class="modal-mask show" v-if="editDateRecord" @mousedown.self="closeDateEditor">
      <div class="modal date-editor-modal">
        <div class="modal-hd"><div><h2>修改{{ DATE_FIELD_LABELS[editDateType] }}</h2><p>{{ editDateRecord.company || '-' }} · {{ editDateRecord.job || '-' }}</p></div><button class="icon-btn" :disabled="editDateSaving" @click="closeDateEditor" title="关闭">&times;</button></div>
        <div class="modal-body"><div class="form-group"><label for="record-date-editor">日期</label><input id="record-date-editor" type="date" v-model="editDateValue" autofocus></div><div class="help">保存后会根据投递、机考和面试日期同步更新进展。</div></div>
        <div class="modal-ft"><button class="btn" :disabled="editDateSaving || !editDateValue" @click="saveRecordDate(true)">清空日期</button><button class="btn" :disabled="editDateSaving" @click="closeDateEditor">取消</button><button class="btn btn-primary" :disabled="editDateSaving || !editDateValue" @click="saveRecordDate()">{{ editDateSaving ? '保存中…' : '保存' }}</button></div>
      </div>
    </div>

    <!-- Day Detail Modal -->
    <div class="modal-mask show" v-if="dayDetailKey" @mousedown.self="closeDayDetail">
      <div class="modal" style="width:min(520px,94vw)">
        <div class="modal-hd"><div><h2>{{ dayDetailKey }}</h2><p>{{ dayDetailItems.length }} 个日程</p></div><button class="icon-btn" @click="closeDayDetail" title="关闭">&times;</button></div>
        <div class="modal-body">
          <div v-if="!dayDetailItems.length" class="center">该日暂无日程</div>
          <div v-for="e in dayDetailItems" :key="e.rid || e.lid || e.label" style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)">
            <div>
              <b>{{ e.label }}</b>
              <div style="color:var(--muted);font-size:12px;margin-top:2px"><template v-if="e.company">{{ e.company }}{{ e.job ? ' · ' + e.job : '' }} · </template><span :class="'badge ' + eventBadgeClass(e.type)">{{ eventTypeName(e.type) }}</span></div>
            </div>
            <button class="btn" style="height:28px;padding:0 10px;font-size:11px;flex-shrink:0" @click="deleteCalendarEvent(e.rid || e.lid, e.etype)">删除</button>
          </div>
        </div>
        <div class="modal-ft">
          <button class="btn btn-primary" @click="openCalendarEventModal(dayDetailKey); closeDayDetail()">新建日程</button>
          <button class="btn" @click="closeDayDetail">关闭</button>
        </div>
      </div>
    </div>

    <!-- Calendar Event Modal -->
    <div class="modal-mask show" v-if="showEventModal" @mousedown.self="showEventModal = false">
      <div class="modal" style="width:min(520px,94vw)">
        <div class="modal-hd"><div><h2>新建日程</h2><p>{{ calEventDate || '-' }}</p></div><button class="icon-btn" @click="showEventModal = false" title="关闭">&times;</button></div>
        <div class="modal-body">
          <div class="form-group"><label for="cal-event-date">日程日期</label><input id="cal-event-date" type="date" v-model="calEventDate"></div>
          <div class="form-group"><label for="cal-event-label">日程内容</label><input id="cal-event-label" v-model="calEventLabel" maxlength="200" placeholder="例如：参加宣讲会、准备材料、与导师沟通"></div>
        </div>
        <div class="modal-ft"><button class="btn" @click="showEventModal = false">取消</button><button class="btn btn-primary" @click="submitCalendarEvent">保存日程</button></div>
      </div>
    </div>
  </div>

  <!-- Tracker pending events modal (on dashboard, match old tracker-test-modal) -->
  <div class="modal-mask" :class="{ show: showTrackerModal }" @mousedown.self="showTrackerModal = false">
    <div class="modal tracker-test-modal">
      <div class="modal-hd">
        <div><h2>{{ trackerModalTitle }}</h2><p>{{ trackerModalSummary }}</p></div>
        <button class="icon-btn" @click="showTrackerModal = false" title="关闭">&times;</button>
      </div>
      <div class="modal-body">
        <div class="tracker-event-list" v-if="trackerModalEvents.length">
          <article v-for="item in trackerModalEvents" :key="item.id" class="tracker-event tracker-test-result" :data-event-id="item.id">
            <div class="tracker-event-main">
              <div><b>{{ item.company || (item.record_id ? '已匹配岗位' : '待补充公司') }}</b><span>{{ item.job || item.subject || '待补充岗位' }}</span></div>
              <em>{{ item.progress || '未识别' }}</em>
            </div>
            <div class="tracker-event-meta">
              <span v-if="item.created_at">{{ formatTrackerTime(item.created_at) }}</span>
              <span>置信度 {{ Math.round((item.confidence || 0) * 100) }}%</span>
              <span v-if="item.scheduled_ms">安排 {{ formatTrackerEventTime(item.scheduled_ms) }}</span>
              <span v-if="item.deadline_ms">截止 {{ formatTrackerEventTime(item.deadline_ms) }}</span>
              <span v-if="item.reason">{{ item.reason }}</span>
              <span v-if="item.time_reason">{{ item.time_reason }}</span>
              <span v-if="!item.record_id" class="tracker-unmatched">未匹配个人总表岗位，可直接新增后再完善信息</span>
            </div>
            <label class="tracker-time-picker"><span>更新时间</span><input :id="'tracker-time-' + item.id" type="datetime-local" :value="inputDateTimeChina(trackerEventTime(item))"><small>已填入邮件自动识别时间，可在确认前修改</small></label>
            <div v-if="item.progress === '面试'" class="tracker-round-picker">
              确认面试轮次
              <select :id="'tracker-round-' + item.id">
                <option value="">请选择</option>
                <option value="1" :selected="item.interview_round === 1">一面</option>
                <option value="2" :selected="item.interview_round === 2">二面</option>
                <option value="3" :selected="item.interview_round === 3">三面</option>
              </select>
            </div>
            <div class="tracker-event-actions">
              <button v-if="item.record_id" class="btn btn-primary" @click="actTrackerPopupEvent(item.id, 'confirm')">接受</button>
              <button v-else class="btn btn-primary" @click="actTrackerPopupEvent(item.id, 'create')">一键添加记录</button>
              <button class="btn" @click="actTrackerPopupEvent(item.id, 'ignore')">忽略</button>
            </div>
          </article>
        </div>
        <div v-else class="center muted">所有结果均已处理</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.date-edit{appearance:none;padding:4px 3px;border:1px solid transparent;border-radius:6px;background:transparent;cursor:pointer;transition:color .15s ease,border-color .15s ease,background .15s ease}.date-edit:hover,.date-edit:focus-visible{border-color:var(--line);color:var(--blue);background:var(--blueS);outline:none}.date-editor-modal{width:min(420px,94vw)}
.record-card-hd{cursor:pointer;user-select:none}.record-card-hd :is(button,input,select,label,a){cursor:pointer}.record-expand-hint{margin-left:2px;color:var(--muted);font:500 10px/1.2 var(--font);letter-spacing:.01em;opacity:.82;transition:color .15s ease,opacity .15s ease}.record-card-hd:hover .record-expand-hint,.calendar-collapsed .record-expand-hint{color:var(--sub);opacity:1}.data-table-card.filter-open{position:relative;z-index:40;overflow:visible}.data-table-card.filter-open .record-card-hd{position:relative;z-index:41}.records-table-scroll{max-height:440px}.calendar-collapsed .data-table-card{display:flex;min-height:calc(100dvh - 260px);flex-direction:column}.calendar-collapsed .records-table-scroll{flex:1;max-height:none;min-height:280px}.calendar-collapsed .data-table-card .table-actions{margin-top:auto}
.progress-filter-menu{width:min(680px,calc(100vw - 32px))}.filter-builder{display:grid;gap:8px;max-height:min(52dvh,420px);padding:12px;overflow:auto;background:var(--panel)}.filter-condition{display:grid;grid-template-columns:24px minmax(112px,.8fr) minmax(86px,.55fr) minmax(190px,1.5fr) 30px;align-items:center;gap:8px;padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}.filter-condition-index{display:grid;width:22px;height:22px;place-items:center;border-radius:50%;color:var(--muted);background:var(--panel);font:800 10px var(--mono)}.filter-condition :is(select,input){min-width:0;width:100%;height:34px;padding:0 9px;border:1px solid var(--line2);border-radius:7px;outline:none;color:var(--ink);background:var(--panel);font:600 11px var(--font)}.filter-condition :is(select,input):focus{border-color:var(--blue);box-shadow:0 0 0 2px var(--blueS)}.filter-range-label{color:var(--sub);font-size:11px;font-weight:700;text-align:center}.filter-date-range{display:grid;grid-template-columns:minmax(118px,1fr) auto minmax(118px,1fr);align-items:center;gap:6px}.filter-date-range span{color:var(--muted);font-size:10px}.filter-condition-remove{display:grid;width:28px;height:28px;place-items:center;padding:0;border:1px solid transparent;border-radius:7px;color:var(--muted);background:transparent;font:700 17px/1 var(--font);cursor:pointer}.filter-condition-remove:hover{border-color:var(--line);color:var(--red);background:var(--redS)}.filter-add-condition{justify-self:start;padding:7px 10px;border:1px dashed var(--line2);border-radius:8px;color:var(--blue);background:transparent;font:800 11px var(--font);cursor:pointer}.filter-add-condition:hover{border-color:var(--blue);background:var(--blueS)}.filter-builder-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-top:1px solid var(--line);background:var(--panel)}.filter-builder-footer span{color:var(--muted);font-size:10px}.filter-builder-footer .btn{height:30px}
.dashboard-page{min-width:0}.dashboard-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.dashboard-page-head h2{margin:0;font-size:clamp(22px,2.5vw,30px);line-height:1.2;letter-spacing:-.035em}.dashboard-page-head p{max-width:620px;margin-top:7px;color:var(--muted);font-size:13px}.dashboard-add{min-width:104px}.kpis{display:grid;grid-template-columns:1.15fr .95fr .95fr 1.05fr;gap:12px;margin-bottom:14px}.kpi{position:relative;overflow:hidden;min-height:112px;padding:17px 18px;border:1px solid var(--line);border-radius:14px;background:var(--panel);box-shadow:var(--shadow)}.kpi:after{content:"";position:absolute;right:-28px;bottom:-38px;width:105px;height:105px;border-radius:50%;background:color-mix(in srgb,var(--blue) 7%,transparent);pointer-events:none}.kpi-label{color:var(--muted);font-size:10px;font-weight:800}.kpi-value{margin-top:11px;color:var(--ink);font-size:30px;line-height:1;letter-spacing:-.04em}.kpi-sub{margin-top:8px;color:var(--sub);font-size:9px}.dashboard-calendar,.data-table-card{overflow:hidden;border-radius:16px}.dashboard-calendar{margin-bottom:14px}.dashboard-calendar>.card-hd,.data-table-card>.card-hd{min-height:54px;padding:0 16px;border-bottom:1px solid var(--line)}.dashboard-calendar>.card-body{padding:12px;background:var(--bg)}.calendar-toolbar{padding:0 0 11px}.calendar-layout{gap:12px}.calendar-scroll,.countdown-panel{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:var(--panel)}.calendar-grid{border:0}.countdown-panel{padding:14px}.countdown-panel h3{margin:0 0 10px;font-size:12px}.countdown-item{border-radius:9px;transition:background .15s ease}.countdown-item:hover{background:var(--blueS)}.data-table-card .tbl{background:var(--panel)}.data-table-card .table-actions{min-height:58px;padding:10px 14px;border-top:1px solid var(--line);background:var(--bg)}.records-table tbody tr{transition:background .15s ease}.records-table tbody tr:hover{background:var(--blueS)}@media(max-width:980px){.kpis{grid-template-columns:1fr 1fr}.calendar-layout{grid-template-columns:1fr}.countdown-panel{max-height:260px}}@media(max-width:620px){.dashboard-page-head{align-items:flex-start;flex-direction:column}.dashboard-add{width:100%}.kpis{grid-template-columns:1fr 1fr;gap:8px}.kpi{min-height:104px;padding:14px}.dashboard-calendar,.data-table-card{border-radius:12px}.calendar-toolbar{align-items:stretch}.calendar-legend{width:100%}}@media(prefers-reduced-motion:reduce){.countdown-item,.records-table tbody tr{transition:none}}
@media(max-width:700px){.filter-builder{max-height:min(56dvh,430px)}.filter-condition{grid-template-columns:24px minmax(0,1fr) 30px;align-items:start}.filter-condition-index{grid-column:1;grid-row:1}.filter-condition>select:first-of-type{grid-column:2;grid-row:1}.filter-condition>select:not(:first-of-type),.filter-condition>input,.filter-range-label,.filter-date-range{grid-column:2}.filter-condition-remove{grid-column:3;grid-row:1}.filter-date-range{grid-template-columns:1fr;gap:5px}.filter-date-range span{text-align:center}.filter-builder-footer{position:sticky;bottom:0}}

/* Filter builder: one stable information hierarchy, themed materials. */
.progress-filter-menu{width:min(570px,calc(100vw - 28px));overflow:hidden}.filter-builder{gap:10px;max-height:min(58dvh,500px);padding:14px}.filter-condition{display:block;padding:0;overflow:hidden;border:1px solid var(--line2);border-radius:12px;background:var(--panel);box-shadow:0 5px 16px color-mix(in srgb,var(--ink) 5%,transparent)}.filter-condition-head{display:flex;align-items:center;justify-content:space-between;min-height:34px;padding:0 11px;border-bottom:1px solid var(--line);color:var(--muted);background:color-mix(in srgb,var(--bg) 70%,var(--panel));font:800 9px/1 var(--mono);letter-spacing:.08em}.filter-condition-remove{display:inline-flex;width:auto;height:24px;padding:0 4px;border:0;border-radius:0;color:var(--muted);background:transparent;font:700 10px/1 var(--font)}.filter-condition-remove:hover{border:0;color:var(--red);background:transparent}.filter-condition-fields{display:grid;grid-template-columns:minmax(120px,.8fr) minmax(94px,.6fr) minmax(210px,1.5fr);gap:10px;padding:11px}.filter-field{display:grid;min-width:0;gap:6px}.filter-field>span{color:var(--muted);font:700 9px/1 var(--font);letter-spacing:.04em}.filter-field>strong{display:flex;align-items:center;height:34px;color:var(--sub);font:700 11px var(--font)}.filter-condition .filter-field :is(select,input){height:34px;border-radius:7px}.filter-date-range{grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:7px}.filter-date-range i{align-self:center;color:var(--muted);font:400 10px var(--font);font-style:normal}.filter-add-condition{width:100%;height:34px;justify-self:stretch;border:1px dashed var(--line2);border-radius:9px;color:var(--sub);background:transparent;font-weight:700}.filter-add-condition:hover{color:var(--blue);border-color:var(--blue);background:var(--blueS)}.filter-builder-footer{padding:11px 14px}.filter-builder-footer .btn{min-width:88px}

:global([data-style="pixelium"]) .progress-filter-menu{border:2px solid var(--ink);border-radius:2px;box-shadow:6px 6px 0 var(--ink)}:global([data-style="pixelium"]) .filter-condition{border:2px solid var(--ink);border-radius:1px;box-shadow:3px 3px 0 var(--ink)}:global([data-style="pixelium"]) .filter-condition-head{border-bottom:2px solid var(--ink);background:var(--bg)}:global([data-style="pixelium"]) .filter-add-condition{border:2px dashed var(--ink);border-radius:1px}:global([data-style="pixelium"]) .filter-condition .filter-field :is(select,input){border:2px solid var(--ink);border-radius:1px;box-shadow:none}
:global([data-style="aurora"]) .progress-filter-menu{border:1px solid rgba(255,255,255,.58);border-radius:20px;background:color-mix(in srgb,var(--panel) 82%,transparent);box-shadow:0 26px 70px rgba(50,42,116,.24),inset 0 1px rgba(255,255,255,.7);backdrop-filter:blur(28px) saturate(160%)}:global([data-style="aurora"]) .filter-builder{background:transparent}:global([data-style="aurora"]) .filter-condition{border-color:rgba(255,255,255,.44);border-radius:14px;background:rgba(255,255,255,.1);box-shadow:inset 0 1px rgba(255,255,255,.36),0 8px 24px rgba(55,48,120,.08)}:global([data-style="aurora"]) .filter-condition-head{border-color:rgba(255,255,255,.25);background:rgba(255,255,255,.08)}:global([data-style="aurora"]) .filter-add-condition{border-color:rgba(117,89,255,.36);border-radius:12px;background:rgba(255,255,255,.06)}
:global([data-style="anime"]) .progress-filter-menu{border:3px solid var(--ink);border-radius:10px 16px 10px 16px;background:var(--panel);box-shadow:7px 7px 0 var(--ink)}:global([data-style="anime"]) .filter-condition{border:2px solid var(--ink);border-radius:7px 11px 7px 11px;background:var(--panel);box-shadow:3px 3px 0 var(--ink)}:global([data-style="anime"]) .filter-condition:nth-child(even){transform:rotate(-.2deg)}:global([data-style="anime"]) .filter-condition-head{border-bottom:2px solid var(--ink);background:var(--redS)}:global([data-style="anime"]) .filter-add-condition{border:2px dashed var(--ink);border-radius:7px 10px;background:var(--amberS)}
:global([data-style="journal"]) .progress-filter-menu{border:1px solid var(--line2);border-radius:3px 10px 10px 3px;background:var(--panel);box-shadow:5px 7px 0 rgba(40,58,50,.12)}:global([data-style="journal"]) .filter-builder{background-image:repeating-linear-gradient(to bottom,transparent 0 27px,color-mix(in srgb,var(--line) 35%,transparent) 28px)}:global([data-style="journal"]) .filter-condition{border:1px solid var(--line2);border-radius:2px;background:color-mix(in srgb,var(--panel) 94%,#fff);box-shadow:2px 3px 0 rgba(40,58,50,.09)}:global([data-style="journal"]) .filter-condition-head{border-left:4px solid var(--green);background:transparent}:global([data-style="journal"]) .filter-add-condition{border-radius:2px;border-color:var(--green);color:var(--green);background:var(--panel)}
:global([data-style="cyber"]) .progress-filter-menu{border:4px solid #111923;border-radius:0;color:#111923;background:#e9ecd9;box-shadow:9px 9px 0 #00d9f5,-5px -5px 0 #ff2a5f;clip-path:polygon(0 0,calc(100% - 18px) 0,100% 18px,100% 100%,12px 100%,0 calc(100% - 12px))}:global([data-style="cyber"]) .filter-builder{background:#e9ecd9}:global([data-style="cyber"]) .filter-condition{border:2px solid #111923;border-radius:0;background:#f1f0db;box-shadow:inset 5px 0 #00d9f5,4px 4px 0 rgba(17,25,35,.22)}:global([data-style="cyber"]) .filter-condition-head{border-color:#111923;color:#f5f5df;background:#172c35}:global([data-style="cyber"]) .filter-condition .filter-field :is(select,input){border:2px solid #111923;border-radius:0;color:#111923;background:#f8f7dc;box-shadow:inset 5px 0 #00d9f5}:global([data-style="cyber"]) .filter-add-condition{border:2px dashed #111923;border-radius:0;color:#111923;background:#f8e71c;box-shadow:4px 4px 0 #ff2a5f}
:global([data-style="shuimo"]) .progress-filter-menu{border:1px solid rgba(25,26,23,.62);border-radius:1px;background:rgba(243,242,237,.97);box-shadow:10px 14px 28px rgba(25,26,23,.16)}:global([data-style="shuimo"]) .filter-builder{background:transparent}:global([data-style="shuimo"]) .filter-condition{border:0;border-bottom:1px solid rgba(25,26,23,.38);border-radius:0;background:transparent;box-shadow:none}:global([data-style="shuimo"]) .filter-condition-head{border:0;border-left:3px solid #a63830;background:transparent}:global([data-style="shuimo"]) .filter-condition .filter-field :is(select,input){border-width:0 0 1px;border-color:rgba(25,26,23,.48);border-radius:0;background:transparent;box-shadow:none}:global([data-style="shuimo"]) .filter-add-condition{border:0;border-bottom:1px solid rgba(25,26,23,.5);border-radius:0;color:#555952;background:transparent}

@media(max-width:700px){.filter-condition-fields{grid-template-columns:1fr 1fr}.filter-field-value{grid-column:1/-1}.filter-date-range{grid-template-columns:1fr auto 1fr}}@media(max-width:430px){.filter-condition-fields{grid-template-columns:1fr}.filter-field-value{grid-column:auto}.filter-date-range{grid-template-columns:1fr}.filter-date-range i{text-align:center}}
</style>
