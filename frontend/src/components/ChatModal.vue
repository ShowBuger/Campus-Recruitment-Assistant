<template>
  <div class="modal-mask show" @click.self="$emit('close')">
    <div class="modal chat-modal" style="max-width:700px;height:70vh;display:flex;flex-direction:column">
      <div class="modal-hd">
        <div><h2>站内聊天</h2><p v-if="activePeer">{{ peerName }}</p></div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>

      <div class="modal-body" style="flex:1;display:flex;gap:0;padding:0;overflow:hidden">
        <!-- User List -->
        <div style="width:200px;border-right:1px solid var(--line);overflow:auto;flex-shrink:0">
          <div v-if="!users.length" class="center muted" style="padding:20px">暂无用户</div>
          <div v-for="u in users" :key="u.id"
               style="padding:10px 14px;cursor:pointer;border-bottom:1px solid var(--line)"
               :style="{ background: activePeer === u.id ? 'var(--blueS)' : '' }"
               @click="selectPeer(u)">
            <b style="font-size:13px">{{ u.username }}</b>
            <span style="font-size:10px;color:var(--sub);display:block">
              {{ u.is_online ? '● 在线' : '○ 离线' }}
              <span v-if="u.unread_count" style="color:var(--red)"> {{ u.unread_count }} 未读</span>
            </span>
          </div>
        </div>

        <!-- Chat Area -->
        <div style="flex:1;display:flex;flex-direction:column;min-width:0">
          <div v-if="!activePeer" class="center muted" style="flex:1;display:flex;align-items:center;justify-content:center">
            选择一位用户开始聊天
          </div>
          <template v-else>
            <!-- Messages -->
            <div ref="msgList" style="flex:1;overflow:auto;padding:12px">
              <div v-if="!messages.length" class="center muted">暂无消息</div>
              <div v-for="m in messages" :key="m.id"
                   :style="{ textAlign: m.sender_id === auth.user?.id ? 'right' : 'left', marginBottom: '8px' }">
                <div style="display:inline-block;max-width:70%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.5"
                     :style="{ background: m.sender_id === auth.user?.id ? 'var(--blue)' : 'var(--line)', color: m.sender_id === auth.user?.id ? '#fff' : 'var(--ink)' }">
                  <span v-if="m.kind === 'job'" style="color:var(--amber)">📋 分享了岗位</span>
                  <span v-else>{{ m.content }}</span>
                </div>
                <div style="font-size:10px;color:var(--sub);margin-top:2px">{{ fmtTime(m.created_at) }}</div>
              </div>
            </div>

            <!-- Input -->
            <div style="display:flex;gap:8px;padding:8px 12px;border-top:1px solid var(--line)">
              <input v-model="text" @keydown.enter="sendText" placeholder="输入消息..."
                     style="flex:1;height:36px;border:1px solid var(--line);border-radius:8px;padding:0 10px;font-size:13px">
              <button class="btn" @click="sendText" :disabled="!text.trim()">发送</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

defineEmits(['close'])

const auth = useAuthStore()
const toast = useToastStore()
const users = ref([])
const messages = ref([])
const activePeer = ref(null)
const text = ref('')
const msgList = ref(null)
let pollTimer = null

onMounted(() => { loadUsers(); startPoll() })
onUnmounted(() => { stopPoll() })

async function loadUsers() {
  try {
    const r = await fetch('/api/chat/users', { headers: { Authorization: `Bearer ${auth.token}` } })
    users.value = (await r.json()).users?.filter(u => u.id !== auth.user?.id) || []
  } catch { users.value = [] }
}

async function selectPeer(u) {
  activePeer.value = u.id
  await loadMessages()
  await fetch(`/api/chat/messages/read`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
    body: JSON.stringify({ peer_id: u.id })
  })
  u.unread_count = 0
  nextTick(() => { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight })
}

async function loadMessages() {
  if (!activePeer.value) return
  try {
    const r = await fetch(`/api/chat/messages/${activePeer.value}`, { headers: { Authorization: `Bearer ${auth.token}` } })
    messages.value = (await r.json()).messages || []
    nextTick(() => { if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight })
  } catch { messages.value = [] }
}

async function sendText() {
  if (!text.value.trim() || !activePeer.value) return
  try {
    await fetch('/api/chat/messages/text', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ receiver_id: activePeer.value, content: text.value })
    })
    text.value = ''
    await loadMessages()
  } catch { toast.error('发送失败') }
}

function startPoll() { pollTimer = setInterval(() => { loadUsers(); if (activePeer.value) loadMessages() }, 5000) }
function stopPoll() { clearInterval(pollTimer) }

const peerName = computed(() => users.value.find(u => u.id === activePeer.value)?.username || '')

function fmtTime(v) { if (!v) return ''; const d = new Date(v); return isNaN(d) ? '' : d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
</script>
