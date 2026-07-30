<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { get } from '@/utils/api'
import { calendarDateChina, fmtDateChina } from '@/utils/date'
import LoginModal from '@/components/LoginModal.vue'

const auth = useAuthStore()
const type = new URLSearchParams(window.location.search).get('desktopWidget') || 'records'
const title = type === 'schedule' ? '近期安排' : '投递记录'
const data = ref(null)
const localEvents = ref([])
const loading = ref(false)
const error = ref('')
const pinned = ref(false)
const locked = ref(false)
const selectedRecord = ref(null)
let pollTimer = null

const applicationRecords = computed(() => data.value?.main?.recent || [])
const records = computed(() => applicationRecords.value)
const eventNames = {
  exam_date: '机考 / 笔试', interview1: '一面', interview2: '二面',
  interview3: '三面', deadline: '截止', warm: '保温', result: '结果',
}

const schedules = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const items = []
  records.value.forEach(record => {
    Object.entries(eventNames).forEach(([field, label]) => {
      const date = calendarDateChina(record[field])
      if (!date) return
      const days = Math.round((date - today) / 86400000)
      if (days >= 0 && days <= 30) items.push({
        key: `${record.record_id}-${field}`,
        company: record.company || '—', job: record.job || '', label, date, days,
      })
    })
  })
  localEvents.value.forEach(event => {
    const parts = String(event.date || '').split('-').map(Number)
    if (parts.length !== 3 || parts.some(Number.isNaN)) return
    const date = new Date(parts[0], parts[1] - 1, parts[2])
    const days = Math.round((date - today) / 86400000)
    if (days >= 0 && days <= 30) items.push({
      key: `local-${event.id}`, company: '我的日程', job: '',
      label: event.label || '自定义安排', date, days,
    })
  })
  return items.sort((a, b) => a.date - b.date || a.company.localeCompare(b.company)).slice(0, 30)
})

function dateText(date) {
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
function daysText(days) {
  if (days === 0) return '今天'
  if (days === 1) return '明天'
  return `${days} 天后`
}
function progressOf(record) {
  return (Array.isArray(record.progress) ? record.progress[0] : record.progress) || '未投递'
}
function textValue(value) {
  if (Array.isArray(value)) return value.filter(Boolean).join('、')
  return String(value || '').trim()
}
function detailRows(record) {
  if (!record) return []
  return [
    ['目标岗位', textValue(record.job)],
    ['当前进展', progressOf(record)],
    ['城市', textValue(record.city)],
    ['批次', textValue(record.batch)],
    ['方向', textValue(record.dir)],
    ['公司类型', textValue(record.type)],
    ['投递时间', fmtDateChina(record.apply_date)],
    ['机考 / 笔试', fmtDateChina(record.exam_date)],
    ['一面', fmtDateChina(record.interview1)],
    ['二面', fmtDateChina(record.interview2)],
    ['三面', fmtDateChina(record.interview3)],
    ['截止时间', fmtDateChina(record.deadline)],
  ].filter(([, value]) => value && value !== '—')
}
function openRecordDetail(record) { selectedRecord.value = record }
function closeRecordDetail() { selectedRecord.value = null }
async function openRecordUrl(record) {
  const rawUrl = String(record?.url || '').trim()
  if (!rawUrl) return
  try {
    const url = new URL(rawUrl)
    if (!['http:', 'https:'].includes(url.protocol)) return
    await window.electronAPI?.openExternal?.(url.toString())
  } catch (_) {}
}

async function load() {
  if (!auth.isLoggedIn) return
  loading.value = true
  error.value = ''
  try {
    const [dashboard, events] = await Promise.all([
      get('/api/dashboard'),
      type === 'schedule' ? get('/api/dashboard/calendar/local-events').catch(() => ({ events: [] })) : Promise.resolve({ events: [] }),
    ])
    data.value = dashboard
    localEvents.value = events?.events || []
  } catch (e) {
    error.value = e?.message || '暂时无法加载数据'
  } finally {
    loading.value = false
  }
}

async function widgetAction(action) {
  const state = await window.electronAPI?.widgetAction?.(type, action)
  if (state) { pinned.value = state.pinned; locked.value = state.locked }
}
function openMain() { window.electronAPI?.showMainWindow?.() }

watch(() => auth.isLoggedIn, loggedIn => {
  if (loggedIn) {
    load()
    if (!pollTimer) pollTimer = setInterval(load, 30000)
  }
})

onMounted(async () => {
  const state = await window.electronAPI?.getWidgetState?.(type)
  if (state) { pinned.value = state.pinned; locked.value = state.locked }
  try { await auth.checkSession() } catch (_) {}
  if (auth.isLoggedIn) {
    await load()
    pollTimer = setInterval(load, 30000)
  }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <LoginModal v-if="!auth.isLoggedIn" />
  <section v-else class="desktop-widget" :class="{ locked }">
    <header class="widget-titlebar">
      <div class="widget-heading"><span class="widget-mark"></span><strong>{{ title }}</strong></div>
      <div class="widget-actions">
        <button type="button" class="pixel-icon-btn" :class="{ active: pinned }" :title="pinned ? '取消置顶' : '窗口置顶'" @click="widgetAction('toggle-pin')">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5 1h6v2h-1v3l2 2v2H9v5H7v-5H4V8l2-2V3H5V1Zm3 2v4L7 8h2L8 7V3Z"/>
          </svg>
        </button>
        <button type="button" class="pixel-icon-btn" :class="{ active: locked }" :title="locked ? '解除位置锁定' : '锁定位置和大小'" @click="widgetAction('toggle-lock')">
          <svg v-if="locked" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M4 7V4h1V2h2V1h2v1h2v2h1v3h1v8H3V7h1Zm2 0h4V4H9V3H7v1H6v3Zm1 3v3h2v-3H7Z"/>
          </svg>
          <svg v-else viewBox="0 0 16 16" aria-hidden="true">
            <path d="M5 7V4h1V2h2V1h2v1h2v2h1v2h-2V4h-1V3H8v1H7v3h6v8H3V7h2Zm2 3v3h2v-3H7Z"/>
          </svg>
        </button>
        <button type="button" title="重新加载组件" @click="widgetAction('refresh')">↻</button>
        <button type="button" title="隐藏" @click="widgetAction('hide')">×</button>
      </div>
    </header>

    <div class="widget-subbar">
      <span>{{ type === 'schedule' ? `${schedules.length} 项未来安排` : `${records.length} 条投递记录` }}</span>
      <button type="button" @click="openMain">打开看板</button>
    </div>

    <main class="widget-body">
      <div v-if="loading && !data" class="widget-empty">正在同步数据…</div>
      <div v-else-if="error" class="widget-empty error">{{ error }}<button type="button" @click="load">重试</button></div>

      <template v-else-if="type === 'records'">
        <article v-for="record in records" :key="record.record_id" class="record-row" role="button" tabindex="0" @click="openRecordDetail(record)" @keydown.enter="openRecordDetail(record)">
          <span class="record-main"><b>{{ record.company || '—' }}</b><small>{{ record.job || '暂未填写岗位' }}</small></span>
          <span class="record-side"><em :data-progress="progressOf(record)">{{ progressOf(record) }}</em><small>{{ fmtDateChina(record.apply_date) }}</small><button v-if="record.url" type="button" class="record-view" @click.stop="openRecordUrl(record)">查看</button></span>
        </article>
        <div v-if="!records.length" class="widget-empty">暂无投递记录</div>
      </template>

      <template v-else>
        <article v-for="item in schedules" :key="item.key" class="schedule-row">
          <span class="schedule-date"><b>{{ dateText(item.date) }}</b><small>{{ daysText(item.days) }}</small></span>
          <span class="schedule-main"><b>{{ item.company }} · {{ item.label }}</b><small>{{ item.job || '自定义日程' }}</small></span>
          <i :class="{ urgent: item.days <= 3 }"></i>
        </article>
        <div v-if="!schedules.length" class="widget-empty">未来 30 天暂无安排</div>
      </template>
    </main>

    <div v-if="selectedRecord" class="widget-detail-mask" @mousedown.self="closeRecordDetail">
      <section class="widget-detail" role="dialog" aria-modal="true" :aria-label="(selectedRecord.company || '投递记录') + '详情'">
        <header><div><small>RECORD / DETAIL</small><h2>{{ selectedRecord.company || '投递记录' }}</h2></div><button type="button" title="关闭详情" @click="closeRecordDetail">×</button></header>
        <div class="widget-detail-body">
          <dl><template v-for="row in detailRows(selectedRecord)" :key="row[0]"><dt>{{ row[0] }}</dt><dd>{{ row[1] }}</dd></template></dl>
          <div v-if="selectedRecord.note" class="widget-detail-note"><b>备注</b><p>{{ selectedRecord.note }}</p></div>
        </div>
        <footer><button v-if="selectedRecord.url" type="button" class="detail-link" @click="openRecordUrl(selectedRecord)">查看投递页面</button><span v-else>该记录没有投递链接</span></footer>
      </section>
    </div>

    <footer class="widget-footer"><span>{{ locked ? '位置已锁定' : '拖动顶部可调整位置' }}</span><span>每 30 秒同步</span></footer>
  </section>
</template>

<style>
.desktop-widget-mode *{box-sizing:border-box}html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{width:100%;height:100%;margin:0;overflow:hidden;background:#eef2f4;color:#18332a;font-family:"Microsoft YaHei",system-ui,sans-serif}
.desktop-widget{display:flex;flex-direction:column;height:100%;border:1px solid #9bb7ab;background:#f8faf9;box-shadow:inset 0 0 0 2px #fff}
.widget-titlebar{-webkit-app-region:drag;display:flex;align-items:center;justify-content:space-between;min-height:46px;padding:0 8px 0 14px;border-bottom:1px solid #cbdad4;background:#e7f0ec}
.widget-heading{display:flex;align-items:center;gap:9px;font-size:14px;letter-spacing:.04em}.widget-mark{width:10px;height:10px;border:2px solid #18332a;background:#5fa783;box-shadow:2px 2px 0 #18332a}
.widget-actions{-webkit-app-region:no-drag;display:flex;gap:4px}.widget-actions button{display:grid;place-items:center;width:28px;height:28px;padding:0;border:1px solid transparent;border-radius:5px;background:transparent;color:#526b62;font:700 15px system-ui;cursor:pointer}.widget-actions button:hover,.widget-actions button.active{border-color:#83aa99;background:#fff;color:#176342}.widget-actions button:last-child:hover{color:#b42318;border-color:#e4a8a3}
.widget-subbar{display:flex;align-items:center;justify-content:space-between;padding:8px 13px;border-bottom:1px solid #dbe5e1;color:#6c8078;font-size:11px}.widget-subbar button,.widget-empty button{border:0;background:transparent;color:#267758;font:700 11px inherit;cursor:pointer}
.widget-body{flex:1;min-height:0;overflow:auto;padding:7px}.widget-body::-webkit-scrollbar{width:6px}.widget-body::-webkit-scrollbar-thumb{border-radius:6px;background:#b9cbc4}
.record-row,.schedule-row{display:flex;width:100%;align-items:center;gap:10px;margin:0 0 6px;padding:10px;border:1px solid #d5e1dc;border-radius:8px;background:#fff;color:inherit;text-align:left;cursor:pointer}.record-row:hover,.schedule-row:hover{border-color:#75a48f;background:#f2f8f5}
.record-main,.schedule-main{display:flex;flex:1;min-width:0;flex-direction:column;gap:4px}.record-main b,.schedule-main b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.record-main small,.schedule-main small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#75877f;font-size:10px}
.record-side{display:flex;flex:0 0 auto;align-items:flex-end;flex-direction:column;gap:4px}.record-side em{padding:3px 7px;border-radius:999px;background:#e6f1ec;color:#267758;font-size:10px;font-style:normal;font-weight:700}.record-side em[data-progress="已挂"],.record-side em[data-progress="放弃"]{background:#fae9e7;color:#b42318}.record-side small{color:#82928c;font-size:9px}
.schedule-date{display:flex;width:48px;flex:0 0 48px;flex-direction:column;align-items:center;gap:3px;padding-right:9px;border-right:1px solid #e0e8e5}.schedule-date b{font-size:13px}.schedule-date small{color:#73877e;font-size:9px}.schedule-row i{width:7px;height:7px;border-radius:50%;background:#5fa783}.schedule-row i.urgent{background:#e14b40;box-shadow:0 0 0 3px #fbe5e2}
.widget-empty{display:flex;height:100%;min-height:140px;align-items:center;justify-content:center;gap:8px;color:#81918a;font-size:12px}.widget-empty.error{color:#b42318}
.widget-footer{display:flex;justify-content:space-between;padding:7px 12px;border-top:1px solid #dbe5e1;color:#8a9993;font-size:9px}.desktop-widget.locked .widget-titlebar{-webkit-app-region:no-drag}
@media(prefers-color-scheme:dark){html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background:#17231f;color:#e4eee9}.desktop-widget{border-color:#3e5b50;background:#1c2924;box-shadow:none}.widget-titlebar{border-color:#3c554b;background:#263a32}.widget-subbar,.widget-footer{border-color:#344a41;color:#91a79e}.widget-actions button{color:#a7bbb2}.widget-actions button:hover,.widget-actions button.active{background:#30473d;color:#85d2ad}.record-row,.schedule-row{border-color:#344b41;background:#22332c}.record-row:hover,.schedule-row:hover{border-color:#5b9078;background:#293e35}.record-main small,.schedule-main small,.record-side small,.schedule-date small{color:#91a59c}}

/* Pixelium desktop widget skin */
html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background-color:#e9efe9;background-image:linear-gradient(rgba(24,51,42,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(24,51,42,.08) 1px,transparent 1px);background-size:12px 12px;font-family:"Fusion Pixel Zh_hans","Microsoft YaHei",monospace;image-rendering:pixelated}
.desktop-widget{border:3px solid #18332a;border-radius:0;background:#f7faf7;box-shadow:inset 0 0 0 2px #fff}
.widget-titlebar{min-height:48px;padding:0 7px 0 13px;border-bottom:3px solid #18332a;background:repeating-linear-gradient(135deg,#386a57 0 8px,#447863 8px 16px);color:#fff;text-shadow:2px 2px 0 #18332a}
.widget-heading{gap:10px;font-size:13px;letter-spacing:.12em}.widget-mark{width:12px;height:12px;border:2px solid #fff;border-radius:0;background:#f0c443;box-shadow:2px 2px 0 #18332a}
.widget-actions{gap:5px}.widget-actions button{width:27px;height:27px;border:2px solid #18332a;border-radius:0;background:#f7faf7;color:#18332a;box-shadow:2px 2px 0 #18332a;font:900 13px monospace;text-shadow:none}.widget-actions button:hover{transform:translate(-1px,-1px);border-color:#18332a;background:#f0c443;color:#18332a;box-shadow:3px 3px 0 #18332a}.widget-actions button.active{border-color:#18332a;background:#67b58f;color:#102b22;box-shadow:inset 2px 2px 0 rgba(24,51,42,.35)}.widget-actions button:last-child:hover{border-color:#18332a;background:#e65b50;color:#fff}
.widget-actions .pixel-icon-btn svg{display:block;width:15px;height:15px;fill:currentColor;shape-rendering:crispEdges}.widget-actions .pixel-icon-btn{padding:4px}
.widget-subbar{padding:8px 11px;border-bottom:2px solid #18332a;background:#dfe9e3;color:#425d53;font:900 10px monospace;letter-spacing:.04em}.widget-subbar:before{content:"// ";color:#386a57}.widget-subbar button,.widget-empty button{padding:3px 6px;border:1px solid #18332a;border-radius:0;background:#fff;color:#265c48;box-shadow:1px 1px 0 #18332a;font:900 10px "Fusion Pixel Zh_hans",monospace}
.widget-body{padding:9px;background-image:linear-gradient(rgba(56,106,87,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(56,106,87,.035) 1px,transparent 1px);background-size:8px 8px}.widget-body::-webkit-scrollbar{width:10px}.widget-body::-webkit-scrollbar-track{border-left:2px solid #18332a;background:#dfe9e3}.widget-body::-webkit-scrollbar-thumb{border:2px solid #18332a;border-radius:0;background:#67b58f}
.record-row,.schedule-row{gap:10px;margin:0 0 8px;padding:9px;border:2px solid #18332a;border-radius:0;background:#fff;box-shadow:3px 3px 0 #aebfb7;transition:none}.record-row:hover,.schedule-row:hover{transform:translate(-1px,-1px);border-color:#18332a;background:#edf7f1;box-shadow:4px 4px 0 #18332a}.record-main b,.schedule-main b{font-size:12px;letter-spacing:.03em}.record-main small,.schedule-main small{color:#60766d;font-size:10px}
.record-side em{padding:3px 6px;border:1px solid #18332a;border-radius:0;background:#cce9d9;color:#174d38;box-shadow:1px 1px 0 #18332a;font:900 9px "Fusion Pixel Zh_hans",monospace}.record-side em[data-progress="已挂"],.record-side em[data-progress="放弃"]{background:#f6c4bf;color:#8e2018}.record-side small{color:#61776e;font:900 9px monospace}
.schedule-date{width:54px;flex-basis:54px;gap:4px;padding:6px 8px 6px 0;border-right:2px dashed #18332a}.schedule-date b{color:#285d49;font:900 14px monospace}.schedule-date small{padding:2px 3px;background:#dfe9e3;color:#425d53;font-size:9px}.schedule-row i{width:9px;height:9px;border:2px solid #18332a;border-radius:0;background:#67b58f;box-shadow:1px 1px 0 #18332a}.schedule-row i.urgent{background:#e65b50;box-shadow:2px 2px 0 #18332a}
.widget-empty{color:#61776e;font:900 11px monospace}.widget-empty:before{content:"[ EMPTY ]";color:#386a57}.widget-empty.error:before{content:"[ ERR ]";color:#b42318}.widget-footer{padding:7px 10px;border-top:2px solid #18332a;background:#dfe9e3;color:#52685f;font:900 9px monospace;letter-spacing:.03em}
@media(prefers-color-scheme:dark){html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background-color:#16241e;background-image:linear-gradient(rgba(126,176,151,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(126,176,151,.08) 1px,transparent 1px)}.desktop-widget{border-color:#0a1511;background:#203129;box-shadow:inset 0 0 0 2px #334c41}.widget-titlebar{border-color:#0a1511;background:repeating-linear-gradient(135deg,#294f40 0 8px,#315e4c 8px 16px)}.widget-subbar,.widget-footer{border-color:#0a1511;background:#263b32;color:#a3b9af}.widget-subbar button{background:#d9e8e0}.widget-body{background-color:#1c2b25}.record-row,.schedule-row{border-color:#0a1511;background:#263a31;color:#e2eee8;box-shadow:3px 3px 0 #0a1511}.record-row:hover,.schedule-row:hover{border-color:#0a1511;background:#30483d}.record-main small,.schedule-main small,.record-side small{color:#9bb0a7}.schedule-date{border-color:#8da99c}.schedule-date b{color:#85c9a8}.schedule-date small{background:#31483e;color:#b8cbc2}}

/* Standalone record detail */
.desktop-widget{position:relative}.record-row:focus-visible{outline:3px solid #f0c443;outline-offset:1px}.record-view{padding:2px 5px;border:1px solid #18332a;border-radius:0;background:#dfe9e3;color:#24684f;box-shadow:1px 1px 0 #18332a;font:900 9px "Fusion Pixel Zh_hans",monospace;text-decoration:none;cursor:pointer}.record-view:hover{background:#f0c443;color:#18332a}.schedule-row{cursor:default}
.widget-detail-mask{position:absolute;inset:0;z-index:50;display:grid;place-items:center;padding:14px;background:rgba(12,25,20,.72)}.widget-detail{display:flex;width:100%;max-height:100%;flex-direction:column;border:3px solid #18332a;background:#f7faf7;box-shadow:7px 7px 0 #0d1c17}.widget-detail>header{display:flex;align-items:center;justify-content:space-between;padding:9px 10px;border-bottom:3px solid #18332a;background:repeating-linear-gradient(135deg,#386a57 0 8px,#447863 8px 16px);color:#fff;text-shadow:2px 2px 0 #18332a}.widget-detail>header small{font:900 8px monospace;letter-spacing:.12em}.widget-detail>header h2{margin:2px 0 0;font-size:14px;line-height:1.2}.widget-detail>header button{width:27px;height:27px;border:2px solid #18332a;background:#f7faf7;color:#18332a;box-shadow:2px 2px 0 #18332a;font:900 15px monospace;cursor:pointer}.widget-detail-body{min-height:0;overflow:auto;padding:9px;background-image:linear-gradient(rgba(56,106,87,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(56,106,87,.04) 1px,transparent 1px);background-size:8px 8px}.widget-detail dl{display:grid;grid-template-columns:82px minmax(0,1fr);margin:0;border-top:2px solid #18332a;border-left:2px solid #18332a}.widget-detail dt,.widget-detail dd{min-width:0;margin:0;padding:6px 7px;border-right:2px solid #18332a;border-bottom:2px solid #18332a;overflow-wrap:anywhere;font-size:10px}.widget-detail dt{background:#dfe9e3;color:#425d53;font-weight:900}.widget-detail dd{background:#fff;color:#18332a}.widget-detail-note{margin-top:9px;border:2px solid #18332a;background:#fff}.widget-detail-note b{display:block;padding:5px 7px;border-bottom:2px solid #18332a;background:#f0c443;font-size:10px}.widget-detail-note p{margin:0;padding:7px;white-space:pre-wrap;overflow-wrap:anywhere;color:#425d53;font-size:10px;line-height:1.5}.widget-detail>footer{display:flex;align-items:center;justify-content:flex-end;min-height:40px;padding:7px 9px;border-top:3px solid #18332a;background:#dfe9e3;color:#61776e;font-size:9px}.detail-link{padding:5px 8px;border:2px solid #18332a;background:#67b58f;color:#102b22;box-shadow:2px 2px 0 #18332a;font:900 10px "Fusion Pixel Zh_hans",monospace;cursor:pointer}.detail-link:hover{transform:translate(-1px,-1px);box-shadow:3px 3px 0 #18332a}
@media(prefers-color-scheme:dark){.record-view{color:#85c9a8}.widget-detail{border-color:#0a1511;background:#203129;box-shadow:7px 7px 0 #07100c}.widget-detail>header,.widget-detail>footer{border-color:#0a1511}.widget-detail>footer{background:#263b32}.widget-detail dl{border-color:#0a1511}.widget-detail dt,.widget-detail dd{border-color:#0a1511}.widget-detail dt{background:#31483e;color:#b8cbc2}.widget-detail dd,.widget-detail-note{background:#263a31;color:#e2eee8}.widget-detail-note{border-color:#0a1511}.widget-detail-note b{border-color:#0a1511;color:#18332a}.widget-detail-note p{color:#b8cbc2}}

/* Widget skins share the preference stored by the main application window. */
html[data-style="aurora"].desktop-widget-mode,html[data-style="aurora"].desktop-widget-mode body,html[data-style="aurora"].desktop-widget-mode #app{background:#15172d;color:#f1f1ff;font-family:"Segoe UI Variable","Microsoft YaHei",sans-serif;background-image:radial-gradient(circle at 10% 0,rgba(117,89,255,.42),transparent 48%),radial-gradient(circle at 100% 80%,rgba(60,200,189,.28),transparent 46%)}
html[data-style="aurora"] .desktop-widget{border:1px solid rgba(255,255,255,.26);border-radius:14px;background:rgba(25,27,53,.8);box-shadow:inset 0 1px 0 rgba(255,255,255,.22);backdrop-filter:blur(22px)}
html[data-style="aurora"] .widget-titlebar{border-bottom:1px solid rgba(255,255,255,.18);background:linear-gradient(100deg,rgba(101,81,216,.88),rgba(59,141,173,.85));text-shadow:none}
html[data-style="aurora"] .widget-mark{border:0;border-radius:50%;background:#ffe074;box-shadow:0 0 14px #ffe074}
html[data-style="aurora"] .widget-actions button{border:1px solid rgba(255,255,255,.2);border-radius:8px;background:rgba(255,255,255,.08);color:#fff;box-shadow:none}
html[data-style="aurora"] .widget-actions button:hover,html[data-style="aurora"] .widget-actions button.active{transform:none;border-color:rgba(255,255,255,.5);background:rgba(255,255,255,.18);color:#fff;box-shadow:none}
html[data-style="aurora"] .widget-subbar,html[data-style="aurora"] .widget-footer{border-color:rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:#aeb0cc;font-family:inherit}
html[data-style="aurora"] .widget-subbar:before{display:none}
html[data-style="aurora"] .widget-subbar button,html[data-style="aurora"] .widget-empty button{border:0;border-radius:7px;background:rgba(155,140,255,.16);color:#c9c1ff;box-shadow:none;font-family:inherit}
html[data-style="aurora"] .widget-body{background:transparent}
html[data-style="aurora"] .record-row,html[data-style="aurora"] .schedule-row{border:1px solid rgba(255,255,255,.12);border-radius:11px;background:rgba(255,255,255,.07);color:#f1f1ff;box-shadow:none}
html[data-style="aurora"] .record-row:hover,html[data-style="aurora"] .schedule-row:hover{transform:none;border-color:rgba(155,140,255,.55);background:rgba(155,140,255,.13);box-shadow:0 10px 25px rgba(0,0,0,.18)}
html[data-style="aurora"] .record-main small,html[data-style="aurora"] .schedule-main small,html[data-style="aurora"] .record-side small{color:#aeb0c6}
html[data-style="aurora"] .record-side em{border:0;border-radius:999px;background:rgba(69,200,175,.17);color:#83e1ce;box-shadow:none;font-family:inherit}
html[data-style="aurora"] .record-view{border:0;border-radius:6px;background:rgba(155,140,255,.17);color:#c9c1ff;box-shadow:none;font-family:inherit}
html[data-style="aurora"] .widget-detail{border:1px solid rgba(255,255,255,.28);border-radius:14px;background:#202341;box-shadow:0 24px 60px rgba(0,0,0,.5)}
html[data-style="aurora"] .widget-detail>header{border-color:rgba(255,255,255,.16);background:linear-gradient(100deg,#6551d8,#3b8dad);text-shadow:none}
html[data-style="aurora"] .widget-detail dl,html[data-style="aurora"] .widget-detail dt,html[data-style="aurora"] .widget-detail dd{border-color:rgba(255,255,255,.14)}
html[data-style="aurora"] .widget-detail dt{background:rgba(155,140,255,.12);color:#b9b8d2}html[data-style="aurora"] .widget-detail dd,html[data-style="aurora"] .widget-detail-note{background:rgba(255,255,255,.05);color:#f1f1ff}

html[data-style="terminal"].desktop-widget-mode,html[data-style="terminal"].desktop-widget-mode body,html[data-style="terminal"].desktop-widget-mode #app{background:#07110d;color:#c8f8dc;font-family:"Cascadia Mono",Consolas,"Microsoft YaHei",monospace;background-image:repeating-linear-gradient(0deg,transparent 0 3px,rgba(65,209,125,.025) 3px 4px)}
html[data-style="terminal"] .desktop-widget{border:1px solid #41d17d;border-radius:0;background:#0b1712;box-shadow:inset 0 0 22px rgba(65,209,125,.04)}
html[data-style="terminal"] .widget-titlebar{border-bottom:1px solid #41d17d;background:#08130e;color:#c8f8dc;text-shadow:none}
html[data-style="terminal"] .widget-heading:before{content:">";color:#41d17d}html[data-style="terminal"] .widget-mark{display:none}
html[data-style="terminal"] .widget-actions button{border:1px solid #2b5a40;border-radius:2px;background:#0b1712;color:#81aa91;box-shadow:none}
html[data-style="terminal"] .widget-actions button:hover,html[data-style="terminal"] .widget-actions button.active{transform:none;border-color:#41d17d;background:rgba(65,209,125,.11);color:#41d17d;box-shadow:none}
html[data-style="terminal"] .widget-subbar,html[data-style="terminal"] .widget-footer{border-color:#2b5a40;background:#08130e;color:#81aa91;font-family:inherit}
html[data-style="terminal"] .widget-subbar:before{content:"// ";color:#41d17d}
html[data-style="terminal"] .widget-subbar button,html[data-style="terminal"] .widget-empty button{border:1px solid #2b5a40;border-radius:2px;background:#0b1712;color:#41d17d;box-shadow:none;font-family:inherit}
html[data-style="terminal"] .widget-body{background:#07110d;background-image:none}
html[data-style="terminal"] .record-row,html[data-style="terminal"] .schedule-row{border:1px solid #183326;border-radius:2px;background:#0b1712;color:#c8f8dc;box-shadow:none}
html[data-style="terminal"] .record-row:hover,html[data-style="terminal"] .schedule-row:hover{transform:none;border-color:#41d17d;background:rgba(65,209,125,.07);box-shadow:none}
html[data-style="terminal"] .record-main small,html[data-style="terminal"] .schedule-main small,html[data-style="terminal"] .record-side small{color:#81aa91}
html[data-style="terminal"] .record-side em{border:1px solid #2b5a40;border-radius:2px;background:rgba(65,209,125,.1);color:#55e68f;box-shadow:none;font-family:inherit}
html[data-style="terminal"] .record-view{border:1px solid #2b5a40;border-radius:2px;background:#0b1712;color:#41d17d;box-shadow:none;font-family:inherit}
html[data-style="terminal"] .widget-detail{border:1px solid #41d17d;background:#0b1712;box-shadow:0 0 28px rgba(65,209,125,.13)}
html[data-style="terminal"] .widget-detail>header{border-color:#41d17d;background:#08130e;color:#c8f8dc;text-shadow:none}
html[data-style="terminal"] .widget-detail dl,html[data-style="terminal"] .widget-detail dt,html[data-style="terminal"] .widget-detail dd{border-color:#2b5a40}
html[data-style="terminal"] .widget-detail dt{background:rgba(65,209,125,.08);color:#81aa91}html[data-style="terminal"] .widget-detail dd,html[data-style="terminal"] .widget-detail-note{background:#0b1712;color:#c8f8dc}
</style>
