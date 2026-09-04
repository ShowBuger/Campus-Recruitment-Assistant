<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import { useToastStore } from '@/stores/toast'
import { post } from '@/utils/api'
import { calculateOffer, DEFAULT_OFFER_WEIGHTS, hasOfferInfo, splitNotes, weightedOfferScore } from '@/utils/offerComparison'
import { PhBriefcase, PhCheck, PhPencilSimple, PhSlidersHorizontal, PhWarning } from '@phosphor-icons/vue'

const store = useDashboardStore()
const app = useAppStore()
const toast = useToastStore()
const selectedIds = ref([])
const weights = ref(loadWeights())
const aiLoading = ref(false)
const aiResult = ref(null)

const weightFields = [
  { key: 'compensation', label: '总薪酬' }, { key: 'growth', label: '职业成长' },
  { key: 'workLife', label: '工作生活' }, { key: 'culture', label: '团队文化' },
  { key: 'location', label: '地点通勤' },
]

const eligible = computed(() => store.records.filter(hasOfferInfo))
const selected = computed(() => selectedIds.value.map(id => eligible.value.find(record => record.record_id === id)).filter(Boolean))
const analyses = computed(() => {
  const calculations = selected.value.map(record => ({ record, ...calculateOffer(record) }))
  const maxComp = Math.max(0, ...calculations.map(item => item.yearOne))
  return calculations.map(item => {
    const compensationScore = maxComp ? item.yearOne / maxComp * 10 : 0
    const weighted = weightedOfferScore(item.record, weights.value, compensationScore)
    return { ...item, compensationScore, weightedScore: weighted.score, factors: weighted.factors }
  }).sort((a, b) => b.weightedScore - a.weightedScore)
})
const maxYearOne = computed(() => Math.max(1, ...analyses.value.map(item => item.yearOne)))
const weightTotal = computed(() => Object.values(weights.value).reduce((sum, value) => sum + Number(value || 0), 0))
const best = computed(() => analyses.value[0] || null)
const mixedCurrencies = computed(() => new Set(analyses.value.map(item => item.details.currency)).size > 1)

function loadWeights() {
  try { return { ...DEFAULT_OFFER_WEIGHTS, ...JSON.parse(localStorage.getItem('offer_compare_weights') || '{}') } }
  catch { return { ...DEFAULT_OFFER_WEIGHTS } }
}
function toggleRecord(id) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter(value => value !== id)
    : [...selectedIds.value, id]
}
function money(value, currency = 'CNY') {
  if (!Number(value)) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
}
function score(value) { return Number(value || 0).toFixed(1) }
function barWidth(value) { return `${Math.max(2, Number(value || 0) / maxYearOne.value * 100)}%` }
function factorLabel(key) { return weightFields.find(item => item.key === key)?.label || key }
async function runAiAnalysis() {
  if (selectedIds.value.length < 2 || aiLoading.value) return
  aiLoading.value = true
  aiResult.value = null
  try {
    aiResult.value = await post('/api/ai/offers/compare', {
      record_ids: selectedIds.value,
      weights: weights.value,
    }, { timeout: 250000, retries: 0 })
    toast.success('AI 深度分析已生成')
  } catch (error) {
    toast.error(error.message || 'AI 深度分析失败')
  } finally {
    aiLoading.value = false
  }
}

watch(weights, value => localStorage.setItem('offer_compare_weights', JSON.stringify(value)), { deep: true })
watch([selectedIds, weights], () => { aiResult.value = null }, { deep: true })
watch(eligible, records => {
  const valid = new Set(records.map(item => item.record_id))
  selectedIds.value = selectedIds.value.filter(id => valid.has(id))
  if (selectedIds.value.length < 2) selectedIds.value = records.slice(0, Math.min(3, records.length)).map(item => item.record_id)
}, { immediate: true })

onMounted(async () => { if (!store.data) await store.fetch() })
</script>

<template>
  <section class="page active offer-page">
    <header class="offer-page-intro">
      <div><h2>把不同结构的 Offer 放在同一把尺子上</h2><p>比较真实薪酬、长期价值、个人优先级与潜在风险。金额计算仅供决策参考。</p></div>
      <div class="offer-intro-actions"><div class="offer-count"><strong>{{ eligible.length }}</strong><span>份可比较 Offer</span></div><button class="btn btn-primary offer-ai-button" type="button" :disabled="selected.length < 2 || aiLoading" @click="runAiAnalysis">{{ aiLoading ? 'AI 分析中...' : 'AI 深度分析' }}</button></div>
    </header>

    <section class="offer-selector card">
      <div class="offer-section-head"><div><h3>选择岗位</h3><p>仅展示已填写 Offer 信息的岗位，至少选择 2 项。</p></div><span>{{ selected.length }} 项已选</span></div>
      <div v-if="eligible.length" class="offer-options">
        <button v-for="record in eligible" :key="record.record_id" type="button" :class="{ selected: selectedIds.includes(record.record_id) }" @click="toggleRecord(record.record_id)">
          <i><PhCheck :size="13" weight="bold" /></i><span><b>{{ record.company || '未命名公司' }}</b><small>{{ record.job || '未命名岗位' }} · {{ record.city || '城市未填' }}</small></span>
          <em>{{ money(calculateOffer(record).yearOne, calculateOffer(record).details.currency) }}</em>
        </button>
      </div>
      <div v-else class="offer-empty"><PhBriefcase :size="30" weight="duotone" /><b>还没有可比较的 Offer</b><p>在“总表信息”中打开岗位详情，填写 Offer 信息后即可选择。</p></div>
    </section>

    <template v-if="selected.length >= 2">
      <div v-if="mixedCurrencies" class="offer-currency-warning"><PhWarning :size="16" /><span>当前选择包含多种币种，系统不会自动换汇。请先按同一币种填写金额，再参考金额排名与综合结论。</span></div>
      <section v-if="aiLoading || aiResult" class="offer-ai-report card" aria-live="polite">
        <div class="offer-section-head"><div><h3>AI 深度分析</h3><p v-if="aiResult">{{ aiResult.provider }} · {{ aiResult.model }}</p><p v-else>正在结合薪酬结构、个人权重与风险信息生成建议</p></div></div>
        <div v-if="aiLoading" class="offer-ai-skeleton"><i></i><i></i><i></i><i></i></div>
        <div v-else class="offer-ai-content" v-html="aiResult.analysis_html"></div>
      </section>
      <section class="offer-decision-grid">
        <article class="offer-leader card">
          <span>当前综合领先</span><h3>{{ best.record.company }}</h3><p>{{ best.record.job }}</p>
          <strong>{{ score(best.weightedScore) }}</strong><small>加权得分 / 10</small>
          <button class="btn" type="button" @click="app.openDetail(best.record.record_id)"><PhPencilSimple :size="14" />完善信息</button>
        </article>
        <article class="offer-comp-chart card">
          <div class="offer-section-head"><div><h3>首年真实价值</h3><p>现金、折价后股权、福利与可量化权益之和</p></div></div>
          <div class="offer-bars">
            <div v-for="item in analyses" :key="item.record.record_id"><label><span>{{ item.record.company }}</span><b>{{ money(item.yearOne, item.details.currency) }}</b></label><i><span :style="{ width: barWidth(item.yearOne) }"></span></i></div>
          </div>
        </article>
      </section>

      <section class="offer-matrix card">
        <div class="offer-section-head"><div><h3>总薪酬模型</h3><p>签字费和搬迁补助只计入首年，股权按归属年限与风险折价计算。</p></div></div>
        <div class="offer-table-scroll"><table><thead><tr><th>指标</th><th v-for="item in analyses" :key="item.record.record_id">{{ item.record.company }}<small>{{ item.record.job }}</small></th></tr></thead><tbody>
          <tr><th>年基本工资</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.base, item.details.currency) }}</td></tr>
          <tr><th>签字费</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.signing, item.details.currency) }}</td></tr>
          <tr><th>年度奖金与佣金</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.bonus + item.commission, item.details.currency) }}</td></tr>
          <tr><th>折价后年度股权</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.annualEquity, item.details.currency) }}</td></tr>
          <tr><th>福利与权益</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.benefits + item.perks, item.details.currency) }}</td></tr>
          <tr class="offer-total-row"><th>首年总价值</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.yearOne, item.details.currency) }}</td></tr>
          <tr><th>持续年度价值</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.ongoing, item.details.currency) }}</td></tr>
          <tr><th>四年累计价值</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.fourYear, item.details.currency) }}</td></tr>
          <tr><th>估算首年税后</th><td v-for="item in analyses" :key="item.record.record_id">{{ money(item.netYearOne, item.details.currency) }}</td></tr>
        </tbody></table></div>
      </section>

      <section class="offer-analysis-layout">
        <article class="offer-weights card">
          <div class="offer-section-head"><div><h3><PhSlidersHorizontal :size="17" />你的决策权重</h3><p>得分会随个人优先级实时变化，无需凑整到 100。</p></div><b>{{ weightTotal }}</b></div>
          <label v-for="field in weightFields" :key="field.key"><span>{{ field.label }}</span><input v-model.number="weights[field.key]" type="range" min="0" max="100" step="5"><b>{{ weights[field.key] }}</b></label>
        </article>
        <article class="offer-scores card">
          <div class="offer-section-head"><div><h3>非货币因素</h3><p>团队文化综合了团队、直属主管和公司稳定性。</p></div></div>
          <div class="offer-score-table"><div class="head"><span>岗位</span><b v-for="field in weightFields" :key="field.key">{{ field.label }}</b><strong>综合</strong></div><div v-for="item in analyses" :key="item.record.record_id"><span>{{ item.record.company }}</span><b v-for="(_, key) in item.factors" :key="key" :title="factorLabel(key)">{{ score(item.factors[key]) }}</b><strong>{{ score(item.weightedScore) }}</strong></div></div>
        </article>
      </section>

      <section class="offer-context-grid">
        <article v-for="item in analyses" :key="item.record.record_id" class="offer-context card">
          <header><div><h3>{{ item.record.company }}</h3><p>{{ item.record.job }} · {{ item.details.remote_policy || '办公方式未确认' }} · 每周 {{ item.details.weekly_hours }} 小时</p></div><button type="button" @click="app.openDetail(item.record.record_id)" title="编辑 Offer"><PhPencilSimple :size="15" /></button></header>
          <dl><div><dt>成长与职责</dt><dd>{{ item.details.role_scope || '尚未填写' }}</dd></div><div><dt>股权说明</dt><dd>{{ item.details.equity_notes || '尚未填写' }}</dd></div><div><dt>福利说明</dt><dd>{{ item.details.benefits_notes || '尚未填写' }}</dd></div></dl>
          <div class="offer-action-list warning"><h4><PhWarning :size="15" />风险信号</h4><p v-if="!splitNotes(item.details.red_flags).length">暂无已记录风险</p><ul v-else><li v-for="note in splitNotes(item.details.red_flags)" :key="note">{{ note }}</li></ul></div>
          <div class="offer-action-list"><h4>决定前待确认</h4><p v-if="!splitNotes(item.details.questions).length">暂无待确认项</p><ul v-else><li v-for="note in splitNotes(item.details.questions)" :key="note">{{ note }}</li></ul></div>
          <div class="offer-action-list"><h4>谈判机会</h4><p>{{ item.details.negotiation || '尚未记录可谈判项' }}</p></div>
          <blockquote>{{ item.details.gut_feeling || '尚未记录直觉判断与长期目标。' }}</blockquote>
        </article>
      </section>
    </template>
    <div v-else-if="eligible.length" class="offer-need-more card"><b>再选择 {{ 2 - selected.length }} 个岗位即可开始比较</b><span>比较结果会在本页实时生成。</span></div>
  </section>
</template>

<style scoped>
.offer-page{display:grid;gap:16px;min-width:0}.offer-page-intro{display:flex;align-items:flex-end;justify-content:space-between;gap:24px}.offer-page-intro h2{max-width:720px;margin:0;color:var(--ink);font-size:24px;letter-spacing:-.035em}.offer-page-intro p{margin:7px 0 0;color:var(--muted);font-size:11px}.offer-intro-actions{display:flex;align-items:center;gap:13px}.offer-count{display:grid;justify-items:end}.offer-count strong{color:var(--blue);font-size:25px}.offer-count span{color:var(--muted);font-size:9px}.offer-ai-button{height:36px;white-space:nowrap}.offer-selector,.offer-matrix,.offer-weights,.offer-scores,.offer-comp-chart{overflow:hidden;padding:16px}.offer-section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.offer-section-head h3{display:flex;align-items:center;gap:7px;margin:0;color:var(--ink);font-size:13px}.offer-section-head p{margin:5px 0 0;color:var(--muted);font-size:9px}.offer-section-head>span,.offer-section-head>b{color:var(--blue);font-size:10px}.offer-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}.offer-options button{display:grid;grid-template-columns:22px minmax(0,1fr) auto;align-items:center;gap:9px;min-width:0;padding:11px;border:1px solid var(--line);border-radius:10px;color:var(--ink);text-align:left;background:var(--bg);cursor:pointer}.offer-options button.selected{border-color:var(--blue);background:var(--blueS);box-shadow:inset 3px 0 var(--blue)}.offer-options i{display:grid;width:18px;height:18px;place-items:center;border:1px solid var(--line2);border-radius:5px;color:transparent}.offer-options .selected i{border-color:var(--blue);color:#fff;background:var(--blue)}.offer-options span{display:grid;min-width:0;gap:3px}.offer-options b,.offer-options small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.offer-options b{font-size:10px}.offer-options small{color:var(--muted);font-size:8px}.offer-options em{color:var(--blue);font-size:9px;font-style:normal;font-weight:800}.offer-empty,.offer-need-more{display:grid;min-height:150px;place-content:center;justify-items:center;gap:7px;color:var(--muted);text-align:center}.offer-empty{margin-top:12px}.offer-empty b,.offer-need-more b{color:var(--ink);font-size:12px}.offer-empty p,.offer-need-more span{margin:0;font-size:9px}.offer-decision-grid{display:grid;grid-template-columns:240px minmax(0,1fr);gap:16px}.offer-leader{display:grid;padding:18px}.offer-leader>span{color:var(--muted);font-size:9px}.offer-leader h3{margin:8px 0 2px;font-size:19px}.offer-leader p{margin:0;color:var(--sub);font-size:10px}.offer-leader>strong{margin-top:15px;color:var(--blue);font-size:34px;line-height:1}.offer-leader>small{margin:3px 0 15px;color:var(--muted);font-size:8px}.offer-leader .btn{display:flex;align-items:center;justify-content:center;gap:6px}.offer-bars{display:grid;gap:13px;margin-top:17px}.offer-bars label{display:flex;justify-content:space-between;gap:16px;margin-bottom:5px;font-size:9px}.offer-bars label b{color:var(--ink)}.offer-bars i{display:block;height:9px;overflow:hidden;border-radius:3px;background:var(--bg)}.offer-bars i span{display:block;height:100%;border-radius:3px;background:var(--blue);transition:width .25s ease}.offer-table-scroll{margin-top:14px;overflow:auto}.offer-matrix table{width:100%;min-width:680px;border-collapse:collapse}.offer-matrix :is(th,td){padding:10px 12px;border-bottom:1px solid var(--line);font-size:9px;text-align:right}.offer-matrix th:first-child{text-align:left}.offer-matrix thead th{color:var(--ink);font-size:10px}.offer-matrix thead small{display:block;margin-top:3px;color:var(--muted);font-size:8px;font-weight:500}.offer-matrix tbody th{color:var(--sub);font-weight:600}.offer-total-row{color:var(--blue);background:var(--blueS)}.offer-total-row :is(th,td){font-weight:850}.offer-analysis-layout{display:grid;grid-template-columns:minmax(280px,.7fr) minmax(0,1.3fr);gap:16px}.offer-weights>label{display:grid;grid-template-columns:78px 1fr 28px;align-items:center;gap:9px;margin-top:12px;color:var(--sub);font-size:9px}.offer-weights input{width:100%;accent-color:var(--blue)}.offer-weights label b{text-align:right}.offer-score-table{margin-top:14px;overflow:auto}.offer-score-table>div{display:grid;grid-template-columns:minmax(92px,1.2fr) repeat(5,minmax(55px,.7fr)) minmax(55px,.7fr);align-items:center;min-width:550px;padding:9px 0;border-bottom:1px solid var(--line);font-size:9px}.offer-score-table .head{color:var(--muted);font-size:8px}.offer-score-table b,.offer-score-table strong{text-align:center}.offer-score-table strong{color:var(--blue);font-size:11px}.offer-context-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.offer-context{padding:16px}.offer-context header{display:flex;justify-content:space-between;gap:12px}.offer-context h3{margin:0;font-size:14px}.offer-context header p{margin:4px 0 0;color:var(--muted);font-size:8px}.offer-context header button{display:grid;width:30px;height:30px;place-items:center;border:1px solid var(--line);border-radius:8px;color:var(--sub);background:var(--bg);cursor:pointer}.offer-context dl{display:grid;gap:0;margin:14px 0}.offer-context dl>div{display:grid;grid-template-columns:88px 1fr;gap:12px;padding:9px 0;border-bottom:1px solid var(--line)}.offer-context dt{color:var(--muted);font-size:8px}.offer-context dd{margin:0;color:var(--ink);font-size:9px;line-height:1.55}.offer-action-list{margin-top:12px;padding:11px;border-radius:9px;background:var(--bg)}.offer-action-list.warning{background:var(--redS)}.offer-action-list h4{display:flex;align-items:center;gap:6px;margin:0 0 7px;font-size:9px}.offer-action-list p,.offer-action-list ul{margin:0;color:var(--sub);font-size:9px;line-height:1.65}.offer-action-list ul{padding-left:16px}.offer-context blockquote{margin:12px 0 0;padding-left:11px;border-left:3px solid var(--blue);color:var(--sub);font-size:9px;line-height:1.6}
.offer-currency-warning{display:flex;align-items:flex-start;gap:9px;padding:11px 13px;border:1px solid color-mix(in srgb,var(--amber) 45%,var(--line));border-radius:10px;color:var(--ink);background:var(--amberS);font-size:9px;line-height:1.55}.offer-currency-warning svg{flex:0 0 auto;color:var(--amber)}
.offer-ai-report{padding:18px}.offer-ai-skeleton{display:grid;gap:10px;margin-top:16px}.offer-ai-skeleton i{height:12px;border-radius:4px;background:var(--line);animation:offer-ai-pulse 1.2s ease-in-out infinite}.offer-ai-skeleton i:nth-child(2){width:88%}.offer-ai-skeleton i:nth-child(3){width:94%}.offer-ai-skeleton i:nth-child(4){width:72%}.offer-ai-content{margin-top:15px;color:var(--sub);font-size:10px;line-height:1.75}.offer-ai-content :deep(h1){margin:0 0 14px;color:var(--ink);font-size:18px}.offer-ai-content :deep(h2){margin:20px 0 8px;color:var(--ink);font-size:13px}.offer-ai-content :deep(p){margin:7px 0}.offer-ai-content :deep(ul),.offer-ai-content :deep(ol){margin:7px 0;padding-left:20px}.offer-ai-content :deep(table){width:100%;margin:10px 0;border-collapse:collapse}.offer-ai-content :deep(th),.offer-ai-content :deep(td){padding:8px;border:1px solid var(--line);text-align:left}.offer-ai-content :deep(blockquote){margin:10px 0;padding:9px 12px;border-left:3px solid var(--blue);background:var(--blueS)}@keyframes offer-ai-pulse{50%{opacity:.45}}
@media(max-width:1000px){.offer-options{grid-template-columns:repeat(2,minmax(0,1fr))}.offer-context-grid{grid-template-columns:1fr}}@media(max-width:760px){.offer-page-intro{align-items:flex-start;flex-direction:column}.offer-intro-actions{width:100%;justify-content:space-between}.offer-count{justify-items:start}.offer-options{grid-template-columns:1fr}.offer-decision-grid,.offer-analysis-layout{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.offer-bars i span{transition:none}.offer-ai-skeleton i{animation:none}}
</style>
