<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'
import { get, del } from '@/utils/api'

const emit = defineEmits(['close'])
const store = useDashboardStore()
const app = useAppStore()
const toast = useToastStore()
const dialog = useDialogStore()
const query = ref('')
const sharedRecords = ref([])
const sharedCanDelete = ref(false)

const isShared = computed(() => app.managerShared)

const personalRecords = computed(() => store.data?.main?.records || [])
const allRecords = computed(() => isShared.value ? sharedRecords.value : personalRecords.value)

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allRecords.value.map((r, i) => ({ record: r, index: i }))
  return allRecords.value.map((r, i) => ({ record: r, index: i })).filter(item => {
    const haystack = [item.record.company, item.record.job, item.record.city, item.record.type, (item.record.dir || []).join(' '), item.record.contributor].join(' ').toLowerCase()
    return haystack.includes(q)
  })
})

onMounted(async () => {
  if (isShared.value) { await loadShared() }
  setTimeout(() => document.getElementById('record-manager-search')?.focus(), 40)
})

async function loadShared() {
  try {
    const d = await get('/api/dashboard/shared/records')
    sharedRecords.value = d.records || []
    sharedCanDelete.value = !!d.can_delete
  } catch { sharedRecords.value = [] }
}

function openDetail(r) {
  if (r?.record_id) { app.openDetail(r.record_id); emit('close') }
}

async function deleteShared(r) {
  const confirmed = await dialog.confirm(
    `确定从共享总表删除“${r.company || '该记录'}”吗？`,
    { title: '删除共享记录', tone: 'danger', confirmText: '删除记录' },
  )
  if (!confirmed) return
  try {
    await del('/api/dashboard/shared/records/' + encodeURIComponent(r.record_id))
    toast.success('共享记录已删除')
    await loadShared()
  } catch (e) { toast.error('删除失败: ' + e.message) }
}
</script>

<template>
  <div class="modal-mask show" @click.self="emit('close')">
    <div class="modal" style="width:min(720px,96vw)">
      <div class="modal-hd"><div><h2>{{ isShared ? '管理共享记录' : '查找记录' }}</h2><p>{{ isShared ? '搜索并管理共享总表中的记录。' : '搜索并打开需要查看或修改的记录。' }}</p></div><button class="icon-btn" @click="emit('close')" title="关闭">&times;</button></div>
      <div class="modal-body">
        <div class="record-manager-search"><input id="record-manager-search" v-model="query" type="search" :placeholder="isShared ? '搜索公司、岗位、城市、方向或类型' : '搜索公司、岗位、城市、方向或类型'"></div>
        <div class="tbl" style="max-height:55vh">
          <table><thead><tr><th>公司</th><th>目标岗位</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-if="!filtered.length"><td colspan="3" class="center">{{ query ? '没有匹配的记录' : '暂无记录' }}</td></tr>
            <tr v-for="item in filtered" :key="item.record.record_id">
              <td class="company">
                <button v-if="!isShared" class="company-link" @click="openDetail(item.record)">{{ item.record.company || '—' }}</button>
                <span v-else>{{ item.record.company || '—' }}</span>
              </td>
              <td class="job">{{ item.record.job || '—' }}</td>
              <td>
                <button v-if="!isShared" class="btn" @click="openDetail(item.record)">打开详情</button>
                <button v-if="isShared && sharedCanDelete" class="btn btn-danger" @click="deleteShared(item.record)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>
    </div>
  </div>
</template>
