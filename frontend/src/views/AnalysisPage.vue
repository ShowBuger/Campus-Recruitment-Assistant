<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useDashboardStore } from '@/stores/dashboard'

const auth = useAuthStore()
const toast = useToastStore()
const dashboard = useDashboardStore()

const resumeFiles = ref([])
const selectedResume = ref('')
const selectedRecord = ref('')
const analysisMode = ref('match')
const focus = ref('')
const loading = ref(false)
const resultHtml = ref('')
const resultMeta = ref('—')
const history = ref([])
const activeHistory = ref('')

// AI provider info
const PROVIDER_LABELS = { deepseek: 'DeepSeek', openai: 'OpenAI GPT', anthropic: 'Claude', kimi: 'Kimi' }
const aiProviderLabel = ref('DeepSeek')
const aiModelLabel = ref('')

const recordsWithJD = computed(() => dashboard.records.filter(r => r.job_jd?.trim()))
const canRun = computed(() => selectedResume.value && selectedRecord.value)
const jdMissingCount = computed(() => (dashboard.records || []).length - recordsWithJD.value.length)

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
    const values = cfg.values || {}
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
  try {
    const r = await fetch('/api/ai/history', { headers: { Authorization: `Bearer ${auth.token}` } })
    history.value = (await r.json()).items || []
  } catch { history.value = [] }
}

async function runAnalysis() {
  if (!selectedResume.value) { toast.error('请先选择简历'); return }
  if (!selectedRecord.value) { toast.error('请选择已填写 JD 的岗位；如无可选项，请先前往总表补充 JD'); return }
  loading.value = true; resultHtml.value = ''; resultMeta.value = '分析中'
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
    resultHtml.value = '<p style="color:var(--err)">分析失败：' + e.message + '</p>'
    resultMeta.value = '失败'
    toast.error(e.message)
  }
  finally { loading.value = false }
}

async function viewHistory(id) {
  activeHistory.value = id
  resultHtml.value = ''; resultMeta.value = '加载中…'
  try {
    const r = await fetch(`/api/ai/history/${id}`, { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('加载失败')
    const data = await r.json()
    resultHtml.value = data.analysis_html || ''
    resultMeta.value = [data.analysis_mode_label || '', data.company || '', data.job || '', data.provider_name || data.provider || '', data.model || '', String(data.created_at || '').replace('T', ' ')].filter(Boolean).join(' · ') || ''
  } catch (e) {
    activeHistory.value = ''
    toast.error('历史记录加载失败')
    resultHtml.value = ''; resultMeta.value = '—'
  }
}

async function deleteHistory(id) {
  if (!confirm('确定删除这条分析历史吗？此操作不可撤销。')) return
  try {
    const r = await fetch(`/api/ai/history/${encodeURIComponent(id)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('删除失败')
    if (activeHistory.value === id) { activeHistory.value = ''; resultHtml.value = ''; resultMeta.value = '—' }
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
  <div class="page active">
    <div class="ai-workspace">
      <div class="ai-side" style="display:flex;flex-direction:column;gap:16px">
        <!-- Config Card -->
        <div class="card ai-config-card">
          <div class="card-hd"><span class="dot g"></span><div class="card-title">AI 简历与岗位分析</div><div class="card-sub">{{ aiModelLabel }}</div></div>
          <div class="card-body">
            <div class="ai-form-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
              <div class="form-group">
                <label>选择简历</label>
                <select v-model="selectedResume" class="input">
                  <option value="">请选择已上传简历</option>
                  <option v-for="f in resumeFiles" :key="f.name" :value="f.name">{{ f.name }}</option>
                </select>
              </div>
              <div class="form-group ai-record-group" style="position:relative">
                <label>选择总表岗位
                  <span class="ai-jd-reminder" :class="{ warning: jdMissingCount > 0 }" role="button" tabindex="0" :title="jdMissingCount > 0 ? '另有 ' + jdMissingCount + ' 个岗位未填写 JD' : '仅展示已填写岗位 JD 的记录'" @click="toast.info(jdMissingCount > 0 ? '另有 ' + jdMissingCount + ' 个岗位未填写 JD' : '仅展示已填写岗位 JD 的记录')">JD</span>
                </label>
                <select v-model="selectedRecord" class="input">
                  <option value="">请选择公司与岗位</option>
                  <option v-for="r in recordsWithJD" :key="r.record_id" :value="r.record_id">{{ r.company }} · {{ r.job }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>分析模式</label>
                <select v-model="analysisMode" class="input">
                  <option value="match">综合匹配分析</option>
                  <option value="technical">技术面试训练</option>
                  <option value="hr">HR 面试训练</option>
                  <option value="full">完整面试流程</option>
                  <option value="resume">简历定向优化</option>
                </select>
              </div>
              <div class="form-group">
                <label>特别关注</label>
                <input v-model="focus" class="input" maxlength="1000" placeholder="例如：重点分析 Linux 项目">
              </div>
            </div>
            <div class="ai-action-row" style="display:flex;align-items:center;gap:12px;margin-top:12px">
              <button class="btn btn-primary" @click="runAnalysis" :disabled="!canRun || loading">{{ loading ? '分析中…' : '开始分析' }}</button>
              <div class="help">将岗位信息与简历文本发送至已配置的 {{ aiProviderLabel }} API。</div>
            </div>
          </div>
        </div>

        <!-- History Card -->
        <div class="card ai-history-card">
          <div class="card-hd"><span class="dot a"></span><div class="card-title">分析历史</div><div class="card-sub">{{ history.length }} 条</div></div>
          <div class="card-body">
            <div class="analysis-history" style="max-height:40vh;overflow:auto">
              <div v-if="!history.length" class="center muted" style="padding:12px">暂无分析历史</div>
              <div v-for="h in history" :key="h.id" class="analysis-history-row" style="border-bottom:1px solid var(--line)">
                <div style="padding:8px 12px;cursor:pointer" @click="viewHistory(h.id)" :class="{ active: activeHistory === h.id }">
                  <b style="font-size:12px">{{ h.company || '—' }}</b>
                  <span style="display:block;font-size:10px;color:var(--sub)">{{ h.analysis_mode_label || '综合匹配分析' }} · {{ h.job || '—' }} · {{ h.resume || '—' }}</span>
                  <time style="font-size:10px;color:var(--muted)">{{ fmtTime(h.created_at) }}</time>
                </div>
                <div class="analysis-history-actions" style="padding:0 12px 8px">
                  <a class="btn analysis-download" :href="'/api/ai/history/' + encodeURIComponent(h.id) + '/download?token=' + encodeURIComponent(auth.token)" target="_blank">下载</a>
                  <button class="btn btn-danger" @click="deleteHistory(h.id)">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Result Card -->
      <div class="card ai-result-card" style="flex:1">
        <div class="card-hd"><span class="dot"></span><div class="card-title">分析结果</div><div class="card-sub">{{ resultMeta }}</div></div>
        <div class="card-body">
          <div class="ai-result" style="line-height:1.8;min-height:200px">
            <div v-if="loading" class="center" style="padding:40px">正在读取简历并调用 AI 分析，请稍候…</div>
            <div v-else-if="resultHtml" v-html="resultHtml"></div>
            <div v-else class="center muted" style="padding:40px">选择简历和岗位后开始分析。</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
