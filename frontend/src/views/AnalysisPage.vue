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
const history = ref([])
const activeHistory = ref('')

const recordsWithJD = computed(() => dashboard.records.filter(r => r.job_jd?.trim()))

const canRun = computed(() => selectedResume.value && selectedRecord.value)

onMounted(async () => {
  if (!dashboard.data) await dashboard.fetch()
  await loadResumes()
  await loadHistory()
})

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
  loading.value = true; resultHtml.value = ''
  try {
    const r = await fetch('/api/ai/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        resume_filename: selectedResume.value,
        record_id: selectedRecord.value,
        analysis_mode: analysisMode.value,
        focus: focus.value
      })
    })
    if (!r.ok) throw new Error((await r.json()).detail || '分析失败')
    const data = await r.json()
    resultHtml.value = data.analysis_html || '<p>无结果</p>'
    toast.success('分析完成')
    await loadHistory()
  } catch (e) { toast.error(e.message) }
  finally { loading.value = false }
}

async function viewHistory(id) {
  activeHistory.value = id
  try {
    const r = await fetch(`/api/ai/history/${id}`, { headers: { Authorization: `Bearer ${auth.token}` } })
    const data = await r.json()
    resultHtml.value = data.analysis_html || ''
  } catch { toast.error('加载历史失败') }
}

function fmtTime(v) { if (!v) return ''; return new Date(v).toLocaleString('zh-CN', { hour12: false }) }
</script>

<template>
  <div class="page active">
    <!-- Config Row -->
    <div class="card" style="margin-bottom:16px">
      <div style="display:flex;gap:12px;align-items:flex-end;padding:16px;flex-wrap:wrap">
        <div class="form-group" style="flex:1;min-width:180px">
          <label>选择简历</label>
          <select v-model="selectedResume" class="input">
            <option value="">请选择已上传简历</option>
            <option v-for="f in resumeFiles" :key="f.name" :value="f.name">{{ f.name }}</option>
          </select>
        </div>
        <div class="form-group" style="flex:1;min-width:200px">
          <label>选择岗位</label>
          <select v-model="selectedRecord" class="input">
            <option value="">请选择已填写JD的岗位</option>
            <option v-for="r in recordsWithJD" :key="r.record_id" :value="r.record_id">{{ r.company }} · {{ r.job }}</option>
          </select>
        </div>
        <div class="form-group" style="min-width:140px">
          <label>分析模式</label>
          <select v-model="analysisMode" class="input">
            <option value="match">综合匹配分析</option>
            <option value="technical">技术面试训练</option>
            <option value="hr">HR 面试训练</option>
            <option value="full">完整面试流程</option>
            <option value="resume">简历定向优化</option>
          </select>
        </div>
        <div class="form-group" style="min-width:120px">
          <label>特别关注（选填）</label>
          <input v-model="focus" class="input" placeholder="如：项目经验深度">
        </div>
        <button class="btn btn-primary" @click="runAnalysis" :disabled="!canRun || loading" style="height:38px">
          {{ loading ? '分析中…' : '开始分析' }}
        </button>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:220px minmax(0,1fr);gap:16px">
      <!-- History Sidebar -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">分析历史</div></div>
        <div style="max-height:60vh;overflow:auto">
          <div v-if="!history.length" class="center muted" style="padding:12px">暂无记录</div>
          <div v-for="h in history" :key="h.id" style="padding:8px 12px;cursor:pointer;border-bottom:1px solid var(--line)"
               @click="viewHistory(h.id)" :class="{ active: activeHistory === h.id }">
            <b style="font-size:12px">{{ h.company || '—' }}</b>
            <span style="display:block;font-size:10px;color:var(--sub)">{{ h.job || '—' }}</span>
            <span style="font-size:10px;color:var(--muted)">{{ fmtTime(h.created_at) }}</span>
          </div>
        </div>
      </div>

      <!-- Result -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">分析结果</div></div>
        <div v-if="loading" class="center" style="padding:40px">分析中，请稍候…</div>
        <div v-else-if="resultHtml" v-html="resultHtml" style="padding:16px;line-height:1.8"></div>
        <div v-else class="center muted" style="padding:40px">选择简历和岗位，点击"开始分析"</div>
      </div>
    </div>
  </div>
</template>
