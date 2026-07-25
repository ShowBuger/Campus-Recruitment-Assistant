<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toast = useToastStore()

const activePanel = ref('users')
const users = ref([])
const inviteCode = ref('')
const genLoading = ref(false)
const noticeTitle = ref('')
const noticeContent = ref('')
const notifLoading = ref(false)
const pwMap = ref({})
const syncEnabled = ref(false)
const syncTime = ref('04:00')
const logLines = ref([])
let logStream = null

const isRoot = computed(() => auth.user && (auth.user.is_root || auth.user.username === 'root'))

const userCountStr = computed(() => {
  const total = users.value.length
  const online = users.value.filter(u => u.is_online).length
  return total + ' 个用户 · ' + online + ' 在线'
})

function formatSystemTime(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T') + 'Z')
  return isNaN(date) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

async function apiReq(method, url, body) {
  const headers = { Authorization: 'Bearer ' + auth.token }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(url, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  if (res.status === 401) { auth.clear(); throw new Error('登录已过期') }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || data.error || '请求失败')
  return data
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
  if (!confirm('确定删除用户"' + user.username + '"？该用户的配置、日程、简历和分析历史也会删除。')) return
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
    toast.success('通知已发布')
  } catch (e) { toast.error('发布失败：' + e.message) }
  finally { notifLoading.value = false }
}

function switchPanel(panel) {
  activePanel.value = panel
  if (panel === 'logs') startLogStream()
}

async function loadSyncSchedule() {
  if (!(auth.user && (auth.user.is_admin || auth.user.is_root))) return
  try {
    const data = await apiReq('GET', '/api/dashboard/admin/sync-schedule')
    syncEnabled.value = data.enabled
    syncTime.value = data.time || '04:00'
  } catch (e) {}
}

async function saveSyncSchedule() {
  const prevEnabled = syncEnabled.value
  try {
    const data = await apiReq('POST', '/api/dashboard/admin/sync-schedule', { enabled: syncEnabled.value, time: syncTime.value || '04:00' })
    toast.success(data.message || '已保存')
  } catch (e) {
    syncEnabled.value = prevEnabled
    toast.error('保存失败：' + e.message)
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
    startLogStream()
  }
})

onUnmounted(() => { if (logStream) { logStream.close(); logStream = null } })
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
      </nav>
      <div class="admin-content-pane">
        <!-- users -->
        <div class="admin-panel" :class="{ active: activePanel === 'users' }" id="admin-panel-users">
          <div class="card"><div class="card-hd"><span class="dot"></span><div class="card-title">用户账号</div><div class="card-sub" id="admin-user-count">{{ userCountStr }}</div></div>
            <div id="admin-user-list">
              <div v-if="!users.length" class="center">暂无用户</div>
              <div v-for="user in users" :key="user.id" class="admin-user-card">
                <span class="uname"><b>{{ user.username }} <i>#{{ user.id }}</i></b><small>最近登录 · {{ user.last_login_at ? formatSystemTime(user.last_login_at) : '尚未登录' }}</small></span>
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
          <div class="card" id="sync-schedule-card"><div class="card-hd"><span class="dot a"></span><div class="card-title">自动同步</div><div class="card-sub"><span id="sync-schedule-status">{{ syncEnabled ? '已启用 · 每日 ' + syncTime : '已关闭' }}</span></div></div><div class="card-body">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
              <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font:13px var(--font);color:var(--ink)">
                <input type="checkbox" id="sync-schedule-enabled" v-model="syncEnabled" @change="saveSyncSchedule" style="display:none">
                <span class="toggle-track" :style="{ background: syncEnabled ? 'var(--blue)' : 'var(--line)', width: '36px', height: '20px', borderRadius: '10px', position: 'relative', transition: 'background .2s', flexShrink: 0 }"><span class="toggle-thumb" :style="{ position: 'absolute', top: '2px', left: syncEnabled ? '18px' : '2px', width: '16px', height: '16px', borderRadius: '50%', background: '#fff', transition: 'left .2s', boxShadow: '0 1px 3px rgba(0,0,0,.2)' }"></span></span>启用
              </label>
              <span style="font:12px var(--font);color:var(--sub)">每天</span>
              <input id="sync-schedule-time" type="time" v-model="syncTime" @change="saveSyncSchedule" style="width:80px;height:30px;padding:0 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);font:12px var(--font);outline:none">
              <span style="font:11px var(--font);color:var(--muted)">从 GiveMeOC 拉取 2027届 秋招岗位</span>
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
      </div>
    </div>
  </section>
  <section v-else class="page" id="page-admin">
    <div class="center muted" style="padding:60px">无权限访问</div>
  </section>
</template>
