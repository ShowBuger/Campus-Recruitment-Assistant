<script>
// Module-level cache (persists across v-if remounts)
let _cachedModels = []
let _cachedProvider = ''
</script>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { del, get, post } from '@/utils/api'
import { externalHttpUrl } from '@/utils/externalUrl'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close'])
const toast = useToastStore()

const showConfig = ref(false)
const configSaving = ref(false)
const configModels = ref([..._cachedModels])
const configProviderLabel = ref('')
const recConfig = reactive({ recommendation_limit: 12, recommendation_min_score: 45, recommendation_model: '' })
const preference = ref('')
const resumeFilename = ref('')
const resumes = ref([])
const loading = ref(false)
const historyResult = ref(null)
const selectedHistory = ref(null)
const progress = ref(null)
const histories = ref([])
const historyLoading = ref(false)
const activeHistoryId = ref('')
const runMode = ref('full')
const baseRunId = ref('')
const expandedJobIds = ref(new Set())
let pollTimer = null
let liveRefreshTimer = null
let liveRefreshRunning = false

const gradeTitle = { S: '强烈推荐', A: '优先推荐', B: '值得关注', C: '备选岗位' }
const historyItems = computed(() => historyResult.value?.items || [])
const baseHistory = computed(() => histories.value.find(item => item.id === baseRunId.value))

function isLongJobName(value) {
  return String(value || '').length > 42
}

function toggleJobName(recordId) {
  const next = new Set(expandedJobIds.value)
  if (next.has(recordId)) next.delete(recordId)
  else next.add(recordId)
  expandedJobIds.value = next
}

async function runRecommendation() {
  loading.value = true
  progress.value = { phase: 'preparing', message: '正在创建筛选任务…', completed_chunks: 0, total_chunks: 0 }
  try {
    const started = await post('/api/recommendations', {
      preference: preference.value,
      resume_filename: resumeFilename.value,
      run_mode: runMode.value,
      base_run_id: baseRunId.value,
    })
    activeHistoryId.value = started.run_id
    await loadHistory()
    await pollRecommendation(started.run_id)
    await loadHistory()
  } catch (error) {
    toast.error(error.message || '岗位筛选失败')
  } finally {
    loading.value = false
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  }
}

function useHistoryAsBase(history, mode) {
  runMode.value = mode
  baseRunId.value = history.id
  preference.value = history.preference || ''
  resumeFilename.value = history.resume_filename || ''
  historyResult.value = null
}

function clearHistoryBase() {
  runMode.value = 'full'
  baseRunId.value = ''
}

async function reconnectRunningRecommendation() {
  const active = histories.value.find(item => item.status === 'running')
  if (!active) return
  loading.value = true
  activeHistoryId.value = active.id
  progress.value = active
  try {
    await pollRecommendation(active.id)
    await loadHistory()
  } catch (error) {
    toast.error(error.message || '读取筛选进度失败')
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
      return
    }
    if (state.status === 'failed') throw new Error(state.message || '岗位筛选失败')
    await new Promise(resolve => { pollTimer = setTimeout(resolve, 900) })
  }
}

async function loadHistory(silent = false) {
  if (!silent) historyLoading.value = true
  try { histories.value = (await get('/api/recommendations/history')).items || [] }
  catch {
    if (!silent) histories.value = []
  }
  finally {
    if (!silent) historyLoading.value = false
  }
}

function updateHistory(runId, state) {
  const index = histories.value.findIndex(item => item.id === runId)
  if (index < 0) return
  histories.value[index] = { ...histories.value[index], ...state, id: runId,
    result_count: state.result?.items?.length ?? histories.value[index].result_count }
}

async function viewHistory(history, silent = false) {
  activeHistoryId.value = history.id
  try {
    const data = await get('/api/recommendations/history/' + encodeURIComponent(history.id))
    selectedHistory.value = data
    historyResult.value = data.result || { items: [] }
    try {
      const dashboard = await get('/api/dashboard', { timeout: 10000 })
      const personalIds = new Set((dashboard?.main?.recent || []).map(r => r.record_id))
      if (historyResult.value?.items) {
        historyResult.value.items.forEach(job => {
          if (personalIds.has(job.record_id)) job.is_added = true
        })
      }
    } catch (_) {}
  } catch (error) {
    if (!silent) toast.error(error.message || '读取筛选历史失败')
  }
}

async function deleteHistory(history) {
  if (!window.confirm('确定删除这次筛选历史吗？')) return
  try {
    await del('/api/recommendations/history/' + encodeURIComponent(history.id))
    histories.value = histories.value.filter(item => item.id !== history.id)
    if (selectedHistory.value?.id === history.id) {
      selectedHistory.value = null
      historyResult.value = null
    }
    if (activeHistoryId.value === history.id) activeHistoryId.value = ''
    toast.success('筛选历史已删除')
  } catch (error) {
    toast.error(error.message || '删除筛选历史失败')
  }
}

async function refreshLiveData() {
  if (liveRefreshRunning) return
  liveRefreshRunning = true
  try {
    await loadHistory(true)
    if (selectedHistory.value?.status === 'running' && historyResult.value) {
      const latest = histories.value.find(item => item.id === selectedHistory.value.id) || selectedHistory.value
      await viewHistory(latest, true)
    }
  } finally {
    liveRefreshRunning = false
  }
}

function historyTime(value) {
  if (!value) return '刚刚'
  const date = new Date(String(value).replace(' ', 'T') + (String(value).includes('Z') ? '' : 'Z'))
  return isNaN(date) ? String(value) : `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
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

async function loadRecConfig() {
  try {
    const data = await get('/api/config/recommendation')
    recConfig.recommendation_limit = data?.recommendation_limit ?? 12
    recConfig.recommendation_min_score = data?.recommendation_min_score ?? 45
    recConfig.recommendation_model = data?.recommendation_model || data?.ai_model || ''
    configProviderLabel.value = _cachedProvider || data?.ai_provider || '当前服务商'
    if (_cachedModels.length) configModels.value = [..._cachedModels]
  } catch (_) {}
}

async function loadRecModels() {
  try {
    const data = await get('/api/config/recommendation/models')
    configModels.value = data.models || []
    _cachedModels = data.models || []
    _cachedProvider = data.provider || ''
    configProviderLabel.value = data.provider || '当前服务商'
    if (!recConfig.recommendation_model) recConfig.recommendation_model = data.current_model || ''
  } catch (err) { toast.error(err.message || '读取推荐模型失败') }
}

async function saveRecConfig() {
  configSaving.value = true
  try {
    const data = await post('/api/config/recommendation', recConfig)
    toast.success(data.message || '岗位推荐配置已保存')
  } catch (err) {
    toast.error(err.message || '岗位推荐配置保存失败')
  } finally { configSaving.value = false }
}

onMounted(async () => {
  try { resumes.value = (await get('/api/resumes')).files || [] } catch { resumes.value = [] }
  await loadHistory()
  reconnectRunningRecommendation()
  loadRecConfig()
  liveRefreshTimer = setInterval(refreshLiveData, 1500)
})

onUnmounted(() => {
  loading.value = false
  if (pollTimer) clearTimeout(pollTimer)
  if (liveRefreshTimer) clearInterval(liveRefreshTimer)
})
</script>

<template>
  <div class="modal-mask show" @mousedown.self="emit('close')">
    <div class="modal recommendation-modal" role="dialog" aria-modal="true" aria-labelledby="recommendation-title">
      <div class="modal-hd recommendation-modal-hd">
        <div><h2 id="recommendation-title">智能岗位筛选</h2><p>结合岗位偏好与简历证据，筛出更值得关注的机会。</p></div>
        <button class="icon-btn" @click="emit('close')" title="关闭">&times;</button>
      </div>
      <div class="modal-body recommendation-body">
        <section class="recommendation-setup" aria-label="筛选条件">
        <div class="recommendation-form">
          <div v-if="baseHistory" class="recommendation-base-notice">
            <div><b>{{ runMode === 'incremental' ? '增量更新' : '继续筛选' }}</b><span>{{ runMode === 'incremental' ? '只分析该次筛选后新增的岗位，并合并原有推荐结果。' : '仅以上次推荐结果为候选，再按当前条件筛选。' }}</span></div>
            <button type="button" class="btn" @click="clearHistoryBase">取消</button>
          </div>
          <div class="recommendation-form-body">
            <div class="form-group"><label for="recommend-preference">岗位偏好</label>
              <textarea id="recommend-preference" v-model="preference" rows="3" placeholder="例如：上海或杭州，嵌入式 Linux / BSP / 驱动，偏 C++，机器人或汽车电子方向"></textarea>
              <div class="help">可描述目标城市、岗位方向、技术栈或希望避开的工作内容。</div>
            </div>
            <div class="form-group"><label for="recommend-resume">关联简历（可选）</label>
              <select id="recommend-resume" v-model="resumeFilename"><option value="">不使用简历，仅按偏好筛选</option><option v-for="file in resumes" :key="file.name" :value="file.name">{{ file.name }}</option></select>
            </div>
          </div>
          <div class="recommendation-form-actions">
            <button class="btn" @click="showConfig = true">配置</button>
            <button class="btn btn-primary" :disabled="loading" @click="runRecommendation">{{ loading ? '正在匹配…' : (runMode === 'incremental' ? '开始增量更新' : runMode === 'refine' ? '继续筛选' : '开始智能筛选') }}</button>
          </div>
        </div>

        <div v-if="loading && progress" class="recommendation-progress" role="status">
          <div><b>{{ progress.phase === 'summarizing' ? '正在压缩简历' : progress.phase === 'ranking' ? '正在筛选岗位' : '正在准备' }}</b><span>{{ progress.message }}</span></div>
          <div v-if="progress.total_chunks" class="recommendation-progress-track"><i :style="{ width: Math.round((progress.completed_chunks || 0) / progress.total_chunks * 100) + '%' }"></i></div>
          <small v-if="progress.total_chunks">第 {{ progress.completed_chunks || 0 }} / {{ progress.total_chunks }} 批（每批最多 20 个岗位，最多 3 批并行）</small>
        </div>
        </section>

        <section class="recommendation-history">
          <div class="recommendation-history-hd"><div><h3>筛选历史</h3><span>保留最近 10 次，可查看结果或继续筛选</span></div><button class="btn" :disabled="historyLoading" @click="loadHistory()">刷新</button></div>
          <div v-if="historyLoading" class="recommendation-history-loading" aria-label="正在读取历史"><i></i><i></i><i></i></div>
          <div v-else-if="!histories.length" class="recommendation-empty"><b>还没有筛选记录</b><span>填写左侧条件并开始筛选，结果会保存在这里。</span></div>
          <div v-for="history in histories" v-else :key="history.id" class="recommendation-history-row">
            <button class="recommendation-history-item" :class="{ active: activeHistoryId === history.id }" @click="viewHistory(history)">
              <div class="recommendation-history-top"><b>{{ historyTime(history.created_at) }}</b><span :class="'history-status-' + history.status">{{ history.status === 'finished' ? '已完成' : history.status === 'failed' ? '失败' : '进行中' }}</span></div>
              <div class="recommendation-history-summary">{{ history.preference || '按简历筛选' }}</div>
              <div class="recommendation-history-counts"><span>扫描 {{ history.scanned || 0 }}</span><span>推荐 {{ history.result_count || 0 }}</span></div>
              <div class="recommendation-history-meta"><span v-if="history.run_mode === 'incremental'">增量更新</span><span v-else-if="history.run_mode === 'refine'">继续筛选</span><span>{{ history.resume_filename || '未使用简历' }}</span><span>{{ history.model || '默认模型' }}</span><span v-if="history.status === 'running'">{{ history.total_chunks ? `${history.completed_chunks || 0}/${history.total_chunks} 批` : history.message }}</span></div>
            </button>
            <div class="recommendation-history-actions">
              <button v-if="history.status === 'finished'" class="btn" title="只筛选此后新增的岗位" @click="useHistoryAsBase(history, 'incremental')">筛选新增</button>
              <button v-if="history.status === 'finished'" class="btn" title="在本次结果中继续筛选" @click="useHistoryAsBase(history, 'refine')">继续筛选</button>
              <button class="btn recommendation-history-delete" title="删除这次筛选历史" @click="deleteHistory(history)">删除</button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>

  <div v-if="showConfig" class="modal-mask show recommendation-history-mask" @mousedown.self="showConfig = false">
    <div class="modal recommendation-history-modal" style="width:min(520px,96vw)">
      <div class="modal-hd">
        <div><h2>智能筛选配置</h2><p>调整推荐模型、数量门槛和最低分</p></div>
        <button class="icon-btn" @click="showConfig = false" title="关闭">&times;</button>
      </div>
      <div class="modal-body recommendation-config-body">
        <div class="form-group"><label>推荐模型</label><div class="model-input-row"><select v-model="recConfig.recommendation_model"><option value="">使用 AI 配置当前模型</option><option v-for="model in configModels" :key="model" :value="model">{{ model }}</option></select><button class="btn" type="button" @click="loadRecModels">读取模型</button></div><div class="help">当前服务商：{{ configProviderLabel || '未读取' }}</div></div>
        <div class="form-group"><label>单次推荐数量</label><input v-model.number="recConfig.recommendation_limit" type="number" min="0" max="5000"><div class="help">填 0 表示不设上限。</div></div>
        <div class="form-group"><label>最低推荐分</label><input v-model.number="recConfig.recommendation_min_score" type="number" min="0" max="95"><div class="help">分数越高，结果越严格。</div></div>
        <button class="btn btn-primary" @click="saveRecConfig" :disabled="configSaving">{{ configSaving ? '保存中…' : '保存配置' }}</button>
      </div>
    </div>
  </div>

  <div v-if="historyResult" class="modal-mask show recommendation-history-mask" @mousedown.self="historyResult = null">
    <div class="modal recommendation-history-modal">
      <div class="modal-hd">
        <div><h2>筛选结果</h2><p>{{ selectedHistory?.preference || '按简历筛选' }}<span v-if="selectedHistory?.created_at">，{{ historyTime(selectedHistory.created_at) }}</span></p></div>
        <button class="icon-btn" @click="historyResult = null" title="关闭">&times;</button>
      </div>
      <div class="modal-body recommendation-history-result-body">
        <div class="recommendation-result">
          <div class="recommendation-summary"><span>扫描 {{ historyResult.scanned || selectedHistory?.scanned || 0 }} 条共享岗位</span><span>{{ historyResult.resume_used ? '已结合简历' : '按岗位偏好' }}</span><span>{{ historyItems.length }} 条推荐</span><em v-if="historyResult.partial">结果仍在更新</em></div>
          <div v-if="!historyItems.length" class="center muted">这次筛选暂时没有符合当前门槛的岗位。</div>
          <div v-if="historyItems.length" class="recommendation-columns" aria-hidden="true">
            <span>推荐</span><span>公司</span><span>岗位</span><span>地点 / 方向</span><span>批次</span><span>AI 岗位画像 / 匹配</span><span>操作</span>
          </div>
          <article v-for="job in historyItems" :key="job.record_id" class="recommendation-card">
            <div class="recommendation-grade" :class="'grade-' + job.recommendation_grade"><b>{{ job.recommendation_grade }}</b><span>{{ job.recommendation_score }} 分</span></div>
            <strong class="recommendation-company">{{ job.company || '-' }}</strong>
            <div class="recommendation-job-cell">
              <div
                class="recommendation-job"
                :class="{ expanded: expandedJobIds.has(job.record_id) }"
                :title="expandedJobIds.has(job.record_id) ? '' : (job.job || '')"
              >{{ job.job || '-' }}</div>
              <button
                v-if="isLongJobName(job.job)"
                type="button"
                class="recommendation-job-toggle"
                :aria-expanded="expandedJobIds.has(job.record_id)"
                @click="toggleJobName(job.record_id)"
              >{{ expandedJobIds.has(job.record_id) ? '收起' : '展开全部' }}</button>
            </div>
            <div class="recommendation-location"><span>{{ job.city || '地点待定' }}</span><span>{{ (job.dir || []).join(' / ') || '方向待补充' }}</span></div>
            <span class="recommendation-batch">{{ job.batch || '-' }}</span>
            <div class="recommendation-insight">
              <p class="recommendation-reason"><b>{{ gradeTitle[job.recommendation_grade] }}</b><span>{{ job.recommendation_reason }}</span></p>
              <p v-if="job.ai_role_profile?.summary" class="recommendation-role-summary">{{ job.ai_role_profile.summary }}</p>
              <div v-if="job.match_strengths?.length || job.match_gaps?.length" class="recommendation-evidence">
                <span v-for="item in job.match_strengths" :key="'s-' + item" class="evidence-good">✓ {{ item }}</span>
                <span v-for="item in job.match_gaps" :key="'g-' + item" class="evidence-gap">△ {{ item }}</span>
              </div>
              <details v-if="job.ai_role_profile" class="recommendation-profile">
                <summary>查看工作内容、要求与薪酬提示</summary>
                <div v-if="job.ai_role_profile.work_content?.length"><b>典型工作</b><span>{{ job.ai_role_profile.work_content.join('；') }}</span></div>
                <div v-if="job.ai_role_profile.likely_requirements?.length"><b>可能要求</b><span>{{ job.ai_role_profile.likely_requirements.join('；') }}</span></div>
                <div v-if="job.ai_role_profile.likely_tech_stack?.length"><b>技术栈</b><span>{{ job.ai_role_profile.likely_tech_stack.join(' / ') }}</span></div>
                <div v-if="job.ai_role_profile.business_context"><b>业务场景</b><span>{{ job.ai_role_profile.business_context }}</span></div>
                <div><b>薪酬待遇</b><span>{{ job.ai_role_profile.compensation }}</span></div>
                <div><b>工作风险</b><span>{{ job.ai_role_profile.work_style_risk }}</span></div>
                <small>以上岗位画像由 AI 根据公司与岗位名称推断，置信度：{{ job.ai_role_profile.confidence === 'medium' ? '中' : '低' }}，投递前请以官方 JD 为准。</small>
              </details>
            </div>
            <div class="recommendation-actions">
              <button class="btn btn-primary" :disabled="job.is_added || job.adding" @click="addToPersonal(job)">{{ job.adding ? '添加中…' : (job.is_added ? '已添加' : '添加个人') }}</button>
              <a v-if="externalHttpUrl(job.url)" :href="externalHttpUrl(job.url)" target="_blank" rel="noopener noreferrer" class="btn">查看岗位</a>
            </div>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-modal { width:min(1320px,98vw); }
.recommendation-history-mask { z-index:10010; }.recommendation-history-modal { width:min(1320px,98vw); }.recommendation-history-result-body { max-height:82vh; overflow:auto; }
.recommendation-body { display:grid; gap:14px; max-height:80vh; overflow:auto; }
.recommendation-form { display:flex; flex-direction:column; gap:12px; padding:14px; border:2px solid var(--ink); background:var(--bg); box-shadow:3px 3px 0 var(--ink); }
.recommendation-base-notice { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:10px 12px; border:1px solid var(--blue); background:var(--blueS); }.recommendation-base-notice > div { display:grid; gap:2px; }.recommendation-base-notice b { color:var(--blue); font-size:12px; }.recommendation-base-notice span { color:var(--sub); font-size:10px; }
.recommendation-form-body { display:grid; grid-template-columns:minmax(0,1fr) 235px; gap:10px; align-items:end; }
.recommendation-form textarea { resize:vertical; min-height:74px; }
.recommendation-form-actions { display:flex; justify-content:space-between; align-items:center; }
.recommendation-progress { display:grid; gap:7px; padding:11px 12px; border:1px solid var(--line2); background:var(--bg); color:var(--sub); font-size:11px; }.recommendation-progress > div:first-child { display:flex; justify-content:space-between; gap:12px; }.recommendation-progress b { color:var(--ink); }.recommendation-progress-track { height:8px; background:var(--line2); overflow:hidden; }.recommendation-progress-track i { display:block; height:100%; min-width:4px; background:var(--blue); transition:width .3s ease; }.recommendation-progress small { color:var(--muted); font:900 10px var(--mono); }
.recommendation-history { display:grid; gap:7px; border-top:2px solid var(--ink); padding-top:13px; }.recommendation-history-hd { display:flex; justify-content:space-between; align-items:center; gap:12px; }.recommendation-history h3 { margin:0; font-size:14px; }.recommendation-history-hd span { color:var(--muted); font-size:10px; }.recommendation-history-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px; align-items:stretch; }.recommendation-history-item { min-width:0; display:grid; gap:5px; text-align:left; border:1px solid var(--line2); background:var(--panel); padding:9px 11px; color:var(--ink); cursor:pointer; }.recommendation-history-item:hover, .recommendation-history-item.active { border-color:var(--ink); box-shadow:3px 3px 0 var(--ink); }.recommendation-history-actions { display:flex; gap:6px; align-items:stretch; }.recommendation-history-actions .btn { white-space:nowrap; }.recommendation-history-delete { color:var(--red); }.recommendation-history-top, .recommendation-history-meta { display:flex; justify-content:space-between; gap:10px; align-items:center; }.recommendation-history-top b { font:900 11px var(--mono); }.recommendation-history-summary { font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }.recommendation-history-meta { justify-content:flex-start; flex-wrap:wrap; color:var(--muted); font-size:10px; }.history-status-finished { color:var(--green); }.history-status-failed { color:var(--red); }.history-status-running { color:var(--blue); }
.recommendation-result { display:grid; gap:0; min-width:1000px; }
.recommendation-summary { font:900 11px var(--mono); color:var(--muted); padding:4px 1px; }
.recommendation-columns, .recommendation-card { display:grid; grid-template-columns:58px minmax(100px,.8fr) minmax(140px,1fr) minmax(140px,.9fr) 90px minmax(340px,2.5fr) 178px; gap:10px; align-items:start; }
.recommendation-columns { margin-top:8px; padding:8px 11px; border:1px solid var(--line2); border-bottom:0; background:var(--bg); color:var(--muted); font:900 10px var(--mono); }
.recommendation-card { border:1px solid var(--line2); background:var(--panel); padding:10px 11px; }
.recommendation-grade { width:48px; min-height:48px; display:grid; place-content:center; text-align:center; border:2px solid var(--ink); font-family:var(--mono); background:var(--amberS); flex:none; }
.recommendation-grade b { font-size:20px; line-height:1; }.recommendation-grade span { font-size:9px; margin-top:3px; }
.grade-S { background:var(--blue); color:#fff; }.grade-A { background:var(--greenS); }.grade-C { background:var(--bg); color:var(--muted); }
.recommendation-company, .recommendation-job { font-size:12px; overflow-wrap:anywhere; }.recommendation-job-cell { min-width:0; display:grid; gap:5px; align-content:start; }.recommendation-job { display:-webkit-box; overflow:hidden; -webkit-box-orient:vertical; -webkit-line-clamp:3; line-clamp:3; line-height:1.55; }.recommendation-job.expanded { display:block; overflow:visible; }.recommendation-job-toggle { width:max-content; max-width:100%; padding:0; border:0; background:transparent; color:var(--blue); font:800 10px var(--sans); cursor:pointer; }.recommendation-job-toggle:hover { text-decoration:underline; }.recommendation-job-toggle:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }.recommendation-location { display:grid; gap:3px; color:var(--sub); font-size:11px; overflow-wrap:anywhere; }.recommendation-deadline { color:var(--sub); font:700 11px var(--mono); }.recommendation-insight { display:grid; gap:6px; }.recommendation-reason { margin:0; color:var(--sub); font-size:11px; line-height:1.5; overflow-wrap:anywhere; }.recommendation-reason b { color:var(--ink); }.recommendation-role-summary { margin:0; color:var(--ink); font-size:11px; line-height:1.45; }.recommendation-evidence { display:flex; flex-wrap:wrap; gap:4px; }.recommendation-evidence span { padding:2px 5px; border:1px solid var(--line2); background:var(--bg); font-size:9px; line-height:1.35; }.evidence-good { color:var(--green); }.evidence-gap { color:var(--red); }.recommendation-profile { font-size:10px; color:var(--sub); }.recommendation-profile summary { width:max-content; max-width:100%; color:var(--blue); cursor:pointer; font-weight:800; }.recommendation-profile > div { display:grid; grid-template-columns:58px minmax(0,1fr); gap:6px; margin-top:5px; line-height:1.45; }.recommendation-profile > div b { color:var(--ink); }.recommendation-profile small { display:block; margin-top:7px; color:var(--muted); line-height:1.4; }.recommendation-actions { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-start; }
.recommendation-batch { font:700 11px var(--mono); color:var(--sub); }

/* Product-modal redesign: one setup rail and one history workspace. */
.recommendation-modal { width:min(1180px,96vw); max-height:min(820px,92dvh); border-radius:16px; }
.recommendation-modal-hd { min-height:72px; padding:14px 18px; }
.recommendation-modal-hd h2 { margin:0; font-size:19px; letter-spacing:-.02em; }
.recommendation-modal-hd p { max-width:560px; margin:3px 0 0; color:var(--muted); font-size:11px; }
.recommendation-body { grid-template-columns:minmax(300px,.72fr) minmax(480px,1.28fr); align-items:start; gap:14px; max-height:calc(92dvh - 74px); padding:14px; overflow:hidden; background:var(--bg); }
.recommendation-setup { display:grid; min-width:0; gap:10px; }
.recommendation-form { gap:16px; padding:16px; border:1px solid var(--line); border-radius:14px; background:var(--panel); box-shadow:0 8px 24px color-mix(in srgb,var(--ink) 6%,transparent); }
.recommendation-form-body { grid-template-columns:1fr; gap:14px; }
.recommendation-form textarea { min-height:116px; padding:10px 12px; line-height:1.55; }
.recommendation-form .form-group { gap:7px; }
.recommendation-form .form-group > label { color:var(--ink); font-size:11px; font-weight:800; }
.recommendation-form .help { color:var(--muted); font-size:9px; line-height:1.45; }
.recommendation-form-actions { gap:8px; padding-top:2px; }
.recommendation-form-actions .btn-primary { flex:1; }
.recommendation-base-notice { padding:10px 11px; border-color:color-mix(in srgb,var(--blue) 35%,var(--line)); border-radius:10px; background:var(--blueS); }
.recommendation-base-notice b { font-size:11px; }.recommendation-base-notice span { font-size:9px; line-height:1.4; }
.recommendation-progress { padding:12px; border-color:var(--line); border-radius:12px; background:var(--panel); }
.recommendation-progress-track { height:4px; border-radius:4px; }.recommendation-progress-track i { border-radius:4px; }
.recommendation-history { align-content:start; gap:8px; max-height:calc(92dvh - 104px); padding:14px; overflow:auto; border:1px solid var(--line); border-radius:14px; background:var(--panel); }
.recommendation-history-hd { position:sticky; top:-14px; z-index:2; margin:-14px -14px 2px; padding:14px; border-bottom:1px solid var(--line); background:var(--panel); }
.recommendation-history h3 { font-size:14px; }.recommendation-history-hd span { display:block; margin-top:3px; font-size:9px; }
.recommendation-history-hd .btn { height:30px; padding:0 11px; font-size:10px; }
.recommendation-history-row { grid-template-columns:1fr; gap:0; overflow:hidden; border:1px solid var(--line); border-radius:11px; background:var(--panel); transition:border-color .16s var(--ease),box-shadow .16s var(--ease),transform .16s var(--ease); }
.recommendation-history-row:hover { border-color:var(--line2); box-shadow:0 7px 20px color-mix(in srgb,var(--ink) 7%,transparent); transform:translateY(-1px); }
.recommendation-history-item { gap:6px; padding:11px 12px 9px; border:0; border-radius:0; background:transparent; }
.recommendation-history-item:hover,.recommendation-history-item.active { border:0; box-shadow:none; }.recommendation-history-item.active { background:var(--blueS); }
.recommendation-history-top b { font-size:10px; }.recommendation-history-summary { color:var(--ink); font-size:11px; font-weight:750; }
.recommendation-history-counts { display:flex; gap:14px; color:var(--sub); font:700 9px var(--mono); }
.recommendation-history-meta { gap:8px 12px; font-size:9px; }
.recommendation-history-actions { justify-content:flex-end; gap:5px; padding:7px 8px; border-top:1px solid var(--line); background:color-mix(in srgb,var(--bg) 72%,var(--panel)); }
.recommendation-history-actions .btn { height:28px; padding:0 10px; border-color:transparent; background:transparent; font-size:10px; }
.recommendation-history-actions .btn:hover { border-color:var(--line); background:var(--panel); box-shadow:none; transform:none; }
.recommendation-history-delete { margin-left:auto; }
.recommendation-empty { display:grid; place-content:center; min-height:210px; padding:24px; text-align:center; }
.recommendation-empty b { color:var(--ink); font-size:13px; }.recommendation-empty span { max-width:260px; margin-top:5px; color:var(--muted); font-size:10px; }
.recommendation-history-loading { display:grid; gap:8px; }.recommendation-history-loading i { display:block; height:72px; border-radius:10px; background:color-mix(in srgb,var(--line) 65%,var(--panel)); }
.recommendation-config-body { display:grid; gap:14px; padding:18px; }
.recommendation-summary { display:flex; flex-wrap:wrap; gap:6px 16px; padding:8px 2px; }.recommendation-summary em { color:var(--blue); font-style:normal; }
.recommendation-card { transition:background .15s var(--ease); }.recommendation-card:hover { background:color-mix(in srgb,var(--blueS) 35%,var(--panel)); }
.recommendation-reason { display:grid; gap:2px; }.recommendation-reason span { color:var(--sub); }
.recommendation-actions .btn { white-space:nowrap; }

@media (prefers-reduced-motion:no-preference) { .recommendation-history-loading i { animation:recommendation-pulse 1.4s ease-in-out infinite alternate; }.recommendation-history-loading i:nth-child(2) { animation-delay:.12s; }.recommendation-history-loading i:nth-child(3) { animation-delay:.24s; } }
@keyframes recommendation-pulse { to { opacity:.45; } }

:global([data-style="pixelium"]) .recommendation-modal,:global([data-style="pixelium"]) .recommendation-form,:global([data-style="pixelium"]) .recommendation-history,:global([data-style="pixelium"]) .recommendation-history-row { border:2px solid var(--ink); border-radius:2px; box-shadow:none; }
:global([data-style="pixelium"]) .recommendation-history-row:hover { box-shadow:3px 3px 0 var(--ink); }
:global([data-style="aurora"]) .recommendation-form,:global([data-style="aurora"]) .recommendation-history { border-color:rgba(255,255,255,.48); background:color-mix(in srgb,var(--panel) 82%,transparent); box-shadow:inset 0 1px rgba(255,255,255,.55),0 18px 42px rgba(50,42,116,.12); backdrop-filter:blur(22px) saturate(150%); }
:global([data-style="anime"]) .recommendation-form,:global([data-style="anime"]) .recommendation-history { border:2px solid var(--ink); border-radius:10px 15px 10px 15px; box-shadow:5px 5px 0 var(--ink); }
:global([data-style="journal"]) .recommendation-form,:global([data-style="journal"]) .recommendation-history { border-radius:3px 11px 11px 3px; box-shadow:3px 4px 0 color-mix(in srgb,var(--ink) 10%,transparent); }

@media (max-width:860px) { .recommendation-modal { width:min(96vw,720px); }.recommendation-body { display:block; overflow:auto; }.recommendation-setup { margin-bottom:12px; }.recommendation-history { max-height:none; }.recommendation-history-hd { top:0; }.recommendation-result { min-width:900px; } }
@media (max-width:520px) { .recommendation-body { padding:10px; }.recommendation-form,.recommendation-history { padding:12px; border-radius:12px; }.recommendation-history-hd { margin:-12px -12px 2px; padding:12px; }.recommendation-base-notice { align-items:flex-start; }.recommendation-history-actions { display:grid; grid-template-columns:1fr 1fr auto; }.recommendation-history-actions .btn { padding:0 8px; }.recommendation-modal-hd p { max-width:32ch; } }
@media (prefers-reduced-motion:reduce) { .recommendation-history-row,.recommendation-card { transition:none; } }
</style>
