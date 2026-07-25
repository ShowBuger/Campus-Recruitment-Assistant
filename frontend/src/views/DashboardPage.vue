<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import ProgressBadge from '@/components/ProgressBadge.vue'
import TooltipCell from '@/components/TooltipCell.vue'

const store = useDashboardStore()
const app = useAppStore()
const showFilter = ref(false)
const activeFilter = ref([])
const draftFilter = ref(null)  // null = not editing; array = editing
const progressOptions = ['已投递', '机考', '面试', 'OC', '已挂', '放弃']

// ---- calendar event modal ----
const showEventModal = ref(false)
const calEventDate = ref('')
const calEventType = ref('apply')
const calEventLabel = ref('')
const calEventRecord = ref('')

// ---- application records (original: _lastData.main.recent) ----
const records = computed(() => store.data?.main?.recent || [])

// Table always uses committed filter (activeFilter), NOT draft
const filteredRecords = computed(() =>
  activeFilter.value.length
    ? records.value.filter(r => activeFilter.value.includes((r.progress || [])[0]))
    : records.value
)

// Preview: what the result WOULD be if draft were applied
const draftFilteredCount = computed(() => {
  const f = draftFilter.value
  if (!f || !f.length) return records.value.length
  return records.value.filter(r => f.includes((r.progress || [])[0])).length
})

const filterSummary = computed(() => {
  if (!showFilter.value) return ''
  const f = draftFilter.value
  if (!f || !f.length) return '选择状态，退出后应用'
  return `退出后应用 · ${draftFilteredCount.value} / ${records.value.length} 条`
})

function openFilter() {
  draftFilter.value = [...activeFilter.value]
  showFilter.value = true
}
function applyFilter() {
  if (draftFilter.value !== null) activeFilter.value = [...draftFilter.value]
  draftFilter.value = null
  showFilter.value = false
}
function clearFilter() {
  draftFilter.value = []
}

function formatDate(ts) { if (!ts) return '—'; const d = new Date(ts); return isNaN(d) ? '—' : String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }
function formatDateFull(ts) { if (!ts) return ''; const d = new Date(ts); return isNaN(d) ? '' : d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }

// ---- Calendar (exact replica of original renderCalendar) ----
const calendarMonth = ref(new Date())
const localEvents = ref([])
const DAY = 86400000

function calendarKey(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }

function calendarDate(ts) { if (!ts) return null; const d = new Date(ts); return isNaN(d) ? null : new Date(d.getFullYear(), d.getMonth(), d.getDate()) }

function calendarEvents() {
  const groups = {}
  function add(ts, type, label, r, extra) {
    const date = calendarDate(ts); if (!date) return
    const key = calendarKey(date)
    if (!groups[key]) groups[key] = []
    groups[key].push({ date, type, label, company: r.company || '—', job: r.job || '', ...(extra || {}) })
  }
  records.value.forEach(r => {
    add(r.apply_date, 'apply', '投递', r, { rid: r.record_id, etype: 'apply' })
    add(r.exam_date, 'exam', '机考/笔试', r, { rid: r.record_id, etype: 'exam' })
    add(r.interview1, 'interview', '一面', r, { rid: r.record_id, etype: 'interview1' })
    add(r.interview2, 'interview', '二面', r, { rid: r.record_id, etype: 'interview2' })
    add(r.interview3, 'interview', '三面', r, { rid: r.record_id, etype: 'interview3' })
    add(r.warm, 'warm', '保温', r, { rid: r.record_id, etype: 'warm' })
    add(r.result, 'result', '结果', r, { rid: r.record_id, etype: 'result' })
    add(r.deadline, 'deadline', '截止', r, { rid: r.record_id, etype: 'deadline' })
  })
  localEvents.value.forEach(e => { add(e.date, 'other', e.label, { company: '我的日程', job: '' }, { lid: e.id }) })
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
      if (days >= 0) upcoming.push({ item, days, key })
    })
  })
  upcoming.sort((a, b) => a.item.date - b.item.date || a.item.company.localeCompare(b.item.company))
  return upcoming.slice(0, 30)
})

function changeMonth(delta) { const d = new Date(calendarMonth.value); d.setMonth(d.getMonth() + delta); calendarMonth.value = d }
function goToday() { calendarMonth.value = new Date() }

function inputDate(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') }

function openCalendarEventModal(dateStr) {
  calEventDate.value = dateStr || inputDate(new Date())
  calEventType.value = 'apply'
  calEventLabel.value = ''
  calEventRecord.value = ''
  showEventModal.value = true
}

async function submitCalendarEvent() {
  if (!calEventDate.value) return
  if (calEventType.value === 'other') {
    if (!calEventLabel.value.trim()) return
    try {
      await fetch('/api/dashboard/calendar/local-event', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
        body: JSON.stringify({ date: calEventDate.value, label: calEventLabel.value.trim() })
      })
      await loadLocalEvents()
      showEventModal.value = false
    } catch {}
    return
  }
  if (!calEventRecord.value) return
  try {
    await fetch('/api/dashboard/calendar/event', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
      body: JSON.stringify({ record_id: calEventRecord.value, event_type: calEventType.value, date: calEventDate.value })
    })
    await store.fetch()
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
  if (!confirm('确定删除这个日程？')) return
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
  if (!confirm('确定删除这个日程？')) return
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

onMounted(() => { store.fetch(); loadLocalEvents(); store.startPolling(); document.addEventListener('keydown', onKeydown) })
onUnmounted(() => { store.stopPolling(); document.removeEventListener('keydown', onKeydown) })
</script>

<template>
  <div class="page active">
    <!-- KPI Cards (exact original structure) -->
    <div class="kpis">
      <div class="kpi b"><div class="kpi-label">投递岗位</div><div class="kpi-value">{{ store.kpi.total_companies }}</div><div class="kpi-sub">已进入投递流程</div></div>
      <div class="kpi a"><div class="kpi-label">笔试 / 机考</div><div class="kpi-value">{{ store.kpi.exam_count }}</div><div class="kpi-sub">有笔试或机考记录</div></div>
      <div class="kpi c"><div class="kpi-label">面试</div><div class="kpi-value">{{ store.kpi.interview_count }}</div><div class="kpi-sub">进入面试流程</div></div>
      <div class="kpi g"><div class="kpi-label">Offer</div><div class="kpi-value">{{ store.kpi.offer_count }}</div><div class="kpi-sub">OC 或已录用</div></div>
    </div>

    <!-- Calendar Card (exact original structure) -->
    <div class="card dashboard-calendar">
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
                  <div v-for="e in day.visible" :key="e.rid || e.lid || e.label" class="calendar-event" :class="e.type" :title="e.label + ' · ' + e.company + (e.job ? ' · ' + e.job : '')" @click.stop="deleteEvent(e.rid || e.lid, e.etype)">
                    {{ e.label }} · {{ e.company }}
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
                  <b>{{ x.item.company }} · {{ x.item.label }}</b>
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
    <div class="card data-table-card">
      <div class="card-hd record-card-hd">
        <span class="dot"></span>
        <div class="card-title">投递记录</div>
        <div class="record-hd-spacer"></div>
        <div class="progress-filter" :class="{ active: showFilter }">
          <button class="progress-filter-toggle" :class="{ 'has-filter': activeFilter.length > 0 }" @click="showFilter ? applyFilter() : openFilter()" aria-haspopup="dialog" :aria-expanded="showFilter">
            <span>{{ activeFilter.length ? activeFilter.length + ' 个状态' : '筛选进展' }}</span>
          </button>
          <div class="progress-filter-backdrop" @click="applyFilter" v-if="showFilter"></div>
          <div class="progress-filter-menu" v-if="showFilter" role="dialog" aria-modal="true">
            <div class="progress-filter-menu-hd">
              <div><b>筛选投递进展</b><span>{{ filterSummary }}</span></div>
              <div class="progress-filter-dialog-actions">
                <button type="button" class="progress-filter-clear" :disabled="!draftFilter || !draftFilter.length" @click="clearFilter">重置</button>
                <button type="button" class="progress-filter-close" @click="applyFilter" aria-label="关闭筛选">&times;</button>
              </div>
            </div>
            <div class="progress-filter-selected" :class="{ show: draftFilter && draftFilter.length }" v-if="draftFilter && draftFilter.length">
              <span v-for="p in draftFilter" :key="p" class="progress-filter-chip">{{ p }}<button @click="draftFilter = draftFilter.filter(x => x !== p)" :aria-label="'移除 '+p">&times;</button></span>
            </div>
            <div class="progress-filter-options">
              <label v-for="p in progressOptions" :key="p" class="progress-filter-option" :class="{ selected: draftFilter && draftFilter.includes(p) }">
                <input type="checkbox" :value="p" :checked="draftFilter && draftFilter.includes(p)" @change="($event.target.checked ? draftFilter.push(p) : draftFilter = draftFilter.filter(x => x !== p))">
                <ProgressBadge :progress="p" />
              </label>
            </div>
          </div>
        </div>
        <div class="card-sub">{{ filteredRecords.length }} 条</div>
      </div>

      <div class="tbl" style="max-height:440px">
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
              <td class="company"><button class="company-link" @click="app.openDetail(r.record_id)">{{ r.company || '—' }}</button></td>
              <td class="job"><TooltipCell :text="r.job || '—'" /></td>
              <td><TooltipCell :text="r.city || '—'" /></td>
              <td><span class="badge bdg-b">{{ r.batch || '—' }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.apply_date)">{{ formatDate(r.apply_date) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.exam_date)">{{ formatDate(r.exam_date) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.interview1)">{{ formatDate(r.interview1) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.interview2)">{{ formatDate(r.interview2) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.interview3)">{{ formatDate(r.interview3) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.warm)">{{ formatDate(r.warm) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.result)">{{ formatDate(r.result) }}</span></td>
              <td><span class="table-date" :title="formatDateFull(r.deadline)">{{ formatDate(r.deadline) }}</span></td>
              <td><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td><a v-if="r.url" :href="r.url" target="_blank" rel="noreferrer">查看</a><span v-else class="table-date">—</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="table-actions">
        <button class="btn btn-primary" @click="app.openRecord()">新增记录</button>
        <button class="btn" @click="app.openManager()">管理记录</button>
        <button class="btn" @click="app.openStats()">统计信息</button>
        <button class="btn" @click="app.openOffer()">Offer 对比</button>
      </div>
    </div>

    <!-- Day Detail Modal -->
    <div class="modal-mask show" v-if="dayDetailKey" @click.self="closeDayDetail">
      <div class="modal" style="width:min(520px,94vw)">
        <div class="modal-hd"><div><h2>{{ dayDetailKey }}</h2><p>{{ dayDetailItems.length }} 个日程</p></div><button class="icon-btn" @click="closeDayDetail" title="关闭">&times;</button></div>
        <div class="modal-body">
          <div v-if="!dayDetailItems.length" class="center">该日暂无日程</div>
          <div v-for="e in dayDetailItems" :key="e.rid || e.lid || e.label" style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)">
            <div>
              <b>{{ e.label }}</b>
              <div style="color:var(--muted);font-size:12px;margin-top:2px">{{ e.company }}{{ e.job ? ' · ' + e.job : '' }} · <span :class="'badge ' + eventBadgeClass(e.type)">{{ eventTypeName(e.type) }}</span></div>
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
    <div class="modal-mask show" v-if="showEventModal" @click.self="showEventModal = false">
      <div class="modal" style="width:min(520px,94vw)">
        <div class="modal-hd"><div><h2>新建日程</h2><p>{{ calEventDate || '—' }}</p></div><button class="icon-btn" @click="showEventModal = false" title="关闭">&times;</button></div>
        <div class="modal-body">
          <div class="form-group"><label for="cal-event-date">日程日期</label><input id="cal-event-date" type="date" v-model="calEventDate"></div>
          <div class="form-group"><label for="cal-event-type">事件类型</label><select id="cal-event-type" v-model="calEventType"><option value="apply">投递</option><option value="exam">机考 / 笔试</option><option value="interview1">一面</option><option value="interview2">二面</option><option value="interview3">三面</option><option value="warm">保温</option><option value="result">结果</option><option value="deadline">截止</option><option value="other">其他（自定义）</option></select></div>
          <div class="form-group" v-show="calEventType === 'other'"><label for="cal-event-label">自定义内容</label><input id="cal-event-label" v-model="calEventLabel" maxlength="200" placeholder="例如：HR 电话沟通、宣讲会、补充材料截止"></div>
          <div class="form-group" v-show="calEventType !== 'other'"><label for="cal-event-record">关联公司</label><select id="cal-event-record" v-model="calEventRecord"><option value="">请选择公司</option><option v-for="r in records" :key="r.record_id" :value="r.record_id">{{ r.company || '—' }} · {{ r.job || '—' }}</option></select></div>
          <div class="help" style="margin-top:6px" v-show="calEventType !== 'other'">选择公司后自动带入对应岗位与城市信息。</div>
        </div>
        <div class="modal-ft"><button class="btn" @click="showEventModal = false">取消</button><button class="btn btn-primary" @click="submitCalendarEvent">保存日程</button></div>
      </div>
    </div>
  </div>
</template>
