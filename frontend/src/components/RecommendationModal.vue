<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { get, post } from '@/utils/api'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close'])
const toast = useToastStore()
const preference = ref('')
const resumeFilename = ref('')
const resumes = ref([])
const loading = ref(false)
const result = ref(null)
const progress = ref(null)
const histories = ref([])
const historyLoading = ref(false)
const activeHistoryId = ref('')
let pollTimer = null

const gradeTitle = { S: '强烈推荐', A: '优先推荐', B: '值得关注', C: '备选岗位' }
const items = computed(() => result.value?.items || [])

async function runRecommendation() {
  loading.value = true
  result.value = null
  progress.value = { phase: 'preparing', message: '正在创建筛选任务…', completed_chunks: 0, total_chunks: 0 }
  try {
    const started = await post('/api/recommendations', {
      preference: preference.value,
      resume_filename: resumeFilename.value,
    })
    activeHistoryId.value = started.run_id
    await loadHistory()
    await pollRecommendation(started.run_id)
    await loadHistory()
    if (!items.value.length) toast.info('没有达到当前推荐门槛的岗位，可在设置中降低最低分。')
  } catch (error) {
    toast.error(error.message || '岗位筛选失败')
  } finally {
    loading.value = false
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  }
}

async function pollRecommendation(runId) {
  while (loading.value) {
    const state = await get('/api/recommendations/' + encodeURIComponent(runId), { timeout: 15000 })
    progress.value = state
    updateHistory(runId, state)
    if (state.status === 'finished') {
      result.value = state.result
      return
    }
    if (state.status === 'failed') throw new Error(state.message || '岗位筛选失败')
    await new Promise(resolve => { pollTimer = setTimeout(resolve, 900) })
  }
}

async function loadHistory() {
  historyLoading.value = true
  try { histories.value = (await get('/api/recommendations/history')).items || [] }
  catch { histories.value = [] }
  finally { historyLoading.value = false }
}

function updateHistory(runId, state) {
  const index = histories.value.findIndex(item => item.id === runId)
  if (index < 0) return
  histories.value[index] = { ...histories.value[index], ...state, id: runId,
    result_count: state.result?.items?.length ?? histories.value[index].result_count }
}

async function viewHistory(history) {
  activeHistoryId.value = history.id
  try {
    const data = await get('/api/recommendations/history/' + encodeURIComponent(history.id))
    progress.value = data
    if (data.result?.items) result.value = data.result
    else result.value = null
  } catch (error) { toast.error(error.message || '读取筛选历史失败') }
}

function historyTime(value) {
  if (!value) return '刚刚'
  const date = new Date(String(value).replace(' ', 'T') + (String(value).includes('Z') ? '' : 'Z'))
  return isNaN(date) ? String(value) : `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function deadline(value) {
  if (!value) return '无截止日期'
  const date = new Date(value)
  return isNaN(date) ? '无截止日期' : `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

async function addToPersonal(job) {
  if (!job?.record_id || job.is_added || job.adding) return
  job.adding = true
  try {
    const data = await post('/api/dashboard/shared/records/' + encodeURIComponent(job.record_id) + '/copy')
    job.is_added = true
    toast.success(data.message || '已添加到个人总表')
  } catch (error) {
    toast.error(error.message || '添加到个人总表失败')
  } finally {
    job.adding = false
  }
}

onMounted(async () => {
  try { resumes.value = (await get('/api/resumes')).files || [] } catch { resumes.value = [] }
  loadHistory()
})

onUnmounted(() => { loading.value = false; if (pollTimer) clearTimeout(pollTimer) })
</script>

<template>
  <div class="modal-mask show" @click.self="emit('close')">
    <div class="modal recommendation-modal">
      <div class="modal-hd">
        <div><h2>智能岗位筛选</h2><p>按输入偏好和已上传简历，从共享总表中分级推荐合适岗位。</p></div>
        <button class="icon-btn" @click="emit('close')" title="关闭">&times;</button>
      </div>
      <div class="modal-body recommendation-body">
        <div class="recommendation-form">
          <div class="form-group"><label for="recommend-preference">岗位偏好</label>
            <textarea id="recommend-preference" v-model="preference" rows="3" placeholder="例如：上海或杭州，嵌入式 Linux / BSP / 驱动，偏 C++，机器人或汽车电子方向"></textarea>
          </div>
          <div class="form-group"><label for="recommend-resume">关联简历（可选）</label>
            <select id="recommend-resume" v-model="resumeFilename"><option value="">不使用简历，仅按偏好筛选</option><option v-for="file in resumes" :key="file.name" :value="file.name">{{ file.name }}</option></select>
          </div>
          <button class="btn btn-primary" :disabled="loading" @click="runRecommendation">{{ loading ? '正在匹配…' : '开始智能筛选' }}</button>
        </div>

        <div v-if="loading && progress" class="recommendation-progress" role="status">
          <div><b>{{ progress.phase === 'summarizing' ? '正在压缩简历' : progress.phase === 'ranking' ? '正在筛选岗位' : '正在准备' }}</b><span>{{ progress.message }}</span></div>
          <div v-if="progress.total_chunks" class="recommendation-progress-track"><i :style="{ width: Math.round((progress.completed_chunks || 0) / progress.total_chunks * 100) + '%' }"></i></div>
          <small v-if="progress.total_chunks">第 {{ progress.completed_chunks || 0 }} / {{ progress.total_chunks }} 批（每批最多 45 个岗位，最多 3 批并行）</small>
        </div>

        <div v-if="result" class="recommendation-result">
          <div class="recommendation-summary">扫描 {{ result.scanned }} 条共享岗位 · {{ result.resume_used ? '已结合简历' : '按岗位偏好' }} · {{ items.length }} 条推荐<span v-if="result.partial">（当前已完成批次，结果将继续追加）</span></div>
          <div v-if="!items.length" class="center muted">没有匹配岗位。可补充偏好、选择简历，或在设置中降低最低推荐分。</div>
          <div v-if="items.length" class="recommendation-columns" aria-hidden="true">
            <span>推荐</span><span>公司</span><span>岗位</span><span>地点 / 方向</span><span>截止日期</span><span>推荐理由</span><span>操作</span>
          </div>
          <article v-for="job in items" :key="job.record_id" class="recommendation-card">
            <div class="recommendation-grade" :class="'grade-' + job.recommendation_grade"><b>{{ job.recommendation_grade }}</b><span>{{ job.recommendation_score }} 分</span></div>
            <strong class="recommendation-company">{{ job.company || '—' }}</strong>
            <div class="recommendation-job">{{ job.job || '—' }}</div>
            <div class="recommendation-location"><span>{{ job.city || '地点待定' }}</span><span>{{ (job.dir || []).join(' / ') || '方向待补充' }}</span></div>
            <time class="recommendation-deadline">{{ deadline(job.deadline) }}</time>
            <p class="recommendation-reason">{{ gradeTitle[job.recommendation_grade] }} · {{ job.recommendation_reason }}</p>
            <div class="recommendation-actions">
              <button class="btn btn-primary" :disabled="job.is_added || job.adding" @click="addToPersonal(job)">{{ job.adding ? '添加中…' : (job.is_added ? '已添加' : '添加至个人') }}</button>
              <a v-if="job.url" :href="job.url" target="_blank" rel="noreferrer" class="btn">查看岗位</a>
            </div>
          </article>
        </div>

        <section class="recommendation-history">
          <div class="recommendation-history-hd"><div><h3>筛选历史</h3><span>保存最近 20 次筛选，可随时查看结果</span></div><button class="btn" :disabled="historyLoading" @click="loadHistory">刷新</button></div>
          <div v-if="historyLoading" class="muted">正在读取历史…</div>
          <div v-else-if="!histories.length" class="muted">暂时没有筛选历史。</div>
          <button v-for="history in histories" v-else :key="history.id" class="recommendation-history-item" :class="{ active: activeHistoryId === history.id }" @click="viewHistory(history)">
            <div class="recommendation-history-top"><b>{{ historyTime(history.created_at) }}</b><span :class="'history-status-' + history.status">{{ history.status === 'finished' ? '已完成' : history.status === 'failed' ? '失败' : '进行中' }}</span></div>
            <div class="recommendation-history-summary">{{ history.preference || '按简历筛选' }} · {{ history.scanned || 0 }} 个岗位 · {{ history.result_count || 0 }} 条推荐</div>
            <div class="recommendation-history-meta"><span>{{ history.resume_filename || '未使用简历' }}</span><span>{{ history.model || '默认模型' }}</span><span v-if="history.status === 'running'">{{ history.total_chunks ? `${history.completed_chunks || 0}/${history.total_chunks} 批` : history.message }}</span></div>
          </button>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-modal { width:min(1320px,98vw); }
.recommendation-body { display:grid; gap:14px; max-height:80vh; overflow:auto; }
.recommendation-form { display:grid; grid-template-columns:minmax(0,1fr) 235px auto; align-items:end; gap:10px; padding:12px; border:2px solid var(--ink); background:var(--bg); box-shadow:3px 3px 0 var(--ink); }
.recommendation-form textarea { resize:vertical; min-height:74px; }
.recommendation-progress { display:grid; gap:7px; padding:11px 12px; border:1px solid var(--line2); background:var(--bg); color:var(--sub); font-size:11px; }.recommendation-progress > div:first-child { display:flex; justify-content:space-between; gap:12px; }.recommendation-progress b { color:var(--ink); }.recommendation-progress-track { height:8px; background:var(--line2); overflow:hidden; }.recommendation-progress-track i { display:block; height:100%; min-width:4px; background:var(--blue); transition:width .3s ease; }.recommendation-progress small { color:var(--muted); font:900 10px var(--mono); }
.recommendation-history { display:grid; gap:7px; border-top:2px solid var(--ink); padding-top:13px; }.recommendation-history-hd { display:flex; justify-content:space-between; align-items:center; gap:12px; }.recommendation-history h3 { margin:0; font-size:14px; }.recommendation-history-hd span { color:var(--muted); font-size:10px; }.recommendation-history-item { display:grid; gap:5px; text-align:left; border:1px solid var(--line2); background:var(--panel); padding:9px 11px; color:var(--ink); cursor:pointer; }.recommendation-history-item:hover, .recommendation-history-item.active { border-color:var(--ink); box-shadow:3px 3px 0 var(--ink); }.recommendation-history-top, .recommendation-history-meta { display:flex; justify-content:space-between; gap:10px; align-items:center; }.recommendation-history-top b { font:900 11px var(--mono); }.recommendation-history-summary { font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }.recommendation-history-meta { justify-content:flex-start; flex-wrap:wrap; color:var(--muted); font-size:10px; }.history-status-finished { color:var(--green); }.history-status-failed { color:var(--red); }.history-status-running { color:var(--blue); }
.recommendation-result { display:grid; gap:0; min-width:1000px; }
.recommendation-summary { font:900 11px var(--mono); color:var(--muted); padding:4px 1px; }
.recommendation-columns, .recommendation-card { display:grid; grid-template-columns:58px minmax(100px,.9fr) minmax(150px,1.2fr) minmax(150px,1.1fr) 105px minmax(220px,1.7fr) 178px; gap:10px; align-items:center; }
.recommendation-columns { margin-top:8px; padding:8px 11px; border:1px solid var(--line2); border-bottom:0; background:var(--bg); color:var(--muted); font:900 10px var(--mono); }
.recommendation-card { border:1px solid var(--line2); background:var(--panel); padding:10px 11px; }
.recommendation-grade { width:48px; min-height:48px; display:grid; place-content:center; text-align:center; border:2px solid var(--ink); font-family:var(--mono); background:var(--amberS); flex:none; }
.recommendation-grade b { font-size:20px; line-height:1; }.recommendation-grade span { font-size:9px; margin-top:3px; }
.grade-S { background:var(--blue); color:#fff; }.grade-A { background:var(--greenS); }.grade-C { background:var(--bg); color:var(--muted); }
.recommendation-company, .recommendation-job { font-size:12px; overflow-wrap:anywhere; }.recommendation-location { display:grid; gap:3px; color:var(--sub); font-size:11px; overflow-wrap:anywhere; }.recommendation-deadline { color:var(--sub); font:700 11px var(--mono); }.recommendation-reason { margin:0; color:var(--sub); font-size:11px; line-height:1.5; overflow-wrap:anywhere; }.recommendation-actions { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-start; }
@media (max-width:720px) { .recommendation-modal { width:min(98vw,1320px); }.recommendation-form { grid-template-columns:1fr; }.recommendation-body { max-height:82vh; }.recommendation-result { min-width:900px; } }
</style>
