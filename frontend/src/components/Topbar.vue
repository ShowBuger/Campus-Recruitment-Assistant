<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/utils/api'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import {
  downloadAnimeResource,
  downloadAuroraResource,
  downloadCyberResource,
  downloadShuimoResource,
  restoreAnimeResource,
  restoreAuroraResource,
  restoreCyberResource,
  restoreShuimoResource,
} from '@/utils/skinResources'
import { isDesktopRuntime } from '@/utils/runtime'

const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()
const toast = useToastStore()
const isDesktop = isDesktopRuntime()
const desktopDownloadUrl = '/api/desktop/download/windows'
const desktopUpdate = ref(null)
const showWidgetPanel = ref(false)
const desktopUpdatePercent = computed(() => {
  const value = Number(desktopUpdate.value?.percent) || 0
  return Math.max(0, Math.min(100, value))
})
let removeDesktopUpdateListener = null
const titleMap = { dashboard: '投递信息', board: '投递看板', records: '总表信息', resumes: '简历管理', analysis: '简历分析', admin: '管理页面' }
const title = computed(() => titleMap[route.name] || '校招信息看板')

const emit = defineEmits(['open-config', 'open-chat', 'open-help'])

// ---- Live clock ----
const lastUpdatedHtml = ref('-')
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
let notifPollTimer = null

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
  } catch (_) {}
}

function toggleNotifications(event) {
  event.stopPropagation()
  const opening = !showNotifications.value
  showNotifications.value = opening
  if (opening) loadNotifications(true)
}

async function loadChatUnread() {
  try {
    const data = await api('GET', '/api/chat/users', undefined, { silent: true })
    const users = data?.users || data || []
    const total = users.filter(u => u.id !== authStore.user?.id).reduce((s, u) => s + (u.unread_count || 0), 0)
    appStore.setChatUnread(total)
  } catch (_) {}
}

function startNotifPoll() {
  stopNotifPoll()
  notifPollTimer = setInterval(() => { loadNotifications(false); loadChatUnread() }, 30000)
}
function stopNotifPoll() { if (notifPollTimer) { clearInterval(notifPollTimer); notifPollTimer = null } }

// ---- Style switcher ----
const showStylePanel = ref(false)
const styleButton = ref(null)
const stylePanelPosition = ref({})
const currentStyle = ref(document.documentElement.dataset.style || 'pixelium')
const useDefaultFont = ref(document.documentElement.dataset.styleFont === 'default')
const shuimoTrailEnabled = ref(document.documentElement.dataset.shuimoTrail !== 'off')
const animeResourceStatus = ref('checking')
const animeResourceProgress = ref({ percent: 0, received: 0, total: 0 })
const shuimoResourceStatus = ref('checking')
const shuimoResourceProgress = ref({ percent: 0, received: 0, total: 0 })
const cyberResourceStatus = ref('checking')
const cyberResourceProgress = ref({ percent: 0, received: 0, total: 0 })
const auroraResourceStatus = ref('checking')
const auroraResourceProgress = ref({ percent: 0, received: 0, total: 0 })

function positionStylePanel() {
  if (!showStylePanel.value || !styleButton.value) return
  const rect = styleButton.value.getBoundingClientRect()
  const width = Math.min(278, window.innerWidth - 20)
  const top = Math.min(rect.bottom + 8, window.innerHeight - 130)
  const left = Math.max(10, Math.min(rect.right - width, window.innerWidth - width - 10))
  stylePanelPosition.value = {
    position: 'fixed',
    top: `${Math.max(10, top)}px`,
    left: `${left}px`,
    right: 'auto',
    width: `${width}px`,
    maxHeight: `${Math.max(120, window.innerHeight - Math.max(10, top) - 10)}px`,
  }
}

async function toggleStylePanel(event) {
  event.stopPropagation()
  showStylePanel.value = !showStylePanel.value
  if (showStylePanel.value) {
    await nextTick()
    positionStylePanel()
  }
}

function enableSheet(id, on) {
  const el = document.getElementById(id)
  if (el) { if (on) el.removeAttribute('disabled'); else el.setAttribute('disabled', '') }
}

function applyStyle(name) {
  if (name === 'aurora' && auroraResourceStatus.value !== 'ready') return
  if (!useDefaultFont.value && name === 'anime' && animeResourceStatus.value !== 'ready') return
  if (!useDefaultFont.value && name === 'shuimo' && shuimoResourceStatus.value !== 'ready') return
  if (!useDefaultFont.value && name === 'cyber' && cyberResourceStatus.value !== 'ready') return
  if (!['classic', 'pixelium', 'aurora', 'anime', 'journal', 'shuimo', 'cyber'].includes(name)) name = 'pixelium'
  const previousStyle = currentStyle.value
  const leavingAurora = previousStyle === 'aurora' && name !== 'aurora'
  if (name === 'aurora' && previousStyle !== 'aurora') {
    localStorage.setItem('radar_non_aurora_theme', document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')
  }
  currentStyle.value = name
  document.documentElement.dataset.style = name
  if (name === 'aurora') {
    isDark.value = true
    document.documentElement.dataset.theme = 'dark'
    localStorage.setItem('radar_theme', 'dark')
  } else if (leavingAurora) {
    const restoredTheme = localStorage.getItem('radar_non_aurora_theme') === 'dark' ? 'dark' : 'light'
    isDark.value = restoredTheme === 'dark'
    document.documentElement.dataset.theme = restoredTheme
    localStorage.setItem('radar_theme', restoredTheme)
  }
  try { localStorage.setItem('radar_style', name) } catch (_) {}
  enableSheet('css-pixelium', name === 'pixelium')
  enableSheet('css-pixelfont', name === 'pixelium')
  enableSheet('css-pixelvue', name === 'pixelium')
  window.electronAPI?.setSkin?.(name)
  showStylePanel.value = false
}

function setDefaultFont(enabled) {
  useDefaultFont.value = enabled
  const mode = enabled ? 'default' : 'themed'
  document.documentElement.dataset.styleFont = mode
  try { localStorage.setItem('radar_style_font', mode) } catch (_) {}
}

async function checkStyleResources() {
  const [auroraReady, animeReady, shuimoReady, cyberReady] = await Promise.all([restoreAuroraResource(), restoreAnimeResource(), restoreShuimoResource(), restoreCyberResource()])
  auroraResourceStatus.value = auroraReady ? 'ready' : 'missing'
  animeResourceStatus.value = animeReady ? 'ready' : 'missing'
  shuimoResourceStatus.value = shuimoReady ? 'ready' : 'missing'
  cyberResourceStatus.value = cyberReady ? 'ready' : 'missing'
}

async function fetchAuroraResource(activateStyle) {
  if (auroraResourceStatus.value === 'downloading') return
  auroraResourceStatus.value = 'downloading'
  auroraResourceProgress.value = { percent: 0, received: 0, total: 0 }
  try {
    await downloadAuroraResource(progress => { auroraResourceProgress.value = progress })
    auroraResourceStatus.value = 'ready'
    toast.success('夜雨视频与海马体已保存到本地')
    if (activateStyle) applyStyle('aurora')
    return true
  } catch (error) {
    auroraResourceStatus.value = 'error'
    toast.error(error.message || '雨幕流光资源下载失败')
    return false
  }
}

function downloadAurora() { return fetchAuroraResource(true) }

async function fetchAnimeResource(activateStyle) {
  if (animeResourceStatus.value === 'downloading') return
  animeResourceStatus.value = 'downloading'
  animeResourceProgress.value = { percent: 0, received: 0, total: 0 }
  try {
    await downloadAnimeResource(progress => { animeResourceProgress.value = progress })
    animeResourceStatus.value = 'ready'
    toast.success('樱愿手账字体已下载')
    if (activateStyle) applyStyle('anime')
    return true
  } catch (error) {
    animeResourceStatus.value = 'error'
    toast.error(error.message || '樱愿手账字体下载失败')
    return false
  }
}

function downloadAnime() { return fetchAnimeResource(true) }

async function fetchShuimoResource(activateStyle) {
  if (shuimoResourceStatus.value === 'downloading') return
  shuimoResourceStatus.value = 'downloading'
  shuimoResourceProgress.value = { percent: 0, received: 0, total: 0 }
  try {
    await downloadShuimoResource(progress => { shuimoResourceProgress.value = progress })
    shuimoResourceStatus.value = 'ready'
    toast.success('龙吟手书已保存到本地')
    if (activateStyle) applyStyle('shuimo')
    return true
  } catch (error) {
    shuimoResourceStatus.value = 'error'
    toast.error(error.message || '水墨资源下载失败')
    return false
  }
}

function downloadShuimo() { return fetchShuimoResource(true) }

watch(() => [authStore.isLoggedIn, authStore.isAdmin], async ([loggedIn, isAdmin]) => {
  document.documentElement.dataset.adminUser = isAdmin ? 'true' : 'false'
  if (!loggedIn || localStorage.getItem('radar_style') !== 'shuimo') return
  if (useDefaultFont.value) {
    applyStyle('shuimo')
    return
  }
  const ready = await restoreShuimoResource()
  shuimoResourceStatus.value = ready ? 'ready' : 'missing'
  if (ready) applyStyle('shuimo')
}, { immediate: true })

async function fetchCyberResource(activateStyle) {
  if (cyberResourceStatus.value === 'downloading') return
  cyberResourceStatus.value = 'downloading'
  cyberResourceProgress.value = { percent: 0, received: 0, total: 0 }
  try {
    await downloadCyberResource(progress => { cyberResourceProgress.value = progress })
    cyberResourceStatus.value = 'ready'
    toast.success('霓虹终端字体已下载')
    if (activateStyle) applyStyle('cyber')
    return true
  } catch (error) {
    cyberResourceStatus.value = 'error'
    toast.error(error.message || '科幻仿生字体下载失败')
    return false
  }
}

function downloadCyber() { return fetchCyberResource(true) }

async function toggleDefaultFont(event) {
  const enabled = event.target.checked
  if (enabled) {
    setDefaultFont(true)
    return
  }
  let ready = true
  if (currentStyle.value === 'anime' && animeResourceStatus.value !== 'ready') ready = await fetchAnimeResource(false)
  if (currentStyle.value === 'shuimo' && shuimoResourceStatus.value !== 'ready') ready = await fetchShuimoResource(false)
  if (currentStyle.value === 'cyber' && cyberResourceStatus.value !== 'ready') ready = await fetchCyberResource(false)
  if (ready) setDefaultFont(false)
  else event.target.checked = true
}

function toggleShuimoTrail(event) {
  shuimoTrailEnabled.value = Boolean(event.target.checked)
  const value = shuimoTrailEnabled.value ? 'on' : 'off'
  document.documentElement.dataset.shuimoTrail = value
  localStorage.setItem('radar_shuimo_trail', value)
}

// ---- Theme toggle ----
const isDark = ref(document.documentElement.dataset.theme === 'dark')
const themeIcon = computed(() => isDark.value ? 'sun' : 'moon')
const themeLocked = computed(() => currentStyle.value === 'aurora')

function toggleTheme() {
  if (themeLocked.value) return
  const next = isDark.value ? 'light' : 'dark'
  isDark.value = !isDark.value
  document.documentElement.dataset.theme = next
  localStorage.setItem('radar_theme', next)
  localStorage.setItem('radar_non_aurora_theme', next)
}

function openDesktopWidget(type) {
  showWidgetPanel.value = false
  window.electronAPI?.showWidget?.(type)
}

function downloadDesktopApp() {
  window.location.assign(desktopDownloadUrl)
}

function formatDownloadSize(bytes) {
  const value = Number(bytes) || 0
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
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
  if (!e.target.closest('.style-wrap,#style-panel')) showStylePanel.value = false
  if (!e.target.closest('.desktop-widget-launcher')) showWidgetPanel.value = false
}

onMounted(() => {
  checkStyleResources()
  updateLiveClock()
  clockTimer = setInterval(updateLiveClock, 1000)
  document.addEventListener('click', onDocumentClick)
  window.addEventListener('resize', positionStylePanel)
  window.addEventListener('scroll', positionStylePanel, true)
  loadNotifications(false)
  loadChatUnread()
  startNotifPoll()
  removeDesktopUpdateListener = window.electronAPI?.onUpdateStatus?.(status => {
    desktopUpdate.value = status
    if (status?.state === 'error') {
      window.setTimeout(() => {
        if (desktopUpdate.value === status) desktopUpdate.value = null
      }, 8000)
    }
  }) || null
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  document.removeEventListener('click', onDocumentClick)
  window.removeEventListener('resize', positionStylePanel)
  window.removeEventListener('scroll', positionStylePanel, true)
  stopNotifPoll()
  if (removeDesktopUpdateListener) removeDesktopUpdateListener()
})
</script>

<template>
  <div class="topbar">
    <h1 id="page-title">{{ title }}</h1>
    <div class="spacer"></div>
    <span class="muted" id="last-updated" style="font-size:12px" v-html="lastUpdatedHtml"></span>

    <button
      v-if="!isDesktop"
      class="btn desktop-download-btn"
      type="button"
      title="下载 Windows 桌面端"
      @click="downloadDesktopApp"
    >
      <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v12M7 10l5 5 5-5"/>
        <path d="M5 19h14"/>
      </svg>
      <span>下载桌面端</span>
    </button>

    <div v-if="isDesktop" class="notification-wrap desktop-widget-launcher">
      <button class="icon-btn" type="button" title="桌面组件" aria-label="桌面组件" @click.stop="showWidgetPanel = !showWidgetPanel">
        <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h7v6H4V5Zm9 0h7v10h-7V5ZM4 13h7v6H4v-6Zm9 4h7v2h-7v-2Z"/></svg>
      </button>
      <div class="notification-panel widget-launch-panel" :class="{ show: showWidgetPanel }">
        <div class="notification-head">桌面组件</div>
        <button type="button" class="style-item widget-launch-item" @click="openDesktopWidget('records')"><span>投递记录<small>查看最近的投递进度</small></span><b>打开</b></button>
        <button type="button" class="style-item widget-launch-item" @click="openDesktopWidget('schedule')"><span>近期安排<small>未来 30 天考试与面试</small></span><b>打开</b></button>
      </div>
    </div>

    <button class="icon-btn" @click="emit('open-help')" title="使用帮助" aria-label="使用帮助">?</button>
    <button class="icon-btn chat-top-btn" id="chat-top-btn" @click="emit('open-chat')" title="站内聊天" aria-label="站内聊天">
      <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 5h16v12H9l-5 4V5Z"/>
        <path d="M8 9h8M8 13h5"/>
      </svg>
      <span v-if="appStore.chatUnread" class="nav-unread" id="chat-nav-unread">{{ appStore.chatUnread }}</span>
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
        <div class="notification-head utility-panel-head"><div><b>通知中心</b><span>{{ notifications.length ? notifications.length + ' 条消息' : '暂无新消息' }}</span></div></div>
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
      <button ref="styleButton" class="icon-btn" id="style-btn" @click="toggleStylePanel" title="界面风格" aria-label="界面风格">
        <svg class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3a9 9 0 1 0 0 18c1.3 0 2-.7 2-1.8 0-.8-.6-1.3-.6-2.1 0-.9.7-1.6 1.6-1.6h2a4 4 0 0 0 4-4C21 6.8 17 3 12 3Z"/>
          <path d="M7.5 10.5h.01M10.5 7h.01M15 8.5h.01M8 14.5h.01"/>
        </svg>
      </button>
      <Teleport to="body">
      <div class="notification-panel style-panel floating-style-panel" id="style-panel" :class="{ show: showStylePanel }" :style="stylePanelPosition" @click.stop>
        <div class="notification-head utility-panel-head"><div><b>界面风格</b><span>选择适合当前场景的视觉主题</span></div></div>
        <label class="style-font-option">
          <span class="style-font-option-copy"><b>使用默认字体</b><small>关闭后使用各风格的限定字体</small></span>
          <span class="style-font-toggle">
            <input type="checkbox" role="switch" aria-label="使用默认字体" :checked="useDefaultFont" :disabled="auroraResourceStatus === 'downloading' || animeResourceStatus === 'downloading' || shuimoResourceStatus === 'downloading' || cyberResourceStatus === 'downloading'" @change="toggleDefaultFont">
            <i aria-hidden="true"></i>
          </span>
        </label>
        <label v-if="authStore.isAdmin && currentStyle === 'shuimo'" class="style-font-option">
          <span class="style-font-option-copy"><b>毛笔拖尾</b><small>短柔笔迹，可随时关闭</small></span>
          <span class="style-font-toggle">
            <input type="checkbox" role="switch" aria-label="启用毛笔拖尾" :checked="shuimoTrailEnabled" @change="toggleShuimoTrail">
            <i aria-hidden="true"></i>
          </span>
        </label>
        <div class="style-item" :class="{ active: currentStyle === 'classic' }" data-style-option="classic" @click="applyStyle('classic')">
          <i class="style-swatch swatch-classic" aria-hidden="true"></i>
          <div>清简原境<small>清爽高效的办公看板</small></div>
          <span class="style-check">✓</span>
        </div>
        <div class="style-item" :class="{ active: currentStyle === 'pixelium' }" data-style-option="pixelium" @click="applyStyle('pixelium')">
          <i class="style-swatch swatch-pixelium" aria-hidden="true"></i>
          <div>像素矩阵<small>2px 像素几何</small></div>
          <span class="style-check">✓</span>
        </div>
        <div
          class="style-item resource-style-item aurora-style-item"
          :class="{ active: currentStyle === 'aurora', locked: auroraResourceStatus !== 'ready', downloading: auroraResourceStatus === 'downloading' }"
          data-style-option="aurora"
          @click="applyStyle('aurora')"
        >
          <i class="style-swatch swatch-aurora" aria-hidden="true"></i>
          <div class="style-item-copy">
            雨幕流光
            <small v-if="auroraResourceStatus === 'downloading'">
              正在保存到本地 {{ formatDownloadSize(auroraResourceProgress.received) }}<template v-if="auroraResourceProgress.total"> / {{ formatDownloadSize(auroraResourceProgress.total) }}</template>
            </small>
            <small v-else-if="auroraResourceStatus === 'error'">下载失败，点击右侧重试</small>
            <small v-else-if="auroraResourceStatus !== 'ready'">下载夜雨视频与海马体后启用</small>
            <small v-else>雨夜霓光 · 清透玻璃质感</small>
          </div>
          <button
            v-if="auroraResourceStatus !== 'ready'"
            class="style-download-btn"
            type="button"
            :disabled="auroraResourceStatus === 'checking' || auroraResourceStatus === 'downloading'"
            :title="auroraResourceStatus === 'downloading' ? '正在下载雨幕流光资源' : '下载雨幕流光资源到本地'"
            :aria-label="auroraResourceStatus === 'downloading' ? '正在下载雨幕流光资源' : '下载雨幕流光资源到本地'"
            @click.stop="downloadAurora"
          >
            <svg v-if="auroraResourceStatus !== 'downloading'" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 20h14"/></svg>
            <span v-else>{{ Math.round(auroraResourceProgress.percent) }}%</span>
          </button>
          <span v-else class="style-check">✓</span>
          <i v-if="auroraResourceStatus === 'downloading'" class="style-resource-progress" :style="{ width: auroraResourceProgress.percent + '%' }"></i>
        </div>
        <div
          class="style-item resource-style-item cyber-style-item"
          :class="{ active: currentStyle === 'cyber', locked: !useDefaultFont && cyberResourceStatus !== 'ready', downloading: cyberResourceStatus === 'downloading' }"
          data-style-option="cyber"
          @click="applyStyle('cyber')"
        >
          <i class="style-swatch swatch-cyber" aria-hidden="true"></i>
          <div class="style-item-copy">
            霓虹终端
            <small v-if="cyberResourceStatus === 'downloading'">
              正在下载 {{ formatDownloadSize(cyberResourceProgress.received) }}<template v-if="cyberResourceProgress.total"> / {{ formatDownloadSize(cyberResourceProgress.total) }}</template>
            </small>
            <small v-else-if="useDefaultFont">当前使用系统默认字体</small>
            <small v-else-if="cyberResourceStatus === 'error'">下载失败，点击右侧重试</small>
            <small v-else-if="cyberResourceStatus !== 'ready'">下载科幻仿生体后解锁主题</small>
            <small v-else>酸性黄警戒界面、故障霓虹与夜城 HUD</small>
          </div>
          <button
            v-if="!useDefaultFont && cyberResourceStatus !== 'ready'"
            class="style-download-btn"
            type="button"
            :disabled="cyberResourceStatus === 'checking' || cyberResourceStatus === 'downloading'"
            :title="cyberResourceStatus === 'downloading' ? '正在下载科幻仿生体' : '下载科幻仿生体'"
            :aria-label="cyberResourceStatus === 'downloading' ? '正在下载科幻仿生体' : '下载科幻仿生体'"
            @click.stop="downloadCyber"
          >
            <svg v-if="cyberResourceStatus !== 'downloading'" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 20h14"/></svg>
            <span v-else>{{ Math.round(cyberResourceProgress.percent) }}%</span>
          </button>
          <span v-else class="style-check">✓</span>
          <i v-if="cyberResourceStatus === 'downloading'" class="style-resource-progress" :style="{ width: cyberResourceProgress.percent + '%' }"></i>
        </div>
        <div
          class="style-item resource-style-item anime-style-item"
          :class="{ active: currentStyle === 'anime', locked: !useDefaultFont && animeResourceStatus !== 'ready', downloading: animeResourceStatus === 'downloading' }"
          data-style-option="anime"
          @click="applyStyle('anime')"
        >
          <i class="style-swatch swatch-anime" aria-hidden="true"></i>
          <div class="style-item-copy">
            樱愿手账
            <small v-if="animeResourceStatus === 'downloading'">
              正在下载 {{ formatDownloadSize(animeResourceProgress.received) }}<template v-if="animeResourceProgress.total"> / {{ formatDownloadSize(animeResourceProgress.total) }}</template>
            </small>
            <small v-else-if="useDefaultFont">当前使用系统默认字体</small>
            <small v-else-if="animeResourceStatus === 'error'">下载失败，点击右侧重试</small>
            <small v-else-if="animeResourceStatus !== 'ready'">下载布丁体后解锁手账主题</small>
            <small v-else>布丁字体、原创角色与漫画贴纸</small>
          </div>
          <button
            v-if="!useDefaultFont && animeResourceStatus !== 'ready'"
            class="style-download-btn"
            type="button"
            :disabled="animeResourceStatus === 'checking' || animeResourceStatus === 'downloading'"
            :title="animeResourceStatus === 'downloading' ? '正在下载布丁体' : '下载布丁体'"
            :aria-label="animeResourceStatus === 'downloading' ? '正在下载布丁体' : '下载布丁体'"
            @click.stop="downloadAnime"
          >
            <svg v-if="animeResourceStatus !== 'downloading'" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 20h14"/></svg>
            <span v-else>{{ Math.round(animeResourceProgress.percent) }}%</span>
          </button>
          <span v-else class="style-check">✓</span>
          <i v-if="animeResourceStatus === 'downloading'" class="style-resource-progress" :style="{ width: animeResourceProgress.percent + '%' }"></i>
        </div>
        <div class="style-item" :class="{ active: currentStyle === 'journal' }" data-style-option="journal" @click="applyStyle('journal')">
          <i class="style-swatch swatch-journal" aria-hidden="true"></i>
          <div>纸页档案<small>精装书页、索引与纸张档案</small></div>
          <span class="style-check">✓</span>
        </div>
        <div
          class="style-item resource-style-item shuimo-style-item"
          :class="{ active: currentStyle === 'shuimo', locked: !useDefaultFont && shuimoResourceStatus !== 'ready', downloading: shuimoResourceStatus === 'downloading' }"
          data-style-option="shuimo"
          @click="applyStyle('shuimo')"
        >
          <i class="style-swatch swatch-shuimo" aria-hidden="true"></i>
          <div class="style-item-copy">
            云水墨境
            <small v-if="shuimoResourceStatus === 'downloading'">
              正在下载 {{ formatDownloadSize(shuimoResourceProgress.received) }}<template v-if="shuimoResourceProgress.total"> / {{ formatDownloadSize(shuimoResourceProgress.total) }}</template>
            </small>
            <small v-else-if="useDefaultFont">当前使用系统默认字体</small>
            <small v-else-if="shuimoResourceStatus === 'error'">下载失败，点击右侧重试</small>
            <small v-else-if="shuimoResourceStatus !== 'ready'">下载龙吟手书后解锁水墨主题</small>
            <small v-else>龙吟手书、宣纸远山与朱砂题签</small>
          </div>
          <button
            v-if="!useDefaultFont && shuimoResourceStatus !== 'ready'"
            class="style-download-btn"
            type="button"
            :disabled="shuimoResourceStatus === 'checking' || shuimoResourceStatus === 'downloading'"
            :title="shuimoResourceStatus === 'downloading' ? '正在下载龙吟手书' : '下载龙吟手书'"
            :aria-label="shuimoResourceStatus === 'downloading' ? '正在下载龙吟手书' : '下载龙吟手书'"
            @click.stop="downloadShuimo"
          >
            <svg v-if="shuimoResourceStatus !== 'downloading'" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 20h14"/></svg>
            <span v-else>{{ Math.round(shuimoResourceProgress.percent) }}%</span>
          </button>
          <span v-else class="style-check">✓</span>
          <i v-if="shuimoResourceStatus === 'downloading'" class="style-resource-progress" :style="{ width: shuimoResourceProgress.percent + '%' }"></i>
        </div>
      </div>
      </Teleport>
    </div>

    <button class="icon-btn" @click="toggleTheme" id="theme-btn" :disabled="themeLocked" :title="themeLocked ? '极光玻璃固定使用黑夜模式' : '切换明暗主题'" :aria-label="themeLocked ? '极光玻璃固定使用黑夜模式' : '切换明暗主题'">
      <svg v-if="themeIcon === 'moon'" class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M19 15.5A8 8 0 0 1 8.5 5a8 8 0 1 0 10.5 10.5Z"/>
      </svg>
      <svg v-else class="tool-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>
        <path d="M8 12a4 4 0 1 0 8 0 4 4 0 0 0-8 0Z"/>
      </svg>
    </button>
  </div>
  <aside
    v-if="isDesktop && ['downloading', 'error'].includes(desktopUpdate?.state)"
    class="desktop-update-progress"
    :class="{ error: desktopUpdate?.state === 'error' }"
    aria-live="polite"
  >
    <template v-if="desktopUpdate?.state === 'error'">
      <div class="desktop-update-progress-head">
        <span>更新下载失败</span>
      </div>
      <small>请稍后通过托盘菜单重新检查更新</small>
    </template>
    <template v-else>
    <div class="desktop-update-progress-head">
      <span>正在下载桌面端更新</span>
      <strong>{{ desktopUpdatePercent.toFixed(0) }}%</strong>
    </div>
    <div class="desktop-update-progress-track">
      <i :style="{ width: `${desktopUpdatePercent}%` }"></i>
    </div>
    <small v-if="desktopUpdate.total">
      {{ formatDownloadSize(desktopUpdate.transferred) }} / {{ formatDownloadSize(desktopUpdate.total) }}
    </small>
    <small v-else>正在获取安装包大小…</small>
    </template>
  </aside>
</template>

<style scoped>
#style-panel{max-height:min(620px,calc(100vh - 20px));overflow-y:auto;font-family:var(--font)!important}#style-panel .style-item,#style-panel .style-item *{font-family:inherit!important}.floating-style-panel{z-index:32000!important}.style-font-option{display:flex;min-height:56px;align-items:center;justify-content:space-between;gap:12px;margin:6px 7px;padding:9px 10px;border-bottom:1px solid var(--line);cursor:pointer}.style-font-option-copy{min-width:0}.style-font-option-copy b,.style-font-option-copy small{display:block}.style-font-option-copy b{font-size:12px}.style-font-option-copy small{margin-top:3px;color:var(--sub);font-size:10px;font-weight:400}.style-font-toggle{position:relative;width:40px;height:22px;flex:0 0 40px}.style-font-toggle input{position:absolute;opacity:0;pointer-events:none}.style-font-toggle i{display:block;width:40px;height:22px;border:1px solid var(--line2);border-radius:999px;background:var(--line);transition:background .18s var(--ease),border-color .18s var(--ease)}.style-font-toggle i:after{content:"";position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:var(--panel);box-shadow:0 1px 4px rgba(16,24,40,.25);transition:transform .18s var(--ease)}.style-font-toggle input:checked+i{border-color:var(--green);background:var(--green)}.style-font-toggle input:checked+i:after{transform:translateX(18px)}.style-font-toggle input:focus-visible+i{outline:2px solid var(--blue);outline-offset:2px}.style-font-toggle input:disabled+i{opacity:.62;cursor:wait}.style-item-copy{min-width:0;flex:1}.resource-style-item{position:relative;overflow:hidden}.resource-style-item.locked{cursor:default}.style-download-btn{display:grid;width:34px;height:34px;flex:0 0 34px;place-items:center;padding:0;border:1px solid var(--line2);border-radius:6px;background:var(--panel);color:var(--ink);cursor:pointer}.style-download-btn:hover:not(:disabled){border-color:var(--blue);color:var(--blue)}.style-download-btn:disabled{cursor:wait;opacity:.72}.style-download-btn svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.style-download-btn span{font-size:9px;font-weight:900}.style-resource-progress{position:absolute;left:0;bottom:0;height:3px;background:var(--blue);transition:width .15s linear}
</style>
