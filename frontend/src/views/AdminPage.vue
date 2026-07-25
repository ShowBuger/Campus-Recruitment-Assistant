<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toast = useToastStore()
const users = ref([])
const inviteCode = ref('')
const genLoading = ref(false)
const notifTitle = ref('')
const notifContent = ref('')
const notifSending = ref(false)

onMounted(() => { if (auth.isAdmin) loadUsers() })

async function loadUsers() {
  try {
    const r = await fetch('/api/admin/users', { headers: { Authorization: `Bearer ${auth.token}` } })
    users.value = (await r.json()).users || []
  } catch { users.value = [] }
}

async function toggleAdmin(u) {
  try {
    const r = await fetch(`/api/admin/users/${u.id}/admin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ is_admin: !u.is_admin })
    })
    if (!r.ok) throw new Error('操作失败')
    u.is_admin = !u.is_admin
    toast.success(u.is_admin ? '已设为管理员' : '已取消管理员')
  } catch (e) { toast.error('操作失败') }
}

const pwMap = ref({})
async function changePw(u) {
  const pw = pwMap.value[u.id] || ''
  if (!pw || pw.length < 4) { toast.error('密码至少 4 个字符'); return }
  try {
    const r = await fetch(`/api/admin/users/${u.id}/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ password: pw })
    })
    if (!r.ok) throw new Error('修改失败')
    toast.success('密码已修改')
    pwMap.value[u.id] = ''
  } catch (e) { toast.error('修改失败') }
}

async function deleteUser(u) {
  if (!confirm(`确定删除用户 ${u.username} 吗？该用户的配置、日程、简历和分析历史也会删除。`)) return
  try {
    const r = await fetch(`/api/admin/users/${u.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
    if (!r.ok) throw new Error('删除失败')
    toast.success('用户已删除')
    await loadUsers()
  } catch (e) { toast.error('删除失败') }
}

async function genInvite() {
  genLoading.value = true
  try {
    const r = await fetch('/api/admin/invite-codes', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` } })
    const data = await r.json()
    inviteCode.value = data.invite_code?.code || ''
    if (inviteCode.value) {
      navigator.clipboard?.writeText(inviteCode.value)
      toast.success('邀请码已生成并复制')
    } else {
      toast.success('邀请码已生成')
    }
  } catch (e) { toast.error('邀请码生成失败') }
  finally { genLoading.value = false }
}

function copyCode() {
  if (inviteCode.value) { navigator.clipboard?.writeText(inviteCode.value); toast.success('已复制') }
}

async function sendNotif() {
  notifSending.value = true
  try {
    const r = await fetch('/api/admin/notifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ title: notifTitle.value, content: notifContent.value })
    })
    if (!r.ok) throw new Error('发送失败')
    toast.success('通知已发布')
    notifTitle.value = ''; notifContent.value = ''
  } catch (e) { toast.error('发送失败') }
  finally { notifSending.value = false }
}

function fmtTime(v) {
  if (!v) return ''
  return new Date(v).toLocaleString('zh-CN', { hour12: false })
}
</script>

<template>
  <div class="page active" v-if="auth.isAdmin">
    <div class="grid-2" style="align-items:start">
      <!-- Left: Users -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">用户账号</div><div class="card-sub">{{ users.length }}</div></div>
        <div id="admin-user-list" style="max-height:60vh;overflow:auto">
          <div v-if="!users.length" class="center muted" style="padding:12px">暂无用户</div>
          <div v-for="u in users" :key="u.id" class="admin-user-card" style="display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap">
            <span class="uname" style="min-width:100px">
              <b style="font-size:13px">{{ u.username }} <i style="color:var(--sub);font-weight:400;font-size:11px">#{{ u.id }}</i></b>
              <small style="display:block;font-size:10px;color:var(--muted)">最近登录 · {{ u.last_login_at ? fmtTime(u.last_login_at) : '尚未登录' }}</small>
            </span>
            <span class="umeta" :style="{ color: u.is_online ? 'var(--green)' : 'var(--muted)', fontSize: '11px' }">{{ u.is_online ? '● 在线' : '○ 离线' }}</span>
            <label class="urole" style="font-size:12px;display:flex;align-items:center;gap:4px;cursor:pointer">
              <input type="checkbox" :checked="u.is_admin" :disabled="u.is_root" @change="toggleAdmin(u)">
              {{ u.is_root ? 'Root' : '管理员' }}
            </label>
            <span class="ubtns" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
              <template v-if="!u.is_root">
                <input type="password" :value="pwMap[u.id]||''" @input="e => pwMap[u.id] = e.target.value" minlength="4" maxlength="100" autocomplete="new-password" placeholder="新密码" style="width:80px;height:28px;font-size:12px;padding:0 6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);outline:none">
                <button class="btn" style="font-size:11px;padding:2px 8px;height:28px" @click="changePw(u)">改密</button>
                <button class="btn btn-danger" style="font-size:11px;padding:2px 8px;height:28px" @click="deleteUser(u)">删除</button>
              </template>
            </span>
          </div>
        </div>
      </div>

      <!-- Right Sidebar -->
      <div style="display:flex;flex-direction:column;gap:16px">
        <!-- Invite Code -->
        <div class="card">
          <div class="card-hd"><span class="dot g"></span><div class="card-title">注册邀请码</div><div class="card-sub">一次性使用</div></div>
          <div class="card-body">
            <div class="invite-generator" style="margin-bottom:10px">
              <div>
                <b style="font-size:14px">创建临时注册凭证</b>
                <p style="margin-top:5px;color:var(--muted);font-size:11px">邀请码注册成功后自动失效。页面不会展示历史生成记录。</p>
              </div>
              <button class="btn btn-primary" @click="genInvite" :disabled="genLoading" style="width:100%">{{ genLoading ? '生成中…' : '生成邀请码' }}</button>
            </div>
            <div v-if="inviteCode" class="invite-current" style="display:grid;grid-template-columns:1fr auto;align-items:center;gap:10px;padding:12px;background:var(--bg);border-radius:8px">
              <span style="color:var(--muted);font-size:11px">本次生成</span>
              <code style="font:700 1em var(--mono,monospace);text-align:center">{{ inviteCode }}</code>
              <button class="btn" type="button" style="font-size:11px;padding:2px 8px" @click="copyCode">复制</button>
            </div>
          </div>
        </div>

        <!-- Notification Publisher -->
        <div class="card">
          <div class="card-hd"><span class="dot a"></span><div class="card-title">发布通知</div></div>
          <div class="card-body">
            <div class="form-group"><input v-model="notifTitle" class="input" maxlength="100" placeholder="通知标题"></div>
            <div class="form-group"><textarea v-model="notifContent" class="input" maxlength="5000" rows="4" placeholder="通知内容" style="resize:vertical;min-height:60px"></textarea></div>
            <button class="btn btn-primary" @click="sendNotif" :disabled="!notifTitle || notifSending" style="width:100%">{{ notifSending ? '发送中…' : '发布通知' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="center muted" style="padding:60px">无权限访问</div>
</template>
