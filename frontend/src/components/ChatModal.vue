<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">>
    <div class="chat-modal-window">
      <div class="chat-modal-bar">
        <div><b>站内聊天</b><span>{{ activePeer ? '消息、图片与岗位分享' : '与已注册用户即时沟通' }}</span></div>
        <button class="icon-btn" @click="$emit('close')" title="关闭聊天" aria-label="关闭聊天">&times;</button>
      </div>
      <div class="chat-shell">
        <!-- 联系人列表 -->
        <aside class="chat-contacts">
          <div class="chat-contacts-head">
            <div><b>消息</b><span>与已注册用户即时沟通</span></div>
            <label class="chat-search"><span>⌕</span><input v-model="searchQuery" type="search" placeholder="搜索联系人" autocomplete="off"></label>
          </div>
          <div class="chat-user-list">
            <div v-if="!filteredUsers.length" class="center" style="padding:20px;font-size:12px;color:var(--muted)">暂无用户</div>
            <button
              v-for="u in filteredUsers"
              :key="u.id"
              class="chat-user"
              :class="{ active: activePeer === u.id }"
              @click="selectPeer(u)"
            >
              <div class="chat-avatar">{{ u.username.charAt(0).toUpperCase() }}</div>
              <div class="chat-user-main">
                <div class="chat-user-name">
                  {{ u.username }}
                  <span v-if="u.unread_count" class="chat-count-inline">{{ u.unread_count }}</span>
                </div>
                <div class="chat-user-last" v-if="u.last_msg">{{ u.last_msg }}</div>
              </div>
            </button>
          </div>
        </aside>

        <!-- 聊天面板 -->
        <div class="chat-panel">
          <div class="chat-head" v-if="activePeer">
            <div class="chat-avatar" style="flex-shrink:0">{{ peerName.charAt(0).toUpperCase() }}</div>
            <div class="chat-head-info"><b>{{ peerName }}</b></div>
          </div>
          <div class="chat-head" v-else>
            <div class="chat-head-info"><b>选择联系人</b><span>发送消息、图片或岗位信息</span></div>
          </div>

          <div class="chat-messages" ref="msgList">
            <div v-if="!activePeer" class="chat-empty"><div><b>开始聊天</b><span>从左侧选择一位已注册用户</span></div></div>
            <div v-else-if="!messages.length" class="chat-empty"><div><b>还没有消息</b><span>发送第一条消息吧</span></div></div>
            <template v-else>
              <div v-for="m in messages" :key="m.id" class="chat-row" :class="{ mine: m.sender_id === auth.user?.id }">
                <!-- 文本消息 -->
                <div v-if="m.kind === 'text'" class="chat-bubble">
                  {{ m.content }}
                  <div class="chat-time">{{ fmtTime(m.created_at) }}</div>
                </div>

                <!-- 图片消息 -->
                <div v-else-if="m.kind === 'image'" class="chat-bubble" style="padding:4px;background:transparent;border:0;box-shadow:none">
                  <img
                    :src="`/api/chat/messages/${m.id}/image`"
                    class="chat-image"
                    :alt="m.content"
                    @click="previewImage(m)"
                  >
                  <div class="chat-time">{{ fmtTime(m.created_at) }}</div>
                </div>

                <!-- 岗位卡片 -->
                <div v-else-if="m.kind === 'job'" class="chat-job-card">
                  <div class="chat-job-title">{{ getJobPayload(m).company || '岗位信息' }}</div>
                  <div class="chat-job-name">{{ getJobPayload(m).job || '岗位未填写' }}</div>
                  <div class="chat-job-meta">
                    <span v-if="getJobPayload(m).city" class="tag">{{ getJobPayload(m).city }}</span>
                    <span v-if="getJobPayload(m).company_type" class="tag">{{ getJobPayload(m).company_type }}</span>
                    <span v-for="d in getJobDirections(m)" :key="d" class="tag">{{ d }}</span>
                  </div>
                  <div class="chat-job-foot">
                    <a v-if="getJobPayload(m).url" :href="getJobPayload(m).url" target="_blank" rel="noreferrer">查看入口</a>
                    <span v-else class="muted">暂无入口</span>
                    <button
                      v-if="m.sender_id !== auth.user?.id"
                      class="btn btn-primary"
                      :disabled="m.copied"
                      @click="copyJob(m)"
                    >{{ m.copied ? '已加入总表' : '加入我的总表' }}</button>
                    <span v-else class="muted" style="font-size:11px">已转发</span>
                  </div>
                  <div class="chat-time">{{ fmtTime(m.created_at) }}</div>
                </div>
              </div>
            </template>
          </div>

          <!-- 输入区 -->
          <div class="chat-compose" v-if="activePeer">
            <input
              ref="imgInput"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              hidden
              @change="sendImage"
            >
            <button
              class="icon-btn chat-tool-btn"
              @click="$refs.imgInput.click()"
              title="发送图片"
              aria-label="发送图片"
            >
              <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 7h4l2-2h6l2 2h4v13H3V7Z"/><path d="M8 13a4 4 0 1 0 8 0 4 4 0 0 0-8 0Z"/><path d="M18 9h1"/>
              </svg>
            </button>
            <button
              class="icon-btn chat-tool-btn"
              @click="openJobPicker"
              title="转发岗位"
              aria-label="转发岗位"
            >
              <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 8h18v12H3V8Z"/><path d="M9 8V5h6v3M3 12h18M10 12v2h4v-2"/>
              </svg>
            </button>
            <!-- Emoji picker -->
            <div class="emoji-wrap">
              <button
                class="icon-btn chat-tool-btn"
                @click="showEmojiPicker = !showEmojiPicker"
                title="表情"
                aria-label="表情"
              ><span class="emoji-trigger-glyph" aria-hidden="true">☻</span></button>
              <div v-if="showEmojiPicker" class="emoji-picker" @click.stop>
                <div class="emoji-picker-hd">
                  <span>表情仓</span>
                  <b>{{ activeEmojiLabel }}</b>
                </div>
                <div class="emoji-cats">
                  <button v-for="cat in emojiCats" :key="cat.name"
                    :class="{ active: emojiCat === cat.name }"
                    @click="emojiCat = cat.name"
                    :title="cat.label"
                    :aria-label="cat.label"
                  >{{ cat.icon }}</button>
                </div>
                <div class="emoji-grid">
                  <button v-for="e in currentEmojis" :key="e"
                    @click="insertEmoji(e)"
                  >{{ e }}</button>
                </div>
              </div>
            </div>
            <textarea
              v-model="text"
              maxlength="3000"
              @keydown="onKeydown"
              placeholder="输入消息，Enter 发送，Shift + Enter 换行"
            ></textarea>
            <button class="btn btn-primary chat-send" @click="sendText" :disabled="!text.trim()">发送</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 岗位转发弹窗 -->
    <div v-if="showJobPicker" class="modal-mask show" @mousedown.self="showJobPicker = false">>
      <div class="modal chat-job-dialog">
        <div class="modal-hd">
          <div><h2>转发岗位信息</h2><p>从个人总表或共享总表选择岗位</p></div>
          <button class="icon-btn" @click="showJobPicker = false" title="关闭">&times;</button>
        </div>
        <div class="chat-job-search-wrap">
          <div class="total-view-switch chat-job-source-switch" role="tablist" aria-label="岗位来源">
            <button
              role="tab"
              :class="{ active: jobSource === 'personal' }"
              :aria-selected="jobSource === 'personal'"
              @click="switchJobSource('personal')"
            >个人总表</button>
            <button
              role="tab"
              :class="{ active: jobSource === 'shared' }"
              :aria-selected="jobSource === 'shared'"
              @click="switchJobSource('shared')"
            >共享总表</button>
          </div>
          <label class="chat-job-search"><span>⌕</span><input v-model="jobSearch" type="search" placeholder="搜索公司、岗位、城市或方向" autocomplete="off"></label>
        </div>
        <div class="modal-body">
          <div v-if="jobPickerLoading" class="center" style="padding:20px">正在加载岗位…</div>
          <div v-else-if="!filteredJobRecords.length" class="chat-job-search-empty">
            <b>{{ jobSearch ? '没有找到相关岗位' : '当前总表暂无岗位' }}</b>
            <span>{{ jobSearch ? '换一个公司、岗位、城市或方向关键词试试' : '切换到另一个总表查看可转发岗位' }}</span>
          </div>
          <div v-else>
            <div class="chat-job-picker-summary">{{ jobSource === 'shared' ? '共享总表' : '个人总表' }} · {{ filteredJobRecords.length }} 个岗位</div>
            <div class="chat-job-picker">
              <div
                v-for="r in filteredJobRecords"
                :key="r.record_id"
                class="chat-job-option"
              >
                <div class="chat-job-option-main">
                  <b>{{ r.company || '—' }}</b>
                  <strong style="display:block;margin-top:2px;font-size:13px">{{ r.job || '岗位未填写' }}</strong>
                  <span v-if="r.meta">{{ r.meta }}</span>
                </div>
                <button class="btn btn-primary" :disabled="r._sending" @click="sendJob(r)">
                  {{ r._sending ? '发送中…' : '转发' }}
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-ft"><button class="btn" @click="showJobPicker = false">取消</button></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useAppStore } from '@/stores/app'

defineEmits(['close'])
const auth = useAuthStore()
const toast = useToastStore()
const app = useAppStore()

const users = ref([])
const messages = ref([])
const activePeer = ref(null)
const text = ref('')
const msgList = ref(null)
const imgInput = ref(null)
const searchQuery = ref('')
let pollTimer = null

// ── 岗位转发弹窗 ──
const showJobPicker = ref(false)
const jobSource = ref('personal')
const jobSearch = ref('')
const personalRecords = ref([])
const sharedRecords = ref([])
const jobPickerLoading = ref(false)

const filteredUsers = computed(() => {
  const q = searchQuery.value.toLowerCase()
  return users.value.filter(u => !q || u.username.toLowerCase().includes(q))
})

const filteredJobRecords = computed(() => {
  const raw = jobSource.value === 'shared' ? sharedRecords.value : personalRecords.value
  const q = jobSearch.value.trim().toLocaleLowerCase()
  return raw
    .map(r => ({
      ...r,
      meta: [r.city, ...(Array.isArray(r.dir) ? r.dir : [])].filter(Boolean).join(' · ')
    }))
    .filter(r => {
      if (!q) return true
      return [r.company, r.job, r.city, (Array.isArray(r.dir) ? r.dir.join(' ') : '')].join(' ').toLocaleLowerCase().indexOf(q) >= 0
    })
})

onMounted(() => { loadUsers(); startPoll() })
onUnmounted(() => { stopPoll() })

async function loadUsers() {
  try {
    const r = await fetch('/api/chat/users', { headers: { Authorization: `Bearer ${auth.token}` } })
    const data = await r.json()
    users.value = (data.users || data || []).filter(u => u.id !== auth.user?.id)
    // Update unread badge
    const total = users.value.reduce((s, u) => s + (u.unread_count || 0), 0)
    app.setChatUnread(total)
  } catch { users.value = [] }
}

async function selectPeer(u) {
  activePeer.value = u.id; showJobPicker.value = false
  await loadMessages()
  await fetch('/api/chat/messages/read', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` }, body: JSON.stringify({ peer_id: u.id }) }).catch(() => {})
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

function onKeydown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText() } }

async function sendText() {
  if (!text.value.trim() || !activePeer.value) return
  try {
    await fetch('/api/chat/messages/text', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` }, body: JSON.stringify({ receiver_id: activePeer.value, text: text.value }) })
    text.value = ''
    await loadMessages()
  } catch { toast.error('发送失败') }
}

async function sendImage(e) {
  const file = e.target.files?.[0]; if (!file || !activePeer.value) return
  if (file.size > 5 * 1024 * 1024) { toast.error('图片不能超过 5MB'); return }
  try {
    const fd = new FormData(); fd.append('file', file); fd.append('receiver_id', String(activePeer.value))
    await fetch('/api/chat/messages/image', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: fd })
    await loadMessages()
  } catch { toast.error('图片发送失败') }
  finally { if (imgInput.value) imgInput.value.value = '' }
}

// ── 岗位转发 ──
async function openJobPicker() {
  if (!activePeer.value) return
  jobSource.value = 'personal'; jobSearch.value = ''; showJobPicker.value = true
  jobPickerLoading.value = true
  try {
    // 加载个人总表
    if (!personalRecords.value.length) {
      const r = await fetch('/api/dashboard', { headers: { Authorization: `Bearer ${auth.token}` } })
      const data = await r.json()
      personalRecords.value = (data?.main?.records || []).map(r => ({
        record_id: r.record_id,
        company: r.company || r.fields?.['公司名称'] || '',
        job: r.job || r.fields?.['秋招岗位'] || '',
        city: r.city || r.fields?.['城市'] || '',
        dir: Array.isArray(r.directions) ? r.directions : (r.fields?.['方向'] || []),
        url: r.url || r.fields?.['入口'] || ''
      }))
    }
    // 加载共享总表
    if (!sharedRecords.value.length) {
      const sr = await fetch('/api/dashboard/shared/records', { headers: { Authorization: `Bearer ${auth.token}` } })
      const sdata = await sr.json()
      sharedRecords.value = (sdata.records || []).map(r => ({
        record_id: r.record_id,
        company: r.company || '',
        job: r.job || '',
        city: r.city || '',
        dir: Array.isArray(r.dir) ? r.dir : [],
        url: r.url || ''
      }))
    }
  } catch { /* silent */ }
  finally { jobPickerLoading.value = false }
}

function switchJobSource(source) { jobSource.value = source }

async function sendJob(record) {
  if (!activePeer.value) return
  record._sending = true
  try {
    await fetch('/api/chat/messages/job', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({ receiver_id: activePeer.value, source: jobSource.value, record_id: record.record_id })
    })
    showJobPicker.value = false
    await loadMessages()
    toast.success('岗位已转发')
  } catch { toast.error('岗位转发失败') }
  finally { record._sending = false }
}

async function copyJob(m) {
  try {
    await fetch(`/api/chat/messages/${m.id}/copy-job`, { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` } })
    m.copied = true
    toast.success('已加入我的总表')
  } catch { toast.error('添加失败') }
}

function getJobPayload(m) {
  const p = m.payload
  if (!p) return {}
  if (typeof p === 'object') return p
  try { return JSON.parse(p) } catch { return {} }
}
function getJobDirections(m) { const p = getJobPayload(m); const d = p.directions || p.dir; return Array.isArray(d) ? d : [] }
function previewImage(m) { window.open(`/api/chat/messages/${m.id}/image`, '_blank') }

function startPoll() { pollTimer = setInterval(() => { loadUsers(); if (activePeer.value) loadMessages() }, 5000) }
function stopPoll() { clearInterval(pollTimer) }

const peerName = computed(() => users.value.find(u => u.id === activePeer.value)?.username || '')
const peerOnline = computed(() => users.value.find(u => u.id === activePeer.value)?.is_online || false)
function fmtTime(v) { if (!v) return ''; const d = new Date(String(v).replace(' ', 'T') + (String(v).includes('Z') ? '' : 'Z')); return isNaN(d) ? '' : d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }

// Emoji picker
const showEmojiPicker = ref(false)
const emojiCat = ref('face')
const emojiCats = [
  { name: 'face', label: '表情', icon: '脸', emojis: '😀😃😄😁😅😂🤣😊😇🙂🙃😉😌😍🥰😘😗😙😚😋😛😝😜🤪🤨🧐🤓😎🥸🤩🥳😏😒😞😔😟😕🙁☹️😣😖😫😩🥺😢😭😤😠😡🤬🤯😳🥵🥶😱😨😰😥😓🤗🤔🤭🤫🤥😶😐😑😬🙄😯😦😧😮😲🥱😴🤤😪😵🤐🥴🤢🤮🤧😷🤒🤕🤑🤠' },
  { name: 'hand', label: '手势', icon: '手', emojis: '👍👎👌✌🤞🤟🤘🤙👈👉👆👇☝️✋🤚🖐🖖👋🤏✍️🙌👏🙏🤝💪🦾🦿🦶🦵🤳👀🫀🫁🧠👅👄👂🦻👃🤲🤜🤛✊👊🤚🖐✋' },
  { name: 'heart', label: '符号', icon: '心', emojis: '❤️🧡💛💚💙💜🖤🤍🤎💔❣️💕💞💓💗💖💘💝💟☮️✝️☪️🕉☸️✡️🔯🕎☯️☦️🛐⛎♈️♉️♊️♋️♌️♍️♎️♏️♐️♑️♒️♓️🆔' },
  { name: 'item', label: '物品', icon: '物', emojis: '🎁🎂🎈🎉🎊🎀🏆🥇🥈🥉🏅🎖️🏵️🎗️🎫🎟️🎪🤹🪄🎭🩰🎨🎬🎤🎧🎼🎹🥁🎷🎺🎸🪕🎻🎲♟️🎯🎳🎮🕹️🎰📱💻⌨️🖥🖨🖱🖲🕹️🗜️💽💾💿📀📼📷📸📹🎥📽🎞📞☎️📟📠📺📻🎙🎚🎛🧭⏰⌚️📡🔋🪫🔌💡🔦🕯️🪔🧯🗑️🛢️💸💵💴💶💷🪙💰💳💎⚖️🪜🔧🔨⚒️🛠️⛏️🔩⚙️🪛🔗⛓️🪝🧰🧲🧪🧫🧬🔬🔭📡💉💊🩹🩺🚪🛏️🪑🚿🛁🧴🧹🧺🧻🧼🧽' },
  { name: 'nature', label: '自然', icon: '然', emojis: '🐶🐱🐭🐹🐰🦊🐻🐼🐻‍❄️🐨🐯🦁🐮🐷🐽🐸🐵🙈🙉🙊🐒🐔🐧🐦🐤🐣🐥🦆🦅🦉🦇🐺🐗🐴🦄🐝🪱🐛🦋🐌🐞🐜🪰🪲🪳🦟🦗🕷🕸🦂🐢🐍🦎🦖🦕🐙🦑🦐🦞🦀🐡🐠🐟🐬🐳🐋🦈🦭🐊🐅🐆🦓🦍🦧🦣🐘🦛🦏🐪🐫🦒🦘🦬🐃🐂🐄🐎🐖🐏🐑🦙🐐🦌🐕🐩🦮🐕‍🦺🐈🐈‍⬛🪶🐓🦃🦤🦚🦜🦢🦩🕊️🐇🦝🦨🦡🦫🦦🦥🐁🐀🐿️🦔🐾🐉🐲🌵🎄🌲🌳🌴🪵🌱🌿☘️🍀🎍🪴🎋🍃🍂🍁🍄🐚🪨🌾💐🌷🌹🥀🌺🌸🌼🌻🌞🌝🌛🌜🌚🌕🌖🌗🌘🌑🌒🌓🌔🌙🌎🌍🌏🪐💫⭐️🌟✨⚡️☄️💥🔥🌪️🌈☀️🌤⛅️🌥☁️🌦🌧⛈🌩🌨❄️☃️⛄️🌬💨💧💦☔️☂️🌊🌫' },
]
const activeEmojiLabel = computed(() =>
  (emojiCats.find(c => c.name === emojiCat.value) || emojiCats[0]).label
)
const currentEmojis = computed(() => {
  const raw = (emojiCats.find(c => c.name === emojiCat.value) || emojiCats[0]).emojis
  // Split by emoji boundaries: match emoji sequences (base + optional modifiers)
  return [...new Intl.Segmenter('en', { granularity: 'grapheme' }).segment(raw)].map(s => s.segment)
})
function insertEmoji(e) { text.value += e; showEmojiPicker.value = false; document.querySelector('.chat-compose textarea')?.focus() }
</script>

<style scoped>
/* 聊天弹窗外层容器 */
.chat-modal-window {
  display: flex;
  flex-direction: column;
  width: min(1180px, 96vw);
  height: min(780px, 94dvh);
  min-height: 520px;
  background: var(--bg);
  border-radius: 20px;
  box-shadow: 0 24px 80px rgba(16, 24, 40, .22);
  overflow: hidden;
}

.chat-modal-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
.chat-modal-bar b { display: block; font-size: 16px; }
.chat-modal-bar span { color: var(--muted); font-size: 11px; }

/* 覆盖 .chat-shell 的外层滚动，让它在弹窗内适配 */
:deep(.chat-shell) {
  flex: 1;
  min-height: 0;
  height: auto;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

/* 联系人搜索 */
.chat-search {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding: 5px 8px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--panel);
}
.chat-search span { color: var(--muted); font-size: 14px; flex-shrink: 0; }
.chat-search input {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--ink);
  font-size: 12px;
  outline: none;
}

/* 岗位搜索区 */
.chat-job-search-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}

.chat-job-search {
  display: flex;
  align-items: center;
  gap: 5px;
  flex: 1;
  min-width: 180px;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--panel);
}
.chat-job-search span { color: var(--muted); font-size: 14px; flex-shrink: 0; }
.chat-job-search input {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--ink);
  font-size: 12px;
  outline: none;
}

/* 岗位选择器汇总 */
.chat-job-picker-summary {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 800;
  color: var(--sub);
}

/* 空搜索结果 */
.chat-job-search-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--muted);
}
.chat-job-search-empty b { display: block; color: var(--ink); font-size: 15px; margin-bottom: 4px; }
.chat-job-search-empty span { font-size: 12px; }

/* Compose: 5 columns for emoji button */
:deep(.chat-compose) { grid-template-columns: auto auto auto minmax(0,1fr) auto; }
:deep(.chat-compose .icon-btn) { height: 36px; width: 36px; }
:deep(.chat-compose textarea) { height: 36px; min-height: 36px; }
:deep(.chat-compose .chat-send) { height: 36px; }

/* Emoji picker */
.emoji-wrap { position: relative; }
.emoji-trigger-glyph { font: 900 18px/1 var(--mono); }
.emoji-picker {
  position: absolute;
  bottom: 44px;
  left: 0;
  z-index: 200;
  width: 336px;
  background: var(--panel);
  border: 2px solid var(--ink);
  border-radius: 2px;
  box-shadow: 5px 5px 0 var(--ink);
  overflow: hidden;
}
.emoji-picker-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 33px;
  padding: 0 10px;
  border-bottom: 2px solid var(--ink);
  background: repeating-linear-gradient(90deg, var(--blue) 0 8px, color-mix(in srgb, var(--blue) 78%, #fff) 8px 16px);
  color: #fff;
  text-shadow: 1px 1px 0 var(--ink);
  font: 900 10px var(--mono);
  letter-spacing: .08em;
}
.emoji-picker-hd b { font: 900 10px var(--font); letter-spacing: 0; }
.emoji-cats {
  display: flex;
  gap: 4px;
  padding: 7px 8px;
  border-bottom: 2px solid var(--line2);
  background: var(--bg);
}
.emoji-cats button {
  width: 34px; height: 30px;
  border: 1px solid var(--line2); border-radius: 1px;
  background: var(--panel);
  color: var(--muted);
  font: 900 11px var(--font);
  cursor: pointer;
  transition: none;
}
.emoji-cats button.active { border-color: var(--ink); background: var(--blue); color: #fff; box-shadow: 2px 2px 0 var(--ink); }
.emoji-cats button:hover { border-color: var(--ink); color: var(--ink); }
.emoji-cats button.active:hover { color: #fff; }
.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  padding: 9px;
  max-height: 216px;
  overflow-y: auto;
  background-color: var(--panel);
  background-image: linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px);
  background-size: 10px 10px;
}
.emoji-grid button {
  width: 34px; height: 34px;
  border: 1px solid transparent; border-radius: 1px;
  background: var(--panel);
  font-size: 18px;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: none;
}
.emoji-grid button:hover { border-color: var(--ink); background: var(--amberS); box-shadow: 2px 2px 0 var(--ink); transform: translate(-1px, -1px); }
@media (max-width: 440px) {
  .emoji-picker { left: -78px; width: min(336px, calc(100vw - 28px)); }
  .emoji-grid { grid-template-columns: repeat(7, 1fr); }
}

/* 联系人列表可滚动 */
:deep(.chat-contacts) { min-height: 0; overflow: hidden; }
:deep(.chat-user-list) { flex: 1; min-height: 0; overflow-y: auto; }
/* 消息计数红点 */
.chat-count-inline { display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 5px; margin-left: 6px; border-radius: 999px; background: var(--red); color: #fff; font-size: 10px; font-weight: 700; vertical-align: middle; }
/* 移动端适配 */
@media (max-width: 760px) {
  .chat-modal-window { width: 96vw; height: 94vh; border-radius: 14px; }
  .chat-compose { grid-template-columns: auto auto auto minmax(0,1fr) !important; }
  .chat-compose .chat-send { grid-column: 1 / -1; width: 100%; }
}
</style>
