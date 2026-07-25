<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import ProgressBadge from '@/components/ProgressBadge.vue'
import { get } from '@/utils/api'

const store = useDashboardStore()
const showShared = ref(false)
const sharedRecords = ref([])

const displayRecords = computed(() => showShared.value ? sharedRecords.value : store.records)

onMounted(async () => {
  if (!store.data) await store.fetch()
})

async function loadShared() {
  try {
    const d = await get('/api/dashboard/shared/records')
    sharedRecords.value = d.records || []
  } catch {
    sharedRecords.value = []
  }
}

watch(showShared, async (v) => {
  if (v) await loadShared()
})

function fmtDate(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return isNaN(d) ? '—' : (d.getMonth() + 1) + '/' + d.getDate()
}

function openDetail(r) {
  alert('记录详情弹窗将在下一阶段实现\n公司：' + r.company)
}

function newRecord() {
  alert('新建记录将在详情弹窗阶段实现')
}
</script>

<template>
  <div class="page active">
    <div class="card">
      <div class="card-hd">
        <span class="dot"></span>
        <div class="card-title">总表信息</div>
        <div class="card-sub">{{ displayRecords.length }} 条</div>
        <div class="total-view-switch" role="tablist" aria-label="总表范围">
          <button
            :class="{ active: !showShared }"
            role="tab"
            :aria-selected="!showShared"
            @click="showShared = false"
          >个人总表</button>
          <button
            :class="{ active: showShared }"
            role="tab"
            :aria-selected="showShared"
            @click="showShared = true"
          >共享总表</button>
        </div>
        <button v-if="!showShared" class="btn btn-primary" @click="newRecord">新建记录</button>
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
              <th>公司</th><th>目标岗位</th><th>方向</th><th>公司类型</th>
              <th>截止</th><th>批次</th><th>进展</th><th>入口</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="store.loading"><td colspan="9" class="center">加载中…</td></tr>
            <tr v-else-if="!displayRecords.length"><td colspan="9" class="center">暂无记录</td></tr>
            <tr v-for="r in displayRecords" :key="r.record_id">
              <td><button class="company-link" @click="openDetail(r)">{{ r.company || '—' }}</button></td>
              <td>{{ r.job || '—' }}</td>
              <td>{{ (r.dir||[]).join('、') || '—' }}</td>
              <td>{{ r.type || '—' }}</td>
              <td><span class="table-date">{{ fmtDate(r.deadline) }}</span></td>
              <td>{{ r.batch || '—' }}</td>
              <td><ProgressBadge :progress="(r.progress||[])[0]||'未投递'" /></td>
              <td><a v-if="r.url" :href="r.url" target="_blank" class="btn">入口</a><span v-else class="btn" style="opacity:0.35;pointer-events:none">入口</span></td>
              <td>
                <button class="btn" @click="openDetail(r)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
