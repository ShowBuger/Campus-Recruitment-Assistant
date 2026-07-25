<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import ProgressBadge from '@/components/ProgressBadge.vue'

const store = useDashboardStore()

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

onMounted(() => store.fetch())
</script>

<template>
  <div class="page">
    <!-- KPI Cards Row -->
    <div class="kpis">
      <div class="kpi-card">
        <span class="kpi-value">{{ store.kpi.total_companies }}</span>
        <span class="kpi-label">投递公司</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-value">{{ store.kpi.exam_count }}</span>
        <span class="kpi-label">笔试/机考</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-value">{{ store.kpi.interview_count }}</span>
        <span class="kpi-label">面试中</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-value">{{ store.kpi.offer_count }}</span>
        <span class="kpi-label">Offer</span>
      </div>
    </div>

    <!-- Main content: table + deadlines sidebar -->
    <div style="display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:16px">
      <!-- Records Table Card -->
      <div class="card data-table-card">
        <div class="card-hd record-card-hd">
          <span class="dot"></span>
          <div class="card-title">投递记录</div>
          <div class="record-hd-spacer"></div>
          <!-- Progress Filter -->
          <div class="progress-filter">
            <button class="progress-filter-toggle" @click="showFilter = !showFilter">
              <span>{{ activeFilter.length ? activeFilter.length + ' 个状态' : '筛选进展' }}</span>
            </button>
            <div class="progress-filter-menu" v-if="showFilter">
              <label v-for="p in progressOptions" :key="p" class="progress-filter-option">
                <input type="checkbox" :value="p" v-model="activeFilter" @change="applyFilter">
                <ProgressBadge :progress="p" />
              </label>
            </div>
          </div>
          <div class="card-sub">{{ filteredRecords.length }} 条</div>
        </div>

        <!-- Table -->
        <div class="tbl" style="max-height:440px">
          <table class="data-table records-table">
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
        <div class="countdown-list">
          <div v-if="!upcomingDeadlines.length" class="center muted">暂无临近截止</div>
          <div v-for="d in upcomingDeadlines" :key="d.company + d.job" class="countdown-item">
            <b>{{ d.company }}</b>
            <span>{{ d.job }}</span>
            <em>{{ formatDate(d.deadline) }}</em>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
