<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import ProgressBadge from '@/components/ProgressBadge.vue'

const store = useDashboardStore()
const showFilter = ref(false)
const progressOptions = ['已投递', '机考', '面试', 'OC', '已挂', '放弃']
const activeFilter = ref([])

// Only show records that have been submitted (have apply_date)
const applicationRecords = computed(() =>
  store.records.filter(r => r.apply_date)
)

const filteredRecords = computed(() =>
  activeFilter.value.length
    ? applicationRecords.value.filter(r => activeFilter.value.includes((r.progress || [])[0]))
    : applicationRecords.value
)

function applyFilter() { showFilter.value = false }

function formatDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return isNaN(d) ? '—' : (d.getMonth() + 1) + '/' + d.getDate()
}

// Calendar
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth())
const events = ref([])
const selectedDate = ref('')
const newLabel = ref('')

const calendarTitle = computed(() => `${year.value}年${month.value + 1}月`)
const daysInMonth = computed(() => new Date(year.value, month.value + 1, 0).getDate())
const firstDayOffset = computed(() => new Date(year.value, month.value, 1).getDay())

function isToday(day) {
  const now = new Date()
  return year.value === now.getFullYear() && month.value === now.getMonth() && day === now.getDate()
}
function getDateStr(day) { return `${year.value}-${String(month.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}` }
function hasEvents(day) { return day && events.value.some(e => e.date === getDateStr(day)) }
function getEvents(day) { return events.value.filter(e => e.date === getDateStr(day)) }
function selectDate(day) { selectedDate.value = getDateStr(day) }
function prevMonth() { if (month.value === 0) { month.value = 11; year.value-- } else month.value-- }
function nextMonth() { if (month.value === 11) { month.value = 0; year.value++ } else month.value++ }
function goToday() {
  const now = new Date()
  year.value = now.getFullYear(); month.value = now.getMonth()
  selectedDate.value = getDateStr(now.getDate())
}
function eventDotClass(e) {
  const label = (e.label || '').toLowerCase()
  if (/投递|apply/.test(label)) return 'g'
  if (/机考|笔试|exam|测评/.test(label)) return 'a'
  if (/截止|deadline|ddl/.test(label)) return 'r'
  if (/结果|offer|oc|录用|通过/.test(label)) return 'c'
  return ''
}

const upcomingEvents = computed(() => [...events.value].sort((a, b) => a.date.localeCompare(b.date)).slice(0, 8))
const dateEvents = computed(() => events.value.filter(e => e.date === selectedDate.value))

async function loadEvents() {
  try {
    const r = await fetch('/api/dashboard/calendar/local-events', { headers: { Authorization: `Bearer ${localStorage.getItem('rb_token')}` } })
    events.value = (await r.json()).events || []
  } catch { events.value = [] }
}
async function addEvent() {
  if (!newLabel.value.trim() || !selectedDate.value) return
  try {
    await fetch('/api/dashboard/calendar/local-event', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
      body: JSON.stringify({ date: selectedDate.value, label: newLabel.value.trim() })
    })
    newLabel.value = ''
    await loadEvents()
  } catch {}
}
async function deleteEvent(id) {
  try {
    await fetch(`/api/dashboard/calendar/local-event/${id}/delete`, {
      method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('rb_token')}` }
    })
    await loadEvents()
  } catch {}
}
function openAddEvent() { if (!selectedDate.value) goToday() }

onMounted(() => { store.fetch(); loadEvents() })
</script>

<template>
  <div class="page active">
    <!-- KPI Cards -->
    <div class="kpis">
      <div class="kpi b"><div class="kpi-label">投递岗位</div><div class="kpi-value">{{ store.kpi.total_companies }}</div><div class="kpi-sub">已进入投递流程</div></div>
      <div class="kpi a"><div class="kpi-label">笔试 / 机考</div><div class="kpi-value">{{ store.kpi.exam_count }}</div><div class="kpi-sub">有笔试或机考记录</div></div>
      <div class="kpi c"><div class="kpi-label">面试</div><div class="kpi-value">{{ store.kpi.interview_count }}</div><div class="kpi-sub">进入面试流程</div></div>
      <div class="kpi g"><div class="kpi-label">Offer</div><div class="kpi-value">{{ store.kpi.offer_count }}</div><div class="kpi-sub">OC 或已录用</div></div>
    </div>

    <!-- Calendar Card -->
    <div class="card dashboard-calendar">
      <div class="card-hd"><span class="dot a"></span><div class="card-title">校招日历</div><div class="card-sub">日程、投递节点与截止日期</div></div>
      <div class="card-body">
        <div class="calendar-toolbar">
          <button class="icon-btn" @click="prevMonth" title="上个月">&#8249;</button>
          <h2>{{ calendarTitle }}</h2>
          <button class="icon-btn" @click="nextMonth" title="下个月">&#8250;</button>
          <button class="btn" @click="goToday">今天</button>
          <button class="btn btn-primary" @click="openAddEvent">新建日程</button>
          <div class="calendar-legend">
            <span class="lg-apply">投递</span><span class="lg-exam">机考/笔试</span><span>面试</span><span class="lg-warm">保温</span><span class="lg-result">结果</span><span class="lg-deadline">截止</span><span class="lg-other">其他</span>
          </div>
        </div>
        <div class="calendar-layout">
          <div class="calendar-scroll">
            <div class="calendar-grid">
              <div v-for="d in '日一二三四五六'.split('')" :key="d" class="calendar-weekday">{{ d }}</div>
              <div v-for="i in firstDayOffset" :key="'e'+i" class="calendar-day other"></div>
              <div v-for="day in daysInMonth" :key="day" class="calendar-day" :class="{ today: isToday(day) }" @click="selectDate(day)">
                <span class="calendar-date">{{ day }}</span>
                <div class="calendar-dots" v-if="hasEvents(day)">
                  <span v-for="e in getEvents(day)" :key="e.id" class="dot" :class="eventDotClass(e)"></span>
                </div>
              </div>
            </div>
          </div>
          <aside class="countdown-panel">
            <h3>近期安排</h3>
            <div class="countdown-list">
              <div v-if="!upcomingEvents.length" class="center">暂无安排</div>
              <div v-for="e in upcomingEvents" :key="e.id" class="countdown-item">
                <b>{{ e.label }}</b><span>{{ e.date }}</span>
                <button class="icon-btn" @click="deleteEvent(e.id)" title="删除">&times;</button>
              </div>
            </div>
            <div v-if="selectedDate" class="calendar-event-form">
              <b>{{ selectedDate }}</b>
              <div v-for="e in dateEvents" :key="e.id" class="calendar-event-row">
                <span>{{ e.label }}</span>
                <button class="icon-btn" @click="deleteEvent(e.id)">&times;</button>
              </div>
              <div class="calendar-event-input">
                <input v-model="newLabel" placeholder="添加日程" @keydown.enter="addEvent" maxlength="100">
                <button class="btn btn-primary" @click="addEvent">添加</button>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>

    <!-- Records Table Card -->
    <div class="card data-table-card">
      <div class="card-hd record-card-hd">
        <span class="dot"></span>
        <div class="card-title">投递记录</div>
        <div class="record-hd-spacer"></div>
        <div class="progress-filter" :class="{ active: showFilter }">
          <button class="progress-filter-toggle" :class="{ 'has-filter': activeFilter.length > 0 }" @click="showFilter = !showFilter" aria-haspopup="dialog" :aria-expanded="showFilter">
            <span>{{ activeFilter.length ? activeFilter.length + ' 个状态' : '筛选进展' }}</span>
          </button>
          <div class="progress-filter-backdrop" @click="showFilter = false" v-if="showFilter"></div>
          <div class="progress-filter-menu" v-if="showFilter" role="dialog" aria-modal="true">
            <div class="progress-filter-menu-hd">
              <div><b>筛选投递进展</b><span>选择一个或多个状态</span></div>
              <div class="progress-filter-dialog-actions">
                <button type="button" class="progress-filter-clear" :disabled="activeFilter.length === 0" @click="activeFilter = []; showFilter = false">重置</button>
                <button type="button" class="progress-filter-close" @click="showFilter = false">&times;</button>
              </div>
            </div>
            <div class="progress-filter-selected" v-if="activeFilter.length">
              <span v-for="p in activeFilter" :key="p" class="progress-filter-chip">
                <span>{{ p }}</span>
                <button @click="activeFilter = activeFilter.filter(x => x !== p)">&times;</button>
              </span>
            </div>
            <div class="progress-filter-options">
              <label v-for="p in progressOptions" :key="p" class="progress-filter-option" :class="{ selected: activeFilter.includes(p) }">
                <input type="checkbox" :value="p" v-model="activeFilter" @change="applyFilter">
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
            <tr v-for="r in filteredRecords.slice(0, 40)" :key="r.record_id">
              <td><button class="company-link">{{ r.company || '—' }}</button></td>
              <td>{{ r.job || '—' }}</td>
              <td>{{ r.city || '—' }}</td>
              <td>{{ r.batch || '—' }}</td>
              <td><span class="table-date">{{ formatDate(r.apply_date) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.exam_date) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.interview1) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.interview2) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.interview3) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.warm) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.result) }}</span></td>
              <td><span class="table-date">{{ formatDate(r.deadline) }}</span></td>
              <td><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td><a v-if="r.url" :href="r.url" target="_blank" class="btn">入口</a></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="table-actions">
        <button class="btn" @click="store.fetch()">刷新数据</button>
      </div>
    </div>
  </div>
</template>
