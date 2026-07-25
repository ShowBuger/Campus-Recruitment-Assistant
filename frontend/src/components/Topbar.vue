<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/utils/api'

const route = useRoute()
const titleMap = { dashboard: '投递信息', board: '投递看板', records: '总表信息', resumes: '简历管理', analysis: '简历分析', admin: '管理页面' }
const title = computed(() => titleMap[route.name] || '校招信息看板')

const emit = defineEmits(['open-config', 'open-chat', 'open-help'])

// ---- Live clock ----
const lastUpdatedHtml = ref('—')
let clockTimer = null
function updateLiveClock() {
  const now = new Date()
  const h = String(now.getHours()).padStart(2, '0')
  const m = String(now.getMinutes()).padStart(2, '0')
  const s = String(now.getSeconds()).padStart(2, '0')
  lastUpdatedHtml.value =
    '<span class="live-clock-dot" aria-hidden="true"></span>' +
    '<span class="live-clock-unit">' + h + '</span><i>:</i>' +
    '<span class="live-clock-unit">' + m + '</span><i>:</i>' +
    '<span class="live-clock-unit live-clock-seconds">' + s + '</span>'
}

// ---- Notification bell ----
const showNotifications = ref(false)
const notifications = ref([])
const backendUnread = ref(0)

async function loadNotifications(markRead) {
  try {
    const data = await api('GET', '/api/notifications', undefined, { silent: true })
    notifications.value = data.notifications || []
    backendUnread.value = data.unread_count || 0
    if (markRead) {
      const ids = notifications.value.filter(n => !n.is_read).map(n => n.id)
      if (ids.length) {
        await api('POST', '/api/notifications/read', { ids }, { silent: true })
        backendUnread.value = Math.max(0, backendUnread.value - ids.length)
        notifications.value.forEach(n => { n.is_read = true })
      }
    }
  } catch (_) { /* silent */ }
}

function toggleNotifications(event) {
  event.stopPropagation()
  const opening = !showNotifications.value
  showNotifications.value = opening
  if (opening) loadNotifications(true)
}

// ---- Style switcher ----
const showStylePanel = ref(false)
const currentStyle = ref(document.documentElement.dataset.style || 'classic')

function toggleStylePanel(event) {
  event.stopPropagation()
  showStylePanel.value = !showStylePanel.value
}

function applyStyle(name) {
  currentStyle.value = name
  document.documentElement.dataset.style = name
  try { localStorage.setItem('radar_style', name) } catch (_) {}
  showStylePanel.value = false
}

// ---- Theme toggle ----
const isDark = ref(document.documentElement.dataset.theme === 'dark')
const themeIcon = computed(() => isDark.value ? 'sun' : 'moon')

function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  isDark.value = !isDark.value
  document.documentElement.dataset.theme = next
  localStorage.setItem('radar_theme', next)
}

// ---- Time formatting ----
function formatTime(value) {
  if (!value) return ''
  const date = new Date(value.replace(' ', 'T') + 'Z')
  return isNaN(date) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

// ---- Document-level click to dismiss panels ----
function onDocumentClick(e) {
  if (!e.target.closest('.notification-wrap')) showNotifications.value = false
  if (!e.target.closest('.style-wrap')) showStylePanel.value = false
}

onMounted(() => {
  updateLiveClock()
  clockTimer = setInterval(updateLiveClock, 1000)
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <div class="topbar">
    <h1 id="page-title">{{ title }}</h1>
    <div class="spacer"></div>
    <span class="muted" id="last-updated" style="font-size:12px" v-html="lastUpdatedHtml"></span>

    <button class="icon-btn" @click="emit('open-help')" title="使用帮助" aria-label="使用帮助">?</button>
    <button class="icon-btn chat-top-btn" id="chat-top-btn" @click="emit('open-chat')" title="站内聊天" aria-label="站内聊天">
      <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 5h16v12H9l-5 4V5Z"/>
        <path d="M8 9h8M8 13h5"/>
      </svg>
      <span class="nav-unread" id="chat-nav-unread">0</span>
    </button>

    <div class="notification-wrap">
      <button class="icon-btn notification-btn" id="notification-btn" @click="toggleNotifications" :class="{ 'has-unread': backendUnread > 0 }" title="通知" aria-label="通知">
        <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 17h12l-2-3V9a4 4 0 0 0-8 0v5l-2 3Z"/>
          <path d="M10 20h4"/>
        </svg>
        <span class="notification-dot"></span>
      </button>
      <div class="notification-panel" id="notification-panel" :class="{ show: showNotifications }">
        <div class="reminder-block" id="reminder-block" style="display:none">
          <div class="reminder-head"><span>📌 待办提醒</span><span class="reminder-sub" id="reminder-sub"></span></div>
          <div id="reminder-list"></div>
        </div>
        <div class="notification-head">最新通知</div>
        <div id="notification-list">
          <template v-if="notifications.length">
            <article v-for="item in notifications" :key="item.id" class="notification-item" :class="{ unread: !item.is_read }">
              <h3>{{ item.title }}</h3>
              <p>{{ item.content }}</p>
              <span class="notification-time">{{ formatTime(item.created_at) }}</span>
            </article>
          </template>
          <div v-else class="center">暂无通知</div>
        </div>
      </div>
    </div>

    <button class="icon-btn" @click="emit('open-config')" title="AI 配置" aria-label="AI 配置">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 15.25A3.25 3.25 0 1 0 12 8.75a3.25 3.25 0 0 0 0 6.5Z" stroke="currentColor" stroke-width="1.8"/>
        <path d="M19.4 13.5a7.8 7.8 0 0 0 .05-1.5 7.8 7.8 0 0 0-.05-1.5l2-1.55-2-3.46-2.48 1a7.7 7.7 0 0 0-2.57-1.5L14 2.35h-4L9.65 5a7.7 7.7 0 0 0-2.57 1.5l-2.48-1-2 3.46 2 1.55a7.8 7.8 0 0 0-.05 1.5c0 .51.02 1.01.05 1.5l-2 1.55 2 3.46 2.48-1a7.7 7.7 0 0 0 2.57 1.5l.35 2.64h4l.35-2.64a7.7 7.7 0 0 0 2.57-1.5l2.48 1 2-3.46-2-1.55Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
      </svg>
    </button>

    <div class="style-wrap">
      <button class="icon-btn" id="style-btn" @click="toggleStylePanel" title="界面风格" aria-label="界面风格">
        <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3a9 9 0 1 0 0 18c1.3 0 2-.7 2-1.8 0-.8-.6-1.3-.6-2.1 0-.9.7-1.6 1.6-1.6h2a4 4 0 0 0 4-4C21 6.8 17 3 12 3Z"/>
          <path d="M7.5 10.5h.01M10.5 7h.01M15 8.5h.01M8 14.5h.01"/>
        </svg>
      </button>
      <div class="notification-panel style-panel" id="style-panel" :class="{ show: showStylePanel }">
        <div class="notification-head">界面风格</div>
        <div class="style-item" :class="{ active: currentStyle === 'classic' }" data-style="classic" @click="applyStyle('classic')">
          <div>经典风格<small>看板原始设计</small></div>
          <span class="style-check">✓</span>
        </div>
        <div class="style-item" :class="{ active: currentStyle === 'antd' }" data-style="antd" @click="applyStyle('antd')">
          <div>Ant Design<small>蚂蚁企业级设计体系</small></div>
          <span class="style-check">✓</span>
        </div>
        <div class="style-item" :class="{ active: currentStyle === 'glass' }" data-style="glass" @click="applyStyle('glass')">
          <div>Liquid Glass<small>液态玻璃 · 真实位移滤镜</small></div>
          <span class="style-check">✓</span>
        </div>
        <div class="style-item" :class="{ active: currentStyle === 'pixelium' }" data-style="pixelium" @click="applyStyle('pixelium')">
          <div>Pixelium 像素风<small>2px 像素几何</small></div>
          <span class="style-check">✓</span>
        </div>
      </div>
    </div>

    <button class="icon-btn" @click="toggleTheme" id="theme-btn" title="主题" aria-label="主题">
      <svg v-if="themeIcon === 'moon'" class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M19 15.5A8 8 0 0 1 8.5 5a8 8 0 1 0 10.5 10.5Z"/>
      </svg>
      <svg v-else class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>
        <path d="M8 12a4 4 0 1 0 8 0 4 4 0 0 0-8 0Z"/>
      </svg>
    </button>
  </div>
</template>
