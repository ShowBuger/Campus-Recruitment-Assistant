const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')

const styles = (process.env.CAMPUS_VISUAL_STYLES || 'pixelium,aurora,anime,terminal').split(',')
const token = process.env.CAMPUS_VISUAL_TOKEN
const target = process.env.CAMPUS_VISUAL_URL || 'http://127.0.0.1:8765'
const outputDir = process.env.CAMPUS_VISUAL_OUTPUT || '/tmp/campus-skin-smoke'

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

app.whenReady().then(async () => {
  ipcMain.handle('desktop:get-version', () => 'visual-smoke')
  ipcMain.handle('desktop:window-control', () => ({ maximized: false }))
  ipcMain.handle('desktop:set-skin', (_event, skin) => skin)
  ipcMain.handle('desktop:widget-state', () => ({ pinned: false, locked: false }))
  ipcMain.handle('desktop:widget-action', () => ({ pinned: false, locked: false }))
  ipcMain.handle('desktop:show-main', () => true)
  ipcMain.handle('desktop:check-for-updates', () => true)
  ipcMain.handle('desktop:open-external', () => true)
  fs.mkdirSync(outputDir, { recursive: true })
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    show: false,
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  await win.loadURL(target)
  await win.webContents.executeJavaScript(`localStorage.setItem('rb_token', ${JSON.stringify(token)}); true`)
  for (const style of styles) {
    await win.webContents.executeJavaScript(`
      localStorage.setItem('radar_style', ${JSON.stringify(style)});
      localStorage.setItem('radar_theme', 'light');
      true
    `)
    await win.reload()
    await wait(1800)
    await win.webContents.executeJavaScript('document.fonts.ready')
    const audit = await win.webContents.executeJavaScript(`
      (() => {
        const visible = selector => {
          const element = document.querySelector(selector)
          return element && getComputedStyle(element).display !== 'none'
        }
        const horizontalOverflow = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) > innerWidth + 2
        const badBounds = Array.from(document.querySelectorAll('.topbar,.card,.kpi,.liquid-dock')).filter(element => {
          if (getComputedStyle(element).display === 'none') return false
          const rect = element.getBoundingClientRect()
          return rect.right > innerWidth + 2 || rect.left < -2
        }).length
        const assistant = document.querySelector('.anime-assistant')
        return {
          horizontalOverflow,
          badBounds,
          sidebarVisible: visible('.sidebar'),
          dockVisible: visible('.liquid-dock'),
          assistantPresent: Boolean(assistant),
          rootClip: getComputedStyle(document.documentElement).clipPath,
        }
      })()
    `)
    const expected = style === 'aurora'
      ? !audit.sidebarVisible && audit.dockVisible
      : style === 'anime'
        ? audit.sidebarVisible && !audit.assistantPresent
        : audit.sidebarVisible
    if (audit.horizontalOverflow || audit.badBounds || audit.rootClip !== 'none' || !expected) {
      throw new Error(`${style} visual audit failed: ${JSON.stringify(audit)}`)
    }
    console.log(`${style} visual audit`, JSON.stringify(audit))
    const image = await win.capturePage()
    fs.writeFileSync(path.join(outputDir, `${style}.png`), image.toPNG())
    if (style === 'aurora' || style === 'anime') {
      await win.webContents.executeJavaScript(`document.querySelector('button[aria-label="AI 配置"]')?.click()`)
      await wait(350)
      await win.webContents.executeJavaScript(`document.querySelector('.settings-modal')?.style.setProperty('animation', 'none')`)
      await wait(120)
      const modalAudit = await win.webContents.executeJavaScript(`
        (() => {
          const modal = document.querySelector('.settings-modal')
          if (!modal) return { visible: false }
          const rect = modal.getBoundingClientRect()
          const center = document.elementFromPoint(innerWidth / 2, innerHeight / 2)
          return { visible: getComputedStyle(modal).display !== 'none', opacity: getComputedStyle(modal).opacity, visibility: getComputedStyle(modal).visibility, zIndex: getComputedStyle(modal.parentElement).zIndex, parentDisplay: getComputedStyle(modal.parentElement).display, centerClass: center?.className || center?.tagName, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom, width: rect.width }
        })()
      `)
      console.log(`${style} modal audit`, JSON.stringify(modalAudit))
      if (!modalAudit.visible || modalAudit.left < 0 || modalAudit.right > win.getContentBounds().width) {
        throw new Error(`${style} modal audit failed: ${JSON.stringify(modalAudit)}`)
      }
      const modalImage = await win.capturePage()
      fs.writeFileSync(path.join(outputDir, `${style}-modal.png`), modalImage.toPNG())
      for (const routePath of ['/board', '/records', '/resumes', '/analysis']) {
        await win.loadURL(`${target}${routePath}`)
        await wait(500)
        const routeAudit = await win.webContents.executeJavaScript(`
          ({
            mounted: Boolean(document.querySelector('.main')),
            horizontalOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) > innerWidth + 2,
            titlebarVisible: getComputedStyle(document.querySelector('.desktop-titlebar')).display !== 'none',
          })
        `)
        if (!routeAudit.mounted || routeAudit.horizontalOverflow || !routeAudit.titlebarVisible) {
          throw new Error(`${style} ${routePath} audit failed: ${JSON.stringify(routeAudit)}`)
        }
      }
      console.log(`${style} route audit`, 'board, records, resumes, analysis passed')
    }
  }

  for (const style of ['aurora', 'anime']) {
    await win.loadURL(`${target}/?desktopWidget=records`)
    await win.webContents.executeJavaScript(`
      localStorage.setItem('rb_token', ${JSON.stringify(token)});
      localStorage.setItem('radar_style', ${JSON.stringify(style)});
      localStorage.setItem('radar_theme', 'light');
      true
    `)
    await win.reload()
    win.setSize(390, 520)
    await wait(1200)
    const widgetAudit = await win.webContents.executeJavaScript(`
      (() => {
        const widget = document.querySelector('.desktop-widget')
        const rows = document.querySelectorAll('.record-row').length
        return {
          visible: Boolean(widget),
          rows,
          overflowX: document.documentElement.scrollWidth > innerWidth + 2,
          overflowY: document.documentElement.scrollHeight > innerHeight + 2,
        }
      })()
    `)
    console.log(`${style} widget audit`, JSON.stringify(widgetAudit))
    if (!widgetAudit.visible || widgetAudit.overflowX || widgetAudit.overflowY) {
      throw new Error(`${style} widget audit failed: ${JSON.stringify(widgetAudit)}`)
    }
    fs.writeFileSync(path.join(outputDir, `${style}-widget.png`), (await win.capturePage()).toPNG())
  }

  for (const style of ['aurora', 'anime']) {
    await win.loadURL(target)
    await win.webContents.executeJavaScript(`
      localStorage.removeItem('rb_token');
      localStorage.setItem('radar_style', ${JSON.stringify(style)});
      true
    `)
    await win.reload()
    win.setSize(430, 590)
    await wait(800)
    const loginAudit = await win.webContents.executeJavaScript(`
      (() => {
        const login = document.querySelector('.desktop-login')
        return { visible: Boolean(login), overflowX: document.documentElement.scrollWidth > innerWidth + 2, overflowY: document.documentElement.scrollHeight > innerHeight + 2 }
      })()
    `)
    console.log(`${style} login audit`, JSON.stringify(loginAudit))
    if (!loginAudit.visible || loginAudit.overflowX || loginAudit.overflowY) {
      throw new Error(`${style} login audit failed: ${JSON.stringify(loginAudit)}`)
    }
    fs.writeFileSync(path.join(outputDir, `${style}-login.png`), (await win.capturePage()).toPNG())
  }
  win.destroy()
  app.quit()
}).catch(error => {
  console.error(error)
  app.exit(1)
})
