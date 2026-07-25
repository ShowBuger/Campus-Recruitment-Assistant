<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close'])
const store = useDashboardStore()
const app = useAppStore()
const toast = useToastStore()
const query = ref('')

const records = computed(() => store.data?.main?.recent || [])
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return records.value.map((r, i) => ({ record: r, index: i }))
  return records.value.map((r, i) => ({ record: r, index: i })).filter(item => {
    const haystack = [item.record.company, item.record.job, item.record.city, item.record.type, (item.record.dir || []).join(' ')].join(' ').toLowerCase()
    return haystack.includes(q)
  })
})

function openDetail(idx) {
  const r = records.value[idx]
  if (r?.record_id) { app.openDetail(r.record_id); emit('close') }
}

onMounted(() => { setTimeout(() => document.getElementById('record-manager-search')?.focus(), 40) })
</script>

<template>
  <div class="modal-mask show" @click.self="emit('close')">
    <div class="modal" style="width:min(720px,96vw)">
      <div class="modal-hd"><div><h2>查找记录</h2><p>搜索并打开需要查看或修改的记录。</p></div><button class="icon-btn" @click="emit('close')" title="关闭">&times;</button></div>
      <div class="modal-body">
        <div class="record-manager-search"><input id="record-manager-search" v-model="query" type="search" placeholder="搜索公司、岗位、城市、方向或类型"></div>
        <div class="tbl" style="max-height:55vh">
          <table><thead><tr><th>公司</th><th>目标岗位</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-if="!filtered.length"><td colspan="3" class="center">{{ query ? '没有匹配的记录' : '暂无记录' }}</td></tr>
            <tr v-for="item in filtered" :key="item.record.record_id">
              <td class="company"><button class="company-link" @click="openDetail(item.index)">{{ item.record.company || '—' }}</button></td>
              <td class="job">{{ item.record.job || '—' }}</td>
              <td><button class="btn" @click="openDetail(item.index)">打开详情</button></td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>
    </div>
  </div>
</template>
