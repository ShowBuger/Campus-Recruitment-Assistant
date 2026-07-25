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

function deadlineDays(item) {
  if (!item.deadline) return null
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const dl = new Date(item.deadline)
  return Math.ceil((dl - today) / 86400000)
}

function formatDeadlineText(days) {
  if (days === null || days === undefined) return '—'
  if (days <= 0) return '今日'
  if (days === 1) return '明天'
  return '剩 ' + days + ' 天'
}

onMounted(() => store.fetch())
</script>

<template>
  <div class="page active">
    <!-- KPI Cards Row -->
    <div class="kpis">
      <div class="kpi b">
        <div class="kpi-label">投递岗位</div>
        <div class="kpi-value">{{ store.kpi.total_companies }}</div>
        <div class="kpi-sub">已进入投递流程</div>
      </div>
      <div class="kpi a">
        <div class="kpi-label">笔试 / 机考</div>
        <div class="kpi-value">{{ store.kpi.exam_count }}</div>
        <div class="kpi-sub">有笔试或机考记录</div>
      </div>
      <div class="kpi c">
        <div class="kpi-label">面试</div>
        <div class="kpi-value">{{ store.kpi.interview_count }}</div>
        <div class="kpi-sub">进入面试流程</div>
      </div>
      <div class="kpi g">
        <div class="kpi-label">Offer</div>
        <div class="kpi-value">{{ store.kpi.offer_count }}</div>
        <div class="kpi-sub">OC 或已录用</div>
      </div>
    </div>

    <!-- Main content: table + deadlines sidebar -->
    <div style="display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start;margin-bottom:22px">

      <!-- Records Table Card -->
      <div class="card data-table-card">
        <div class="card-hd record-card-hd">
          <span class="dot"></span>
          <div class="card-title">投递记录</div>
          <div class="record-hd-spacer"></div>

          <!-- Progress Filter -->
          <div class="progress-filter" :class="{ active: showFilter }">
            <button
              class="progress-filter-toggle"
              :class="{ 'has-filter': activeFilter.length > 0 }"
              @click="showFilter = !showFilter"
              aria-haspopup="dialog"
              :aria-expanded="showFilter"
            >
              <span>{{ activeFilter.length ? activeFilter.length + ' 个状态' : '筛选进展' }}</span>
            </button>
            <div class="progress-filter-backdrop" @click="showFilter = false" v-if="showFilter"></div>
            <div class="progress-filter-menu" v-if="showFilter" role="dialog" aria-modal="true" aria-labelledby="progress-filter-dialog-title">
              <div class="progress-filter-menu-hd">
                <div>
                  <b id="progress-filter-dialog-title">筛选投递进展</b>
                  <span>选择一个或多个状态</span>
                </div>
                <div class="progress-filter-dialog-actions">
                  <button type="button" class="progress-filter-clear" :disabled="activeFilter.length === 0" @click="activeFilter = []; showFilter = false">重置</button>
                  <button type="button" class="progress-filter-close" @click="showFilter = false" aria-label="关闭筛选">&times;</button>
                </div>
              </div>
              <div class="progress-filter-selected" v-if="activeFilter.length">
                <span v-for="p in activeFilter" :key="p" class="progress-filter-chip">
                  <span>{{ p }}</span>
                  <button @click="activeFilter = activeFilter.filter(x => x !== p)" aria-label="移除筛选">&times;</button>
                </span>
              </div>
              <div class="progress-filter-options">
                <label v-for="p in progressOptions" :key="p" class="progress-filter-option" :class="{ selected: activeFilter.includes(p) }">
                  <input type="checkbox" :value="p" v-model="activeFilter" @change="applyFilter">
                  <ProgressBadge :progress="p" />
                </label>
              </div>
            </div>
          </div>

          <div class="card-sub">{{ filteredRecords.length }} 条</div>
        </div>

        <!-- Table -->
        <div class="tbl" style="max-height:440px">
          <table class="data-table records-table">
            <colgroup>
              <col style="width:120px"><col style="width:145px"><col style="width:68px"><col style="width:88px">
              <col style="width:68px"><col style="width:58px"><col style="width:58px"><col style="width:58px"><col style="width:58px">
              <col style="width:58px"><col style="width:58px"><col style="width:68px"><col style="width:76px"><col style="width:58px">
            </colgroup>
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
        <div class="countdown-list" style="max-height:440px;overflow:auto">
          <div v-if="!upcomingDeadlines.length" class="center" style="padding:18px">暂无临近截止</div>
          <div v-for="d in upcomingDeadlines" :key="d.company + d.job" class="countdown-item">
            <div>
              <b>{{ d.company }}</b>
              <span>{{ d.job || '' }}</span>
            </div>
            <div class="countdown-days" :class="{ urgent: deadlineDays(d) <= 3 }">
              {{ formatDeadlineText(deadlineDays(d)) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
