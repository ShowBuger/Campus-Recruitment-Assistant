<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">
    <div class="modal application-stats-modal">
      <div class="modal-hd">
        <div>
          <h2>投递统计</h2>
          <p>{{ '仅统计 ' + records.length + ' 家公司的当前主记录' }}</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>
      <div class="modal-body">
        <div class="stats-rate-grid">
          <article class="stats-rate-card">
            <div class="stats-rate-ring" :style="{ '--rate': examRate, '--chart-color': 'var(--amber)' }">
              <div><b>{{ examRate }}%</b><span>{{ examCount }} / {{ records.length }}</span></div>
            </div>
            <div class="stats-rate-copy"><b>笔试率</b><span>有笔试、机考时间或处于相应阶段</span></div>
          </article>
          <article class="stats-rate-card">
            <div class="stats-rate-ring" :style="{ '--rate': interviewRate, '--chart-color': 'var(--cyan)' }">
              <div><b>{{ interviewRate }}%</b><span>{{ interviewCount }} / {{ records.length }}</span></div>
            </div>
            <div class="stats-rate-copy"><b>面试率</b><span>有任一面试时间或已进入面试阶段</span></div>
          </article>
          <article class="stats-rate-card">
            <div class="stats-rate-ring" :style="{ '--rate': offerRate, '--chart-color': 'var(--green)' }">
              <div><b>{{ offerRate }}%</b><span>{{ offerCount }} / {{ records.length }}</span></div>
            </div>
            <div class="stats-rate-copy"><b>Offer 率</b><span>当前进展为 OC、Offer 或录用</span></div>
          </article>
        </div>
        <div class="stats-chart-grid">
          <section class="stats-chart">
            <h3>方向分布</h3>
            <div class="stats-chart-body">
              <div v-if="directionBars.length === 0" class="center">暂无数据</div>
              <div v-for="bar in directionBars" :key="bar[0]" class="bar">
                <div class="bar-row"><span>{{ bar[0] }}</span><strong>{{ bar[1] }}</strong></div>
                <div class="track"><div class="fill" :style="{ width: barWidth(bar[1], directionMax) + '%' }"></div></div>
              </div>
            </div>
          </section>
          <section class="stats-chart">
            <h3>公司类型</h3>
            <div class="stats-chart-body">
              <div v-if="companyTypeBars.length === 0" class="center">暂无数据</div>
              <div v-for="bar in companyTypeBars" :key="bar[0]" class="bar">
                <div class="bar-row"><span>{{ bar[0] }}</span><strong>{{ bar[1] }}</strong></div>
                <div class="track"><div class="fill g" :style="{ width: barWidth(bar[1], companyTypeMax) + '%' }"></div></div>
              </div>
            </div>
          </section>
          <section class="stats-chart">
            <h3>当前进展</h3>
            <div class="stats-chart-body">
              <div v-if="progressBars.length === 0" class="center">暂无数据</div>
              <div v-for="bar in progressBars" :key="bar[0]" class="bar">
                <div class="bar-row"><span>{{ bar[0] }}</span><strong>{{ bar[1] }}</strong></div>
                <div class="track"><div class="fill" :style="{ width: barWidth(bar[1], progressMax) + '%' }"></div></div>
              </div>
            </div>
          </section>
          <section class="stats-chart">
            <h3>批次分布</h3>
            <div class="stats-chart-body">
              <div v-if="batchBars.length === 0" class="center">暂无数据</div>
              <div v-for="bar in batchBars" :key="bar[0]" class="bar">
                <div class="bar-row"><span>{{ bar[0] }}</span><strong>{{ bar[1] }}</strong></div>
                <div class="track"><div class="fill g" :style="{ width: barWidth(bar[1], batchMax) + '%' }"></div></div>
              </div>
            </div>
          </section>
          <section class="stats-chart stats-chart-wide">
            <h3>投递城市</h3>
            <div class="stats-chart-body">
              <div v-if="cityBars.length === 0" class="center">暂无数据</div>
              <div v-for="bar in cityBars" :key="bar[0]" class="bar">
                <div class="bar-row"><span>{{ bar[0] }}</span><strong>{{ bar[1] }}</strong></div>
                <div class="track"><div class="fill" :style="{ width: barWidth(bar[1], cityMax) + '%' }"></div></div>
              </div>
            </div>
          </section>
        </div>
      </div>
      <div class="modal-ft">
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useRecordGroups } from '@/composables/useRecordGroups'

const emit = defineEmits(['close'])
const store = useDashboardStore()
const allRecords = computed(() => store.records || [])
const { groupedRecords } = useRecordGroups(allRecords)
const records = computed(() => groupedRecords.value.filter(record => {
  const progress = toArray(record?.progress)[0]
  return (progress && progress !== '未投递') || !!(record && (record.apply_date || record.exam_date || record.interview1 || record.interview2 || record.interview3 || record.warm || record.result))
}))

function toArray(v) {
  return Array.isArray(v) ? v : (v ? [v] : [])
}

function esc(s) {
  return String(s || '').replace(/[&<>"]/g, function(m) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]
  })
}

function applicationMilestones(record) {
  const progress = toArray(record && record.progress).join(' ')
  const offer = /\bOC\b|offer|录用/i.test(progress)
  const interview = !!(record && (record.interview1 || record.interview2 || record.interview3)) || offer || /面试/.test(progress)
  const exam = !!(record && record.exam_date) || /机考|笔试/.test(progress)
  return { exam, interview, offer }
}

function applicationDistribution(records, getter, splitValues) {
  const counts = new Map()
  records.forEach(function(record) {
    const values = toArray(getter(record))
    const seen = new Set()
    values.forEach(function(value) {
      const parts = splitValues ? String(value || '').split(/[,，、]+/) : [value]
      parts.forEach(function(part) {
        const name = String(part || '').trim()
        if (name) seen.add(name)
      })
    })
    seen.forEach(function(name) {
      counts.set(name, (counts.get(name) || 0) + 1)
    })
  })
  return Array.from(counts.entries()).sort(function(a, b) {
    return b[1] - a[1] || String(a[0]).localeCompare(String(b[0]), 'zh-CN')
  })
}

const examCount = computed(() => {
  let count = 0
  records.value.forEach(function(r) {
    if (applicationMilestones(r).exam) count++
  })
  return count
})
const interviewCount = computed(() => {
  let count = 0
  records.value.forEach(function(r) {
    if (applicationMilestones(r).interview) count++
  })
  return count
})
const offerCount = computed(() => {
  let count = 0
  records.value.forEach(function(r) {
    if (applicationMilestones(r).offer) count++
  })
  return count
})

const examRate = computed(() => records.value.length ? Math.round(examCount.value / records.value.length * 100) : 0)
const interviewRate = computed(() => records.value.length ? Math.round(interviewCount.value / records.value.length * 100) : 0)
const offerRate = computed(() => records.value.length ? Math.round(offerCount.value / records.value.length * 100) : 0)

const directionBars = computed(() => applicationDistribution(records.value, function(r) { return r.dir }, true))
const companyTypeBars = computed(() => applicationDistribution(records.value, function(r) { return r.type }))
const progressBars = computed(() => applicationDistribution(records.value, function(r) { return toArray(r.progress).slice(0, 1) }))
const batchBars = computed(() => applicationDistribution(records.value, function(r) { return r.batch }))
const cityBars = computed(() => applicationDistribution(records.value, function(r) { return r.city }, true))

const directionMax = computed(() => { const m = Math.max.apply(null, directionBars.value.map(function(x) { return x[1] })); return m || 1 })
const companyTypeMax = computed(() => { const m = Math.max.apply(null, companyTypeBars.value.map(function(x) { return x[1] })); return m || 1 })
const progressMax = computed(() => { const m = Math.max.apply(null, progressBars.value.map(function(x) { return x[1] })); return m || 1 })
const batchMax = computed(() => { const m = Math.max.apply(null, batchBars.value.map(function(x) { return x[1] })); return m || 1 })
const cityMax = computed(() => { const m = Math.max.apply(null, cityBars.value.map(function(x) { return x[1] })); return m || 1 })

function barWidth(count, max) {
  return Math.max(8, count / max * 100).toFixed(0)
}
</script>
<｜｜DSML｜｜parameter name="file_path" string="true">/home/ubuntu/Campus-Recruitment-Assistant/frontend/src/components/StatsModal.vue
