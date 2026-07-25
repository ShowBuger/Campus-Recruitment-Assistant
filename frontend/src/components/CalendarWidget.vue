<template>
  <div class="calendar-widget">
    <button class="calendar-fab" @click="show = !show" title="校招日历">
      📅
    </button>
    <div class="calendar-panel card" v-if="show" style="position:fixed;bottom:70px;right:20px;width:320px;z-index:35;max-height:500px;overflow:auto">
      <div class="card-hd"><span class="dot"></span><div class="card-title">校招日历</div></div>
      <div style="padding:8px 12px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <button class="btn" @click="prevMonth">←</button>
          <b>{{ year }}年{{ month + 1 }}月</b>
          <button class="btn" @click="nextMonth">→</button>
        </div>
        <div style="display:grid;grid-template-columns:repeat(7,1fr);text-align:center;font-size:11px;color:var(--sub)">
          <span v-for="d in '日一二三四五六'.split('')" :key="d">{{ d }}</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center">
          <div v-for="(day, i) in calendarDays" :key="i"
               :style="{
                 gridColumn: i === 0 ? (firstDayOfWeek + 1) : '',
                 padding: '6px 0', cursor: 'pointer', borderRadius: '6px',
                 background: hasEvent(day) ? 'var(--blueS)' : '',
                 fontWeight: hasEvent(day) ? 800 : 400,
                 color: day ? 'var(--ink)' : 'var(--sub)'
               }"
               @click="day && selectDate(day)">
            {{ day || '' }}
          </div>
        </div>
        <div v-if="selectedDate" style="margin-top:8px;border-top:1px solid var(--line);padding-top:8px">
          <b style="font-size:12px">{{ selectedDate }}</b>
          <div v-for="e in dateEvents" :key="e.id" style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:12px">
            <span>{{ e.label }}</span>
            <button class="btn" style="font-size:10px;padding:1px 6px" @click="deleteEvent(e.id)">×</button>
          </div>
          <div style="display:flex;gap:4px;margin-top:6px">
            <input v-model="newLabel" placeholder="添加日程" style="flex:1;height:28px;font-size:12px;border:1px solid var(--line);border-radius:6px;padding:0 8px" @keydown.enter="addEvent">
            <button class="btn btn-primary" style="font-size:11px;padding:2px 8px" @click="addEvent">添加</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const show = ref(false)
const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth())
const events = ref([])
const selectedDate = ref('')
const newLabel = ref('')

onMounted(() => loadEvents())

async function loadEvents() {
  try {
    const r = await fetch('/api/dashboard/calendar/local-events', { headers: { Authorization: `Bearer ${auth.token}` } })
    events.value = (await r.json()).events || []
  } catch { events.value = [] }
}

const firstDayOfWeek = computed(() => new Date(year.value, month.value, 1).getDay())
const daysInMonth = computed(() => new Date(year.value, month.value + 1, 0).getDate())
const calendarDays = computed(() => Array.from({ length: daysInMonth.value }, (_, i) => i + 1))

function hasEvent(day) {
  if (!day) return false
  const ds = `${year.value}-${String(month.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  return events.value.some(e => e.date === ds)
}

const dateEvents = computed(() => events.value.filter(e => e.date === selectedDate.value))

function selectDate(day) {
  selectedDate.value = `${year.value}-${String(month.value + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function prevMonth() {
  if (month.value === 0) { month.value = 11; year.value-- }
  else month.value--
}

function nextMonth() {
  if (month.value === 11) { month.value = 0; year.value++ }
  else month.value++
}

async function addEvent() {
  if (!newLabel.value.trim() || !selectedDate.value) return
  try {
    await fetch('/api/dashboard/calendar/local-event', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ date: selectedDate.value, label: newLabel.value })
    })
    newLabel.value = ''
    await loadEvents()
  } catch {}
}

async function deleteEvent(id) {
  try {
    await fetch(`/api/dashboard/calendar/local-event/${id}/delete`, { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` } })
    await loadEvents()
  } catch {}
}
</script>
