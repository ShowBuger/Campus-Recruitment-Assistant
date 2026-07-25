<template>
  <div class="modal-mask show" @click.self="$emit('close')">
    <div class="modal" style="width:min(820px,96vw)">
      <div class="modal-hd">
        <div>
          <h2>管理记录</h2>
          <p>搜索、批量操作或查看个人总表中的全部记录。</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>

      <div class="modal-body">
        <!-- Search -->
        <div class="record-manager-search">
          <input
            ref="searchInput"
            v-model="query"
            type="search"
            placeholder="搜索公司、岗位、城市、方向或类型"
          >
        </div>

        <!-- Batch action bar -->
        <div v-if="selectedIds.length" class="batch-bar">
          <span class="batch-count">已选 {{ selectedIds.length }} 条</span>
          <button class="btn btn-danger" @click="batchDelete" :disabled="batchLoading">批量删除</button>
          <button class="btn" @click="showProgressPicker = true" :disabled="batchLoading">批量更新进展</button>
          <button class="btn" @click="showPriorityPicker = true" :disabled="batchLoading">批量设置优先级</button>
          <button class="btn" @click="clearSelection">清除选择</button>
        </div>

        <!-- Progress picker sub-bar -->
        <div v-if="showProgressPicker" class="batch-sub-bar">
          <label>更新进展为：</label>
          <select v-model="batchProgress" class="batch-select">
            <option value="未投递">未投递</option>
            <option value="已投递">已投递</option>
            <option value="机考">机考</option>
            <option value="面试">面试</option>
            <option value="OC">OC</option>
            <option value="已挂">已挂</option>
            <option value="放弃">放弃</option>
          </select>
          <button class="btn btn-primary" @click="confirmBatchProgress" :disabled="batchLoading">{{ batchLoading ? '处理中…' : '确认更新' }}</button>
          <button class="btn" @click="showProgressPicker = false">取消</button>
        </div>

        <!-- Priority picker sub-bar -->
        <div v-if="showPriorityPicker" class="batch-sub-bar">
          <label>设置优先级为：</label>
          <select v-model="batchPriority" class="batch-select">
            <option value="⭐⭐⭐⭐⭐">⭐⭐⭐⭐⭐</option>
            <option value="⭐⭐⭐⭐">⭐⭐⭐⭐</option>
            <option value="⭐⭐⭐">⭐⭐⭐</option>
            <option value="⭐⭐">⭐⭐</option>
            <option value="⭐">⭐</option>
          </select>
          <button class="btn btn-primary" @click="confirmBatchPriority" :disabled="batchLoading">{{ batchLoading ? '处理中…' : '确认设置' }}</button>
          <button class="btn" @click="showPriorityPicker = false">取消</button>
        </div>

        <!-- Table -->
        <div class="tbl" style="max-height:55vh">
          <table>
            <colgroup>
              <col style="width:40px">
              <col style="width:auto">
              <col style="width:auto">
              <col style="width:100px">
              <col style="width:90px">
              <col style="width:80px">
            </colgroup>
            <thead>
              <tr>
                <th>
                  <label class="checkbox-label">
                    <input type="checkbox" :checked="allSelected" :indeterminate="someSelected && !allSelected" @change="toggleAll">
                  </label>
                </th>
                <th>公司</th>
                <th>目标岗位</th>
                <th>进展</th>
                <th>优先级</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!filteredRecords.length">
                <td colspan="6" class="center">{{ query ? '没有匹配的记录' : '暂无记录' }}</td>
              </tr>
              <tr v-for="r in filteredRecords" :key="r.record_id">
                <td>
                  <label class="checkbox-label">
                    <input type="checkbox" :checked="selectedIds.includes(r.record_id)" @change="toggleSelect(r.record_id)">
                  </label>
                </td>
                <td class="company">{{ r.company || '—' }}</td>
                <td class="job" :title="r.job || ''">{{ r.job || '—' }}</td>
                <td><span class="badge bdg-b">{{ (r.progress || [])[0] || '未投递' }}</span></td>
                <td>{{ r.priority || '—' }}</td>
                <td>
                  <div class="manager-actions">
                    <button class="btn btn-danger" @click="deleteSingle(r)" :disabled="batchLoading">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close'])
const store = useDashboardStore()
const toast = useToastStore()

// Search
const query = ref('')
const searchInput = ref(null)

// Selection
const selectedIds = ref([])
const batchLoading = ref(false)

// Batch sub-bars
const showProgressPicker = ref(false)
const showPriorityPicker = ref(false)
const batchProgress = ref('已投递')
const batchPriority = ref('⭐⭐⭐')

// ── helpers ──────────────────────────────────────────────

function tokenHeader() {
  const t = localStorage.getItem('rb_token')
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...tokenHeader() },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

function progressValue(r) {
  return (Array.isArray(r.progress) ? r.progress[0] : r.progress) || '未投递'
}

// ── computed ─────────────────────────────────────────────

const records = computed(() => store.records || [])

const filteredRecords = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter(r => {
    const haystack = [
      r.company, r.job, r.city, r.type,
      Array.isArray(r.dir) ? r.dir.join(' ') : '',
    ].join(' ').toLowerCase()
    return haystack.indexOf(q) >= 0
  })
})

const allSelected = computed(() => {
  if (!filteredRecords.value.length) return false
  return filteredRecords.value.every(r => selectedIds.value.includes(r.record_id))
})

const someSelected = computed(() => {
  return filteredRecords.value.some(r => selectedIds.value.includes(r.record_id))
})

// ── selection actions ───────────────────────────────────

function toggleAll() {
  if (allSelected.value) {
    const ids = new Set(filteredRecords.value.map(r => r.record_id))
    selectedIds.value = selectedIds.value.filter(id => !ids.has(id))
  } else {
    const existing = new Set(selectedIds.value)
    for (const r of filteredRecords.value) {
      existing.add(r.record_id)
    }
    selectedIds.value = Array.from(existing)
  }
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value = selectedIds.value.filter(x => x !== id)
  } else {
    selectedIds.value.push(id)
  }
}

function clearSelection() {
  selectedIds.value = []
  showProgressPicker.value = false
  showPriorityPicker.value = false
}

// ── single delete ───────────────────────────────────────

async function deleteSingle(r) {
  const name = r.company || '该记录'
  if (!confirm(`确定永久删除"${name}"吗？此操作不可撤销。`)) return
  batchLoading.value = true
  try {
    await apiPost(`/api/dashboard/records/${encodeURIComponent(r.record_id)}/permanent-delete`)
    await store.refresh()
    toast.success(`已删除"${name}"`)
  } catch (err) {
    toast.error('删除失败：' + err.message)
  } finally {
    batchLoading.value = false
  }
}

// ── batch delete ────────────────────────────────────────

async function batchDelete() {
  if (!selectedIds.value.length) return
  if (!confirm(`确定永久删除选中的 ${selectedIds.value.length} 条记录吗？此操作不可撤销。`)) return
  batchLoading.value = true
  let success = 0
  for (const id of selectedIds.value) {
    try {
      await apiPost(`/api/dashboard/records/${encodeURIComponent(id)}/permanent-delete`)
      success++
    } catch (err) {
      toast.error(`删除失败（${id}）：${err.message}`)
    }
  }
  await store.refresh()
  selectedIds.value = []
  toast.success(`已删除 ${success} 条记录`)
  batchLoading.value = false
}

// ── batch update progress ──────────────────────────────

async function confirmBatchProgress() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  let success = 0
  for (const id of selectedIds.value) {
    try {
      const r = store.records.find(x => x.record_id === id)
      if (!r) continue
      await apiPost(`/api/dashboard/records/${encodeURIComponent(id)}/master/update`, {
        company: r.company || '',
        job: r.job || '',
        city: r.city || '',
        batch: r.batch || '秋招',
        progress: batchProgress.value,
        directions: Array.isArray(r.dir) ? r.dir : [],
        company_type: r.type || '',
        url: r.url || '',
        priority: r.priority || '⭐⭐⭐',
      })
      success++
    } catch (err) {
      toast.error(`更新进展失败（${id}）：${err.message}`)
    }
  }
  await store.refresh()
  selectedIds.value = []
  showProgressPicker.value = false
  toast.success(`已更新 ${success} 条记录的进展为"${batchProgress.value}"`)
  batchLoading.value = false
}

// ── batch set priority ─────────────────────────────────

async function confirmBatchPriority() {
  if (!selectedIds.value.length) return
  batchLoading.value = true
  let success = 0
  for (const id of selectedIds.value) {
    try {
      const r = store.records.find(x => x.record_id === id)
      if (!r) continue
      await apiPost(`/api/dashboard/records/${encodeURIComponent(id)}/master/update`, {
        company: r.company || '',
        job: r.job || '',
        city: r.city || '',
        batch: r.batch || '秋招',
        progress: progressValue(r),
        directions: Array.isArray(r.dir) ? r.dir : [],
        company_type: r.type || '',
        url: r.url || '',
        priority: batchPriority.value,
      })
      success++
    } catch (err) {
      toast.error(`设置优先级失败（${id}）：${err.message}`)
    }
  }
  await store.refresh()
  selectedIds.value = []
  showPriorityPicker.value = false
  toast.success(`已设置 ${success} 条记录的优先级为"${batchPriority.value}"`)
  batchLoading.value = false
}

// ── mount ────────────────────────────────────────────────

onMounted(async () => {
  if (!store.data) await store.fetch()
  nextTick(() => {
    if (searchInput.value) searchInput.value.focus()
  })
})
</script>
