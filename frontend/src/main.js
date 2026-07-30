import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import WidgetApp from './WidgetApp.vue'

const widgetType = new URLSearchParams(window.location.search).get('desktopWidget')
if (widgetType) document.documentElement.classList.add('desktop-widget-mode')
else if (window.electronAPI?.customTitlebar) document.documentElement.classList.add('desktop-main-mode')
const app = createApp(widgetType ? WidgetApp : App)
app.use(createPinia())
if (!widgetType) app.use(router)
app.mount('#app')
