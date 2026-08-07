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
        company: record.company || '未填写', job: record.job || '', label, date, days,
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
  ].filter(([, value]) => value && value !== '未填写')
}
function openRecordDetail(record) { selectedRecord.value = record }
function closeRecordDetail() { selectedRecord.value = null }
async function openRecordUrl(record) {
  const rawUrl = String(record?.url || '').trim()
  if (!rawUrl) return
  try {
    await window.electronAPI?.openExternal?.(rawUrl)
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
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M9 3.5h6l-.8 5.2 3.3 3.2v1.6h-11v-1.6l3.3-3.2L9 3.5Z"/>
            <path d="M12 13.5V21"/>
          </svg>
        </button>
        <button type="button" class="pixel-icon-btn" :class="{ active: locked }" :title="locked ? '解除位置锁定' : '锁定位置和大小'" @click="widgetAction('toggle-lock')">
          <svg v-if="locked" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="10" width="14" height="11" rx="2.5"/>
            <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10M12 14.5v2"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" aria-hidden="true">
            <rect x="5" y="10" width="14" height="11" rx="2.5"/>
            <path d="M8.5 10V7.5a3.5 3.5 0 0 1 6.8-1.2M12 14.5v2"/>
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
          <span class="record-main"><b>{{ record.company || '未填写' }}</b><small>{{ record.job || '暂未填写岗位' }}</small></span>
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
.widget-actions .pixel-icon-btn{padding:4px}.widget-actions .pixel-icon-btn svg{display:block;width:17px;height:17px;overflow:visible;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round;shape-rendering:auto}
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
@scope (html[data-style="pixelium"]) {
html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background-color:#e9efe9;background-image:linear-gradient(rgba(24,51,42,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(24,51,42,.08) 1px,transparent 1px);background-size:12px 12px;font-family:"Fusion Pixel Zh_hans","Microsoft YaHei",monospace;image-rendering:pixelated}
.desktop-widget{border:3px solid #18332a;border-radius:0;background:#f7faf7;box-shadow:inset 0 0 0 2px #fff}
.widget-titlebar{min-height:48px;padding:0 7px 0 13px;border-bottom:3px solid #18332a;background:repeating-linear-gradient(135deg,#386a57 0 8px,#447863 8px 16px);color:#fff;text-shadow:2px 2px 0 #18332a}
.widget-heading{gap:10px;font-size:13px;letter-spacing:.12em}.widget-mark{width:12px;height:12px;border:2px solid #fff;border-radius:0;background:#f0c443;box-shadow:2px 2px 0 #18332a}
.widget-actions{gap:5px}.widget-actions button{width:27px;height:27px;border:2px solid #18332a;border-radius:0;background:#f7faf7;color:#18332a;box-shadow:2px 2px 0 #18332a;font:900 13px monospace;text-shadow:none}.widget-actions button:hover{transform:translate(-1px,-1px);border-color:#18332a;background:#f0c443;color:#18332a;box-shadow:3px 3px 0 #18332a}.widget-actions button.active{border-color:#18332a;background:#67b58f;color:#102b22;box-shadow:inset 2px 2px 0 rgba(24,51,42,.35)}.widget-actions button:last-child:hover{border-color:#18332a;background:#e65b50;color:#fff}
.widget-subbar{padding:8px 11px;border-bottom:2px solid #18332a;background:#dfe9e3;color:#425d53;font:900 10px monospace;letter-spacing:.04em}.widget-subbar:before{content:"// ";color:#386a57}.widget-subbar button,.widget-empty button{padding:3px 6px;border:1px solid #18332a;border-radius:0;background:#fff;color:#265c48;box-shadow:1px 1px 0 #18332a;font:900 10px "Fusion Pixel Zh_hans",monospace}
.widget-body{padding:9px;background-image:linear-gradient(rgba(56,106,87,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(56,106,87,.035) 1px,transparent 1px);background-size:8px 8px}.widget-body::-webkit-scrollbar{width:10px}.widget-body::-webkit-scrollbar-track{border-left:2px solid #18332a;background:#dfe9e3}.widget-body::-webkit-scrollbar-thumb{border:2px solid #18332a;border-radius:0;background:#67b58f}
.record-row,.schedule-row{gap:10px;margin:0 0 8px;padding:9px;border:2px solid #18332a;border-radius:0;background:#fff;box-shadow:3px 3px 0 #aebfb7;transition:none}.record-row:hover,.schedule-row:hover{transform:translate(-1px,-1px);border-color:#18332a;background:#edf7f1;box-shadow:4px 4px 0 #18332a}.record-main b,.schedule-main b{font-size:12px;letter-spacing:.03em}.record-main small,.schedule-main small{color:#60766d;font-size:10px}
.record-side em{padding:3px 6px;border:1px solid #18332a;border-radius:0;background:#cce9d9;color:#174d38;box-shadow:1px 1px 0 #18332a;font:900 9px "Fusion Pixel Zh_hans",monospace}.record-side em[data-progress="已挂"],.record-side em[data-progress="放弃"]{background:#f6c4bf;color:#8e2018}.record-side small{color:#61776e;font:900 9px monospace}
.schedule-date{width:54px;flex-basis:54px;gap:4px;padding:6px 8px 6px 0;border-right:2px dashed #18332a}.schedule-date b{color:#285d49;font:900 14px monospace}.schedule-date small{padding:2px 3px;background:#dfe9e3;color:#425d53;font-size:9px}.schedule-row i{width:9px;height:9px;border:2px solid #18332a;border-radius:0;background:#67b58f;box-shadow:1px 1px 0 #18332a}.schedule-row i.urgent{background:#e65b50;box-shadow:2px 2px 0 #18332a}
.widget-empty{color:#61776e;font:900 11px monospace}.widget-empty:before{content:"[ EMPTY ]";color:#386a57}.widget-empty.error:before{content:"[ ERR ]";color:#b42318}.widget-footer{padding:7px 10px;border-top:2px solid #18332a;background:#dfe9e3;color:#52685f;font:900 9px monospace;letter-spacing:.03em}
@media(prefers-color-scheme:dark){html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background-color:#16241e;background-image:linear-gradient(rgba(126,176,151,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(126,176,151,.08) 1px,transparent 1px)}.desktop-widget{border-color:#0a1511;background:#203129;box-shadow:inset 0 0 0 2px #334c41}.widget-titlebar{border-color:#0a1511;background:repeating-linear-gradient(135deg,#294f40 0 8px,#315e4c 8px 16px)}.widget-subbar,.widget-footer{border-color:#0a1511;background:#263b32;color:#a3b9af}.widget-subbar button{background:#d9e8e0}.widget-body{background-color:#1c2b25}.record-row,.schedule-row{border-color:#0a1511;background:#263a31;color:#e2eee8;box-shadow:3px 3px 0 #0a1511}.record-row:hover,.schedule-row:hover{border-color:#0a1511;background:#30483d}.record-main small,.schedule-main small,.record-side small{color:#9bb0a7}.schedule-date{border-color:#8da99c}.schedule-date b{color:#85c9a8}.schedule-date small{background:#31483e;color:#b8cbc2}}
}

/* Standalone record detail */
.desktop-widget{position:relative}.record-row:focus-visible{outline:3px solid #f0c443;outline-offset:1px}.record-view{padding:2px 5px;border:1px solid #18332a;border-radius:0;background:#dfe9e3;color:#24684f;box-shadow:1px 1px 0 #18332a;font:900 9px "Fusion Pixel Zh_hans",monospace;text-decoration:none;cursor:pointer}.record-view:hover{background:#f0c443;color:#18332a}.schedule-row{cursor:default}
.widget-detail-mask{position:absolute;inset:0;z-index:50;display:grid;place-items:center;padding:14px;background:rgba(12,25,20,.72)}.widget-detail{display:flex;width:100%;max-height:100%;flex-direction:column;border:3px solid #18332a;background:#f7faf7;box-shadow:7px 7px 0 #0d1c17}.widget-detail>header{display:flex;align-items:center;justify-content:space-between;padding:9px 10px;border-bottom:3px solid #18332a;background:repeating-linear-gradient(135deg,#386a57 0 8px,#447863 8px 16px);color:#fff;text-shadow:2px 2px 0 #18332a}.widget-detail>header small{font:900 8px monospace;letter-spacing:.12em}.widget-detail>header h2{margin:2px 0 0;font-size:14px;line-height:1.2}.widget-detail>header button{width:27px;height:27px;border:2px solid #18332a;background:#f7faf7;color:#18332a;box-shadow:2px 2px 0 #18332a;font:900 15px monospace;cursor:pointer}.widget-detail-body{min-height:0;overflow:auto;padding:9px;background-image:linear-gradient(rgba(56,106,87,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(56,106,87,.04) 1px,transparent 1px);background-size:8px 8px}.widget-detail dl{display:grid;grid-template-columns:82px minmax(0,1fr);margin:0;border-top:2px solid #18332a;border-left:2px solid #18332a}.widget-detail dt,.widget-detail dd{min-width:0;margin:0;padding:6px 7px;border-right:2px solid #18332a;border-bottom:2px solid #18332a;overflow-wrap:anywhere;font-size:10px}.widget-detail dt{background:#dfe9e3;color:#425d53;font-weight:900}.widget-detail dd{background:#fff;color:#18332a}.widget-detail-note{margin-top:9px;border:2px solid #18332a;background:#fff}.widget-detail-note b{display:block;padding:5px 7px;border-bottom:2px solid #18332a;background:#f0c443;font-size:10px}.widget-detail-note p{margin:0;padding:7px;white-space:pre-wrap;overflow-wrap:anywhere;color:#425d53;font-size:10px;line-height:1.5}.widget-detail>footer{display:flex;align-items:center;justify-content:flex-end;min-height:40px;padding:7px 9px;border-top:3px solid #18332a;background:#dfe9e3;color:#61776e;font-size:9px}.detail-link{padding:5px 8px;border:2px solid #18332a;background:#67b58f;color:#102b22;box-shadow:2px 2px 0 #18332a;font:900 10px "Fusion Pixel Zh_hans",monospace;cursor:pointer}.detail-link:hover{transform:translate(-1px,-1px);box-shadow:3px 3px 0 #18332a}
@media(prefers-color-scheme:dark){.record-view{color:#85c9a8}.widget-detail{border-color:#0a1511;background:#203129;box-shadow:7px 7px 0 #07100c}.widget-detail>header,.widget-detail>footer{border-color:#0a1511}.widget-detail>footer{background:#263b32}.widget-detail dl{border-color:#0a1511}.widget-detail dt,.widget-detail dd{border-color:#0a1511}.widget-detail dt{background:#31483e;color:#b8cbc2}.widget-detail dd,.widget-detail-note{background:#263a31;color:#e2eee8}.widget-detail-note{border-color:#0a1511}.widget-detail-note b{border-color:#0a1511;color:#18332a}.widget-detail-note p{color:#b8cbc2}}

/* Widget skins share the preference stored by the main application window. */
html[data-style="aurora"].desktop-widget-mode,html[data-style="aurora"].desktop-widget-mode body,html[data-style="aurora"].desktop-widget-mode #app{background:rgba(232,237,255,.16);color:var(--ink);font-family:var(--font);background-image:radial-gradient(circle at 10% 0,rgba(117,89,255,.36),transparent 48%),radial-gradient(circle at 100% 80%,rgba(60,200,189,.3),transparent 46%)}
html[data-style="aurora"] .desktop-widget{border:1px solid rgba(255,255,255,.58);border-radius:18px;background:linear-gradient(145deg,rgba(255,255,255,.26),rgba(255,255,255,.08));box-shadow:inset 0 1px rgba(255,255,255,.6),0 18px 54px rgba(49,40,117,.18);backdrop-filter:blur(28px) saturate(165%)}
html[data-style="aurora"] .widget-titlebar{border-bottom:1px solid rgba(255,255,255,.2);background:linear-gradient(100deg,rgba(101,81,216,.44),rgba(59,141,173,.3));text-shadow:none;backdrop-filter:blur(22px) saturate(170%)}
html[data-style="aurora"] .widget-mark{border:0;border-radius:50%;background:#ffe074;box-shadow:0 0 14px #ffe074}
html[data-style="aurora"] .widget-actions button{border:1px solid rgba(255,255,255,.2);border-radius:8px;background:rgba(255,255,255,.08);color:#fff;box-shadow:none}
html[data-style="aurora"] .widget-actions button:hover,html[data-style="aurora"] .widget-actions button.active{transform:none;border-color:rgba(255,255,255,.5);background:rgba(255,255,255,.18);color:#fff;box-shadow:none}
html[data-style="aurora"] .widget-subbar,html[data-style="aurora"] .widget-footer{border-color:rgba(255,255,255,.26);background:rgba(255,255,255,.09);color:var(--muted);font-family:inherit;backdrop-filter:blur(18px)}
html[data-style="aurora"] .widget-subbar:before{display:none}
html[data-style="aurora"] .widget-subbar button,html[data-style="aurora"] .widget-empty button{border:0;border-radius:7px;background:var(--blueS);color:var(--blue);box-shadow:none;font-family:inherit}
html[data-style="aurora"] .widget-body{background:transparent}
html[data-style="aurora"] .record-row,html[data-style="aurora"] .schedule-row{border:1px solid rgba(255,255,255,.4);border-radius:13px;background:linear-gradient(145deg,rgba(255,255,255,.2),rgba(255,255,255,.06));color:var(--ink);box-shadow:inset 0 1px rgba(255,255,255,.42),0 8px 22px rgba(49,40,117,.08);backdrop-filter:blur(16px) saturate(150%)}
html[data-style="aurora"] .record-row:hover,html[data-style="aurora"] .schedule-row:hover{transform:none;border-color:var(--blue);background:var(--blueS);box-shadow:0 10px 25px rgba(49,40,117,.14)}
html[data-style="aurora"] .record-main small,html[data-style="aurora"] .schedule-main small,html[data-style="aurora"] .record-side small{color:var(--muted)}
html[data-style="aurora"] .record-side em{border:0;border-radius:999px;background:var(--greenS);color:var(--green);box-shadow:none;font-family:inherit}
html[data-style="aurora"] .record-view{border:0;border-radius:6px;background:var(--blueS);color:var(--blue);box-shadow:none;font-family:inherit}
html[data-style="aurora"] .widget-detail{border:1px solid rgba(255,255,255,.46);border-radius:18px;background:linear-gradient(145deg,rgba(255,255,255,.3),rgba(255,255,255,.1));box-shadow:0 24px 60px rgba(0,0,0,.28),inset 0 1px rgba(255,255,255,.54);backdrop-filter:blur(30px) saturate(160%)}
html[data-style="aurora"] .widget-detail>header{border-color:rgba(255,255,255,.16);background:linear-gradient(100deg,rgba(101,81,216,.5),rgba(59,141,173,.34));text-shadow:none}
html[data-style="aurora"] .widget-detail dl,html[data-style="aurora"] .widget-detail dt,html[data-style="aurora"] .widget-detail dd{border-color:rgba(255,255,255,.14)}
html[data-style="aurora"] .widget-detail dt{background:var(--blueS);color:var(--muted)}html[data-style="aurora"] .widget-detail dd,html[data-style="aurora"] .widget-detail-note{background:color-mix(in srgb,var(--panel) 90%,transparent);color:var(--ink)}

html[data-style="anime"].desktop-widget-mode,html[data-style="anime"].desktop-widget-mode body,html[data-style="anime"].desktop-widget-mode #app{background:#fff7e9;color:#24335e;font-family:"Segoe UI","Microsoft YaHei",sans-serif;background-image:radial-gradient(circle at 1px 1px,rgba(223,98,121,.14) 1px,transparent 1.3px);background-size:18px 18px}
html[data-style="anime"] .desktop-widget{border:3px solid #24335e;border-radius:12px 20px 12px 20px;background:#fffdf8;box-shadow:inset 0 0 0 2px #fff}
html[data-style="anime"] .widget-titlebar{border-bottom:2px solid #24335e;background:linear-gradient(100deg,#354f9e 0 68%,#df6279 68%);color:#fff;text-shadow:none}
html[data-style="anime"] .widget-heading:after{content:"★";color:#ffd071;font-size:16px;transform:rotate(10deg)}
html[data-style="anime"] .widget-mark{border:2px solid #24335e;border-radius:50%;background:#ffd071;box-shadow:2px 2px 0 #24335e}
html[data-style="anime"] .widget-actions button{border:2px solid #24335e;border-radius:7px 10px 7px 10px;background:#fffdf8;color:#24335e;box-shadow:2px 2px 0 #24335e}
html[data-style="anime"] .widget-actions button:hover,html[data-style="anime"] .widget-actions button.active{transform:rotate(-3deg);border-color:#24335e;background:#ffd071;color:#24335e;box-shadow:2px 2px 0 #24335e}
html[data-style="anime"] .widget-subbar,html[data-style="anime"] .widget-footer{border-color:#24335e;background:#fff3df;color:#647092;font-family:inherit}
html[data-style="anime"] .widget-subbar:before{content:"✦ ";color:#df6279}
html[data-style="anime"] .widget-subbar button,html[data-style="anime"] .widget-empty button{border:1px solid #24335e;border-radius:6px;background:#fffdf8;color:#526dc7;box-shadow:1px 1px 0 #24335e;font-family:inherit}
html[data-style="anime"] .widget-body{background:transparent}
html[data-style="anime"] .record-row,html[data-style="anime"] .schedule-row{border:2px solid #24335e;border-radius:8px 14px 8px 14px;background:#fffdf8;color:#24335e;box-shadow:3px 3px 0 rgba(36,51,94,.15)}
html[data-style="anime"] .record-row:nth-child(even),html[data-style="anime"] .schedule-row:nth-child(even){border-radius:14px 8px 14px 8px}
html[data-style="anime"] .record-row:hover,html[data-style="anime"] .schedule-row:hover{transform:rotate(-.5deg);border-color:#24335e;background:#fff1f3;box-shadow:4px 4px 0 #24335e}
html[data-style="anime"] .record-main small,html[data-style="anime"] .schedule-main small,html[data-style="anime"] .record-side small{color:#647092}
html[data-style="anime"] .record-side em{border:1px solid #24335e;border-radius:7px;background:#dff4ec;color:#286c5b;box-shadow:1px 1px 0 #24335e;font-family:inherit}
html[data-style="anime"] .record-view{border:1px solid #24335e;border-radius:6px;background:#e8edff;color:#354f9e;box-shadow:1px 1px 0 #24335e;font-family:inherit}
html[data-style="anime"] .widget-detail{border:3px solid #24335e;border-radius:14px 24px 14px 24px;background:#fffdf8;box-shadow:7px 8px 0 #24335e}
html[data-style="anime"] .widget-detail>header{border-color:#24335e;background:linear-gradient(100deg,#354f9e,#df6279);text-shadow:none}
html[data-style="anime"] .widget-detail dl,html[data-style="anime"] .widget-detail dt,html[data-style="anime"] .widget-detail dd{border-color:#24335e}
html[data-style="anime"] .widget-detail dt{background:#fff0d7;color:#647092}html[data-style="anime"] .widget-detail dd,html[data-style="anime"] .widget-detail-note{background:#fffdf8;color:#24335e}

html[data-style="journal"].desktop-widget-mode{--ink:#392d28;--muted:#716157;--sub:#9a897b;--line:#d4c2a5;--line2:#aa9270;--blue:#7b3140;--blueS:rgba(123,49,64,.1);--green:#55745d;--greenS:rgba(85,116,93,.12);--red:#a53f3f;--redS:rgba(165,63,63,.1);--panel:#fbf4e5}
html[data-style="journal"] .desktop-widget{border:1px solid #70513d;background-color:#fbf4e5;background-image:linear-gradient(90deg,rgba(123,49,64,.11) 0 25px,transparent 25px),repeating-linear-gradient(0deg,transparent 0 24px,rgba(117,85,53,.065) 25px);box-shadow:inset 0 0 0 1px rgba(255,255,255,.55),0 16px 42px rgba(45,29,20,.24);color:#392d28;font-family:"Noto Sans SC","Microsoft YaHei",sans-serif}
html[data-style="journal"] .widget-titlebar{border-bottom:1px solid #4a1a24;background:linear-gradient(90deg,#511d29,#7b3140 72%,#9a6f44);color:#f7ead3;text-shadow:none}
html[data-style="journal"] .widget-heading{font-family:"Songti SC","STSong",serif;letter-spacing:.08em}html[data-style="journal"] .widget-mark{border:1px solid #e1c08d;border-radius:2px;background:#efe0bd;box-shadow:2px 2px 0 #3d1820}
html[data-style="journal"] .widget-actions button{border:1px solid rgba(244,224,190,.35);border-radius:3px;background:rgba(255,255,255,.1);color:#f7ead3;box-shadow:none}html[data-style="journal"] .widget-actions button:hover,html[data-style="journal"] .widget-actions button.active{transform:none;border-color:#f0d8ac;background:rgba(255,255,255,.22);color:#fff;box-shadow:none}
html[data-style="journal"] .widget-subbar,html[data-style="journal"] .widget-footer{border-color:#c9b394;background:rgba(123,49,64,.055);color:#716157;font-family:Georgia,"Microsoft YaHei",serif}html[data-style="journal"] .widget-subbar:before{content:"BOOKMARK / ";color:#7b3140;font-size:8px;letter-spacing:.1em}
html[data-style="journal"] .widget-subbar button,html[data-style="journal"] .widget-empty button{border:1px solid #aa9270;border-radius:3px;background:#fff8ea;color:#7b3140;box-shadow:1px 1px 0 rgba(82,55,38,.14);font-family:inherit}
html[data-style="journal"] .widget-body{background:transparent}html[data-style="journal"] .record-row,html[data-style="journal"] .schedule-row{border:1px solid #d4c2a5;border-left:4px solid #7b3140;border-radius:2px;background:rgba(255,250,239,.84);box-shadow:2px 3px 0 rgba(104,74,48,.1);color:#392d28}
html[data-style="journal"] .record-row:hover,html[data-style="journal"] .schedule-row:hover{transform:translateY(-1px);border-color:#aa9270;border-left-color:#7b3140;background:#fffaf0;box-shadow:3px 5px 0 rgba(104,74,48,.12)}
html[data-style="journal"] .record-main small,html[data-style="journal"] .schedule-main small,html[data-style="journal"] .record-side small{color:#837166}html[data-style="journal"] .record-side em{border:1px solid currentColor;border-radius:2px;background:transparent;color:#55745d;box-shadow:none;font-family:inherit}
html[data-style="journal"] .record-view{border:1px solid #aa9270;border-radius:2px;background:#f2e5ce;color:#7b3140;box-shadow:none;font-family:inherit}
html[data-style="journal"] .schedule-date{border-color:#aa9270}html[data-style="journal"] .schedule-date b{color:#7b3140;font-family:Georgia,serif}html[data-style="journal"] .schedule-date small{background:transparent;color:#716157}
html[data-style="journal"] .widget-detail-mask{background:rgba(45,29,20,.62)}html[data-style="journal"] .widget-detail{border:1px solid #806145;background-color:#fbf4e5;background-image:linear-gradient(90deg,rgba(123,49,64,.1) 0 25px,transparent 25px);box-shadow:8px 10px 0 rgba(45,29,20,.2)}
html[data-style="journal"] .widget-detail>header{border-color:#4a1a24;background:linear-gradient(90deg,#511d29,#7b3140);text-shadow:none}html[data-style="journal"] .widget-detail dl,html[data-style="journal"] .widget-detail dt,html[data-style="journal"] .widget-detail dd{border-color:#aa9270}html[data-style="journal"] .widget-detail dt{background:#eadbbf;color:#716157}html[data-style="journal"] .widget-detail dd,html[data-style="journal"] .widget-detail-note{background:#fff8ea;color:#392d28}
html[data-style="journal"][data-theme="dark"] .desktop-widget{border-color:#130d0b;background-color:#302722;background-image:linear-gradient(90deg,rgba(202,120,135,.12) 0 25px,transparent 25px),repeating-linear-gradient(0deg,transparent 0 24px,rgba(215,190,153,.04) 25px);color:#efe2cb;box-shadow:inset 0 0 0 1px rgba(255,255,255,.06),0 16px 42px rgba(0,0,0,.4)}
html[data-style="journal"][data-theme="dark"] .widget-subbar,html[data-style="journal"][data-theme="dark"] .widget-footer{border-color:#493b34;background:rgba(202,120,135,.05);color:#c2b29f}html[data-style="journal"][data-theme="dark"] .record-row,html[data-style="journal"][data-theme="dark"] .schedule-row{border-color:#493b34;border-left-color:#ca7887;background:#382e29;color:#efe2cb;box-shadow:2px 3px 0 rgba(0,0,0,.18)}
html[data-style="journal"][data-theme="dark"] .record-row:hover,html[data-style="journal"][data-theme="dark"] .schedule-row:hover{border-color:#6c5648;border-left-color:#ca7887;background:#40332e}html[data-style="journal"][data-theme="dark"] .record-main small,html[data-style="journal"][data-theme="dark"] .schedule-main small,html[data-style="journal"][data-theme="dark"] .record-side small{color:#b5a493}
html[data-style="journal"][data-theme="dark"] .widget-detail{border-color:#6c5648;background:#302722;color:#efe2cb}html[data-style="journal"][data-theme="dark"] .widget-detail dt{background:#3b302a;color:#c2b29f}html[data-style="journal"][data-theme="dark"] .widget-detail dd,html[data-style="journal"][data-theme="dark"] .widget-detail-note{background:#382e29;color:#efe2cb}

/* Paperbound archive widget edition. */
html[data-style="journal"].desktop-widget-mode{--ink:#202b27;--muted:#59655f;--sub:#89928d;--line:#c2c8bc;--line2:#76877c;--blue:#2f6756;--blueS:rgba(47,103,86,.12);--green:#2f6756;--greenS:rgba(47,103,86,.12);--red:#b95746;--redS:rgba(185,87,70,.12);--panel:#f8f6ed}
html[data-style="journal"] .desktop-widget{border:1px solid #244d41;background-color:#f8f6ed;background-image:linear-gradient(90deg,transparent 0 27px,rgba(185,87,70,.14) 27px 28px,transparent 28px),repeating-linear-gradient(0deg,transparent 0 26px,rgba(47,103,86,.075) 26px 27px);box-shadow:inset 0 0 0 1px rgba(255,255,255,.6),0 16px 42px rgba(24,52,43,.25);color:#202b27}
html[data-style="journal"] .widget-titlebar{border-bottom:1px solid #102820;background:linear-gradient(90deg,#173b30,#2f6756 74%,#b95746);color:#f5f1e5}
html[data-style="journal"] .widget-mark{border:1px solid #d9cfad;background:#f2edda;box-shadow:inset 4px 0 #b95746,2px 2px 0 #102820}
html[data-style="journal"] .widget-subbar,html[data-style="journal"] .widget-footer{border-color:#c2c8bc;background:rgba(47,103,86,.06);color:#59655f}
html[data-style="journal"] .widget-subbar:before{color:#2f6756}
html[data-style="journal"] .widget-subbar button,html[data-style="journal"] .widget-empty button{border-color:#76877c;background:#f8f6ed;color:#2f6756;box-shadow:1px 1px 0 rgba(40,58,50,.15)}
html[data-style="journal"] .record-row,html[data-style="journal"] .schedule-row{border-color:#c2c8bc;border-left-color:#2f6756;background:rgba(248,246,237,.88);box-shadow:2px 3px 0 rgba(40,58,50,.1);color:#202b27}
html[data-style="journal"] .record-row:hover,html[data-style="journal"] .schedule-row:hover{border-color:#76877c;border-left-color:#2f6756;background:#f2f4ea;box-shadow:3px 5px 0 rgba(40,58,50,.12)}
html[data-style="journal"] .record-main small,html[data-style="journal"] .schedule-main small,html[data-style="journal"] .record-side small{color:#68746d}
html[data-style="journal"] .record-view{border-color:#76877c;background:#e3e9df;color:#2f6756}
html[data-style="journal"] .schedule-date{border-color:#76877c}html[data-style="journal"] .schedule-date b{color:#2f6756}
html[data-style="journal"] .widget-detail-mask{background:rgba(15,35,29,.66)}html[data-style="journal"] .widget-detail{border-color:#76877c;border-left:7px solid #2f6756;background-color:#f8f6ed;background-image:linear-gradient(90deg,transparent 0 25px,rgba(185,87,70,.13) 25px 26px,transparent 26px);box-shadow:8px 10px 0 rgba(25,48,40,.2)}
html[data-style="journal"] .widget-detail>header{border-color:#102820;background:linear-gradient(90deg,#173b30,#2f6756)}html[data-style="journal"] .widget-detail dl,html[data-style="journal"] .widget-detail dt,html[data-style="journal"] .widget-detail dd{border-color:#76877c}html[data-style="journal"] .widget-detail dt{background:#dce5db;color:#59655f}html[data-style="journal"] .widget-detail dd,html[data-style="journal"] .widget-detail-note{background:#f8f6ed;color:#202b27}
html[data-style="journal"][data-theme="dark"] .desktop-widget{border-color:#0d211b;background-color:#252e2a;background-image:linear-gradient(90deg,transparent 0 27px,rgba(220,124,105,.13) 27px 28px,transparent 28px),repeating-linear-gradient(0deg,transparent 0 26px,rgba(114,179,157,.06) 26px 27px);color:#f1eee3}
html[data-style="journal"][data-theme="dark"] .widget-subbar,html[data-style="journal"][data-theme="dark"] .widget-footer{border-color:#46524b;background:rgba(114,179,157,.05);color:#c3c9c0}html[data-style="journal"][data-theme="dark"] .record-row,html[data-style="journal"][data-theme="dark"] .schedule-row{border-color:#46524b;border-left-color:#72b39d;background:#2d3732;color:#f1eee3}html[data-style="journal"][data-theme="dark"] .widget-detail{border-color:#728178;border-left-color:#72b39d;background:#252e2a;color:#f1eee3}html[data-style="journal"][data-theme="dark"] .widget-detail dt{background:#34413b;color:#c3c9c0}html[data-style="journal"][data-theme="dark"] .widget-detail dd,html[data-style="journal"][data-theme="dark"] .widget-detail-note{background:#2d3732;color:#f1eee3}

html[data-style="shuimo"].desktop-widget-mode{--ink:#232521;--muted:#62675f;--sub:#8b8d83;--line:rgba(53,61,54,.2);--blue:#344b4a;--blueS:rgba(52,75,74,.1);--green:#657c68;--greenS:rgba(101,124,104,.12);--red:#a33a32;--redS:rgba(163,58,50,.11);--panel:#f8f5ec}
html[data-style="shuimo"] .desktop-widget{border:1px solid #344b4a;background-color:#f4f1e8;background-image:linear-gradient(rgba(248,245,236,.7),rgba(248,245,236,.88)),url('/static/themes/shuimo/mountain-panorama.webp');background-position:center,bottom center;background-size:auto,cover;color:#232521;font-family:"Zihun Longyin Shoushu","STKaiti","KaiTi",cursive;box-shadow:inset 0 0 0 1px rgba(255,255,255,.55),0 18px 44px rgba(25,31,27,.24)}
html[data-style="shuimo"] .widget-titlebar{border-bottom:1px solid rgba(244,241,232,.2);background:linear-gradient(105deg,#202824,#344b4a 68%,#53645a);color:#f4f1e8;text-shadow:none}
html[data-style="shuimo"] .widget-heading{font-family:"Zihun Longyin Shoushu","STKaiti","KaiTi",cursive}
html[data-style="shuimo"] .widget-heading{letter-spacing:.1em}html[data-style="shuimo"] .widget-heading:after{content:"卷";display:grid;width:20px;height:20px;place-items:center;border:1px solid rgba(255,255,255,.7);background:#a33a32;font-size:9px;transform:rotate(-5deg)}
html[data-style="shuimo"] .widget-mark{border:0;border-radius:50%;background:radial-gradient(circle at 65% 35%,transparent 0 27%,#f4f1e8 29% 50%,rgba(244,241,232,.3) 52% 66%,transparent 68%);box-shadow:none}
html[data-style="shuimo"] .widget-actions button{border:1px solid rgba(244,241,232,.22);border-radius:2px 7px;background:rgba(255,255,255,.04);color:#f4f1e8;box-shadow:none;text-shadow:none}
html[data-style="shuimo"] .widget-actions button:hover,html[data-style="shuimo"] .widget-actions button.active{transform:none;border-color:rgba(255,255,255,.55);background:rgba(255,255,255,.12);color:#fff;box-shadow:none}
html[data-style="shuimo"] .widget-subbar,html[data-style="shuimo"] .widget-footer{border-color:rgba(53,61,54,.2);background:rgba(248,245,236,.55);color:#62675f;font-family:inherit}
html[data-style="shuimo"] .widget-subbar:before{content:"题签 / ";color:#a33a32}
html[data-style="shuimo"] .widget-subbar button,html[data-style="shuimo"] .widget-empty button{border:0;border-bottom:1px solid #344b4a;border-radius:0;background:transparent;color:#344b4a;box-shadow:none;font-family:inherit}
html[data-style="shuimo"] .widget-body{background:transparent}
html[data-style="shuimo"] .record-row,html[data-style="shuimo"] .schedule-row{border:1px solid rgba(53,61,54,.2);border-left:3px solid #344b4a;border-radius:2px 10px;background:rgba(248,245,236,.76);color:#232521;box-shadow:2px 3px 10px rgba(35,37,33,.06)}
html[data-style="shuimo"] .record-row:hover,html[data-style="shuimo"] .schedule-row:hover{transform:translateY(-1px);border-color:#344b4a;background:#f8f5ec;box-shadow:3px 6px 14px rgba(35,37,33,.1)}
html[data-style="shuimo"] .record-main small,html[data-style="shuimo"] .schedule-main small,html[data-style="shuimo"] .record-side small{color:#73776f}
html[data-style="shuimo"] .record-side em{border:1px solid currentColor;border-radius:2px 6px;background:transparent;color:#657c68;box-shadow:none;font-family:inherit}
html[data-style="shuimo"] .record-view{border:0;border-bottom:1px solid #344b4a;border-radius:0;background:transparent;color:#344b4a;box-shadow:none;font-family:inherit}
html[data-style="shuimo"] .schedule-date{border-color:rgba(53,61,54,.3)}html[data-style="shuimo"] .schedule-date b{color:#a33a32;font-family:Georgia,serif}html[data-style="shuimo"] .schedule-date small{background:transparent;color:#62675f}
html[data-style="shuimo"] .widget-detail-mask{background:rgba(25,29,26,.54);backdrop-filter:blur(4px)}html[data-style="shuimo"] .widget-detail{border:1px solid #344b4a;background:#f4f1e8;box-shadow:10px 14px 35px rgba(20,24,21,.28)}
html[data-style="shuimo"] .widget-detail>header{border-color:#263b3a;background:linear-gradient(105deg,#202824,#344b4a);text-shadow:none}html[data-style="shuimo"] .widget-detail dl,html[data-style="shuimo"] .widget-detail dt,html[data-style="shuimo"] .widget-detail dd{border-color:rgba(53,61,54,.3)}html[data-style="shuimo"] .widget-detail dt{background:rgba(52,75,74,.09);color:#62675f}html[data-style="shuimo"] .widget-detail dd,html[data-style="shuimo"] .widget-detail-note{background:#f8f5ec;color:#232521}
html[data-style="shuimo"][data-theme="dark"] .desktop-widget{border-color:#0d110f;background-color:#171b19;background-image:linear-gradient(rgba(23,27,25,.86),rgba(23,27,25,.91)),url('/static/themes/shuimo/mountain-panorama.webp');background-blend-mode:multiply,luminosity;color:#e7e2d6}
html[data-style="shuimo"][data-theme="dark"] .widget-subbar,html[data-style="shuimo"][data-theme="dark"] .widget-footer{border-color:rgba(216,210,192,.13);background:rgba(34,39,36,.8);color:#b4b5aa}html[data-style="shuimo"][data-theme="dark"] .record-row,html[data-style="shuimo"][data-theme="dark"] .schedule-row{border-color:rgba(216,210,192,.14);border-left-color:#7f9b92;background:rgba(34,39,36,.84);color:#e7e2d6}html[data-style="shuimo"][data-theme="dark"] .record-main small,html[data-style="shuimo"][data-theme="dark"] .schedule-main small,html[data-style="shuimo"][data-theme="dark"] .record-side small{color:#a7aaa1}

/* The BrowserWindow itself is transparent. Keep every widget skin inside one
   rounded clipping boundary so theme page backgrounds cannot fill the corners. */
html.desktop-widget-mode,html.desktop-widget-mode body,html.desktop-widget-mode #app{background:transparent!important;background-image:none!important}
html.desktop-widget-mode .desktop-widget{overflow:hidden;border-radius:14px!important;clip-path:inset(0 round 14px)}
html.desktop-widget-mode .widget-titlebar{overflow:hidden}
html.desktop-widget-mode .widget-detail-mask{border-radius:inherit}
html.desktop-widget-mode .widget-detail{overflow:hidden;border-radius:14px!important}

/* Classic keeps the calm native component language; pixel cosmetics above
   must never leak into the default widget or its record detail sheet. */
html[data-style="classic"] .record-view{border:0;border-radius:6px;background:#e6f1ec;color:#267758;box-shadow:none;font:700 9px inherit}
html[data-style="classic"] .widget-detail-mask{background:rgba(18,35,29,.46);backdrop-filter:blur(4px)}
html[data-style="classic"] .widget-detail{border:1px solid #9bb7ab;background:#f8faf9;box-shadow:0 18px 48px rgba(18,51,39,.2)}
html[data-style="classic"] .widget-detail>header{border-bottom:1px solid #cbdad4;background:#e7f0ec;color:#18332a;text-shadow:none}
html[data-style="classic"] .widget-detail>header button{border:0;border-radius:6px;background:#fff;color:#526b62;box-shadow:none}
html[data-style="classic"] .widget-detail-body{background:#f8faf9;background-image:none}
html[data-style="classic"] .widget-detail dl{border:0;border-radius:8px;overflow:hidden}
html[data-style="classic"] .widget-detail dt,html[data-style="classic"] .widget-detail dd{border:0;border-bottom:1px solid #dbe5e1}
html[data-style="classic"] .widget-detail dt{background:#eaf2ef;color:#526b62}
html[data-style="classic"] .widget-detail dd,html[data-style="classic"] .widget-detail-note{background:#fff;color:#18332a}
html[data-style="classic"] .widget-detail>footer{border-top:1px solid #dbe5e1;background:#edf4f1}
html[data-style="classic"] .detail-link{border:0;border-radius:7px;background:#267758;color:#fff;box-shadow:none;font:700 10px inherit}

/* High-chroma cyber widget skin. */
html[data-style="cyber"].desktop-widget-mode{--ink:#111923;--muted:#344650;--sub:#667177;--line:#68777b;--line2:#263e47;--blue:#006b78;--green:#007b59;--amber:#716900;--red:#c7194b;--panel:#eef0d9;font-family:"Zihun Bionic","Microsoft YaHei",sans-serif}
html[data-style="cyber"][data-theme="dark"].desktop-widget-mode{--blue:#00d9f5;--green:#00d68f;--amber:#f8e71c;--red:#ff2a5f}
html[data-style="cyber"].desktop-widget-mode .desktop-widget{border:3px solid #111923;border-radius:8px!important;color:#111923;background-color:#d3d7c7;background-image:linear-gradient(118deg,rgba(248,231,28,.43) 0 26%,transparent 26.2%),linear-gradient(rgba(17,25,35,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(17,25,35,.1) 1px,transparent 1px);background-size:100% 100%,28px 28px,28px 28px;box-shadow:inset 0 0 0 2px #00d9f5;clip-path:inset(0 round 8px)}
html[data-style="cyber"] .widget-titlebar{min-height:48px;padding:0 7px 0 13px;border-bottom:3px solid #111923;color:#111923;background:#f8e71c;text-shadow:2px 1px 0 rgba(255,255,255,.65);box-shadow:inset 0 -5px #ff2a5f}
html[data-style="cyber"] .widget-heading{gap:10px;letter-spacing:.1em}html[data-style="cyber"] .widget-heading:after{content:"//";color:#ff2a5f;text-shadow:2px 0 #00d9f5}
html[data-style="cyber"] .widget-mark{width:12px;height:12px;border:2px solid #111923;border-radius:0;background:#ff2a5f;box-shadow:4px 0 #00d9f5;transform:skew(-10deg)}
html[data-style="cyber"] .widget-actions button{width:27px;height:27px;border:2px solid #111923;border-radius:0;color:#f8e71c;background:#111923;box-shadow:3px 3px 0 #00d9f5;font-family:inherit}
html[data-style="cyber"] .widget-actions button:hover,html[data-style="cyber"] .widget-actions button.active{transform:translate(-2px,-2px);border-color:#111923;color:#111923;background:#00d9f5;box-shadow:5px 5px 0 #ff2a5f}
html[data-style="cyber"] .widget-actions button:last-child:hover{color:#fff;background:#ff2a5f}
html[data-style="cyber"] .widget-subbar{padding:8px 11px;border-bottom:3px solid #111923;color:#f1f0db;background:#172c35;font-family:inherit;box-shadow:inset 7px 0 #00d9f5}
html[data-style="cyber"] .widget-subbar:before{content:"// LIVE_FEED";color:#f8e71c;font-size:8px;letter-spacing:.08em}
html[data-style="cyber"] .widget-subbar button,html[data-style="cyber"] .widget-empty button{padding:3px 7px;border:2px solid #111923;border-radius:0;color:#111923;background:#f8e71c;box-shadow:3px 3px 0 #ff2a5f;font-family:inherit}
html[data-style="cyber"] .widget-body{padding:9px;background:transparent}
html[data-style="cyber"] .widget-body::-webkit-scrollbar{width:9px}html[data-style="cyber"] .widget-body::-webkit-scrollbar-track{background:#172c35}html[data-style="cyber"] .widget-body::-webkit-scrollbar-thumb{border:2px solid #172c35;border-radius:0;background:#f8e71c}
html[data-style="cyber"] .record-row,html[data-style="cyber"] .schedule-row{gap:10px;margin:0 0 8px;padding:10px;border:2px solid #111923;border-radius:0;color:#111923;background:#eff0da;box-shadow:5px 5px 0 rgba(17,25,35,.24),inset 5px 0 #00d9f5;clip-path:polygon(0 0,calc(100% - 10px) 0,100% 10px,100% 100%,7px 100%,0 calc(100% - 7px));transition:transform .12s steps(2,end),box-shadow .12s}
html[data-style="cyber"] .record-row:nth-child(3n+2),html[data-style="cyber"] .schedule-row:nth-child(3n+2){background:#e7e744;box-shadow:5px 5px 0 #00d9f5,inset 5px 0 #ff2a5f}
html[data-style="cyber"] .record-row:hover,html[data-style="cyber"] .schedule-row:hover{transform:translate(-3px,-3px);border-color:#111923;background:#00d9f5;box-shadow:8px 8px 0 #ff2a5f}
html[data-style="cyber"] .record-main small,html[data-style="cyber"] .schedule-main small,html[data-style="cyber"] .record-side small{color:#53646b}
html[data-style="cyber"] .record-side em{border:2px solid #111923;border-radius:0;color:#111923;background:#00d9f5;box-shadow:2px 2px 0 #ff2a5f;font-family:inherit}
html[data-style="cyber"] .record-side em[data-progress="已挂"],html[data-style="cyber"] .record-side em[data-progress="放弃"]{color:#fff;background:#ff2a5f}
html[data-style="cyber"] .record-view{border:2px solid #111923;border-radius:0;color:#111923;background:#f8e71c;box-shadow:2px 2px 0 #111923;font-family:inherit}
html[data-style="cyber"] .schedule-date{border-color:#111923}html[data-style="cyber"] .schedule-date b{color:#ff2a5f}html[data-style="cyber"] .schedule-date small{color:#111923;background:#00d9f5}
html[data-style="cyber"] .schedule-row i{border:2px solid #111923;border-radius:0;background:#00d68f;box-shadow:2px 2px 0 #111923}html[data-style="cyber"] .schedule-row i.urgent{background:#ff2a5f;box-shadow:2px 2px 0 #f8e71c}
html[data-style="cyber"] .widget-footer{border-top:3px solid #111923;color:#8ed5da;background:#172c35;font-family:inherit;box-shadow:inset 8px 0 #ff2a5f}
html[data-style="cyber"] .widget-detail-mask{background:rgba(23,44,53,.74);background-image:repeating-linear-gradient(180deg,transparent 0 4px,rgba(0,217,245,.08) 4px 5px)}
html[data-style="cyber"] .widget-detail{border:3px solid #111923;border-radius:6px!important;color:#111923;background:#eef0d9;box-shadow:9px 9px 0 #ff2a5f,-5px -5px 0 #00d9f5}
html[data-style="cyber"] .widget-detail>header{border-color:#111923;color:#111923;background:#f8e71c;text-shadow:3px 2px 0 rgba(0,217,245,.65)}
html[data-style="cyber"] .widget-detail>header button{border:2px solid #111923;color:#f8e71c;background:#111923;box-shadow:3px 3px 0 #00d9f5}
html[data-style="cyber"] .widget-detail-body{background:#d3d7c7;background-image:linear-gradient(rgba(17,25,35,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(17,25,35,.08) 1px,transparent 1px);background-size:22px 22px}
html[data-style="cyber"] .widget-detail dl,html[data-style="cyber"] .widget-detail dt,html[data-style="cyber"] .widget-detail dd{border-color:#111923}html[data-style="cyber"] .widget-detail dt{color:#111923;background:#00d9f5}html[data-style="cyber"] .widget-detail dd,html[data-style="cyber"] .widget-detail-note{color:#111923;background:#eef0d9}
html[data-style="cyber"] .widget-detail>footer{border-color:#111923;background:#172c35}html[data-style="cyber"] .detail-link{border:2px solid #111923;color:#111923;background:#f8e71c;box-shadow:3px 3px 0 #ff2a5f;font-family:inherit}
</style>
