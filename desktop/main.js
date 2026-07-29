const { app, BrowserWindow, Tray, Menu, Notification, shell, nativeImage, dialog } = require('electron')
const path = require('path')

// 单实例锁 — 同一时间只允许一个应用实例
const GOT_LOCK = app.requestSingleInstanceLock()
if (!GOT_LOCK) {
  app.quit()
  return
}

const APP_URL = 'https://toudimianban.cloud'
const APP_TITLE = '校招信息看板'

let mainWindow = null
let tray = null
let isQuitting = false

// ── 窗口创建 ──

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: APP_TITLE,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
    show: false, // 等 ready-to-show 再显示，避免白屏闪烁
    backgroundColor: '#f5f6fa',
  })

  mainWindow.loadURL(APP_URL)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  // 标题随页面变化
  mainWindow.on('page-title-updated', (event) => {
    event.preventDefault()
  })

  // 拦截新窗口（外部链接在系统浏览器打开）
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(APP_URL)) {
      shell.openExternal(url)
    }
    return { action: 'deny' }
  })

  // 页面内导航到外部链接时
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(APP_URL)) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  // 关闭行为 → 隐藏到托盘
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ── 系统托盘 ──

function createTray() {
  // 用 16x16 图标作为托盘图标，没有则用空白
  let icon
  try {
    icon = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png'))
    icon = icon.resize({ width: 16, height: 16 })
  } catch {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip(APP_TITLE)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show()
          mainWindow.focus()
        }
      },
    },
    { type: 'separator' },
    {
      label: '重启应用',
      click: () => {
        app.relaunch()
        app.exit()
      },
    },
    {
      label: '退出',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  // 双击托盘图标显示窗口
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show()
      mainWindow.focus()
    }
  })
}

// ── 应用生命周期 ──

app.whenReady().then(() => {
  createTray()
  createMainWindow()

  // 开机自启（Windows 注册表）
  app.setLoginItemSettings({
    openAtLogin: false,
    path: app.getPath('exe'),
  })
})

// 第二个实例启动时，激活已有窗口
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
  }
})

app.on('window-all-closed', () => {
  // 不退出，保持托盘运行
})

app.on('before-quit', () => {
  isQuitting = true
})

app.on('activate', () => {
  // macOS: 点击 Dock 图标
  if (mainWindow) {
    mainWindow.show()
  } else {
    createMainWindow()
  }
})
