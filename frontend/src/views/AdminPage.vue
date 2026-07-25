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
    await fetch(`/api/admin/users/${u.id}/admin`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ is_admin: !u.is_admin })
    })
    u.is_admin = !u.is_admin
    toast.success(u.is_admin ? '已设为管理员' : '已取消管理员')
  } catch (e) { toast.error('操作失败') }
}

async function changePw(u) {
  const pw = document.getElementById('pw-' + u.id)?.value
  if (!pw || pw.length < 4) { toast.error('密码至少4位'); return }
  try {
    await fetch(`/api/admin/users/${u.id}/password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ password: pw })
    })
    toast.success('密码已修改')
    document.getElementById('pw-' + u.id).value = ''
  } catch (e) { toast.error('修改失败') }
}

async function deleteUser(u) {
  if (!confirm(`确定删除用户 ${u.username} 吗？此操作不可撤销。`)) return
  try {
    await fetch(`/api/admin/users/${u.id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
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
    if (inviteCode.value) { navigator.clipboard?.writeText(inviteCode.value); toast.success('已生成并复制') }
  } catch (e) { toast.error('生成失败') }
  finally { genLoading.value = false }
}

function copyCode() {
  if (inviteCode.value) { navigator.clipboard?.writeText(inviteCode.value); toast.success('已复制') }
}

async function sendNotif() {
  notifSending.value = true
  try {
    await fetch('/api/admin/notifications', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ title: notifTitle.value, content: notifContent.value })
    })
    toast.success('通知已发布')
    notifTitle.value = ''; notifContent.value = ''
  } catch (e) { toast.error('发送失败') }
  finally { notifSending.value = false }
}

function fmtTime(v) { if (!v) return ''; return new Date(v).toLocaleString('zh-CN', { hour12: false }) }
</script>

<template>
  <div class="page active" v-if="auth.isAdmin">
    <div class="admin-layout" style="display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px">
      <!-- Main: Users -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">用户管理</div></div>
        <div style="max-height:60vh;overflow:auto">
          <div v-for="u in users" :key="u.id" style="display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap">
            <b>{{ u.username }} <i style="color:var(--sub);font-weight:400">#{{ u.id }}</i></b>
            <span :style="{color: u.is_online ? 'var(--green)' : 'var(--muted)'}">{{ u.is_online ? '● 在线' : '○ 离线' }}</span>
            <label style="font-size:12px">
              <input type="checkbox" :checked="u.is_admin" :disabled="u.is_root" @change="toggleAdmin(u)"> {{ u.is_root ? 'Root' : '管理员' }}
            </label>
            <span style="font-size:11px;color:var(--sub)">{{ u.last_login_at ? '最近登录 '+fmtTime(u.last_login_at) : '未登录' }}</span>
            <input v-if="!u.is_root" type="password" :id="'pw-'+u.id" placeholder="新密码" style="width:80px;height:28px;font-size:12px" minlength="4">
            <button v-if="!u.is_root" class="btn" style="font-size:11px;padding:2px 8px" @click="changePw(u)">改密</button>
            <button v-if="!u.is_root" class="btn btn-danger" style="font-size:11px;padding:2px 8px" @click="deleteUser(u)">删除</button>
          </div>
        </div>
      </div>

      <!-- Sidebar: Invite + Notifications -->
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <div class="card-hd"><span class="dot"></span><div class="card-title">邀请码</div></div>
          <div style="padding:12px">
            <button class="btn btn-primary" @click="genInvite" :disabled="genLoading" style="width:100%">
              {{ genLoading ? '生成中…' : '生成邀请码' }}
            </button>
            <div v-if="inviteCode" style="margin-top:10px;padding:8px;background:var(--bg);border-radius:8px;text-align:center;font:700 16px var(--mono)">
              {{ inviteCode }}
              <button class="btn" style="margin-left:8px;font-size:11px" @click="copyCode">复制</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-hd"><span class="dot"></span><div class="card-title">发布通知</div></div>
          <div style="padding:12px">
            <div class="form-group"><input v-model="notifTitle" placeholder="通知标题" maxlength="200"></div>
            <div class="form-group"><textarea v-model="notifContent" placeholder="通知内容" rows="4" maxlength="5000"></textarea></div>
            <button class="btn btn-primary" @click="sendNotif" :disabled="!notifTitle||notifSending" style="width:100%">
              {{ notifSending ? '发送中…' : '发布通知' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div v-else class="center muted" style="padding:60px">无权限访问</div>
</template>
