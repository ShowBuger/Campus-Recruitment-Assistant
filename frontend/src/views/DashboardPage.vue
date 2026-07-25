<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import ProgressBadge from '@/components/ProgressBadge.vue'

const store = useDashboardStore()
const auth = useAuthStore()

const showFilter = ref(false)
const progressOptions = ['已投递', '机考', '面试', 'OC', '已挂', '放弃']
const activeFilter = ref([])

const filteredRecords = computed(() =>
  activeFilter.value.length
    ? store.recentRecords.filter(r => activeFilter.value.includes((r.progress || [])[0]))
    : store.recentRecords
)

function applyFilter() {
  showFilter.value = false
}

const upcomingDeadlines = computed(() =>
  store.deadlines
    .filter(d => d.deadline)
    .sort((a, b) => a.deadline - b.deadline)
    .slice(0, 8)
)

function formatDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return isNaN(d) ? '—' : (d.getMonth() + 1) + '/' + d.getDate()
}

function deadlineDays(item) {
  if (!item.deadline) return null
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const dl = new Date(item.deadline)
  return Math.ceil((dl - today) / 86400000)
}

function formatDeadlineText(days) {
  if (days === null || days === undefined) return '—'
  if (days <= 0) return '今日'
  if (days === 1) return '明天'
  return '剩 ' + days + ' 天'
}

/* ── Calendar ────────────────────────────────────────── */
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

function getDateStr(day) {
  return `${year.value}-${String(month.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function hasEvents(day) {
  if (!day) return false
  return events.value.some(e => e.date === getDateStr(day))
}

function getEvents(day) {
  return events.value.filter(e => e.date === getDateStr(day))
}

function eventDotClass(e) {
  const label = e.label || ''
  if (/投递|申请|apply/i.test(label)) return 'g'
  if (/机考|笔试|exam/i.test(label)) return 'a'
  if (/截止|deadline|ddl/i.test(label)) return 'r'
  if (/结果|offer|oc|录用|通过/i.test(label)) return 'c'
  return ''
}

const upcomingEvents = computed(() =>
  [...events.value]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 8)
)

const dateEvents = computed(() =>
  events.value.filter(e => e.date === selectedDate.value)
)

function selectDate(day) {
  selectedDate.value = getDateStr(day)
}

function prevMonth() {
  if (month.value === 0) { month.value = 11; year.value-- }
  else month.value--
}

function nextMonth() {
  if (month.value === 11) { month.value = 0; year.value++ }
  else month.value++
}

function goToday() {
  const now = new Date()
  year.value = now.getFullYear()
  month.value = now.getMonth()
  selectedDate.value = getDateStr(now.getDate())
}

async function loadEvents() {
  try {
    const r = await fetch('/api/dashboard/calendar/local-events', {
      headers: { Authorization: `Bearer ${auth.token}` }
    })
    events.value = (await r.json()).events || []
  } catch { events.value = [] }
}

async function addEvent() {
  if (!newLabel.value.trim() || !selectedDate.value) return
  try {
    await fetch('/api/dashboard/calendar/local-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ date: selectedDate.value, label: newLabel.value.trim() })
    })
    newLabel.value = ''
    await loadEvents()
  } catch {}
}

async function deleteEvent(id) {
  try {
    await fetch(`/api/dashboard/calendar/local-event/${id}/delete`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` }
    })
    await loadEvents()
  } catch {}
}

function openAddEvent() {
  if (!selectedDate.value) goToday()
}

onMounted(() => {
  store.fetch()
  loadEvents()
})
</script>

<template>
  <div class="page active">
    <!-- KPI Cards Row -->
    <div class="kpis">
      <div class="kpi b">
        <div class="kpi-label">投递岗位</div>
        <div class="kpi-value">{{ store.kpi.total_companies }}</div>
        <div class="kpi-sub">已进入投递流程</div>
      </div>
      <div class="kpi a">
        <div class="kpi-label">笔试 / 机考</div>
        <div class="kpi-value">{{ store.kpi.exam_count }}</div>
        <div class="kpi-sub">有笔试或机考记录</div>
      </div>
      <div class="kpi c">
        <div class="kpi-label">面试</div>
        <div class="kpi-value">{{ store.kpi.interview_count }}</div>
        <div class="kpi-sub">进入面试流程</div>
      </div>
      <div class="kpi g">
        <div class="kpi-label">Offer</div>
        <div class="kpi-value">{{ store.kpi.offer_count }}</div>
        <div class="kpi-sub">OC 或已录用</div>
      </div>
    </div>

    <!-- Calendar Card -->
    <div class="card dashboard-calendar">
      <div class="card-hd">
        <span class="dot a"></span>
        <div class="card-title">校招日历</div>
        <div class="card-sub">日程、投递节点与截止日期</div>
      </div>
      <div class="card-body">
        <div class="calendar-toolbar" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <button class="icon-btn" style="width:36px;height:36px;font-size:20px;line-height:1" @click="prevMonth" title="上个月">&#8249;</button>
          <h2 style="min-width:142px;padding:5px 9px;border:2px solid var(--ink);background:var(--panel);box-shadow:2px 2px 0 var(--ink);font:900 14px/1.4 var(--mono,monospace);letter-spacing:.04em;text-align:center">{{ calendarTitle }}</h2>
          <button class="icon-btn" style="width:36px;height:36px;font-size:20px;line-height:1" @click="nextMonth" title="下个月">&#8250;</button>
          <button class="btn" style="min-height:34px;padding:5px 14px;font-size:12px" @click="goToday">今天</button>
          <button class="btn btn-primary" style="min-height:34px;padding:5px 14px;font-size:12px" @click="openAddEvent">新建日程</button>
          <div class="calendar-legend" style="display:flex;gap:10px;margin-left:auto;flex-wrap:wrap">
            <span class="lg-apply" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--green)"></span>投递</span>
            <span class="lg-exam" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--amber)"></span>机考/笔试</span>
            <span style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--blue)"></span>面试</span>
            <span class="lg-warm" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--muted)"></span>保温</span>
            <span class="lg-result" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--cyan)"></span>结果</span>
            <span class="lg-deadline" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink);background:var(--red)"></span>截止</span>
            <span class="lg-other" style="display:inline-flex;align-items:center;gap:4px;padding:3px 5px;border:1px solid var(--line2);border-radius:1px;background:var(--panel);font-size:9px"><span style="width:7px;height:7px;border:1px solid var(--ink)"></span>其他</span>
          </div>
        </div>

        <div class="calendar-layout" style="display:flex;gap:16px;align-items:stretch">
          <div class="calendar-scroll" style="flex:1;min-width:0">
            <div class="calendar-grid">
              <div v-for="d in '日一二三四五六'.split('')" :key="d" class="calendar-weekday" style="text-align:center;padding:8px 5px;border-bottom:2px solid var(--ink);color:var(--ink);background:var(--bg);font:900 10px var(--mono,monospace);letter-spacing:.1em">{{ d }}</div>
              <div v-for="i in firstDayOffset" :key="'e'+i" class="calendar-day other"></div>
              <div v-for="day in daysInMonth" :key="day" class="calendar-day" :class="{ today: isToday(day) }" @click="selectDate(day)">
                <span class="calendar-date">{{ day }}</span>
                <div class="calendar-dots" v-if="hasEvents(day)" style="display:flex;flex-wrap:wrap;gap:2px;margin-top:3px">
                  <span v-for="e in getEvents(day)" :key="e.id" class="dot" :class="eventDotClass(e)" style="width:7px;height:7px;border:1px solid var(--ink);border-radius:0"></span>
                </div>
              </div>
            </div>
          </div>

          <aside class="countdown-panel" style="width:280px;flex-shrink:0;display:flex;flex-direction:column">
            <h3 style="padding:10px 14px;font-size:13px;border-bottom:2px solid var(--ink);background:var(--bg);letter-spacing:.05em;flex-shrink:0">近期安排</h3>
            <div class="countdown-list" style="flex:1;max-height:320px;overflow:auto">
              <div v-if="!upcomingEvents.length" class="center" style="padding:24px 14px;color:var(--sub);font-size:11px">暂无安排</div>
              <div v-for="e in upcomingEvents" :key="e.id" class="countdown-item" style="padding:10px 14px;border-bottom:1px dashed var(--line2)">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
                  <b style="font-size:12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ e.label }}</b>
                  <button class="icon-btn" style="flex-shrink:0;width:22px;height:22px;font-size:10px;line-height:1;border-width:1px;padding:0" @click="deleteEvent(e.id)" title="删除">&times;</button>
                </div>
                <span style="font-size:10px;color:var(--muted);margin-top:3px;display:block">{{ e.date }}</span>
              </div>
            </div>
            <div v-if="selectedDate" style="border-top:2px solid var(--ink);padding:10px 14px;flex-shrink:0;background:var(--bg)">
              <div style="font-size:11px;font-weight:800;margin-bottom:6px;color:var(--blue);letter-spacing:.02em">{{ selectedDate }}</div>
              <div v-for="e in dateEvents" :key="e.id" style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:11px;border-bottom:1px dashed var(--line2)">
                <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ e.label }}</span>
                <button class="icon-btn" style="flex-shrink:0;width:20px;height:20px;font-size:9px;line-height:1;border-width:1px;padding:0" @click="deleteEvent(e.id)" title="删除">&times;</button>
              </div>
              <div style="display:flex;gap:4px;margin-top:6px">
                <input v-model="newLabel" placeholder="添加日程" style="flex:1;height:30px;font-size:11px;border:2px solid var(--line2);border-radius:2px;padding:0 8px;background:var(--panel);color:var(--ink);min-width:0" @keydown.enter="addEvent" maxlength="100">
                <button class="btn btn-primary" style="height:30px;padding:0 10px;font-size:11px;min-height:30px" @click="addEvent">添加</button>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>

    <!-- Main content: table + deadlines sidebar -->
    <div style="display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start;margin-bottom:22px">

      <!-- Records Table Card -->
      <div class="card data-table-card">
        <div class="card-hd record-card-hd">
          <span class="dot"></span>
          <div class="card-title">投递记录</div>
          <div class="record-hd-spacer"></div>

          <!-- Progress Filter -->
          <div class="progress-filter" :class="{ active: showFilter }">
            <button
              class="progress-filter-toggle"
              :class="{ 'has-filter': activeFilter.length > 0 }"
              @click="showFilter = !showFilter"
              aria-haspopup="dialog"
              :aria-expanded="showFilter"
            >
              <span>{{ activeFilter.length ? activeFilter.length + ' 个状态' : '筛选进展' }}</span>
            </button>
            <div class="progress-filter-backdrop" @click="showFilter = false" v-if="showFilter"></div>
            <div class="progress-filter-menu" v-if="showFilter" role="dialog" aria-modal="true" aria-labelledby="progress-filter-dialog-title">
              <div class="progress-filter-menu-hd">
                <div>
                  <b id="progress-filter-dialog-title">筛选投递进展</b>
                  <span>选择一个或多个状态</span>
                </div>
                <div class="progress-filter-dialog-actions">
                  <button type="button" class="progress-filter-clear" :disabled="activeFilter.length === 0" @click="activeFilter = []; showFilter = false">重置</button>
                  <button type="button" class="progress-filter-close" @click="showFilter = false" aria-label="关闭筛选">&times;</button>
                </div>
              </div>
              <div class="progress-filter-selected" v-if="activeFilter.length">
                <span v-for="p in activeFilter" :key="p" class="progress-filter-chip">
                  <span>{{ p }}</span>
                  <button @click="activeFilter = activeFilter.filter(x => x !== p)" aria-label="移除筛选">&times;</button>
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

        <!-- Table -->
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
      </div>

      <!-- Deadlines Sidebar -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">即将截止</div></div>
        <div class="countdown-list" style="max-height:440px;overflow:auto">
          <div v-if="!upcomingDeadlines.length" class="center" style="padding:18px">暂无临近截止</div>
          <div v-for="d in upcomingDeadlines" :key="d.company + d.job" class="countdown-item">
            <div>
              <b>{{ d.company }}</b>
              <span>{{ d.job || '' }}</span>
            </div>
            <div class="countdown-days" :class="{ urgent: deadlineDays(d) <= 3 }">
              {{ formatDeadlineText(deadlineDays(d)) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
