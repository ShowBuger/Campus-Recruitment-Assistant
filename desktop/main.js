const { app, BrowserWindow, Tray, Menu, Notification, shell, nativeImage, dialog, ipcMain, screen } = require('electron')
const { autoUpdater } = require('electron-updater')
const path = require('path')
const fs = require('fs')
const os = require('os')

const APP_URL = process.env.CAMPUS_APP_URL || 'https://www.toudimianban.cloud'
const APP_ORIGIN = new URL(APP_URL).origin
const APP_TITLE = '校招信息看板'
const UPDATE_INTERVAL_MS = 6 * 60 * 60 * 1000

let mainWindow = null
let tray = null
let isQuitting = false
let manualUpdateCheck = false
let updateProgressTimer = null
let updateProgressTransferred = 0
const widgetWindows = new Map()
let widgetState = null
let widgetSaveTimer = null
const WIDGET_DEFS = Object.freeze({
  records: { title: '投递记录', width: 390, height: 520 },
  schedule: { title: '近期安排', width: 390, height: 460 },
})

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
}

function isAppUrl(rawUrl) {
  try {
    return new URL(rawUrl).origin === APP_ORIGIN
  } catch {
    return false
  }
}

function showMainWindow() {
  if (!mainWindow) return
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 430,
    height: 590,
    minWidth: 380,
    minHeight: 500,
    title: APP_TITLE,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    backgroundColor: '#f5f6fa',
    show: false,
    frame: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.setMenuBarVisibility(false)
  mainWindow.loadURL(APP_URL)
  mainWindow.once('ready-to-show', showMainWindow)
  mainWindow.on('page-title-updated', event => event.preventDefault())
  const sendWindowState = () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('desktop-window-state', { maximized: mainWindow.isMaximized() })
    }
  }
  mainWindow.on('maximize', sendWindowState)
  mainWindow.on('unmaximize', sendWindowState)

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isAppUrl(url)) return { action: 'allow' }
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isAppUrl(url)) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedUrl, isMainFrame) => {
    if (!isMainFrame || errorCode === -3) return
    dialog.showMessageBox(mainWindow, {
      type: 'warning',
      title: '网络连接失败',
      message: '暂时无法连接校招信息看板',
      detail: `${errorDescription}\n${validatedUrl}`,
      buttons: ['重试', '退出'],
      defaultId: 0,
      cancelId: 1,
    }).then(({ response }) => {
      if (response === 0 && mainWindow) mainWindow.loadURL(APP_URL)
      else {
        isQuitting = true
        app.quit()
      }
    })
  })

  mainWindow.on('close', event => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

function checkForUpdates(manual = false) {
  if (!app.isPackaged) {
    if (manual) {
      dialog.showMessageBox({ type: 'info', title: '检查更新', message: '开发模式不会检查安装包更新。' })
    }
    return
  }
  manualUpdateCheck = manual
  autoUpdater.checkForUpdates().catch(error => {
    if (manual) {
      dialog.showMessageBox({
        type: 'error',
        title: '检查更新失败',
        message: '暂时无法连接更新服务器',
        detail: error.message,
      })
    }
  })
}

function stopUpdateProgressFallback() {
  if (updateProgressTimer) clearInterval(updateProgressTimer)
  updateProgressTimer = null
  updateProgressTransferred = 0
}

function sendUpdateProgress({ version, transferred, total, bytesPerSecond = 0 }) {
  if (!mainWindow || !total) return
  updateProgressTransferred = Math.max(updateProgressTransferred, transferred)
  const percent = Math.max(0, Math.min(100, (updateProgressTransferred / total) * 100))
  mainWindow.setProgressBar(percent / 100)
  mainWindow.webContents.send('desktop-update-status', {
    state: 'downloading',
    version,
    percent,
    transferred: updateProgressTransferred,
    total,
    bytesPerSecond,
  })
  if (tray) tray.setToolTip(`${APP_TITLE} · 正在下载更新 ${percent.toFixed(0)}%`)
}

function startUpdateProgressFallback(info, installer) {
  stopUpdateProgressFallback()
  const total = Number(installer?.size) || 0
  const installerName = path.basename(String(installer?.url || ''))
  if (!total || !installerName) return

  const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local')
  const pendingDir = path.join(localAppData, 'campus-recruitment-updater', 'pending')
  const reportCachedBytes = () => {
    try {
      const candidates = fs.readdirSync(pendingDir)
        .filter(name => name === installerName || name.endsWith(`temp-${installerName}`))
        .map(name => fs.statSync(path.join(pendingDir, name)).size)
      if (candidates.length) {
        sendUpdateProgress({
          version: info.version,
          transferred: Math.min(total, Math.max(...candidates)),
          total,
        })
      }
    } catch {}
  }

  reportCachedBytes()
  updateProgressTimer = setInterval(reportCachedBytes, 500)
}

function configureAutoUpdater() {
  autoUpdater.autoDownload = true
  autoUpdater.autoInstallOnAppQuit = true
  autoUpdater.allowPrerelease = false
  autoUpdater.disableDifferentialDownload = true

  autoUpdater.on('update-available', info => {
    const installer = Array.isArray(info.files)
      ? info.files.find(file => String(file.url || '').toLowerCase().endsWith('.exe'))
      : null
    if (mainWindow) {
      mainWindow.webContents.send('desktop-update-status', {
        state: 'downloading',
        version: info.version,
        percent: 0,
        transferred: 0,
        total: Number(installer?.size) || 0,
      })
    }
    startUpdateProgressFallback(info, installer)
  })

  autoUpdater.on('download-progress', progress => {
    sendUpdateProgress({
      transferred: Number(progress.transferred) || 0,
      total: Number(progress.total) || 0,
      bytesPerSecond: Number(progress.bytesPerSecond) || 0,
    })
  })

  autoUpdater.on('update-not-available', () => {
    stopUpdateProgressFallback()
    if (manualUpdateCheck) {
      dialog.showMessageBox({
        type: 'info',
        title: '检查更新',
        message: `当前已是最新版本 v${app.getVersion()}`,
      })
    }
    manualUpdateCheck = false
  })

  autoUpdater.on('update-downloaded', info => {
    stopUpdateProgressFallback()
    manualUpdateCheck = false
    if (mainWindow) mainWindow.setProgressBar(-1)
    if (tray) tray.setToolTip(`${APP_TITLE} v${app.getVersion()}`)
    if (mainWindow) {
      mainWindow.webContents.send('desktop-update-status', {
        state: 'downloaded',
        version: info.version,
      })
    }
    dialog.showMessageBox(mainWindow || undefined, {
      type: 'info',
      title: '更新已就绪',
      message: `校招信息看板 v${info.version} 已下载完成`,
      detail: '现在重启即可完成升级；也可以稍后退出应用时自动安装。',
      buttons: ['立即重启升级', '稍后'],
      defaultId: 0,
      cancelId: 1,
    }).then(({ response }) => {
      if (response === 0) {
        isQuitting = true
        autoUpdater.quitAndInstall(false, true)
      }
    })
  })

  autoUpdater.on('error', error => {
    stopUpdateProgressFallback()
    if (mainWindow) mainWindow.setProgressBar(-1)
    if (tray) tray.setToolTip(`${APP_TITLE} v${app.getVersion()}`)
    if (mainWindow) {
      mainWindow.webContents.send('desktop-update-status', {
        state: 'error',
        message: error.message,
      })
    }
    if (manualUpdateCheck) {
      dialog.showMessageBox({
        type: 'error',
        title: '检查更新失败',
        message: '暂时无法获取最新版本',
        detail: error.message,
      })
    }
    manualUpdateCheck = false
  })

  setTimeout(() => checkForUpdates(false), 10_000)
  setInterval(() => checkForUpdates(false), UPDATE_INTERVAL_MS)
}

function widgetStatePath() {
  return path.join(app.getPath("userData"), "desktop-widgets.json")
}

function loadWidgetState() {
  if (widgetState) return widgetState
  try { widgetState = JSON.parse(fs.readFileSync(widgetStatePath(), "utf8")) } catch { widgetState = {} }
  return widgetState
}

function saveWidgetStateSoon() {
  if (widgetSaveTimer) clearTimeout(widgetSaveTimer)
  widgetSaveTimer = setTimeout(() => {
    widgetSaveTimer = null
    try { fs.writeFileSync(widgetStatePath(), JSON.stringify(loadWidgetState(), null, 2)) } catch {}
  }, 180)
}

function getWidgetSettings(type) {
  const state = loadWidgetState()
  return state[type] || (state[type] = { visible: false, pinned: false, locked: false })
}

function validWidgetBounds(saved, def) {
  if (!saved || !Number.isFinite(saved.x) || !Number.isFinite(saved.y)) return { width: def.width, height: def.height }
  const proposed = { x: saved.x, y: saved.y, width: saved.width || def.width, height: saved.height || def.height }
  const area = screen.getDisplayMatching(proposed).workArea
  return {
    x: Math.min(Math.max(proposed.x, area.x), area.x + area.width - 120),
    y: Math.min(Math.max(proposed.y, area.y), area.y + area.height - 80),
    width: Math.min(Math.max(proposed.width, 320), area.width),
    height: Math.min(Math.max(proposed.height, 300), area.height),
  }
}

function widgetStatus(type) {
  if (!WIDGET_DEFS[type]) throw new Error("未知桌面组件")
  const settings = getWidgetSettings(type)
  const win = widgetWindows.get(type)
  return { type, visible: Boolean(win && win.isVisible()), pinned: Boolean(settings.pinned), locked: Boolean(settings.locked) }
}

function createWidgetWindow(type, shouldShow = true) {
  const def = WIDGET_DEFS[type]
  if (!def) throw new Error("未知桌面组件")
  const existing = widgetWindows.get(type)
  if (existing && !existing.isDestroyed()) {
    if (shouldShow) { existing.show(); existing.focus() }
    return existing
  }
  const settings = getWidgetSettings(type)
  const win = new BrowserWindow({
    ...validWidgetBounds(settings.bounds, def),
    minWidth: 320, minHeight: 300,
    title: def.title, frame: false, show: false, skipTaskbar: true,
    alwaysOnTop: Boolean(settings.pinned), resizable: !settings.locked, movable: !settings.locked,
    backgroundColor: "#f4f6f8",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  })
  widgetWindows.set(type, win)
  win.loadURL(APP_URL + "/?desktopWidget=" + encodeURIComponent(type))
  win.on("page-title-updated", event => event.preventDefault())
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!isAppUrl(url)) shell.openExternal(url)
    return { action: "deny" }
  })
  win.webContents.on("will-navigate", (event, url) => {
    if (!isAppUrl(url)) { event.preventDefault(); shell.openExternal(url) }
  })
  win.once("ready-to-show", () => { if (shouldShow || settings.visible) win.show() })
  const rememberBounds = () => {
    if (win.isDestroyed() || settings.locked) return
    settings.bounds = win.getBounds()
    saveWidgetStateSoon()
  }
  win.on("move", rememberBounds)
  win.on("resize", rememberBounds)
  win.on("show", () => { settings.visible = true; saveWidgetStateSoon() })
  win.on("hide", () => { settings.visible = false; saveWidgetStateSoon() })
  win.on("close", event => {
    if (!isQuitting) { event.preventDefault(); win.hide() }
  })
  win.on("closed", () => widgetWindows.delete(type))
  return win
}

function showWidget(type) {
  createWidgetWindow(type, true)
  return widgetStatus(type)
}

function applyWidgetAction(type, action) {
  const settings = getWidgetSettings(type)
  const win = createWidgetWindow(type, false)
  if (action === "toggle-pin") { settings.pinned = !settings.pinned; win.setAlwaysOnTop(settings.pinned) }
  else if (action === "toggle-lock") { settings.locked = !settings.locked; win.setMovable(!settings.locked); win.setResizable(!settings.locked) }
  else if (action === "hide") win.hide()
  else if (action === "show") { win.show(); win.focus() }
  else if (action === "refresh") win.reload()
  else throw new Error("未知组件操作")
  saveWidgetStateSoon()
  return widgetStatus(type)
}

function restoreVisibleWidgets() {
  Object.keys(WIDGET_DEFS).forEach(type => { if (getWidgetSettings(type).visible) createWidgetWindow(type, true) })
}

function createTray() {
  let icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png'))
  if (!icon.isEmpty()) icon = icon.resize({ width: 16, height: 16 })

  tray = new Tray(icon)
  tray.setToolTip(`${APP_TITLE} v${app.getVersion()}`)
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '显示主窗口', click: showMainWindow },
    {
      label: '桌面组件',
      submenu: [
        { label: '投递记录', click: () => showWidget('records') },
        { label: '近期安排', click: () => showWidget('schedule') },
        { type: 'separator' },
        { label: '隐藏全部组件', click: () => widgetWindows.forEach(win => win.hide()) },
      ],
    },
    { label: '检查更新', click: () => checkForUpdates(true) },
    { type: 'separator' },
    {
      label: '重新加载页面',
      click: () => mainWindow && mainWindow.reload(),
    },
    {
      label: '退出',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ]))
  tray.on('double-click', showMainWindow)
}

ipcMain.handle('desktop:get-version', () => app.getVersion())
ipcMain.handle('desktop:set-skin', (_event, requestedSkin) => {
  const skin = ['classic', 'pixelium', 'aurora', 'anime', 'terminal'].includes(requestedSkin)
    ? requestedSkin
    : 'pixelium'
  if (!mainWindow || mainWindow.isDestroyed()) return skin
  try {
    if (process.platform === 'win32' && typeof mainWindow.setBackgroundMaterial === 'function') {
      mainWindow.setBackgroundMaterial(skin === 'aurora' ? 'mica' : 'none')
    } else if (process.platform === 'darwin' && typeof mainWindow.setVibrancy === 'function') {
      mainWindow.setVibrancy(skin === 'aurora' ? 'under-window' : null, { animationDuration: 180 })
    }
    mainWindow.setBackgroundColor(skin === 'aurora' ? '#00000000' : '#f5f6fa')
  } catch (error) {
    console.warn('Unable to apply native skin material:', error.message)
  }
  return skin
})
ipcMain.handle('desktop:window-control', (event, action) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win || win !== mainWindow) throw new Error('窗口操作不可用')
  if (action === 'minimize') win.minimize()
  else if (action === 'toggle-maximize') win.isMaximized() ? win.unmaximize() : win.maximize()
  else if (action === 'close') win.close()
  else if (action === 'login-size') {
    if (win.isMaximized()) win.unmaximize()
    win.setMinimumSize(380, 500)
    win.setResizable(false)
    win.setSize(430, 590, true)
    win.center()
  }
  else if (action === 'main-size') {
    win.setResizable(true)
    win.setSize(1280, 800, true)
    win.setMinimumSize(900, 600)
    win.center()
  }
  else if (action !== 'state') throw new Error('未知窗口操作')
  return { maximized: win.isMaximized() }
})
ipcMain.handle('desktop:widget-show', (_event, type) => showWidget(String(type || '')))
ipcMain.handle('desktop:widget-state', (_event, type) => widgetStatus(String(type || '')))
ipcMain.handle('desktop:widget-action', (_event, type, action) => applyWidgetAction(String(type || ''), String(action || '')))
ipcMain.handle('desktop:show-main', () => { showMainWindow(); return true })
ipcMain.handle('desktop:check-for-updates', () => checkForUpdates(true))
ipcMain.handle('desktop:open-external', (_event, url) => {
  const parsed = new URL(url)
  if (!['https:', 'http:'].includes(parsed.protocol)) throw new Error('不支持的链接协议')
  return shell.openExternal(parsed.toString())
})
ipcMain.on('desktop:notify', (_event, title, body) => {
  if (Notification.isSupported()) {
    new Notification({
      title: String(title || APP_TITLE).slice(0, 100),
      body: String(body || '').slice(0, 500),
      icon: path.join(__dirname, 'assets', 'icon.png'),
    }).show()
  }
})

app.whenReady().then(() => {
  app.setAppUserModelId('com.campus.recruitment')
  Menu.setApplicationMenu(null)
  createTray()
  createMainWindow()
  restoreVisibleWidgets()
  configureAutoUpdater()
})

app.on('second-instance', showMainWindow)
app.on('window-all-closed', () => {})
app.on('before-quit', () => {
  isQuitting = true
  if (widgetSaveTimer) { clearTimeout(widgetSaveTimer); widgetSaveTimer = null }
  try { fs.writeFileSync(widgetStatePath(), JSON.stringify(loadWidgetState(), null, 2)) } catch {}
})
app.on('activate', () => mainWindow ? showMainWindow() : createMainWindow())
