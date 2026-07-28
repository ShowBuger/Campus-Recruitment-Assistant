<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">>
    <div class="modal offer-compare-modal">
      <div class="modal-hd">
        <div>
          <h2>Offer 对比</h2>
          <p>{{ '并排对比进展为 OC 的 ' + offers.length + ' 个岗位' }}</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>
      <div class="modal-body">
        <div v-if="offers.length === 0" class="center">
          暂无 OC 记录。<br>把某条记录的进展改为「OC」，并在记录详情的「Offer 信息」里填写总包等信息，即可在此并排对比。
        </div>
        <div v-else class="offer-compare-scroll">
          <table class="offer-compare-table">
            <thead>
              <tr>
                <th class="offer-dim">对比项</th>
                <th v-for="(o, i) in offers" :key="i">
                  <span class="company-link">{{ o.record.company || '—' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="offer-dim">总包</td>
                <td v-for="(o, i) in offers" :key="i">
                  {{ o.record.offer_total || '—' }}
                  <span v-if="i === maxIdx && maxVal > 0 && offers.length > 1" class="offer-best">最高</span>
                </td>
              </tr>
              <tr>
                <td class="offer-dim">base（月/年）</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.offer_base || '—' }}</td>
              </tr>
              <tr>
                <td class="offer-dim">奖金/股票/补贴</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.offer_bonus || '—' }}</td>
              </tr>
              <tr>
                <td class="offer-dim">城市</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.city || '—' }}</td>
              </tr>
              <tr>
                <td class="offer-dim">方向</td>
                <td v-for="(o, i) in offers" :key="i">{{ (toArray(o.record.dir).join('、') || '—') }}</td>
              </tr>
              <tr>
                <td class="offer-dim">岗位</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.job || '—' }}</td>
              </tr>
              <tr>
                <td class="offer-dim">决策截止</td>
                <td v-for="(o, i) in offers" :key="i">
                  <span v-if="o.record.offer_deadline">{{ fmtShortDate(o.record.offer_deadline) }}</span>
                  <span v-else>&mdash;</span>
                </td>
              </tr>
              <tr>
                <td class="offer-dim">优先级</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.priority || '—' }}</td>
              </tr>
              <tr>
                <td class="offer-dim">备注</td>
                <td v-for="(o, i) in offers" :key="i">{{ o.record.note || '—' }}</td>
              </tr>
            </tbody>
          </table>
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
import { fmtDateChina } from '@/utils/date'

defineEmits(['close'])
const store = useDashboardStore()

function toArray(v) {
  return Array.isArray(v) ? v : (v ? [v] : [])
}

function parseSalaryNum(s) {
  const t = String(s || '').replace(/,/g, '')
  const m = t.match(/\d+(\.\d+)?/)
  if (!m) return null
  let n = parseFloat(m[0])
  if (/[wW万]/.test(t)) n *= 10000
  else if (/[kK千]/.test(t)) n *= 1000
  return n
}

function fmtShortDate(v) {
  return fmtDateChina(v)
}

const records = computed(() => store.records || [])

const offers = computed(() => {
  const all = records.value
  return all.map(function(r, i) { return { record: r, index: i } })
    .filter(function(it) {
      const p = toArray(it.record.progress)
      return p.indexOf('OC') >= 0 || p.indexOf('Offer') >= 0
    })
})

const maxIdx = computed(() => {
  const nums = offers.value.map(function(o) { return parseSalaryNum(o.record.offer_total) })
  let maxIdx = -1, maxVal = -1
  nums.forEach(function(n, i) {
    if (n != null && n > maxVal) { maxVal = n; maxIdx = i }
  })
  return maxIdx
})

const maxVal = computed(() => {
  const nums = offers.value.map(function(o) { return parseSalaryNum(o.record.offer_total) })
  let maxVal = -1
  nums.forEach(function(n) {
    if (n != null && n > maxVal) maxVal = n
  })
  return maxVal
})
</script>
