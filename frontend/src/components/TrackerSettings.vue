<template>
  <div class="tracker-settings">
    <div class="settings-section-title">
      <div><b>进度跟踪配置</b><span>通过通用 IMAP 读取招聘邮件并匹配个人总表</span></div>
      <span class="tracker-state" :class="{ active: config.enabled }">{{ config.enabled ? '跟踪中' : config.email ? '已配置' : '未配置' }}</span>
    </div>

    <div class="grid-2 tracker-form">
      <div class="form-group"><label for="tracker-email">邮箱地址</label><input id="tracker-email" v-model="form.email" type="email" autocomplete="email" placeholder="name@163.com"></div>
      <div class="form-group"><label for="tracker-code">客户端授权码</label><input id="tracker-code" v-model="form.authorization_code" type="password" autocomplete="new-password" :placeholder="config.authorization_code_saved ? '••••••••••••••••  已保存' : '请输入客户端授权码'" :class="{ 'secret-saved': config.authorization_code_saved }"><div class="help" id="tracker-code-help" :class="{ saved: config.authorization_code_saved }">{{ config.authorization_code_saved ? '✓ 授权码已安全保存；留空不会删除，输入新授权码才会替换' : '请勿填写邮箱登录密码' }}</div></div>
      <div class="form-group tracker-mode-group" style="max-width:220px"><label for="tracker-mode">更新方式</label><select id="tracker-mode" v-model="form.mode"><option value="confirm">识别后由我确认</option><option value="auto">高置信度自动更新</option></select></div>
      <div class="form-group tracker-enable-group"><label>自动跟踪</label>
        <div class="total-view-switch">
          <button :class="{ active: !form.enabled }" @click="form.enabled = false">关闭</button>
          <button :class="{ active: form.enabled }" @click="form.enabled = true">开启</button>
        </div>
      </div>
      <div class="form-group" style="max-width:180px" :style="{ visibility: form.enabled ? 'visible' : 'hidden' }"><label for="tracker-cycle">跟踪周期</label>
        <select id="tracker-cycle" v-model="form.sync_interval_minutes">
          <option v-for="opt in cycleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="form-group tracker-ai-group"><label>识别引擎</label>
        <div class="total-view-switch">
          <button :class="{ active: !form.ai_enabled }" @click="form.ai_enabled = false">本地</button>
          <button :class="{ active: form.ai_enabled }" @click="form.ai_enabled = true; loadAiModels()">大模型</button>
        </div>
      </div>
      <div class="form-group" id="tracker-ai-model-group" :style="{ visibility: form.ai_enabled ? 'visible' : 'hidden' }"><label for="tracker-ai-model">跟踪模型</label>
        <select id="tracker-ai-model" v-model="selectedModelIndex">
          <option v-if="!aiModels.length" value="">请先在 AI 配置中保存 API Key</option>
          <option v-for="(m,i) in aiModels" :key="i" :value="i">{{ m.label }} · {{ m.model }}</option>
        </select>
        <div class="help">选择用于批量识别招聘邮件的模型，建议使用轻量模型以节省成本</div>
      </div>
    </div>

    <div class="tracker-ai-notice" :style="{ visibility: form.ai_enabled ? 'visible' : 'hidden' }">大模型模式：邮件前段会发送给当前 AI 服务商；接口失效、超时或余额不足时自动切换本地关键词识别。</div>
    <div class="tracker-sync-note">{{ syncStatus }}</div>
    <div class="tracker-task" v-if="taskProgress" :class="{ running: taskProgress.status === 'running' && taskProgress.progress < 100 }">
      <div><b>{{ taskProgress.stage }}</b><span>{{ taskProgress.progress }}%</span></div>
      <i><em :style="{ width: taskProgress.progress + '%' }"></em></i>
    </div>

    <!-- Results Modal (test sync preview / pending events confirmation) -->
    <div class="modal-mask" :class="{ show: showResultsModal }" @mousedown.self="showResultsModal = false">>
      <div class="modal tracker-test-modal">
        <div class="modal-hd">
          <div><h2>{{ resultsTitle }}</h2><p>{{ resultsSummary }}</p></div>
          <button class="icon-btn" @click="showResultsModal = false" title="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <div class="tracker-event-list" v-if="resultsEvents.length">
            <article v-for="item in resultsEvents" :key="item.id" class="tracker-event" :class="{ 'tracker-test-result': resultsMode === 'test' }" :data-event-id="item.id">
              <div class="tracker-event-main">
                <div><b>{{ item.company || (item.record_id ? '已匹配岗位' : item.progress === '非招聘邮件' ? '普通邮件' : '未匹配岗位') }}</b><span>{{ item.job || item.subject || '招聘邮件' }}</span></div>
                <em>{{ item.progress }}</em>
              </div>
              <div class="tracker-event-meta">
                <span v-if="item.created_at">{{ formatTime(item.created_at) }}</span>
                <span>置信度 {{ Math.round(Number(item.confidence || 0) * 100) }}%</span>
                <span v-if="!item.record_id && item.progress !== '非招聘邮件' && item.progress !== '判断失败'" class="tracker-unmatched">请先在个人总表维护相同公司名称</span>
                <span v-if="item.error" class="tracker-unmatched">{{ item.error }}</span>
              </div>

              <!-- Pending mode: actions -->
              <template v-if="resultsMode === 'pending' && item.status === 'pending'">
                <div v-if="item.progress === '面试'" class="tracker-round-picker">
                  确认面试轮次
                  <select :id="'tracker-round-' + item.id">
                    <option value="">请选择</option>
                    <option value="1" :selected="Number(item.interview_round) === 1">一面</option>
                    <option value="2" :selected="Number(item.interview_round) === 2">二面</option>
                    <option value="3" :selected="Number(item.interview_round) === 3">三面</option>
                  </select>
                </div>
                <div class="tracker-event-actions">
                  <button v-if="item.record_id" class="btn btn-primary" @click="actEvent(item.id, 'confirm')">确认更新</button>
                  <button v-else class="btn btn-primary" @click="actEvent(item.id, 'create')">一键添加记录</button>
                  <button class="btn" @click="actEvent(item.id, 'ignore')">忽略</button>
                </div>
                <span v-if="item.status !== 'pending'" class="tracker-event-state" :class="item.status">{{ statusLabels[item.status] || item.status }}</span>
              </template>
            </article>
          </div>
          <div v-else class="center muted">没有可预览的邮件</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { get, post } from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useDashboardStore } from '@/stores/dashboard'
import { useAppStore } from '@/stores/app'
import { useDialogStore } from '@/stores/dialog'

// ── 邮箱自动判断 IMAP 服务器与端口 ──
const IMAP_PRESETS = {
  '163.com':  { host: 'imap.163.com', port: 993 },
  '126.com':  { host: 'imap.126.com', port: 993 },
  'yeah.net': { host: 'imap.yeah.net', port: 993 },
  'qq.com':   { host: 'imap.qq.com', port: 993 },
  'foxmail.com': { host: 'imap.qq.com', port: 993 },
  'gmail.com': { host: 'imap.gmail.com', port: 993 },
  'outlook.com': { host: 'outlook.office365.com', port: 993 },
  'hotmail.com': { host: 'outlook.office365.com', port: 993 },
  'live.com':  { host: 'outlook.office365.com', port: 993 },
  'sina.com':  { host: 'imap.sina.com', port: 993 },
  'aliyun.com': { host: 'imap.aliyun.com', port: 993 },
}

function detectIMAP(email) {
  if (!email || !email.includes('@')) return null
  const domain = email.split('@')[1]?.toLowerCase()
  if (!domain) return null
  return IMAP_PRESETS[domain] || null
}

// --- stores ---
const auth = useAuthStore()
const toast = useToastStore()
const dashboard = useDashboardStore()
const app = useAppStore()
const dialog = useDialogStore()

// --- constants ---
const cycleOptions = [
  { label: '5分钟', value: 5 },
  { label: '15分钟', value: 15 },
  { label: '30分钟', value: 30 },
  { label: '1小时', value: 60 },
  { label: '3小时', value: 180 },
  { label: '6小时', value: 360 },
  { label: '12小时', value: 720 },
  { label: '24小时', value: 1440 },
]
const statusLabels = { pending: '待确认', applied: '已更新', ignored: '已忽略', preview: '测试预览', error: '判断失败' }

// --- state ---
const form = ref({
  email: '',
  authorization_code: '',
  imap_host: '',
  imap_port: 993,
  enabled: false,
  mode: 'confirm',
  ai_enabled: false,
  sync_interval_minutes: 30,
})

const config = ref({})
const aiModels = ref([])
const selectedModelIndex = ref(0)
const syncStatus = ref('')
const taskProgress = ref(null)
const syncing = ref(false)
const saving = ref(false)
const resetting = ref(false)
let pollingTimer = null

// Visual progress smoothing (match old showTrackerTask)
const STAGE_CAPS = {
  '创建同步任务': 4, '等待开始': 5, '连接邮箱': 8, '打开收件箱': 10,
  '检查新增邮件': 12, '缓存邮件': 52, 'AI 批量分析': 80,
  'AI 不可用，切换本地识别': 80, '本地分析': 80, '整理识别结果': 96, '完成': 100
}
let visualProgress = 0
let visualStage = ''
let visualStageAt = 0

function resetVisualProgress() {
  visualProgress = 0
  visualStage = ''
  visualStageAt = Date.now()
}

function updateVisualProgress(task) {
  const stage = task.stage || '处理中'
  const actual = Math.max(0, Math.min(100, Number(task.progress || 0)))
  const isAI = stage.indexOf('AI ') === 0
  const cap = isAI ? 80 : (STAGE_CAPS[stage] || Math.min(99, actual + 5))

  if (stage !== visualStage) {
    visualStage = stage
    visualStageAt = Date.now()
    visualProgress = Math.max(visualProgress, actual)
  } else if (task.status === 'running' && visualProgress < cap) {
    const step = isAI ? 1 : (stage === '连接邮箱' ? 0.5 : 0.35)
    visualProgress = Math.min(cap, visualProgress + step)
  }
  visualProgress = Math.max(visualProgress, actual)
  if (task.status === 'completed' || stage === '完成') visualProgress = 100

  const shown = Math.round(Math.min(100, visualProgress))
  const wait = Math.floor((Date.now() - visualStageAt) / 1000)
  const label = stage + (task.status === 'running' && wait >= 3 ? ' · ' + wait + 's' : '')

  taskProgress.value = {
    status: task.status || 'queued',
    stage: label,
    progress: shown,
  }
}

// Pending events
const pendingCount = ref(0)

// Results modal
const showResultsModal = ref(false)
const resultsMode = ref('test') // 'test' | 'pending'
const resultsTitle = ref('同步结果')
const resultsSummary = ref('')
const resultsEvents = ref([])

// --- lifecycle ---
onMounted(async () => {
  await loadConfig()
  await loadAiModels().catch(() => {})
})

onUnmounted(() => {
  stopPolling()
})

// ── 邮箱变动自动判断 IMAP 配置 ──
watch(() => form.value.email, (email) => {
  const preset = detectIMAP(email)
  if (preset) {
    form.value.imap_host = preset.host
    form.value.imap_port = preset.port
  }
})

// --- helpers ---
function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function formatTime(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T') + 'Z')
  return isNaN(date) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

// --- data loading ---
async function loadConfig() {
  try {
    const data = await get('/api/progress-tracker')
    if (data.config) {
      config.value = data.config
      const c = data.config
      form.value.email = c.email || ''
      form.value.imap_host = c.imap_host || 'imap.163.com'
      form.value.imap_port = c.imap_port ?? 993
      form.value.enabled = c.enabled ?? false
      form.value.mode = c.mode || 'confirm'
      form.value.ai_enabled = c.ai_enabled ?? false
      form.value.sync_interval_minutes = c.sync_interval_minutes || 30

      if (c.tracker_ai_provider && c.tracker_ai_model && aiModels.value.length) {
        const idx = aiModels.value.findIndex(
          m => m.provider === c.tracker_ai_provider && m.model === c.tracker_ai_model
        )
        if (idx >= 0) selectedModelIndex.value = idx
      }
      // Show last sync time (match old loadTrackerConfig)
      if (c.last_sync_at) {
        syncStatus.value = '上次同步 ' + formatTime(c.last_sync_at)
      } else if (c.last_error) {
        syncStatus.value = '错误：' + c.last_error
      } else {
        syncStatus.value = '尚未同步'
      }
    }
    // Load pending events count
    updatePendingCount(data.events)
  } catch (e) {
    // silently fail
  }
}

async function updatePendingCount(events) {
  if (events) {
    const pending = (events || []).filter(e => e.status === 'pending')
    pendingCount.value = pending.length
    app.setTrackerPending(pending)
  }
}

async function loadPendingEvents() {
  try {
    const data = await get('/api/progress-tracker')
    const events = data.events || []
    updatePendingCount(events)
    return events.filter(e => e.status === 'pending')
  } catch (e) {
    return []
  }
}

async function loadAiModels() {
  if (!form.value.ai_enabled) return
  try {
    const data = await get('/api/progress-tracker/ai-models')
    const flat = []
    for (const p of data.providers || []) {
      if (p.models && Array.isArray(p.models)) {
        for (const m of p.models) {
          flat.push({ provider: p.provider, label: p.label, model: m })
        }
      }
    }
    aiModels.value = flat

    if (config.value.tracker_ai_provider && config.value.tracker_ai_model && flat.length) {
      const idx = flat.findIndex(
        m => m.provider === config.value.tracker_ai_provider && m.model === config.value.tracker_ai_model
      )
      if (idx >= 0) selectedModelIndex.value = idx
    }
  } catch (e) {
    toast.error('加载 AI 模型列表失败: ' + e.message)
  }
}

// --- polling ---
function pollTask(taskId, isTest) {
  stopPolling()
  let attempts = 0

  pollingTimer = setInterval(async () => {
    try {
      const data = await get(`/api/progress-tracker/tasks/${taskId}`)
      const task = data.task || {}
      attempts++

      updateVisualProgress(task)

      if (task.status === 'completed') {
        stopPolling()
        syncing.value = false
        taskProgress.value.progress = 100
        syncStatus.value = '同步完成'

        const result = task.result || {}
        const events = result.events || []

        if (isTest) {
          // Show test results modal
          resultsMode.value = 'test'
          resultsTitle.value = '测试同步结果'
          resultsSummary.value = `已读取并判断 ${events.length} 封最近邮件，仅供预览，不会更新岗位进度`
          resultsEvents.value = events
          showResultsModal.value = true
        } else {
          // Reload tracker config to get pending events
          await loadConfig()
          // Refresh dashboard data so progress updates are visible
          await dashboard.fetch().catch(() => {})
          // Show pending events if any
          const pending = await loadPendingEvents()
          if (pending.length) {
            showPendingResults(pending)
          }
        }

        toast.success(result.message || '同步完成')
        setTimeout(() => { taskProgress.value = null }, 1800)
      } else if (task.status === 'failed') {
        stopPolling()
        syncing.value = false
        const errMsg = task.error || '未知错误'
        toast.error('同步失败: ' + errMsg)
        syncStatus.value = '同步失败: ' + errMsg
        setTimeout(() => { taskProgress.value = null }, 1800)
      } else if (attempts >= 360) {
        stopPolling()
        syncing.value = false
        toast.error('同步任务运行时间过长，请稍后查看结果')
        syncStatus.value = '同步超时'
        setTimeout(() => { taskProgress.value = null }, 1800)
      }
    } catch (e) {
      stopPolling()
      syncing.value = false
      syncStatus.value = '轮询失败: ' + e.message
    }
  }, 1000)
}

// --- actions ---
async function testSync() {
  // Save config first (match old saveTrackerConfig(false))
  if (!(await saveConfigSilent())) return
  syncing.value = true
  syncStatus.value = '测试同步中...'
  resetVisualProgress()
  updateVisualProgress({ stage: '创建同步任务', progress: 0, status: 'queued' })
  try {
    const data = await post('/api/progress-tracker/test')
    pollTask(data.task.id, true)
  } catch (e) {
    syncing.value = false
    syncStatus.value = '测试同步失败: ' + e.message
    taskProgress.value = null
    toast.error('测试同步失败: ' + e.message)
  }
}

async function startSync() {
  // Save config first (match old saveTrackerConfig(false))
  if (!(await saveConfigSilent())) return
  syncing.value = true
  syncStatus.value = '同步中...'
  resetVisualProgress()
  updateVisualProgress({ stage: '创建同步任务', progress: 0, status: 'queued' })
  try {
    const data = await post('/api/progress-tracker/sync')
    pollTask(data.task.id, false)
  } catch (e) {
    syncing.value = false
    syncStatus.value = '同步失败: ' + e.message
    taskProgress.value = null
    toast.error('同步失败: ' + e.message)
  }
}

function showPendingResults(events) {
  resultsMode.value = 'pending'
  resultsTitle.value = '待确认更新'
  resultsSummary.value = events.length ? `发现 ${events.length} 条待确认进度，可以现在处理或稍后再看` : '当前没有需要确认的进度'
  resultsEvents.value = events
  showResultsModal.value = true
}

async function actEvent(id, action) {
  try {
    const payload = { action }
    // Check for interview round picker
    const roundEl = document.getElementById('tracker-round-' + id)
    if ((action === 'confirm' || action === 'create') && roundEl && roundEl.value) {
      payload.interview_round = Number(roundEl.value)
    }
    const result = await post(`/api/progress-tracker/events/${id}`, payload)

    // Remove this event from the list
    resultsEvents.value = resultsEvents.value.filter(item => Number(item.id) !== Number(id))
    const remaining = resultsEvents.value.length
    resultsSummary.value = remaining ? `还有 ${remaining} 条待确认进度` : '处理完成，没有待确认进度'
    if (!remaining) {
      resultsEvents.value = []
    }

    // Refresh pending count
    await loadConfig()
    // Refresh dashboard if confirmed
    if (action === 'confirm' || action === 'create') {
      await dashboard.fetch().catch(() => {})
    }
    toast.success(result.message || '已处理')
  } catch (e) {
    toast.error('处理失败: ' + e.message)
  }
}

async function saveConfigSilent() {
  try {
    const payload = { ...form.value }
    if (payload.ai_enabled && aiModels.value[selectedModelIndex.value]) {
      const m = aiModels.value[selectedModelIndex.value]
      payload.tracker_ai_provider = m.provider
      payload.tracker_ai_model = m.model
    }
    if (!payload.authorization_code && config.value.authorization_code_saved) {
      delete payload.authorization_code
    }
    await post('/api/progress-tracker', payload)
    return true
  } catch (e) {
    toast.error('请先保存跟踪配置: ' + e.message)
    return false
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form.value }

    if (payload.ai_enabled && aiModels.value[selectedModelIndex.value]) {
      const m = aiModels.value[selectedModelIndex.value]
      payload.tracker_ai_provider = m.provider
      payload.tracker_ai_model = m.model
    }

    if (!payload.authorization_code && config.value.authorization_code_saved) {
      delete payload.authorization_code
    }

    await post('/api/progress-tracker', payload)
    toast.success('配置已保存')
    await loadConfig()
  } catch (e) {
    toast.error('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function resetCache() {
  const confirmed = await dialog.confirm(
    '这会删除待确认更新、邮件缓存和同步任务记录，并让下次同步按首次同步重新读取。\n\n邮箱与 AI 配置不会删除。',
    { title: '清空同步缓存', tone: 'danger', confirmText: '确认清空' },
  )
  if (!confirmed) return
  resetting.value = true
  try {
    await post('/api/progress-tracker/reset')
    pendingCount.value = 0
    app.clearTrackerPending()
    showResultsModal.value = false
    await loadConfig()
    await dashboard.fetch().catch(() => {})
    toast.success('同步缓存已清空')
  } catch (e) {
    toast.error('清空失败: ' + e.message)
  } finally {
    resetting.value = false
  }
}

defineExpose({ testSync, startSync, save, resetCache, syncing, saving, resetting })
</script>
