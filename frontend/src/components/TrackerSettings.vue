<template>
  <div class="tracker-settings">
    <div class="settings-section-title">
      <div><b>进度跟踪配置</b><span>通过通用 IMAP 读取招聘邮件并匹配个人总表</span></div>
      <span class="tracker-state" :class="{ active: config.enabled }">{{ config.enabled ? '跟踪中' : config.email ? '已配置' : '未配置' }}</span>
    </div>

    <div class="grid-2 tracker-form">
      <div class="form-group"><label>邮箱地址</label><input v-model="form.email" type="email" placeholder="name@163.com"></div>
      <div class="form-group"><label>客户端授权码</label><input v-model="form.authorization_code" type="password" :placeholder="config.authorization_code_saved ? '已保存时可留空' : '请输入客户端授权码'"></div>
      <div class="form-group"><label>IMAP 服务器</label><input v-model="form.imap_host"></div>
      <div class="form-group"><label>SSL 端口</label><input v-model.number="form.imap_port" type="number" min="1" max="65535"></div>
      <div class="form-group"><label>更新方式</label><select v-model="form.mode"><option value="confirm">识别后由我确认</option><option value="auto">高置信度自动更新</option></select></div>
      <div class="form-group tracker-enable-group"><label>自动跟踪</label>
        <label class="tracker-toggle"><input type="checkbox" v-model="form.enabled"><span></span><b>按设定周期检查新邮件</b></label>
      </div>
      <div class="form-group tracker-ai-group"><label>识别引擎</label>
        <label class="tracker-toggle"><input type="checkbox" v-model="form.ai_enabled" @change="loadAiModels"><span></span><b>使用当前大模型判断全部新增邮件</b></label>
      </div>
      <div class="form-group" v-if="form.ai_enabled"><label>跟踪模型</label>
        <select v-model="selectedModelIndex">
          <option v-for="(m,i) in aiModels" :key="i" :value="i">{{ m.label }} · {{ m.model }}</option>
        </select>
      </div>
      <div class="form-group tracker-cycle-group"><label>跟踪周期</label>
        <div class="tracker-cycle">
          <button v-for="opt in cycleOptions" :key="opt.value" type="button" :data-minutes="opt.value"
                  :class="{ active: form.sync_interval_minutes === opt.value }"
                  @click="form.sync_interval_minutes = opt.value">{{ opt.label }}</button>
        </div>
      </div>
    </div>

    <div class="tracker-ai-notice">{{ form.ai_enabled ? 'AI模式：邮件将发送至大模型进行批量识别' : '本地模式：仅使用本地关键词判断，邮件正文不会发送给大模型' }}</div>
    <div class="tracker-sync-note">{{ syncStatus }}</div>
    <div class="tracker-task" v-if="taskProgress" :class="{ running: taskProgress.status === 'running' }">
      <div><b>{{ taskProgress.stage }}</b><span>{{ taskProgress.progress }}%</span></div>
      <i><em :style="{ width: taskProgress.progress + '%' }"></em></i>
    </div>

    <div style="display:flex;gap:8px;margin-top:12px">
      <button class="btn btn-danger" @click="resetCache">清空同步缓存</button>
      <button class="btn" @click="testSync" :disabled="syncing">测试同步</button>
      <button class="btn" @click="startSync" :disabled="syncing">立即同步</button>
      <button class="btn btn-primary" @click="save" :disabled="saving">保存跟踪配置</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { get, post } from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

// --- stores ---
const auth = useAuthStore()
const toast = useToastStore()

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

// --- state ---
const form = ref({
  email: '',
  authorization_code: '',
  imap_host: 'imap.163.com',
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
let pollingTimer = null

// --- lifecycle ---
onMounted(async () => {
  await Promise.all([
    loadConfig(),
    loadAiModels().catch(() => {}),
  ])
})

onUnmounted(() => {
  stopPolling()
})

// --- helpers ---
function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
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

      // Restore AI model selection if models are already loaded
      if (c.ai_provider && c.ai_model && aiModels.value.length) {
        const idx = aiModels.value.findIndex(
          m => m.provider === c.ai_provider && m.model === c.ai_model
        )
        if (idx >= 0) selectedModelIndex.value = idx
      }
    }
    if (data.events && data.events.length) {
      const last = data.events[0]
      syncStatus.value = `上次同步: ${last.message || last.status || ''}`
    }
  } catch (e) {
    // silently fail — form stays at defaults
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

    // Try to restore saved AI model selection
    if (config.value.ai_provider && config.value.ai_model && flat.length) {
      const idx = flat.findIndex(
        m => m.provider === config.value.ai_provider && m.model === config.value.ai_model
      )
      if (idx >= 0) selectedModelIndex.value = idx
    }
  } catch (e) {
    toast.error('加载 AI 模型列表失败: ' + e.message)
  }
}

// --- polling ---
function pollTask(taskId) {
  stopPolling()

  pollingTimer = setInterval(async () => {
    try {
      const data = await get(`/api/progress-tracker/tasks/${taskId}`)
      taskProgress.value = {
        status: data.status,
        stage: data.stage || '',
        progress: Number(data.progress) || 0,
      }

      if (data.status === 'completed') {
        stopPolling()
        syncing.value = false
        toast.success('同步完成')
        syncStatus.value = '同步完成'
        await loadConfig()
      } else if (data.status === 'failed') {
        stopPolling()
        syncing.value = false
        const errMsg = data.error || '未知错误'
        toast.error('同步失败: ' + errMsg)
        syncStatus.value = '同步失败: ' + errMsg
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
  syncing.value = true
  syncStatus.value = '测试同步中...'
  taskProgress.value = { status: 'running', stage: '测试同步', progress: 0 }
  try {
    const data = await post('/api/progress-tracker/test')
    pollTask(data.task_id)
  } catch (e) {
    syncing.value = false
    syncStatus.value = '测试同步失败: ' + e.message
    taskProgress.value = null
    toast.error('测试同步失败: ' + e.message)
  }
}

async function startSync() {
  syncing.value = true
  syncStatus.value = '同步中...'
  taskProgress.value = { status: 'running', stage: '同步中', progress: 0 }
  try {
    const data = await post('/api/progress-tracker/sync')
    pollTask(data.task_id)
  } catch (e) {
    syncing.value = false
    syncStatus.value = '同步失败: ' + e.message
    taskProgress.value = null
    toast.error('同步失败: ' + e.message)
  }
}

async function save() {
  saving.value = true
  try {
    const payload = { ...form.value }

    // Resolve AI provider/model from selected index
    if (payload.ai_enabled && aiModels.value[selectedModelIndex.value]) {
      const m = aiModels.value[selectedModelIndex.value]
      payload.ai_provider = m.provider
      payload.ai_model = m.model
    }

    // Don't send empty authorization_code if the server already has one saved
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
  if (!confirm('确定清空同步缓存？此操作不可恢复。')) return
  try {
    await post('/api/progress-tracker/reset')
    toast.success('缓存已清空')
    syncStatus.value = '缓存已清空'
  } catch (e) {
    toast.error('清空缓存失败: ' + e.message)
  }
}
</script>
