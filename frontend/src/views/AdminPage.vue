<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'

const auth = useAuthStore()
const toast = useToastStore()
const dialog = useDialogStore()

const activePanel = ref('users')
const users = ref([])
const inviteCode = ref('')
const genLoading = ref(false)
const noticeTitle = ref('')
const noticeContent = ref('')
const notifLoading = ref(false)
const notifications = ref([])
const notificationsLoading = ref(false)
const pwMap = ref({})
const syncEnabled = ref(false)
const syncTime = ref('04:00')
const syncSources = ref({ givemeoc: true, qiuzhifangzhou: true })
const aiDedupEnabled = ref(true)
const sourceSyncing = ref(false)
const sourceProgress = ref(null)
const logLines = ref([])
const backups = ref([])
const backupLoading = ref(false)
let logStream = null
let sourcePollTimer = null

const aiDedupRunning = ref(false)
async function runAiDedup() {
  aiDedupRunning.value = true
  sourceProgress.value = { phase: 'ai_dedup', message: '正在用规则和 AI 分析共享总表中的重复记录…' }
  try {
    const data = await apiReq('POST', '/api/dashboard/shared/records/ai-dedup')
    sourceProgress.value = { finished: true, message: data.message }
    data.duplicates_removed > 0 ? toast.success(data.message) : toast.info(data.message)
  } catch (e) {
    sourceProgress.value = { failed: true, finished: true, message: e.message }
    toast.error('智能去重失败：' + e.message)
  } finally {
    aiDedupRunning.value = false
  }
}

const isRoot = computed(() => auth.user && (auth.user.is_root || auth.user.username === 'root'))

const userCountStr = computed(() => {
  const total = users.value.length
  const online = users.value.filter(u => u.is_online).length
  return total + ' 个用户 · ' + online + ' 在线'
})

function formatSystemTime(value) {
  if (!value) return ''
  const raw = String(value).replace(' ', 'T')
  const date = new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(raw) ? raw : raw + 'Z')
  return isNaN(date) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function formatBytes(value) {
  const bytes = Number(value || 0)
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function apiReq(method, url, body) {
  const headers = { Authorization: 'Bearer ' + auth.token }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const maxRetries = 1
  let lastError
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(30_000)
      })
      if (res.status === 401) { auth.clear(); throw new Error('登录已过期') }
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.error || '请求失败')
      return data
    } catch (e) {
      lastError = e
      if (e.message === '登录已过期') throw e
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 500 * (attempt + 1)))
        continue
      }
    }
  }
  throw lastError
}

async function loadAdminUsers() {
  try {
    const data = await apiReq('GET', '/api/admin/users')
    users.value = data.users || []
  } catch (e) { toast.error('用户列表加载失败：' + e.message) }
}

async function toggleAdmin(user) {
  try {
    await apiReq('POST', '/api/admin/users/' + user.id + '/admin', { is_admin: user.is_admin })
    toast.success('管理员权限已更新')
    await loadAdminUsers()
  } catch (e) {
    toast.error('权限修改失败：' + e.message)
    await loadAdminUsers()
  }
}

async function changePassword(user) {
  const pw = pwMap.value[user.id]
  if (!pw || pw.length < 4) { toast.error('密码至少 4 个字符'); return }
  try {
    await apiReq('POST', '/api/admin/users/' + user.id + '/password', { password: pw })
    toast.success('密码已更新')
    pwMap.value[user.id] = ''
  } catch (e) { toast.error('修改密码失败：' + e.message) }
}

async function deleteUser(user) {
  const confirmed = await dialog.confirm(
    '确定删除用户“' + user.username + '”吗？\n该用户的配置、日程、简历和分析历史也会一并删除。',
    { title: '删除用户', tone: 'danger', confirmText: '永久删除' },
  )
  if (!confirmed) return
  try {
    await apiReq('DELETE', '/api/admin/users/' + user.id)
    toast.success('用户已删除')
    await loadAdminUsers()
  } catch (e) {
    toast.error('删除失败：' + e.message)
    try { const d = await apiReq('GET', '/api/admin/users'); users.value = d.users || [] } catch (_) {}
  }
}

async function genInvite() {
  genLoading.value = true
  try {
    const data = await apiReq('POST', '/api/admin/invite-codes')
    const code = (data.invite_code && data.invite_code.code) || ''
    inviteCode.value = code
    if (code && navigator.clipboard) navigator.clipboard.writeText(code)
    toast.success(code ? '邀请码已生成并复制' : '邀请码已生成')
  } catch (e) { toast.error('邀请码生成失败：' + e.message) }
  finally { genLoading.value = false }
}

function copyCode() {
  const code = inviteCode.value
  if (code && navigator.clipboard) navigator.clipboard.writeText(code)
  toast.success('邀请码已复制')
}

async function sendNotif() {
  const title = noticeTitle.value.trim()
  const content = noticeContent.value.trim()
  if (!title || !content) { toast.error('请填写通知标题和内容'); return }
  notifLoading.value = true
  const requestId = (window.crypto && crypto.randomUUID ? crypto.randomUUID() : 'notice-' + Date.now() + '-' + Math.random().toString(36).slice(2))
  try {
    await apiReq('POST', '/api/admin/notifications', { title, content, request_id: requestId })
    noticeTitle.value = ''
    noticeContent.value = ''
    await loadNotifications()
    toast.success('通知已发布')
  } catch (e) { toast.error('发布失败：' + e.message) }
  finally { notifLoading.value = false }
}

async function loadNotifications() {
  notificationsLoading.value = true
  try {
    const data = await apiReq('GET', '/api/admin/notifications')
    notifications.value = data.notifications || []
  } catch (e) { toast.error('通知列表加载失败：' + e.message) }
  finally { notificationsLoading.value = false }
}

async function deleteNotification(item) {
  const confirmed = await dialog.confirm(
    '确定删除通知“' + item.title + '”吗？\n所有用户的通知列表中都会移除这条内容。',
    { title: '删除通知', tone: 'danger', confirmText: '永久删除' },
  )
  if (!confirmed) return
  try {
    await apiReq('DELETE', '/api/admin/notifications/' + item.id)
    notifications.value = notifications.value.filter(notification => notification.id !== item.id)
    toast.success('通知已删除')
  } catch (e) { toast.error('删除失败：' + e.message) }
}

function switchPanel(panel) {
  activePanel.value = panel
  if (panel === 'notice') loadNotifications()
  if (panel === 'logs') startLogStream()
  if (panel === 'backups') loadBackups()
}

async function loadBackups() {
  if (!isRoot.value) return
  try {
    const data = await apiReq('GET', '/api/admin/backups')
    backups.value = data.backups || []
  } catch (e) { toast.error('备份信息加载失败：' + e.message) }
}

async function createBackup() {
  backupLoading.value = true
  try {
    await apiReq('POST', '/api/admin/backups')
    await loadBackups()
    toast.success('数据库备份已创建')
  } catch (e) { toast.error('创建备份失败：' + e.message) }
  finally { backupLoading.value = false }
}

async function restoreBackup(backup) {
  const confirmed = await dialog.confirm(
    '确定恢复备份“' + backup.name + '”吗？\n当前数据库会先自动备份，恢复后所有用户需要重新登录。',
    { title: '恢复数据库', tone: 'warning', confirmText: '确认恢复' },
  )
  if (!confirmed) return
  backupLoading.value = true
  try {
    const data = await apiReq('POST', '/api/admin/backups/' + encodeURIComponent(backup.name) + '/restore')
    toast.success(data.message || '数据库已恢复')
    await loadBackups()
  } catch (e) { toast.error('恢复失败：' + e.message) }
  finally { backupLoading.value = false }
}

async function deleteBackup(backup) {
  const confirmed = await dialog.confirm(
    '确定删除备份“' + backup.name + '”吗？此操作不可撤销。',
    { title: '删除备份', tone: 'danger', confirmText: '永久删除' },
  )
  if (!confirmed) return
  try {
    await apiReq('DELETE', '/api/admin/backups/' + encodeURIComponent(backup.name))
    backups.value = backups.value.filter(item => item.name !== backup.name)
    toast.success('备份已删除')
  } catch (e) { toast.error('删除失败：' + e.message) }
}

async function loadSyncSchedule() {
  if (!(auth.user && (auth.user.is_admin || auth.user.is_root))) return
  try {
    const data = await apiReq('GET', '/api/dashboard/admin/sync-schedule')
    syncEnabled.value = data.enabled
    syncTime.value = data.time || '04:00'
    syncSources.value = {
      givemeoc: data.sources?.givemeoc ?? true,
      qiuzhifangzhou: data.sources?.qiuzhifangzhou ?? true,
    }
    aiDedupEnabled.value = data.ai_dedup_enabled ?? true
  } catch (e) {}
}

async function saveSyncSchedule() {
  try {
    const data = await apiReq('POST', '/api/dashboard/admin/sync-schedule', {
      enabled: syncEnabled.value,
      time: syncTime.value || '04:00',
      givemeoc: syncSources.value.givemeoc,
      qiuzhifangzhou: syncSources.value.qiuzhifangzhou,
      ai_dedup_enabled: aiDedupEnabled.value,
    })
    toast.success(data.message || '已保存')
  } catch (e) {
    await loadSyncSchedule()
    toast.error('保存失败：' + e.message)
  }
}

const sourceProgressPercent = computed(() => {
  const p = sourceProgress.value
  if (!p) return 0
  if (p.finished && !p.failed) return 100
  if (p.phase === 'deduplicating') return 94
  if (p.phase === 'cleaning' || p.phase === 'preparing') return 4
  const sourcePart = p.source_total ? ((Number(p.source_index || 1) - 1) / p.source_total) * 80 : 0
  const itemPart = p.total ? (Number(p.done || 0) / p.total) * (80 / Math.max(1, p.source_total || 1)) : 4
  return Math.min(92, Math.max(6, Math.round(sourcePart + itemPart + 8)))
})

function stopSourcePolling() {
  if (sourcePollTimer) clearInterval(sourcePollTimer)
  sourcePollTimer = null
}

async function runSourceSync() {
  if (!syncSources.value.givemeoc && !syncSources.value.qiuzhifangzhou) {
    toast.error('请至少开启一个同步来源')
    return
  }
  await saveSyncSchedule()
  sourceSyncing.value = true
  sourceProgress.value = { phase: 'preparing', message: '正在创建同步任务…' }
  try {
    const started = await apiReq('POST', '/api/dashboard/sync-sources')
    stopSourcePolling()
    const poll = async () => {
      try {
        const data = await apiReq('GET', '/api/dashboard/sync-from-givemeoc/progress?sync_id=' + encodeURIComponent(started.sync_id))
        sourceProgress.value = data
        if (data.finished) {
          stopSourcePolling()
          sourceSyncing.value = false
          data.failed ? toast.error(data.message) : toast.success(data.message)
        }
      } catch (e) {
        stopSourcePolling()
        sourceSyncing.value = false
        toast.error('同步进度读取失败：' + e.message)
      }
    }
    await poll()
    if (sourceSyncing.value) sourcePollTimer = setInterval(poll, 800)
  } catch (e) {
    sourceSyncing.value = false
    sourceProgress.value = { failed: true, finished: true, message: e.message }
    toast.error('同步启动失败：' + e.message)
  }
}

function startLogStream() {
  if (logStream) { logStream.close(); logStream = null }
  logLines.value = []
  apiReq('GET', '/api/logs/history').then(data => { logLines.value = data.logs || [] }).catch(() => {})
  logStream = new EventSource('/api/stream?token=' + encodeURIComponent(auth.token))
  logStream.onmessage = function(e) {
    try { const evt = JSON.parse(e.data); logLines.value.push(evt); if (logLines.value.length > 300) logLines.value.shift() } catch (ex) {}
  }
  logStream.onerror = function() { if (logStream) { logStream.close(); logStream = null } }
}

onMounted(() => {
  if (auth.isAdmin) {
    if (isRoot.value) { activePanel.value = 'users' }
    else { activePanel.value = 'invite' }
    loadAdminUsers()
    loadSyncSchedule()
    loadNotifications()
    startLogStream()
  }
})

onUnmounted(() => {
  if (logStream) { logStream.close(); logStream = null }
  stopSourcePolling()
})
</script>

<template>
  <section class="page active" id="page-admin" v-if="auth.isAdmin">
    <div class="admin-layout">
      <nav class="admin-nav-pane">
        <button class="admin-nav-item" :class="{ active: activePanel === 'users' }" data-panel="users" id="admin-nav-users" @click="switchPanel('users')">用户账号</button>
        <button class="admin-nav-item" :class="{ active: activePanel === 'invite' }" data-panel="invite" @click="switchPanel('invite')">邀请码</button>
        <button class="admin-nav-item" :class="{ active: activePanel === 'sync' }" data-panel="sync" @click="switchPanel('sync')">自动同步</button>
        <button class="admin-nav-item" :class="{ active: activePanel === 'notice' }" data-panel="notice" @click="switchPanel('notice')">发布通知</button>
        <button class="admin-nav-item" :class="{ active: activePanel === 'logs' }" data-panel="logs" @click="switchPanel('logs')">系统日志</button>
        <button v-if="isRoot" class="admin-nav-item" :class="{ active: activePanel === 'backups' }" data-panel="backups" @click="switchPanel('backups')">备份信息</button>
      </nav>
      <div class="admin-content-pane">
        <!-- users -->
        <div class="admin-panel" :class="{ active: activePanel === 'users' }" id="admin-panel-users">
          <div class="card"><div class="card-hd"><span class="dot"></span><div class="card-title">用户账号</div><div class="card-sub" id="admin-user-count">{{ userCountStr }}</div></div>
            <div id="admin-user-list">
              <div v-if="!users.length" class="center">暂无用户</div>
              <div v-for="user in users" :key="user.id" class="admin-user-card">
                <span class="uname"><b>{{ user.username }} <i>#{{ user.id }}</i></b><small>最近在线 · {{ user.last_seen_at ? formatSystemTime(user.last_seen_at) : '尚未上线' }}</small></span>
                <span class="umeta" :style="{ color: user.is_online ? 'var(--green)' : 'var(--muted)' }">{{ user.is_online ? '● 在线' : '○ 离线' }}</span>
                <label class="urole"><input type="checkbox" v-model="user.is_admin" :disabled="!isRoot || user.is_root || user.username === 'root'" @change="toggleAdmin(user)">{{ user.is_root ? 'Root Admin' : (user.is_admin ? '管理员' : '普通') }}</label>
                <span class="udate">{{ formatSystemTime(user.created_at) }}</span>
                <span class="ubtns" v-if="isRoot"><input type="password" :id="'admin-password-' + user.id" minlength="4" maxlength="100" autocomplete="new-password" placeholder="新密码" :value="pwMap[user.id] || ''" @input="e => pwMap[user.id] = e.target.value"><button class="btn" @click="changePassword(user)">改密</button><button v-if="!user.is_root && user.username !== 'root'" class="btn btn-danger" @click="deleteUser(user)">删除</button></span>
              </div>
            </div>
          </div>
        </div>
        <!-- invite -->
        <div class="admin-panel" :class="{ active: activePanel === 'invite' }" id="admin-panel-invite">
          <div class="card"><div class="card-hd"><span class="dot g"></span><div class="card-title">注册邀请码</div><div class="card-sub">一次性使用</div></div><div class="card-body">
            <div class="invite-generator">
              <div><b>创建临时注册凭证</b><p>邀请码注册成功后自动失效。页面不会展示历史生成记录。</p></div>
              <button class="btn btn-primary" id="invite-generate-btn" :disabled="genLoading" @click="genInvite">{{ genLoading ? '生成中…' : '生成邀请码' }}</button>
            </div>
            <div class="invite-current" id="invite-current" :style="{ display: inviteCode ? 'grid' : 'none' }">
              <span>本次生成</span>
              <code id="invite-current-code">{{ inviteCode }}</code>
              <button class="btn" type="button" @click="copyCode">复制</button>
            </div>
          </div></div>
        </div>
        <!-- sync -->
        <div class="admin-panel" :class="{ active: activePanel === 'sync' }" id="admin-panel-sync">
          <div class="card" id="sync-schedule-card"><div class="card-hd"><span class="dot a"></span><div class="card-title">岗位来源同步</div><div class="card-sub"><span id="sync-schedule-status">{{ syncEnabled ? '自动同步已启用 · 每日 ' + syncTime : '自动同步已关闭' }}</span></div></div><div class="card-body" style="display:grid;gap:16px">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
              <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font:13px var(--font);color:var(--ink)">
                <input type="checkbox" id="sync-schedule-enabled" v-model="syncEnabled" @change="saveSyncSchedule" style="display:none">
                <span class="toggle-track" :style="{ background: syncEnabled ? 'var(--blue)' : 'var(--line)', width: '36px', height: '20px', borderRadius: '10px', position: 'relative', transition: 'background .2s', flexShrink: 0 }"><span class="toggle-thumb" :style="{ position: 'absolute', top: '2px', left: syncEnabled ? '18px' : '2px', width: '16px', height: '16px', borderRadius: '50%', background: '#fff', transition: 'left .2s', boxShadow: '0 1px 3px rgba(0,0,0,.2)' }"></span></span>启用自动同步
              </label>
              <span style="font:12px var(--font);color:var(--sub)">每天</span>
              <input id="sync-schedule-time" type="time" v-model="syncTime" @change="saveSyncSchedule" style="width:80px;height:30px;padding:0 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);font:12px var(--font);outline:none">
            </div>
            <div>
              <b style="display:block;margin-bottom:8px;font-size:13px">同步来源</b>
              <div style="display:flex;gap:10px;flex-wrap:wrap">
                <label class="sync-source-option">
                  <input type="checkbox" v-model="syncSources.givemeoc" @change="saveSyncSchedule">
                  <span><b>GiveMeOC</b><small>2027 届秋招岗位</small></span>
                </label>
                <label class="sync-source-option">
                  <input type="checkbox" v-model="syncSources.qiuzhifangzhou" @change="saveSyncSchedule">
                  <span><b>求职方舟</b><small>近 90 天秋招及提前批</small></span>
                </label>
              </div>
            </div>
            <div style="margin-top:4px">
              <b style="display:block;margin-bottom:8px;font-size:13px">AI 功能</b>
              <label class="sync-source-option">
                <input type="checkbox" v-model="aiDedupEnabled" @change="saveSyncSchedule">
                <span><b>AI 去重</b><small>同步写入前自动复核可能重复的岗位</small></span>
              </label>
            </div>
            <div style="display:flex;align-items:center;gap:10px">
              <button class="btn btn-primary" :disabled="sourceSyncing || (!syncSources.givemeoc && !syncSources.qiuzhifangzhou)" @click="runSourceSync">
                {{ sourceSyncing ? '同步中…' : '立即同步已开启来源' }}
              </button>
              <button class="btn" :disabled="aiDedupRunning" @click="runAiDedup">
                {{ aiDedupRunning ? '智能去重中…' : '对已有数据智能去重' }}
              </button>
              <span style="font-size:11px;color:var(--muted)">所有来源获取完成后统一去重并写入共享总表</span>
            </div>
            <div v-if="sourceProgress" class="source-sync-progress" :class="{ error: sourceProgress.failed }">
              <div class="source-sync-progress-head"><b>{{ sourceProgress.finished ? (sourceProgress.failed ? '同步失败' : '同步完成') : '正在同步' }}</b><span>{{ sourceProgressPercent }}%</span></div>
              <div class="source-sync-progress-track"><i :style="{ width: sourceProgressPercent + '%' }"></i></div>
              <span>{{ sourceProgress.message }}</span>
            </div>
          </div></div>
        </div>
        <!-- notice -->
        <div class="admin-panel" :class="{ active: activePanel === 'notice' }" id="admin-panel-notice">
          <div class="card"><div class="card-hd"><span class="dot a"></span><div class="card-title">发布通知</div></div><div class="card-body">
            <div class="form-group"><input id="notice-title" v-model="noticeTitle" maxlength="100" placeholder="通知标题"></div>
            <div class="form-group"><textarea id="notice-content" v-model="noticeContent" maxlength="5000" rows="4" placeholder="通知内容"></textarea></div>
            <button class="btn btn-primary" id="notice-submit" :disabled="notifLoading" @click="sendNotif">{{ notifLoading ? '发送中…' : '发布通知' }}</button>
          </div></div>
          <div class="card notice-history-card">
            <div class="card-hd"><span class="dot"></span><div class="card-title">已发布通知</div><div class="card-sub">{{ notifications.length }} 条</div></div>
            <div class="notice-history-list">
              <div v-if="notificationsLoading" class="center muted notice-history-state">正在加载通知</div>
              <div v-else-if="!notifications.length" class="center muted notice-history-state">暂无已发布通知</div>
              <article v-for="item in notifications" v-else :key="item.id" class="notice-history-item">
                <div class="notice-history-copy"><div><b>{{ item.title }}</b><time>{{ formatSystemTime(item.created_at) }}</time></div><p>{{ item.content }}</p><small>发布人：{{ item.created_by_name }}</small></div>
                <button class="btn btn-danger" type="button" @click="deleteNotification(item)">删除</button>
              </article>
            </div>
          </div>
        </div>
        <!-- logs -->
        <div class="admin-panel" :class="{ active: activePanel === 'logs' }" id="admin-panel-logs">
          <div class="card" id="log-viewer-card"><div class="card-hd"><span class="dot"></span><div class="card-title">系统日志</div><div class="card-sub" id="log-count">{{ logLines.length ? logLines.length + ' 条' : '—' }}</div></div>
            <div id="log-list" style="max-height:calc(100vh - 280px);overflow-y:auto;font:11px/1.6 var(--font-mono,monospace);background:var(--bg);border-radius:0 0 18px 18px;padding:6px 12px">
              <div v-if="!logLines.length" class="center muted">暂无日志</div>
              <div v-for="(l, i) in logLines.slice().reverse()" :key="i" style="display:flex;gap:8px;white-space:nowrap">
                <span style="color:var(--muted);flex-shrink:0">{{ l.time }}</span>
                <span style="color:var(--blue);flex-shrink:0">[{{ l.channel }}]</span>
                <span :style="{ color: { error: '#dc2626', warn: '#d97706', info: 'var(--ink)', success: '#16a34a', system: 'var(--sub)' }[l.level] || 'var(--sub)' }">{{ l.message }}</span>
              </div>
            </div>
          </div>
        </div>
        <!-- backups -->
        <div v-if="isRoot" class="admin-panel" :class="{ active: activePanel === 'backups' }" id="admin-panel-backups">
          <div class="card">
            <div class="card-hd">
              <span class="dot g"></span>
              <div class="card-title">数据库备份</div>
              <div class="card-sub">每 12 小时自动备份 · 仅保留最近 3 天</div>
            </div>
            <div class="card-body backup-panel">
              <div class="backup-toolbar">
                <div><b>整库快照</b><p>恢复前会自动创建一份当前数据库快照。</p></div>
                <button class="btn btn-primary" :disabled="backupLoading" @click="createBackup">{{ backupLoading ? '处理中…' : '立即备份' }}</button>
              </div>
              <div v-if="!backups.length" class="center muted">暂无备份</div>
              <div v-for="backup in backups" :key="backup.name" class="backup-row">
                <div><b>{{ backup.name }}</b><span>{{ formatSystemTime(backup.created_at) }} · {{ formatBytes(backup.size) }}</span></div>
                <div>
                  <button class="btn" :disabled="backupLoading" @click="restoreBackup(backup)">恢复</button>
                  <button class="btn btn-danger" :disabled="backupLoading" @click="deleteBackup(backup)">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
  <section v-else class="page" id="page-admin">
    <div class="center muted" style="padding:60px">无权限访问</div>
  </section>
</template>

<style scoped>
/* User management is structural UI, not a Pixelium skin feature. Keep the
   same grid and native-size controls in every theme. */
.admin-layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:16px;align-items:start;max-height:calc(100vh - 140px)}
.admin-nav-pane{display:flex;flex-direction:column;gap:4px}
.admin-nav-item{display:block;width:100%;padding:11px 16px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--ink);font:13px var(--font);text-align:left;cursor:pointer}
.admin-nav-item.active{border-color:var(--blue);background:var(--blue);color:#fff;font-weight:800}
.admin-content-pane{min-width:0;max-height:calc(100vh - 140px);overflow-y:auto;padding-right:4px}
.admin-panel{display:none}.admin-panel.active{display:block}.admin-panel .card{margin-bottom:0}
#admin-panel-users .card{overflow:hidden}
#admin-user-list{display:grid;gap:0;padding:0}
.admin-user-card{display:grid;grid-template-columns:minmax(150px,1fr) 92px 128px minmax(280px,1.35fr);align-items:center;gap:12px;min-width:0;margin:0;padding:13px 16px;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent}
.admin-user-card:last-child{border-bottom:0}
.admin-user-card:hover{background:var(--blueS)}
.admin-user-card .uname{display:grid;gap:4px;min-width:0;font-size:14px;font-style:normal;letter-spacing:.01em}
.admin-user-card .uname b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.admin-user-card .uname i{color:var(--muted);font:400 10px var(--mono,monospace)}
.admin-user-card .uname small{overflow:hidden;color:var(--sub);font:600 10px/1.25 var(--font);text-overflow:ellipsis;white-space:nowrap}
.admin-user-card .umeta{justify-self:start;padding:3px 7px;border:1px solid var(--line);border-radius:999px;background:var(--bg);font-size:10px}
.admin-user-card .urole{display:inline-flex;align-items:center;gap:7px;min-width:0;margin:0;cursor:pointer;font-size:11px;white-space:nowrap}
.admin-user-card .urole input{display:inline-block;flex:0 0 16px;width:16px;height:16px;margin:0;padding:0;accent-color:var(--blue);border-radius:3px;box-shadow:none}
.admin-user-card .urole:has(input:disabled){cursor:default}
.admin-user-card .udate{display:none}
.admin-user-card .ubtns{grid-column:auto;display:grid;grid-template-columns:minmax(120px,1fr) auto auto;align-items:center;gap:7px;min-width:0}
.admin-user-card .ubtns input{width:100%;min-width:0;height:34px;margin:0;padding:0 9px;border:1px solid var(--line2);border-radius:8px;background:var(--bg);color:var(--ink);font:12px var(--font);box-shadow:none}
.admin-user-card .ubtns .btn{min-width:54px;min-height:34px;height:34px;padding:4px 9px;font-size:10px;white-space:nowrap}
.sync-source-option{display:flex;align-items:center;gap:9px;min-width:210px;padding:11px 13px;border:1px solid var(--line);background:var(--panel);cursor:pointer}
.sync-source-option input{width:17px;height:17px;accent-color:var(--blue)}
.sync-source-option span{display:grid;gap:2px}.sync-source-option b{font-size:12px}.sync-source-option small{color:var(--muted);font-size:10px}
.source-sync-progress{display:grid;gap:7px;padding:12px;border:1px solid var(--line);background:var(--bg)}
.source-sync-progress-head{display:flex;justify-content:space-between;gap:12px;font-size:12px}.source-sync-progress-head span{font-family:var(--mono)}
.source-sync-progress-track{height:9px;overflow:hidden;background:var(--line)}.source-sync-progress-track i{display:block;height:100%;background:var(--blue);transition:width .25s ease}
.source-sync-progress>span{color:var(--muted);font-size:10px}.source-sync-progress.error{border-color:var(--red)}.source-sync-progress.error i{background:var(--red)}
.backup-panel{display:grid;gap:12px}.backup-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.backup-toolbar p{margin-top:3px;color:var(--muted);font-size:11px}.backup-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid var(--line);background:var(--bg)}
.backup-row>div:first-child{display:grid;gap:3px;min-width:0}.backup-row b{overflow:hidden;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.backup-row span{color:var(--muted);font-size:10px}.backup-row>div:last-child{display:flex;gap:7px}
.notice-history-card{margin-top:14px!important;overflow:hidden}.notice-history-list{display:grid;max-height:420px;overflow:auto}.notice-history-state{padding:34px 16px}.notice-history-item{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:18px;padding:14px 16px;border-bottom:1px solid var(--line)}.notice-history-item:last-child{border-bottom:0}.notice-history-copy{min-width:0}.notice-history-copy>div{display:flex;align-items:baseline;justify-content:space-between;gap:12px}.notice-history-copy b{font-size:13px}.notice-history-copy time,.notice-history-copy small{color:var(--sub);font-size:10px}.notice-history-copy p{margin:5px 0;color:var(--muted);font-size:11px;line-height:1.55;white-space:pre-wrap;word-break:break-word}.notice-history-item>.btn{min-width:58px}
@media(max-width:1120px){.admin-user-card{grid-template-columns:minmax(130px,1fr) 84px 112px}.admin-user-card .ubtns{grid-column:1/-1;grid-template-columns:minmax(160px,1fr) auto auto}}
@media(max-width:760px){.admin-layout{grid-template-columns:1fr;max-height:none}.admin-nav-pane{flex-direction:row;flex-wrap:wrap}.admin-nav-item{width:auto;padding:8px 14px;font-size:12px}.admin-content-pane{max-height:none;overflow:visible}}
@media(max-width:700px){#admin-user-list{gap:10px;padding:10px}.admin-user-card{grid-template-columns:minmax(0,1fr) auto;gap:9px 10px;padding:13px;border:1px solid var(--line);border-radius:12px}.admin-user-card:last-child{border-bottom:1px solid var(--line)}.admin-user-card .umeta{justify-self:end}.admin-user-card .urole,.admin-user-card .ubtns{grid-column:1/-1}.admin-user-card .ubtns{grid-template-columns:minmax(0,1fr) auto auto}}
@media(max-width:620px){.backup-toolbar,.backup-row{align-items:stretch;flex-direction:column}.backup-row>div:last-child{display:grid;grid-template-columns:1fr 1fr}.admin-user-card .ubtns{grid-template-columns:1fr 1fr}.admin-user-card .ubtns input{grid-column:1/-1}.admin-user-card .ubtns .btn{width:100%}.notice-history-item{grid-template-columns:1fr}.notice-history-copy>div{align-items:flex-start;flex-direction:column;gap:3px}.notice-history-item>.btn{width:100%}}
</style>
