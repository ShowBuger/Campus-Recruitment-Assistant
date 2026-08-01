<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useDashboardStore } from '@/stores/dashboard'
import { useDialogStore } from '@/stores/dialog'

const auth = useAuthStore()
const toast = useToastStore()
const dashboard = useDashboardStore()
const dialog = useDialogStore()

const resumeFiles = ref([])
const selectedResume = ref('')
const selectedRecord = ref('')
const analysisMode = ref('match')
const focus = ref('')
const loading = ref(false)
const resultHtml = ref('')
const resultError = ref('')
const resultMeta = ref('尚未生成分析')
const history = ref([])
const activeHistory = ref('')
const loadingHistory = ref(true)

// AI provider info
const PROVIDER_LABELS = { deepseek: 'DeepSeek', openai: 'OpenAI GPT', anthropic: 'Claude', kimi: 'Kimi' }
const aiProviderLabel = ref('DeepSeek')
const aiModelLabel = ref('')

const recordsWithJD = computed(() => dashboard.records.filter(r => r.job_jd?.trim()))
const canRun = computed(() => selectedResume.value && selectedRecord.value)
const jdMissingCount = computed(() => (dashboard.records || []).length - recordsWithJD.value.length)
const selectedRecordInfo = computed(() => recordsWithJD.value.find(record => String(record.record_id) === String(selectedRecord.value)) || null)

onMounted(async () => {
  if (!dashboard.data) await dashboard.fetch()
  await loadResumes()
  await loadHistory()
  await loadAIProvider()
})

async function loadAIProvider() {
  try {
    const r = await fetch('/api/config', { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) return
    const cfg = await r.json()
    const values = cfg?.values || {}
    const provider = values.ai_provider || 'deepseek'
    const model = values[provider + '_model'] || ''
    aiProviderLabel.value = PROVIDER_LABELS[provider] || 'DeepSeek'
    aiModelLabel.value = aiProviderLabel.value + (model ? ' · ' + model : '')
  } catch {}
}

async function loadResumes() {
  try {
    const r = await fetch('/api/resumes', { headers: { Authorization: `Bearer ${auth.token}` } })
    resumeFiles.value = (await r.json()).files || []
  } catch { resumeFiles.value = [] }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const r = await fetch('/api/ai/history', { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('加载失败')
    history.value = (await r.json()).items || []
  } catch { history.value = [] }
  finally { loadingHistory.value = false }
}

async function runAnalysis() {
  if (!selectedResume.value) { toast.error('请先选择简历'); return }
  if (!selectedRecord.value) { toast.error('请选择已填写 JD 的岗位；如无可选项，请先前往总表补充 JD'); return }
  loading.value = true; resultHtml.value = ''; resultError.value = ''; resultMeta.value = '正在分析'
  activeHistory.value = ''
  try {
    const r = await fetch('/api/ai/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        resume_filename: selectedResume.value,
        record_id: selectedRecord.value,
        analysis_mode: analysisMode.value,
        focus: focus.value.trim()
      })
    })
    if (!r.ok) throw new Error((await r.json()).detail || '分析失败')
    const data = await r.json()
    resultHtml.value = data.analysis_html || data.analysis || '<p>无结果</p>'
    resultMeta.value = [data.analysis_mode_label || '', data.company || '', data.job || '', data.provider_name || data.provider || '', data.model || ''].filter(Boolean).join(' · ') || '分析完成'
    toast.success('简历分析完成并已保存')
    await loadHistory()
  } catch (e) {
    resultError.value = e.message || '分析失败，请稍后重试'
    resultMeta.value = '分析失败'
    toast.error(e.message)
  }
  finally { loading.value = false }
}

async function viewHistory(id) {
  activeHistory.value = id
  resultHtml.value = ''; resultError.value = ''; resultMeta.value = '正在加载'
  try {
    const r = await fetch(`/api/ai/history/${id}`, { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('加载失败')
    const data = await r.json()
    resultHtml.value = data.analysis_html || ''
    resultMeta.value = [data.analysis_mode_label || '', data.company || '', data.job || '', data.provider_name || data.provider || '', data.model || '', String(data.created_at || '').replace('T', ' ')].filter(Boolean).join(' · ') || ''
  } catch (e) {
    activeHistory.value = ''
    toast.error('历史记录加载失败')
    resultHtml.value = ''; resultError.value = ''; resultMeta.value = '尚未生成分析'
  }
}

async function deleteHistory(id) {
  const confirmed = await dialog.confirm(
    '确定删除这条分析历史吗？\n此操作不可撤销。',
    { title: '删除分析历史', tone: 'danger', confirmText: '永久删除' },
  )
  if (!confirmed) return
  try {
    const r = await fetch(`/api/ai/history/${encodeURIComponent(id)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('删除失败')
    if (activeHistory.value === id) { activeHistory.value = ''; resultHtml.value = ''; resultError.value = ''; resultMeta.value = '尚未生成分析' }
    toast.success('分析记录已删除')
    await loadHistory()
  } catch (e) { toast.error(e.message) }
}

function fmtTime(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 19)
}
</script>

<template>
  <div class="page active analysis-page">
    <header class="analysis-page-head">
      <div>
        <h2>让简历更贴近目标岗位</h2>
        <p>结合岗位 JD 识别匹配点、表达缺口和面试准备方向。</p>
      </div>
      <div class="analysis-provider"><span>当前模型</span><strong>{{ aiModelLabel || aiProviderLabel }}</strong></div>
    </header>

    <div class="analysis-workspace">
      <aside class="analysis-controls">
        <section class="analysis-setup">
          <div class="analysis-section-head">
            <div><h3>配置分析</h3><p>选择一份简历和已填写 JD 的岗位。</p></div>
            <span class="analysis-ready" :class="{ ready: canRun }">{{ canRun ? '可以开始' : '等待选择' }}</span>
          </div>

          <div class="analysis-form">
            <div class="analysis-field">
              <label for="analysis-resume">简历</label>
              <select id="analysis-resume" v-model="selectedResume">
                <option value="">请选择已上传简历</option>
                <option v-for="f in resumeFiles" :key="f.name" :value="f.name">{{ f.name }}</option>
              </select>
              <router-link v-if="!resumeFiles.length" to="/resumes">先去上传简历</router-link>
            </div>

            <div class="analysis-field">
              <div class="analysis-label-row">
                <label for="analysis-record">目标岗位</label>
                <button v-if="jdMissingCount > 0" class="analysis-jd-note" type="button" @click="toast.info('另有 ' + jdMissingCount + ' 个岗位未填写 JD')">{{ jdMissingCount }} 个岗位缺少 JD</button>
              </div>
              <select id="analysis-record" v-model="selectedRecord">
                <option value="">请选择公司与岗位</option>
                <option v-for="r in recordsWithJD" :key="r.record_id" :value="r.record_id">{{ r.company }} / {{ r.job }}</option>
              </select>
              <small v-if="!recordsWithJD.length">请先在总表中为岗位补充 JD。</small>
            </div>

            <div class="analysis-field">
              <label for="analysis-mode">分析模式</label>
              <select id="analysis-mode" v-model="analysisMode">
                <option value="match">综合匹配分析</option>
                <option value="technical">技术面试训练</option>
                <option value="hr">HR 面试训练</option>
                <option value="full">完整面试流程</option>
                <option value="resume">简历定向优化</option>
              </select>
            </div>

            <div class="analysis-field">
              <label for="analysis-focus">特别关注</label>
              <textarea id="analysis-focus" v-model="focus" maxlength="1000" rows="3" placeholder="例如：重点分析 Linux 项目的表达与技术深度"></textarea>
              <small>{{ focus.length }} / 1000，可选</small>
            </div>
          </div>

          <button class="btn btn-primary analysis-run" type="button" :disabled="!canRun || loading" @click="runAnalysis">
            <span v-if="loading" class="analysis-spinner" aria-hidden="true"></span>
            {{ loading ? '正在分析' : '开始分析' }}
          </button>
          <p class="analysis-privacy">简历和岗位信息将发送至已配置的 {{ aiProviderLabel }} API。</p>
        </section>

        <section class="analysis-history-panel">
          <div class="analysis-section-head compact">
            <div><h3>分析历史</h3><p>{{ history.length }} 条已保存记录</p></div>
            <button class="analysis-history-refresh" type="button" :disabled="loadingHistory" @click="loadHistory">刷新</button>
          </div>

          <div class="analysis-history-list" aria-live="polite">
            <div v-if="loadingHistory" class="analysis-history-loading"><span v-for="item in 3" :key="item"></span></div>
            <div v-else-if="!history.length" class="analysis-history-empty"><strong>暂无分析记录</strong><p>完成第一次分析后，结果会保存在这里。</p></div>
            <article v-for="h in history" v-else :key="h.id" class="analysis-history-entry" :class="{ active: activeHistory === h.id }">
              <button class="analysis-history-main" type="button" @click="viewHistory(h.id)">
                <span class="analysis-history-title"><strong>{{ h.company || '未命名公司' }}</strong><time>{{ fmtTime(h.created_at) }}</time></span>
                <span>{{ h.job || '未填写岗位' }}</span>
                <small>{{ h.analysis_mode_label || '综合匹配分析' }} / {{ h.resume || '简历名称未知' }}</small>
              </button>
              <div class="analysis-history-actions">
                <a class="analysis-text-action" :href="'/api/ai/history/' + encodeURIComponent(h.id) + '/download?token=' + encodeURIComponent(auth.token)" target="_blank" rel="noopener">下载</a>
                <button class="analysis-text-action danger" type="button" @click="deleteHistory(h.id)">删除</button>
              </div>
            </article>
          </div>
        </section>
      </aside>

      <section class="analysis-result-panel">
        <header class="analysis-result-head">
          <div><h3>分析结果</h3><p>{{ resultMeta }}</p></div>
          <div v-if="selectedRecordInfo" class="analysis-target"><span>{{ selectedRecordInfo.company }}</span><strong>{{ selectedRecordInfo.job }}</strong></div>
        </header>

        <div class="analysis-result-body">
          <div v-if="loading" class="analysis-result-loading" aria-live="polite">
            <div class="analysis-loading-copy"><span class="analysis-spinner dark" aria-hidden="true"></span><div><strong>正在生成分析</strong><p>读取简历并对照岗位要求，请稍候。</p></div></div>
            <div class="analysis-result-skeleton"><span></span><span></span><span></span><span></span><span></span></div>
          </div>
          <div v-else-if="resultError" class="analysis-result-error" role="alert">
            <strong>分析未完成</strong><p>{{ resultError }}</p><button class="btn" type="button" :disabled="!canRun" @click="runAnalysis">重新分析</button>
          </div>
          <div v-else-if="resultHtml" class="ai-result analysis-result-content" v-html="resultHtml"></div>
          <div v-else class="analysis-result-empty">
            <div class="analysis-empty-lines" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
            <h3>从一次有目标的分析开始</h3><p>选择简历、目标岗位和分析模式，结果会在这里生成。</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.analysis-page{min-width:0}.analysis-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.analysis-page-head h2{margin:0;font-size:clamp(22px,2.5vw,30px);line-height:1.2;letter-spacing:-.035em}.analysis-page-head>div:first-child p{max-width:600px;margin-top:7px;color:var(--muted);font-size:13px}.analysis-provider{display:flex;align-items:baseline;gap:8px;padding:8px 11px;border:1px solid var(--line);border-radius:10px;background:var(--panel);white-space:nowrap}.analysis-provider span{color:var(--sub);font-size:10px}.analysis-provider strong{color:var(--blue);font-size:11px}.analysis-workspace{display:grid;grid-template-columns:minmax(320px,390px) minmax(0,1fr);gap:14px;min-height:calc(100vh - 188px)}.analysis-controls{display:grid;min-width:0;align-content:start;gap:14px}.analysis-setup,.analysis-history-panel,.analysis-result-panel{min-width:0;overflow:hidden;border:1px solid var(--line);border-radius:16px;background:var(--panel);box-shadow:var(--shadow)}.analysis-setup{padding:17px}.analysis-section-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.analysis-section-head h3,.analysis-result-head h3{margin:0;font-size:14px}.analysis-section-head p,.analysis-result-head p{margin-top:4px;color:var(--sub);font-size:10px;line-height:1.5}.analysis-section-head.compact{padding:15px 16px 12px;border-bottom:1px solid var(--line)}.analysis-ready{padding:4px 8px;border-radius:8px;background:var(--bg);color:var(--sub);font-size:9px;font-weight:800;white-space:nowrap}.analysis-ready.ready{background:var(--greenS);color:var(--green)}.analysis-form{display:grid;gap:13px;margin-top:18px}.analysis-field{min-width:0}.analysis-field label{display:block;margin-bottom:6px;color:var(--muted);font-size:11px;font-weight:800}.analysis-label-row{display:flex;align-items:center;justify-content:space-between;gap:10px}.analysis-label-row label{margin-bottom:6px}.analysis-field select,.analysis-field textarea{width:100%;border:1px solid var(--line2);border-radius:10px;outline:none;background:var(--bg);color:var(--ink);font:12px var(--font);transition:border-color .18s ease,box-shadow .18s ease}.analysis-field select{height:39px;padding:0 10px}.analysis-field textarea{min-height:74px;padding:9px 10px;resize:vertical;line-height:1.55}.analysis-field select:focus,.analysis-field textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blueS)}.analysis-field textarea::placeholder{color:var(--sub)}.analysis-field>small{display:block;margin-top:5px;color:var(--sub);font-size:9px;text-align:right}.analysis-field>a{display:inline-block;margin-top:5px;font-size:10px}.analysis-jd-note{margin-bottom:6px;padding:0;border:0;background:transparent;color:var(--amber);font:800 9px var(--font);cursor:pointer}.analysis-jd-note:hover{text-decoration:underline}.analysis-run{display:inline-flex;width:100%;height:42px;align-items:center;justify-content:center;gap:8px;margin-top:15px;white-space:nowrap}.analysis-spinner{width:14px;height:14px;flex:0 0 auto;border:2px solid color-mix(in srgb,#fff 44%,transparent);border-top-color:#fff;border-radius:50%;animation:analysis-spin .75s linear infinite}.analysis-spinner.dark{width:18px;height:18px;border-color:var(--line2);border-top-color:var(--blue)}.analysis-privacy{margin:9px 4px 0;color:var(--sub);font-size:9px;line-height:1.45;text-align:center}.analysis-history-panel{display:flex;min-height:260px;max-height:390px;flex-direction:column}.analysis-history-refresh{padding:2px 0;border:0;background:transparent;color:var(--blue);font:800 10px var(--font);cursor:pointer}.analysis-history-refresh:disabled{cursor:wait;opacity:.55}.analysis-history-list{min-height:0;padding:8px;overflow:auto}.analysis-history-entry{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;border:1px solid transparent;border-radius:11px}.analysis-history-entry+.analysis-history-entry{margin-top:5px}.analysis-history-entry:hover{background:var(--bg)}.analysis-history-entry.active{border-color:var(--blue);background:var(--blueS)}.analysis-history-main{min-width:0;padding:9px 8px;border:0;background:transparent;color:var(--ink);text-align:left;cursor:pointer}.analysis-history-title{display:flex;min-width:0;align-items:baseline;justify-content:space-between;gap:8px}.analysis-history-title strong,.analysis-history-main>span,.analysis-history-main small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.analysis-history-title strong{font-size:11px}.analysis-history-title time{color:var(--sub);font-size:8px;white-space:nowrap}.analysis-history-main>span{margin-top:2px;color:var(--muted);font-size:10px}.analysis-history-main small{margin-top:3px;color:var(--sub);font-size:8px}.analysis-history-actions{display:grid;gap:3px;padding-right:9px}.analysis-text-action{padding:2px;border:0;background:transparent;color:var(--blue);font:800 9px var(--font);text-align:center;text-decoration:none;cursor:pointer}.analysis-text-action.danger{color:var(--red)}.analysis-text-action:hover{text-decoration:underline}.analysis-history-empty{padding:34px 16px;color:var(--muted);text-align:center}.analysis-history-empty strong{color:var(--ink);font-size:12px}.analysis-history-empty p{margin-top:6px;font-size:10px}.analysis-history-loading{display:grid;gap:6px}.analysis-history-loading span{height:54px;border-radius:10px;background:linear-gradient(100deg,var(--bg) 20%,var(--line) 42%,var(--bg) 64%);background-size:220% 100%;animation:analysis-shimmer 1.2s ease-in-out infinite}.analysis-result-panel{display:grid;grid-template-rows:auto minmax(0,1fr);min-height:560px}.analysis-result-head{display:flex;min-width:0;align-items:center;justify-content:space-between;gap:18px;padding:15px 18px;border-bottom:1px solid var(--line)}.analysis-result-head>div:first-child{min-width:0}.analysis-result-head p{max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.analysis-target{min-width:0;max-width:42%;padding-left:16px;border-left:1px solid var(--line);text-align:right}.analysis-target span,.analysis-target strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.analysis-target span{color:var(--sub);font-size:9px}.analysis-target strong{margin-top:2px;font-size:11px}.analysis-result-body{min-height:0;padding:12px;overflow:hidden;background:var(--bg)}.analysis-result-content{height:100%;min-height:520px;padding:22px 24px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}.analysis-result-loading{min-height:520px;padding:30px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}.analysis-loading-copy{display:flex;align-items:center;gap:12px}.analysis-loading-copy strong{display:block;font-size:13px}.analysis-loading-copy p{margin-top:3px;color:var(--muted);font-size:10px}.analysis-result-skeleton{display:grid;gap:13px;margin-top:34px}.analysis-result-skeleton span{height:12px;border-radius:6px;background:var(--line)}.analysis-result-skeleton span:nth-child(2){width:82%}.analysis-result-skeleton span:nth-child(3){width:94%}.analysis-result-skeleton span:nth-child(4){width:68%}.analysis-result-skeleton span:nth-child(5){width:76%;margin-top:20px}.analysis-result-error,.analysis-result-empty{display:grid;min-height:520px;align-content:center;justify-items:center;padding:42px 24px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--muted);text-align:center}.analysis-result-error strong{color:var(--red);font-size:15px}.analysis-result-error p{max-width:480px;margin:8px 0 16px;font-size:11px;line-height:1.6}.analysis-empty-lines{display:grid;width:120px;gap:8px}.analysis-empty-lines span{height:7px;border-radius:4px;background:var(--line2)}.analysis-empty-lines span:nth-child(1){width:56%;height:12px;background:var(--blue)}.analysis-empty-lines span:nth-child(3){width:84%}.analysis-empty-lines span:nth-child(4){width:70%}.analysis-result-empty h3{margin:25px 0 0;color:var(--ink);font-size:16px}.analysis-result-empty p{max-width:390px;margin-top:7px;font-size:11px;line-height:1.6}@keyframes analysis-spin{to{transform:rotate(360deg)}}@keyframes analysis-shimmer{to{background-position:-120% 0}}
.analysis-workspace{min-height:0}
.analysis-workspace{height:auto;align-items:stretch}
.analysis-controls{grid-template-rows:none;min-height:0}
.analysis-history-panel{height:auto;min-height:260px;max-height:390px}
.analysis-result-panel{height:auto;min-height:0;contain:size}
.analysis-result-body{min-height:0;overflow:auto}
.analysis-result-content{height:auto;min-height:100%;box-sizing:border-box}
.analysis-result-loading,.analysis-result-error,.analysis-result-empty{height:100%;min-height:0;box-sizing:border-box}
.analysis-result-empty{padding:clamp(48px,8vh,88px) clamp(28px,5vw,64px)}
.analysis-empty-lines{width:clamp(180px,22vw,250px);gap:clamp(10px,1.4vh,15px)}
.analysis-empty-lines span{height:clamp(10px,1.2vh,14px);border-radius:7px}
.analysis-empty-lines span:nth-child(1){height:clamp(18px,2vh,24px)}
.analysis-result-empty h3{margin-top:clamp(30px,4vh,46px);font-size:clamp(22px,2.5vw,30px);letter-spacing:-.025em}
.analysis-result-empty p{max-width:560px;margin-top:clamp(12px,1.8vh,18px);font-size:clamp(13px,1.35vw,17px);line-height:1.75}
@media(max-width:1060px){.analysis-workspace{grid-template-columns:minmax(290px,340px) minmax(0,1fr)}}
@media(max-width:820px){.analysis-page-head{align-items:flex-start;flex-direction:column}.analysis-provider{max-width:100%}.analysis-workspace{height:auto;grid-template-columns:1fr;min-height:0}.analysis-controls{display:contents}.analysis-setup{order:1}.analysis-result-panel{height:auto;order:2;min-height:480px;contain:none}.analysis-history-panel{height:auto;order:3;max-height:420px}.analysis-result-content,.analysis-result-loading,.analysis-result-error,.analysis-result-empty{height:auto;min-height:430px}}
@media(max-width:520px){.analysis-page-head>div:first-child p{font-size:12px}.analysis-provider{width:100%;justify-content:space-between}.analysis-setup,.analysis-history-panel,.analysis-result-panel{border-radius:12px}.analysis-target{display:none}.analysis-result-body{padding:8px}.analysis-result-content{padding:17px 15px}}
@media(prefers-reduced-motion:reduce){.analysis-spinner,.analysis-history-loading span{animation:none}}
</style>
