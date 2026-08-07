<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import ProgressBadge from '@/components/ProgressBadge.vue'
import { fmtDateChina, fmtDateFullChina } from '@/utils/date'
import { externalHttpUrl } from '@/utils/externalUrl'
import TooltipCell from '@/components/TooltipCell.vue'
import { get, post } from '@/utils/api'
import { useAppStore } from '@/stores/app'
import { useDialogStore } from '@/stores/dialog'
const app = useAppStore()
const store = useDashboardStore()
const auth = useAuthStore()
const dialog = useDialogStore()
const showShared = ref(false)
const hideApplied = ref(false)
const sharedRecords = ref([])
const sharedCanDelete = ref(false)
const searchQuery = ref('')
const sortValue = ref('default')
const importLoading = ref(false)
const feishuSyncing = ref(false)
const givemeocSyncing = ref(false)
const qiuzhiSyncing = ref(false)
const givemeocProgress = ref('')
const givemeocShow = ref(false)
const givemeocPhase = ref('scanning')
const givemeocLabel = ref('扫描岗位')
const givemeocPercent = ref('检索中')
const givemeocBarWidth = ref('36%')
const givemeocDetail = ref('正在查找 2027届 秋招岗位…')
const givemeocError = ref(false)
const givemeocIndeterminate = ref(false)
const canFeishuSync = computed(() => Boolean(auth.user?.is_root))
function isAdmin() { return auth.isAdmin }

const displayRecords = computed(() => {
  const records = showShared.value ? sharedRecords.value : store.records
  const query = searchQuery.value.trim().toLowerCase()
  let items = records
  if (query) {
    items = records.filter(r => {
      const haystack = [
        r.company,
        r.job,
        r.city,
        r.batch,
        r.type,
        r.priority,
        r.contributor,
        ...(r.dir || []),
        ...(r.progress || []),
      ].join(' ').toLowerCase()
      return haystack.indexOf(query) >= 0
    })
  }
  if (!showShared.value && hideApplied.value) {
    items = items.filter(r => !r.apply_date)
  }
  if (!showShared.value && sortValue.value !== 'default') {
    const sorted = items.map((r, i) => ({ r, i }))
    sorted.sort((a, b) => {
      const pa = priorityScore(a.r)
      const pb = priorityScore(b.r)
      if (pa === pb) return a.i - b.i
      if (!pa) return 1
      if (!pb) return -1
      return sortValue.value === 'priority-desc' ? pb - pa : pa - pb
    })
    return sorted.map(s => s.r)
  }
  return items
})

const recordCountText = computed(() => {
  const total = showShared.value ? sharedRecords.value.length : store.records.length
  const filtered = displayRecords.value.length
  const prefix = showShared.value ? '共享' : '个人'
  if (searchQuery.value.trim()) {
    return prefix + ' · ' + filtered + ' / ' + total + ' 条记录'
  }
  return prefix + ' · ' + total + ' 条记录'
})

function priorityScore(r) {
  return (String(r.priority || '').match(/⭐/g) || []).length
}

function isApplied(r) {
  const progress = ((r && r.progress) || [])[0] || '未投递'
  return progress !== '未投递' || !!(r && (r.apply_date || r.exam_date || r.interview1 || r.interview2 || r.interview3 || r.warm || r.result))
}

function dirText(dir) {
  if (!dir) return '-'
  if (Array.isArray(dir)) return dir.filter(Boolean).join('、') || '-'
  return String(dir).trim() || '-'
}

function fmtDate(ts) {
  return fmtDateChina(ts)
}
function fmtDateFull(ts) {
  return fmtDateFullChina(ts)
}

onMounted(async () => {
  if (!store.data) await store.fetch()
})

watch(showShared, async (v) => {
  if (v) {
    searchQuery.value = ''
    sortValue.value = 'default'
    await loadShared()
  }
})

async function switchTab(shared) {
  showShared.value = shared
}

async function loadShared() {
  try {
    const d = await get('/api/dashboard/shared/records')
    sharedRecords.value = d.records || []
    sharedCanDelete.value = !!d.can_delete
  } catch {
    sharedRecords.value = []
  }
}

function openDetail(r) {
  app.openDetail(r.record_id)
}

/* ---- Personal tab actions ---- */
function newRecord() { app.openRecord() }
function manageRecords() { app.openManager('records') }

function downloadTemplate() {
  downloadBlob('/api/dashboard/records/template', '总表导入模板.xlsx')
}

function exportExcel() {
  downloadBlob('/api/dashboard/records/export', '总表信息.xlsx')
}

async function downloadBlob(url, fallbackName) {
  try {
    const headers = {}
    if (auth.token) headers['Authorization'] = `Bearer ${auth.token}`
    const res = await fetch(url, { headers })
    if (!res.ok) throw new Error('HTTP ' + res.status)
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?([^";]+)"?/i)
    const name = match ? match[1] : fallbackName
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl; a.download = name
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  } catch (e) {
    await dialog.alert('下载失败：' + e.message, { title: '下载失败', tone: 'danger' })
  }
}

function triggerImport() {
  const el = document.getElementById('total-import-file')
  if (el) el.click()
}

async function handleImport(event) {
  const file = event.target.files?.[0]; if (!file) return
  const ext = (file.name || '').toLowerCase().split('.').pop()
  if (ext !== 'xlsx') {
    await dialog.alert('仅支持 .xlsx 格式的 Excel 文件。', { title: '文件格式不支持', tone: 'warning' })
    event.target.value = ''
    return
  }
  importLoading.value = true
  try {
    const fd = new FormData(); fd.append('file', file)
    const r = await fetch('/api/dashboard/records/import', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: fd })
    const data = await r.json()
    if (!r.ok) throw new Error(data.detail || '导入失败')
    await store.refresh()
    await dialog.alert(
      data.message || `成功导入 ${data.imported_count || 0} 条记录`,
      { title: '导入完成', tone: 'success' },
    )
  } catch (e) {
    await dialog.alert('导入失败：' + e.message, { title: '导入失败', tone: 'danger' })
  }
  finally { importLoading.value = false; event.target.value = '' }
}

async function feishuSync() {
  let savedUrl = ''
  try {
    const config = await get('/api/dashboard/records/feishu-sync')
    savedUrl = String(config?.url || '').trim()
  } catch (e) {
    await dialog.alert('无法读取飞书同步配置：' + e.message, { title: '读取配置失败', tone: 'danger' })
    return
  }
  const url = await dialog.prompt(
    savedUrl
      ? '已填入上次同步链接，直接确认即可同步；修改后会覆盖原链接。'
      : '粘贴需要同步的飞书电子表格链接，成功校验后会自动保存。',
    {
      title: '同步飞书表格',
      inputLabel: '飞书表格链接',
      initialValue: savedUrl,
      placeholder: 'https://example.feishu.cn/sheets/...',
      confirmText: '开始同步',
      required: true,
      tone: 'info',
    },
  )
  if (!url || !url.trim()) return
  feishuSyncing.value = true
  try {
    await post('/api/dashboard/records/feishu-sync', { url: url.trim() })
    await store.refresh()
  } catch (e) {
    await dialog.alert('飞书同步失败：' + e.message, { title: '同步失败', tone: 'danger' })
  }
  finally { feishuSyncing.value = false }
}

async function givemeocSync() {
  const confirmed = await dialog.confirm(
    '即将从 GiveMeOC 同步 2027 届岗位到共享总表。',
    { title: '同步招聘岗位', tone: 'info', confirmText: '开始同步' },
  )
  if (!confirmed) return
  givemeocSyncing.value = true; givemeocShow.value = true; givemeocError.value = false
  givemeocIndeterminate.value = true; givemeocLabel.value = '扫描岗位'
  givemeocPercent.value = '检索中'; givemeocBarWidth.value = '36%'
  givemeocDetail.value = '正在查找 2027届 秋招岗位…'
  let pollTimer = null
  const done = (msg, ok) => {
    clearInterval(pollTimer)
    givemeocIndeterminate.value = false; givemeocError.value = !ok
    givemeocLabel.value = ok ? '同步完成' : '同步失败'
    givemeocPercent.value = ok ? '100%' : '-'
    givemeocBarWidth.value = ok ? '100%' : '0'
    givemeocDetail.value = msg || '同步完成'
    givemeocSyncing.value = false
    if (msg) void dialog.alert(msg, {
      title: ok ? '同步完成' : '同步失败',
      tone: ok ? 'success' : 'danger',
    })
    loadShared()
    if (ok) givemeocShow.value = false
  }
  try {
    const start = await post('/api/dashboard/sync-from-givemeoc')
    pollTimer = setInterval(async () => {
      try {
        const p = await get('/api/dashboard/sync-from-givemeoc/progress?sync_id=' + encodeURIComponent(start.sync_id), { silent: true })
        const ratio = p.total ? Math.round((Number(p.done || 0) / p.total) * 100) : 0
        if (p.phase === 'scanning') {
          givemeocIndeterminate.value = true; givemeocLabel.value = '扫描岗位'
          givemeocPercent.value = (Number(p.found || 0)) + ' 条'; givemeocDetail.value = '正在筛选符合条件的招聘信息'
        } else if (p.phase === 'writing') {
          givemeocIndeterminate.value = false; givemeocLabel.value = '批量写入'
          givemeocPercent.value = '95%'; givemeocBarWidth.value = '95%'
          givemeocDetail.value = p.message || '正在去重并保存'
        } else {
          givemeocIndeterminate.value = false; givemeocLabel.value = '同步详情'
          givemeocPercent.value = ratio + '%'; givemeocBarWidth.value = Math.max(4, ratio) + '%'
          givemeocDetail.value = '已处理 ' + Number(p.done || 0) + ' / ' + Number(p.total || 0) + ' 条'
        }
        if (p.finished) { done(p.message, !p.failed) }
      } catch (e) { done('同步异常：' + e.message, false) }
    }, 800)
  } catch (err) {
    if (pollTimer) clearInterval(pollTimer)
    done('GiveMeOC 同步启动失败：' + err.message, false)
  }
}

function sharedNewRecord() { app.openRecord(true) }
function sharedManageRecords() { app.openManager(true) }

/* ---- Row actions ---- */
async function addToApplications(r) {
  if (!r || !r.record_id) return
  try {
    const result = await post('/api/dashboard/records/' + encodeURIComponent(r.record_id) + '/apply')
    if (result.dashboard) {
      store.data = result.dashboard
    } else {
      await store.refresh()
    }
  } catch (e) {
    await dialog.alert('加入投递失败：' + e.message, { title: '操作失败', tone: 'danger' })
  }
}

async function addToPersonal(r) {
  if (!r || !r.record_id || r.is_added) return
  try {
    const result = await post('/api/dashboard/shared/records/' + encodeURIComponent(r.record_id) + '/copy')
    r.is_added = true
    if (result.dashboard) {
      store.data = result.dashboard
    }
  } catch (e) {
    r.is_added = false
    await dialog.alert('添加失败：' + e.message, { title: '操作失败', tone: 'danger' })
  }
}

async function qiuzhiSync() {
  const confirmed = await dialog.confirm(
    '将同步求职方舟近 90 天的 2027 届秋招及提前批岗位到共享总表；其他届别和已过期岗位不会保留。',
    { title: '同步求职方舟岗位', tone: 'info', confirmText: '开始同步' },
  )
  if (!confirmed) return
  qiuzhiSyncing.value = true
  try {
    const data = await post('/api/dashboard/sync-from-qiuzhifangzhou')
    await dialog.alert(data.message || '求职方舟同步完成', { title: '同步完成', tone: 'success' })
    await loadShared()
  } catch (error) {
    await dialog.alert('求职方舟同步失败：' + error.message, { title: '同步失败', tone: 'danger' })
  } finally { qiuzhiSyncing.value = false }
}
</script>

<template>
  <section class="page active records-page" id="page-total">
    <div class="card data-table-card records-shell">
      <div class="total-tools">
        <div class="total-view-switch" role="tablist" aria-label="总表范围">
          <button
            :class="{ active: !showShared }"
            role="tab"
            :aria-selected="!showShared"
            @click="switchTab(false)"
          >个人总表</button>
          <button
            :class="{ active: showShared }"
            role="tab"
            :aria-selected="showShared"
            @click="switchTab(true)"
          >共享总表</button>
        </div>
        <div class="total-search">
          <input
            v-model="searchQuery"
            type="search"
            placeholder="查找公司、岗位、城市、方向或类型"
            aria-label="查找总表记录"
          >
        </div>
        <button v-if="showShared" class="btn btn-primary" @click="app.openRecommendation()">智能筛选</button>
        <select
          v-if="!showShared"
          v-model="sortValue"
          aria-label="总表排序方式"
        >
          <option value="default">默认排序</option>
          <option value="priority-desc">优先级：高到低</option>
          <option value="priority-asc">优先级：低到高</option>
        </select>
        <button v-if="!showShared" class="btn hide-applied-btn" :class="{ active: hideApplied }" @click="hideApplied = !hideApplied">{{ hideApplied ? '已隐藏' : '隐藏已投递' }}</button>
        <span class="records-inline-count">{{ recordCountText }}</span>
      </div>
      <div class="tbl" style="max-height:calc(100vh - 160px)">
        <table class="data-table master-table">
          <colgroup>
            <col style="width:14%">
            <col style="width:18%">
            <col style="width:13%">
            <col style="width:11%">
            <col style="width:9%">
            <col style="width:8%">
            <col style="width:10%">
            <col style="width:7%">
            <col style="width:10%">
          </colgroup>
          <thead>
            <tr>
              <th>公司</th>
              <th>目标岗位</th>
              <th>方向</th>
              <th>公司类型</th>
              <th>截止</th>
              <th>批次</th>
              <th id="total-status-head">{{ showShared ? '贡献者' : '进展' }}</th>
              <th>入口</th>
              <th class="total-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="store.loading"><td colspan="9" class="center">加载中…</td></tr>
            <tr v-else-if="!displayRecords.length"><td colspan="9" class="center">没有匹配的记录</td></tr>
            <tr v-for="r in displayRecords" :key="r.record_id">
              <td class="company">
                <button v-if="!showShared" class="company-link" @click="openDetail(r)">{{ r.company || '-' }}</button>
                <span v-else>{{ r.company || '-' }}</span>
              </td>
              <td class="job"><TooltipCell :text="r.job || '-'" /></td>
              <td><TooltipCell :text="dirText(r.dir)" /></td>
              <td><TooltipCell :text="r.type || '-'" /></td>
              <td><span class="table-date" :title="fmtDateFull(r.deadline)">{{ fmtDate(r.deadline) }}</span></td>
              <td><span class="badge bdg-b">{{ r.batch || '-' }}</span></td>
              <td v-if="showShared">{{ r.contributor || '-' }}</td>
              <td v-else><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td>
                <a v-if="externalHttpUrl(r.url)" :href="externalHttpUrl(r.url)" target="_blank" rel="noopener noreferrer">查看</a><span v-else class="table-date">-</span>
              </td>
              <td class="total-action">
                <button
                  v-if="!showShared"
                  class="btn"
                  :disabled="isApplied(r)"
                  @click="addToApplications(r)"
                >{{ isApplied(r) ? '已投递' : '加入投递' }}</button>
                <button
                  v-else
                  class="btn"
                  :disabled="r.is_added"
                  @click="addToPersonal(r)"
                >{{ r.is_added ? '已添加' : '添加个人' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="table-actions" v-if="!showShared">
        <button class="btn btn-primary" @click="newRecord">新增记录</button>
        <button class="btn" @click="manageRecords">管理记录</button>
        <button class="btn" @click="downloadTemplate">下载模板</button>
        <button class="btn" @click="exportExcel">导出 Excel</button>
        <input id="total-import-file" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden @change="handleImport">
        <button class="btn" @click="triggerImport" :disabled="importLoading">{{ importLoading ? '导入中...' : '导入 Excel' }}</button>
        <button v-if="canFeishuSync" class="btn" @click="feishuSync" :disabled="feishuSyncing">{{ feishuSyncing ? '同步中...' : '飞书同步' }}</button>
      </div>
      <div class="table-actions" v-else>
        <div
          id="shared-admin-actions"
          :style="{ display: 'flex', gap: '9px', flexWrap: 'wrap' }"
        >
          <button v-if="sharedCanDelete" class="btn btn-primary" @click="sharedNewRecord">新建记录</button>
          <button v-if="sharedCanDelete" class="btn" @click="sharedManageRecords">管理记录</button>
        </div>
        <span class="muted">共享总表所有用户均可查看；完整个人记录可在"个人总表 → 管理记录"中上传。</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.records-page{min-width:0}.records-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.records-page-head h2{margin:0;font-size:clamp(22px,2.5vw,30px);line-height:1.2;letter-spacing:-.035em}.records-page-head p{max-width:620px;margin-top:7px;color:var(--muted);font-size:13px}.records-count{display:flex;align-items:baseline;gap:7px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.records-count strong{color:var(--blue);font-size:18px}.records-count span{color:var(--sub);font-size:10px}.records-shell{overflow:hidden;border-radius:16px}.total-tools{display:grid;grid-template-columns:auto minmax(220px,1fr) auto auto auto;align-items:center;gap:9px;padding:13px 14px;border-bottom:1px solid var(--line);background:var(--panel)}.total-view-switch{padding:3px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}.total-view-switch button{height:31px;padding:0 13px;border:0;border-radius:7px;background:transparent;color:var(--muted);font:800 10px var(--font);cursor:pointer}.total-view-switch button.active{background:var(--panel);color:var(--ink);box-shadow:0 1px 5px color-mix(in srgb,var(--ink) 10%,transparent)}.total-search input,.total-tools>select{height:39px;border:1px solid var(--line2);border-radius:10px;outline:none;background:var(--bg);color:var(--ink);font:11px var(--font)}.total-search input{width:100%;padding:0 12px}.total-tools>select{padding:0 30px 0 10px}.total-search input:focus,.total-tools>select:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blueS)}.records-shell .tbl{background:var(--panel)}.records-shell .table-actions{min-height:58px;padding:10px 14px;border-top:1px solid var(--line);background:var(--bg)}.master-table tbody tr{transition:background .15s ease}.master-table tbody tr:hover{background:var(--blueS)}.master-table .total-action .btn{min-width:72px}.hide-applied-btn.active{border-color:var(--blue);background:var(--blueS);color:var(--blue)}@media(max-width:1100px){.total-tools{grid-template-columns:auto minmax(200px,1fr) auto}.total-tools>.btn,.total-tools>select{grid-row:2}}@media(max-width:720px){.records-page-head{align-items:flex-start;flex-direction:column}.records-count{width:100%;justify-content:space-between}.total-tools{grid-template-columns:1fr}.total-tools>*{width:100%}.total-tools>.btn,.total-tools>select{grid-row:auto}.total-view-switch{display:grid;grid-template-columns:1fr 1fr}.records-shell{border-radius:12px}}@media(prefers-reduced-motion:reduce){.master-table tbody tr{transition:none}}
.total-search input{padding-left:40px}.records-inline-count{justify-self:end;color:var(--sub);font-size:10px;white-space:nowrap}@media(max-width:1100px){.records-inline-count{grid-row:2;justify-self:end}}@media(max-width:720px){.records-inline-count{grid-row:auto;justify-self:start}}
</style>
