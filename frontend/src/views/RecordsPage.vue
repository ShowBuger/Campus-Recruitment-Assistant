<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import ProgressBadge from '@/components/ProgressBadge.vue'
import { get, post } from '@/utils/api'

const emit = defineEmits(['open-detail'])
const store = useDashboardStore()
const showShared = ref(false)
const sharedRecords = ref([])
const sharedCanDelete = ref(false)
const searchQuery = ref('')
const sortValue = ref('default')

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
  if (!showShared.value && sortValue.value !== 'default') {
    const sorted = [...items]
    sorted.sort((a, b) => {
      const pa = priorityScore(a)
      const pb = priorityScore(b)
      if (pa === pb) return 0
      if (!pa) return 1
      if (!pb) return -1
      return sortValue.value === 'priority-desc' ? pb - pa : pa - pb
    })
    return sorted
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
  const map = { '高': 3, '中': 2, '低': 1 }
  return map[r.priority] || 0
}

function isApplied(r) {
  const progress = ((r && r.progress) || [])[0] || '未投递'
  return progress !== '未投递' || !!(r && (r.apply_date || r.exam_date || r.interview1 || r.interview2 || r.interview3 || r.warm || r.result))
}

function dirText(dir) {
  if (!dir) return '—'
  if (Array.isArray(dir)) return dir.filter(Boolean).join('、') || '—'
  return String(dir).trim() || '—'
}

function fmtDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return isNaN(d) ? '—' : (d.getMonth() + 1) + '/' + d.getDate()
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
  emit('open-detail', r.record_id)
}

/* ---- Personal tab actions ---- */
function newRecord() {
  /* placeholder - will open create modal */
}

function manageRecords() {
  /* placeholder - will open record manager */
}

function downloadTemplate() {
  const a = document.createElement('a')
  a.href = '/api/dashboard/records/template'
  a.download = '总表导入模板.xlsx'
  document.body.appendChild(a)
  a.click()
  a.remove()
}

function exportExcel() {
  const a = document.createElement('a')
  a.href = '/api/dashboard/records/export'
  a.download = '总表信息.xlsx'
  document.body.appendChild(a)
  a.click()
  a.remove()
}

function triggerImport() {
  const el = document.getElementById('total-import-file')
  if (el) el.click()
}

function handleImport(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return
  /* full implementation will be added later */
  event.target.value = ''
}

/* ---- Shared tab actions ---- */
function sharedNewRecord() {
  /* placeholder - will open shared create modal */
}

function sharedManageRecords() {
  /* placeholder - will open shared record manager */
}

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
    /* toast will be added later */
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
    /* toast will be added later */
  }
}
</script>

<template>
  <section class="page active" id="page-total">
    <div class="card data-table-card">
      <div class="card-hd">
        <span class="dot"></span>
        <div class="card-title">总表信息</div>
        <div class="card-sub">{{ recordCountText }}</div>
      </div>
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
        <select
          v-model="sortValue"
          :disabled="showShared"
          aria-label="总表排序方式"
        >
          <option value="default">默认排序</option>
          <option value="priority-desc">优先级：高到低</option>
          <option value="priority-asc">优先级：低到高</option>
        </select>
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
                <button class="company-link" @click="openDetail(r)">{{ r.company || '—' }}</button>
              </td>
              <td class="job" :title="r.job || ''">{{ r.job || '—' }}</td>
              <td>{{ dirText(r.dir) }}</td>
              <td>{{ r.type || '—' }}</td>
              <td><span class="table-date">{{ fmtDate(r.deadline) }}</span></td>
              <td><span class="badge bdg-b">{{ r.batch || '—' }}</span></td>
              <td v-if="showShared">{{ r.contributor || '—' }}</td>
              <td v-else><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td>
                <a v-if="r.url" :href="r.url" target="_blank" rel="noreferrer">查看</a><span v-else class="table-date">—</span>
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
        <button class="btn" @click="triggerImport">导入 Excel</button>
      </div>
      <div class="table-actions" v-else>
        <div
          id="shared-admin-actions"
          :style="{ display: sharedCanDelete ? 'flex' : 'none', gap: '9px' }"
        >
          <button class="btn btn-primary" @click="sharedNewRecord">新建记录</button>
          <button class="btn" @click="sharedManageRecords">管理记录</button>
        </div>
        <span class="muted">共享总表所有用户均可查看；完整个人记录可在“个人总表 → 管理记录”中上传。</span>
      </div>
    </div>
  </section>
</template>
