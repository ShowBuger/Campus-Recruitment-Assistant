import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import WidgetApp from './WidgetApp.vue'
import { restoreAnimeResource, restoreAuroraResource, restoreCyberResource, restoreShuimoResource } from './utils/skinResources'
import { hasDesktopTitlebar } from './utils/runtime'

const widgetType = new URLSearchParams(window.location.search).get('desktopWidget')
if (widgetType) document.documentElement.classList.add('desktop-widget-mode')
else if (hasDesktopTitlebar()) document.documentElement.classList.add('desktop-main-mode')

function syncStyleSheets(style) {
  const pixelium = style === 'pixelium'
  for (const id of ['css-pixelium', 'css-pixelfont', 'css-pixelvue']) {
    const sheet = document.getElementById(id)
    if (sheet) sheet.disabled = !pixelium
  }
}

async function restoreStyleResource(style) {
  if (style === 'aurora') return restoreAuroraResource()
  if (style === 'anime') return restoreAnimeResource()
  if (style === 'cyber') return restoreCyberResource()
  if (style === 'shuimo') return restoreShuimoResource()
  return true
}

window.addEventListener('storage', async event => {
  if (event.key === 'radar_style' && event.newValue) {
    const previousStyle = document.documentElement.dataset.style
    let style = event.newValue
    if (style === 'shuimo' && document.documentElement.dataset.adminUser !== 'true') style = 'pixelium'
    if ((style === 'aurora' || document.documentElement.dataset.styleFont !== 'default') && !(await restoreStyleResource(style))) style = 'pixelium'
    document.documentElement.dataset.style = style
    if (previousStyle === 'aurora' && style !== 'aurora') {
      document.documentElement.dataset.theme = localStorage.getItem('radar_non_aurora_theme') === 'dark' ? 'dark' : 'light'
    } else if (style === 'aurora') {
      document.documentElement.dataset.theme = 'dark'
    }
    syncStyleSheets(style)
  } else if (event.key === 'radar_theme' && event.newValue) {
    document.documentElement.dataset.theme = document.documentElement.dataset.style === 'aurora' ? 'dark' : event.newValue
  } else if (event.key === 'radar_style_font' && event.newValue) {
    const mode = event.newValue === 'default' ? 'default' : 'themed'
    if (mode === 'themed' && !(await restoreStyleResource(document.documentElement.dataset.style))) return
    document.documentElement.dataset.styleFont = mode
  }
})

async function bootstrap() {
  const pendingStyle = document.documentElement.dataset.pendingStyle
  if (pendingStyle) {
    const restored = await restoreStyleResource(pendingStyle)
    document.documentElement.dataset.style = restored ? pendingStyle : 'pixelium'
    delete document.documentElement.dataset.pendingStyle
    if (!restored) localStorage.setItem('radar_style', 'pixelium')
  }
  const initialStyle = document.documentElement.dataset.style || 'pixelium'
  syncStyleSheets(initialStyle)
  if (!widgetType) window.electronAPI?.setSkin?.(initialStyle)

  const app = createApp(widgetType ? WidgetApp : App)
  app.use(createPinia())
  if (!widgetType) app.use(router)
  app.mount('#app')
}

bootstrap()
