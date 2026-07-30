import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import WidgetApp from './WidgetApp.vue'

const widgetType = new URLSearchParams(window.location.search).get('desktopWidget')
if (widgetType) document.documentElement.classList.add('desktop-widget-mode')
else if (window.electronAPI?.customTitlebar) document.documentElement.classList.add('desktop-main-mode')

function syncStyleSheets(style) {
  const pixelium = style === 'pixelium'
  for (const id of ['css-pixelium', 'css-pixelfont', 'css-pixelvue']) {
    const sheet = document.getElementById(id)
    if (sheet) sheet.disabled = !pixelium
  }
}

window.addEventListener('storage', event => {
  if (event.key === 'radar_style' && event.newValue) {
    document.documentElement.dataset.style = event.newValue
    syncStyleSheets(event.newValue)
  } else if (event.key === 'radar_theme' && event.newValue) {
    document.documentElement.dataset.theme = event.newValue
  }
})

const app = createApp(widgetType ? WidgetApp : App)
app.use(createPinia())
if (!widgetType) app.use(router)
app.mount('#app')
