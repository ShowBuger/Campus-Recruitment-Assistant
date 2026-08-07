const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')

const styles = (process.env.CAMPUS_VISUAL_STYLES || 'pixelium,aurora,anime,journal,shuimo,cyber').split(',')
const token = process.env.CAMPUS_VISUAL_TOKEN
const target = process.env.CAMPUS_VISUAL_URL || 'http://127.0.0.1:8765'
const outputDir = process.env.CAMPUS_VISUAL_OUTPUT || '/tmp/campus-skin-smoke'
const theme = process.env.CAMPUS_VISUAL_THEME === 'dark' ? 'dark' : 'light'
const webMode = process.env.CAMPUS_VISUAL_WEB === '1'
const resourceOnly = process.env.CAMPUS_VISUAL_RESOURCE_ONLY === '1'
const trailOnly = process.env.CAMPUS_VISUAL_TRAIL_ONLY === '1'
const collapsibleStyles = webMode ? ['classic', 'pixelium', 'aurora', 'anime', 'journal', 'shuimo', 'cyber'] : ['classic', 'pixelium', 'anime', 'journal', 'cyber']
const resourceStyles = {
  aurora: { selector: '.aurora-style-item', family: 'Zihun Haima', sample: '雨幕流光' },
  anime: { selector: '.anime-style-item', family: 'Zihun Buding', sample: '投递信息' },
  shuimo: { selector: '.shuimo-style-item', family: 'Zixiaohun Danqing Xingshu', sample: '云水墨境' },
  cyber: { selector: '.cyber-style-item', family: 'Zihun Bionic', sample: '投递信息' },
}

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
    show: true,
    frame: false,
    webPreferences: {
      ...(webMode ? {} : { preload: path.join(__dirname, 'preload.js') }),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
    },
  })
  await win.webContents.session.clearCache()
  await win.loadURL(target)
  await win.webContents.executeJavaScript(`localStorage.setItem('rb_token', ${JSON.stringify(token)}); true`)
  for (const style of styles) {
    await win.webContents.executeJavaScript(`
      localStorage.setItem('radar_style', ${JSON.stringify(style)});
      localStorage.setItem('radar_theme', ${JSON.stringify(theme)});
      localStorage.setItem('radar_sidebar_collapsed', '0');
      true
    `)
    await win.loadURL(target)
    await wait(1800)
    const resource = resourceStyles[style]
    if (resource && !webMode) {
      await win.webContents.executeJavaScript(`document.querySelector('#style-btn')?.click()`)
      await wait(150)
      const resourceState = await win.webContents.executeJavaScript(`(() => {
        const button = document.querySelector(${JSON.stringify(resource.selector + ' .style-download-btn')})
        const panel = document.querySelector('#style-panel')
        const rect = panel.getBoundingClientRect()
        const hit = document.elementFromPoint(rect.left + Math.min(24, rect.width / 2), rect.top + Math.min(90, rect.height / 2))
        return {
          buttonVisible: Boolean(button) && getComputedStyle(button).display !== 'none',
          panelVisible: getComputedStyle(panel).display !== 'none',
          panelZ: getComputedStyle(panel).zIndex,
          ownsHitPoint: Boolean(hit?.closest('#style-panel')),
          panelBounds: { top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left },
          style: document.documentElement.dataset.style,
        }
      })()`)
      if (!resourceState.panelVisible || !resourceState.ownsHitPoint || Number(resourceState.panelZ) < 30000) throw new Error(`${style} resource panel did not reach the top layer: ${JSON.stringify(resourceState)}`)
      if (resourceState.buttonVisible) {
        fs.writeFileSync(path.join(outputDir, `${style}-resource-locked.png`), (await win.capturePage()).toPNG())
        if (style === 'aurora') {
          await win.webContents.executeJavaScript(`document.querySelector(${JSON.stringify(resource.selector + ' .style-download-btn')})?.click()`)
        } else {
          await win.webContents.executeJavaScript(`document.querySelector('.style-font-option input')?.click()`)
          await wait(120)
          await win.webContents.executeJavaScript(`document.querySelector(${JSON.stringify(resource.selector)})?.click()`)
          await wait(180)
          const defaultFontAudit = await win.webContents.executeJavaScript(`({
            style: document.documentElement.dataset.style,
            fontMode: document.documentElement.dataset.styleFont,
            bodyFont: getComputedStyle(document.body).fontFamily,
            downloadButtonVisible: Boolean(document.querySelector(${JSON.stringify(resource.selector + ' .style-download-btn')}))
          })`)
          if (defaultFontAudit.style !== style || defaultFontAudit.fontMode !== 'default' || defaultFontAudit.bodyFont.includes(resource.family) || defaultFontAudit.downloadButtonVisible) {
            throw new Error(`${style} default font bypass audit failed: ${JSON.stringify(defaultFontAudit)}`)
          }
          console.log(`${style} default font bypass audit`, JSON.stringify(defaultFontAudit))
          await win.loadURL(target)
          await wait(700)
          const defaultFontRestored = await win.webContents.executeJavaScript(`({
            style: document.documentElement.dataset.style,
            fontMode: document.documentElement.dataset.styleFont,
            bodyFont: getComputedStyle(document.body).fontFamily
          })`)
          if (defaultFontRestored.style !== style || defaultFontRestored.fontMode !== 'default' || defaultFontRestored.bodyFont.includes(resource.family)) {
            throw new Error(`${style} default font persistence audit failed: ${JSON.stringify(defaultFontRestored)}`)
          }
          console.log(`${style} default font persistence audit`, JSON.stringify(defaultFontRestored))
          await win.webContents.executeJavaScript(`document.querySelector('#style-btn')?.click()`)
          await wait(120)
          await win.webContents.executeJavaScript(`document.querySelector('.style-font-option input')?.click()`)
        }
        for (let attempt = 0; attempt < 120; attempt += 1) {
          await wait(250)
          const ready = await win.webContents.executeJavaScript(`document.documentElement.dataset.style === ${JSON.stringify(style)} && document.documentElement.dataset.styleFont === 'themed'`)
          if (ready) break
          if (attempt === 119) throw new Error(`${style} resource download did not unlock the style`)
        }
      }
      await win.loadURL(target)
      await wait(900)
      const restored = await win.webContents.executeJavaScript(`({
        style: document.documentElement.dataset.style,
        downloadButtonVisible: Boolean(document.querySelector(${JSON.stringify(resource.selector + ' .style-download-btn')})),
        fontLoaded: document.fonts.check(${JSON.stringify(`32px "${resource.family}"`)}, ${JSON.stringify(resource.sample)}),
        bodyFont: getComputedStyle(document.body).fontFamily,
        tableFont: getComputedStyle(document.querySelector('table') || document.body).fontFamily
      })`)
      if (restored.style !== style || restored.downloadButtonVisible || !restored.fontLoaded || !restored.bodyFont.includes(resource.family) || !restored.tableFont.includes(resource.family)) {
        throw new Error(`${style} persisted resource audit failed: ${JSON.stringify(restored)}`)
      }
      console.log(`${style} persisted resource audit`, JSON.stringify(restored))
      console.log(`${style} resource audit`, JSON.stringify(resourceState))
      if (!resourceState.buttonVisible) await win.webContents.executeJavaScript(`document.querySelector('#style-btn')?.click()`)
      if (resourceOnly) {
        fs.writeFileSync(path.join(outputDir, `${style}-resource.png`), (await win.capturePage()).toPNG())
        win.destroy()
        app.quit()
        return
      }
    }
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
        const appElement = document.querySelector('.app')
        const appStyle = getComputedStyle(appElement)
        const main = document.querySelector('.main')
        return {
          horizontalOverflow,
          badBounds,
          sidebarVisible: visible('.sidebar'),
          visibleNavItems: Array.from(document.querySelectorAll('.sidebar a')).filter(element => {
            const rect = element.getBoundingClientRect()
            return getComputedStyle(element).display !== 'none' && rect.width > 0 && rect.height > 0
          }).length,
          dockVisible: visible('.liquid-dock'),
          collapseButtonVisible: visible('.sidebar-collapse'),
          inkStageVisible: visible('.ink-stage'),
          inkTrailVisible: visible('.ink-cursor-trail'),
          assistantPresent: Boolean(assistant),
          appBackground: appStyle.backgroundColor,
          appBorderWidths: [appStyle.borderTopWidth, appStyle.borderRightWidth, appStyle.borderBottomWidth, appStyle.borderLeftWidth],
          appBoxShadow: appStyle.boxShadow,
          mainBackground: getComputedStyle(main).backgroundColor,
          mainHorizontalOverflow: main.scrollWidth > main.clientWidth + 2,
          mainScrollWidth: main.scrollWidth,
          mainScrollHeight: main.scrollHeight,
          desktopBackdropAnimation: getComputedStyle(document.querySelector('.cyber-desktop-backdrop i')).animationName,
          desktopBackdropPlayState: getComputedStyle(document.querySelector('.cyber-desktop-backdrop i')).animationPlayState,
          desktopBackdropTransform: getComputedStyle(document.querySelector('.cyber-desktop-backdrop i')).transform,
          reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
          rootClip: getComputedStyle(document.documentElement).clipPath,
          activePage: (() => { const el = document.querySelector('.page.active'); if (!el) return null; const style = getComputedStyle(el); return { opacity: style.opacity, clipPath: style.clipPath, animation: style.animationName, state: style.animationPlayState } })(),
          inkSignature: (() => { const el = document.querySelector('.ink-signature'); if (!el) return null; const rect = el.getBoundingClientRect(); return { display: getComputedStyle(el).display, opacity: getComputedStyle(el).opacity, width: rect.width, height: rect.height } })(),
          contentCards: Array.from(document.querySelectorAll('.page.active .card,.page.active .kpi,.page.active .metric')).map(el => { const rect = el.getBoundingClientRect(); const hit = document.elementFromPoint(Math.max(0, Math.min(innerWidth - 1, rect.left + rect.width / 2)), Math.max(0, Math.min(innerHeight - 1, rect.top + Math.min(rect.height, 20) / 2))); return { opacity: getComputedStyle(el).opacity, visibility: getComputedStyle(el).visibility, top: rect.top, left: rect.left, width: rect.width, height: rect.height, hit: hit?.className || hit?.tagName } }),
        }
      })()
    `)
    const expected = webMode
      ? audit.sidebarVisible && !audit.dockVisible
      : style === 'aurora' || style === 'shuimo'
      ? !audit.sidebarVisible && audit.dockVisible
      : style === 'anime'
        ? audit.sidebarVisible && !audit.assistantPresent
        : audit.sidebarVisible
    if (audit.horizontalOverflow || audit.badBounds || audit.rootClip !== 'none' || !expected || (audit.sidebarVisible && !audit.visibleNavItems)) {
      throw new Error(`${style} visual audit failed: ${JSON.stringify(audit)}`)
    }
    if (style === 'cyber' && !webMode && ([audit.appBackground, audit.mainBackground].some(color => color === 'rgba(0, 0, 0, 0)' || color === 'transparent') || audit.mainHorizontalOverflow)) {
      throw new Error(`${style} desktop surface remained transparent: ${JSON.stringify(audit)}`)
    }
    if (style === 'aurora' && !webMode && (audit.appBorderWidths.some(width => width !== '0px') || audit.appBoxShadow !== 'none')) {
      throw new Error(`${style} desktop window outline remained: ${JSON.stringify(audit)}`)
    }
    if ((style === 'cyber' || style === 'aurora') && !webMode) {
      await win.webContents.executeJavaScript(`document.querySelector('.desktop-widget-launcher > .icon-btn')?.click()`)
      await wait(120)
      const widgetPanelAudit = await win.webContents.executeJavaScript(`(() => {
        const panel = document.querySelector('.desktop-widget-launcher .widget-launch-panel')
        const topbar = document.querySelector('.topbar')
        const item = panel?.querySelector('.widget-launch-item')
        const small = item?.querySelector('small')
        const rect = panel?.getBoundingClientRect()
        const hit = rect && document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
        return {
          visible: Boolean(panel) && getComputedStyle(panel).display !== 'none',
          ownsCenterPoint: Boolean(hit?.closest('.widget-launch-panel')),
          hitClass: hit?.className || hit?.tagName,
          topbarZ: topbar ? getComputedStyle(topbar).zIndex : null,
          itemBackground: item ? getComputedStyle(item).backgroundColor : null,
          itemColor: item ? getComputedStyle(item).color : null,
          smallColor: small ? getComputedStyle(small).color : null,
          bounds: rect ? { top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left } : null,
        }
      })()`)
      const cyberLayerFailed = style === 'cyber' && Number(widgetPanelAudit.topbarZ) < 90
      const auroraContrastFailed = style === 'aurora' && (widgetPanelAudit.itemBackground === 'rgb(255, 255, 255)' || widgetPanelAudit.itemColor !== 'rgb(242, 244, 255)' || widgetPanelAudit.smallColor !== 'rgb(195, 201, 232)')
      if (!widgetPanelAudit.visible || !widgetPanelAudit.ownsCenterPoint || cyberLayerFailed || auroraContrastFailed) {
        throw new Error(`${style} desktop widget panel audit failed: ${JSON.stringify(widgetPanelAudit)}`)
      }
      console.log(`${style} desktop widget panel audit`, JSON.stringify(widgetPanelAudit))
      await win.webContents.executeJavaScript(`document.querySelector('.desktop-widget-launcher > .icon-btn')?.click()`)
    }
    if (style === 'cyber' && !webMode && !audit.reducedMotion) {
      const mainBounds = await win.webContents.executeJavaScript(`(() => {
        const rect = document.querySelector('.main').getBoundingClientRect()
        return { right: rect.right, top: rect.top, bottom: rect.bottom }
      })()`)
      const motionRect = {
        x: Math.max(0, Math.floor(mainBounds.right - 24)),
        y: Math.max(0, Math.floor(mainBounds.top + 100)),
        width: 10,
        height: Math.max(20, Math.floor(Math.min(480, mainBounds.bottom - mainBounds.top - 130))),
      }
      const frameBefore = (await win.capturePage(motionRect)).toBitmap()
      await wait(800)
      const frameAfter = (await win.capturePage(motionRect)).toBitmap()
      let changedPixels = 0
      for (let index = 0; index < Math.min(frameBefore.length, frameAfter.length); index += 4) {
        const delta = Math.abs(frameBefore[index] - frameAfter[index]) + Math.abs(frameBefore[index + 1] - frameAfter[index + 1]) + Math.abs(frameBefore[index + 2] - frameAfter[index + 2])
        if (delta > 3) changedPixels += 1
      }
      const motion = await win.webContents.executeJavaScript(`({
        backdropTransform: getComputedStyle(document.querySelector('.cyber-desktop-backdrop i')).transform,
        scrollWidth: document.querySelector('.main').scrollWidth,
        scrollHeight: document.querySelector('.main').scrollHeight
      })`)
      if (audit.desktopBackdropAnimation !== 'bgDrift' || audit.desktopBackdropPlayState !== 'running' || motion.backdropTransform === audit.desktopBackdropTransform || motion.scrollWidth !== audit.mainScrollWidth || motion.scrollHeight !== audit.mainScrollHeight || changedPixels < 5) {
        throw new Error(`${style} desktop background animation did not advance: ${JSON.stringify({ ...audit, ...motion, changedPixels })}`)
      }
      console.log(`${style} desktop background pixel audit`, JSON.stringify({ changedPixels, motionRect }))
    }
    if (style !== 'shuimo' && (audit.inkStageVisible || audit.inkTrailVisible || (audit.inkSignature && audit.inkSignature.display !== 'none'))) {
      throw new Error(`${style} leaked shuimo layer: ${JSON.stringify(audit)}`)
    }
    if (audit.collapseButtonVisible !== collapsibleStyles.includes(style)) {
      throw new Error(`${style} collapse button availability failed: ${JSON.stringify(audit)}`)
    }
    if (collapsibleStyles.includes(style)) {
      await win.webContents.executeJavaScript(`document.querySelector('.sidebar-collapse')?.click()`)
      await wait(320)
      const sidebarAudit = await win.webContents.executeJavaScript(`
        (() => {
          const sidebar = document.querySelector('.sidebar')
          const button = document.querySelector('.sidebar-collapse')
          const links = Array.from(sidebar.querySelectorAll('a'))
          const logout = sidebar.querySelector('.sidebar-logout')
          const avatar = sidebar.querySelector('.sidebar-profile-avatar')
          const sidebarRect = sidebar.getBoundingClientRect()
          const avatarRect = avatar.getBoundingClientRect()
          const sidebarAfter = getComputedStyle(sidebar, '::after')
          const stripeBottom = sidebarRect.bottom - Number.parseFloat(sidebarAfter.bottom || '0')
          const stripeTop = stripeBottom - Number.parseFloat(sidebarAfter.height || '0')
          return {
            collapsed: document.documentElement.classList.contains('sidebar-collapsed'),
            stored: localStorage.getItem('radar_sidebar_collapsed'),
            buttonVisible: getComputedStyle(button).display !== 'none',
            width: sidebar.getBoundingClientRect().width,
            grid: getComputedStyle(document.querySelector('.app')).gridTemplateColumns,
            appClass: document.querySelector('.app').className,
            appStyle: document.querySelector('.app').getAttribute('style'),
            links: links.length,
            icons: links.filter(link => link.querySelector('.sidebar-nav-icon')?.getBoundingClientRect().width >= 18).length,
            labelsHidden: links.every(link => getComputedStyle(link.querySelector('.sidebar-nav-label')).display === 'none'),
            logoutVisible: getComputedStyle(logout).display !== 'none' && logout.getBoundingClientRect().width > 20,
            cyberStripeOverlap: document.documentElement.dataset.style === 'cyber' && stripeTop < avatarRect.bottom && stripeBottom > avatarRect.top,
            overflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) > innerWidth + 2,
          }
        })()
      `)
      const maxCollapsedWidth = style === 'journal' ? 86 : 82
      if (!sidebarAudit.collapsed || sidebarAudit.stored !== '1' || !sidebarAudit.buttonVisible || sidebarAudit.width > maxCollapsedWidth || sidebarAudit.icons !== sidebarAudit.links || !sidebarAudit.labelsHidden || !sidebarAudit.logoutVisible || sidebarAudit.cyberStripeOverlap || sidebarAudit.overflow) {
        throw new Error(`${style} collapsed sidebar audit failed: ${JSON.stringify(sidebarAudit)}`)
      }
      console.log(`${style} collapsed sidebar audit`, JSON.stringify(sidebarAudit))
      fs.writeFileSync(path.join(outputDir, `${style}-collapsed.png`), (await win.capturePage()).toPNG())
      await win.webContents.executeJavaScript(`document.querySelector('.sidebar-collapse')?.click()`)
      await wait(220)
    }
    if (webMode && style === 'aurora') {
      for (const [buttonSelector, panelSelector] of [['#style-btn', '#style-panel'], ['#notification-btn', '#notification-panel']]) {
        await win.webContents.executeJavaScript(`document.querySelector(${JSON.stringify(buttonSelector)})?.click()`)
        await wait(180)
        const popoverAudit = await win.webContents.executeJavaScript(`
          (() => {
            const panel = document.querySelector(${JSON.stringify(panelSelector)})
            const topbar = document.querySelector('.topbar')
            if (!panel) return { visible: false }
            const rect = panel.getBoundingClientRect()
            const hit = document.elementFromPoint(rect.left + Math.min(24, rect.width / 2), rect.top + Math.min(80, rect.height / 2))
            return {
              visible: getComputedStyle(panel).display !== 'none',
              ownsHitPoint: Boolean(hit?.closest(${JSON.stringify(panelSelector)})),
              panelZ: getComputedStyle(panel).zIndex,
              topbarZ: getComputedStyle(topbar).zIndex,
              right: rect.right,
              bottom: rect.bottom,
            }
          })()
        `)
        if (!popoverAudit.visible || !popoverAudit.ownsHitPoint || popoverAudit.right > win.getContentBounds().width + 2) throw new Error(`aurora web popover audit failed: ${JSON.stringify(popoverAudit)}`)
        console.log(`aurora web ${panelSelector} audit`, JSON.stringify(popoverAudit))
        await win.webContents.executeJavaScript(`document.querySelector(${JSON.stringify(buttonSelector)})?.click()`)
      }
    }
    if (style === 'shuimo' && !webMode) {
      if (!audit.inkSignature || audit.inkSignature.display === 'none' || audit.inkSignature.opacity === '0' || audit.inkSignature.height < 40 || audit.contentCards.some(card => card.opacity === '0' || card.visibility === 'hidden' || card.height < 1)) {
        throw new Error(`shuimo animation audit failed: ${JSON.stringify(audit)}`)
      }
      const radiusAudit = await win.webContents.executeJavaScript(`
        (() => {
          const root = document.documentElement
          const surface = document.querySelector('.app')
          const restored = getComputedStyle(surface).borderRadius
          root.classList.add('desktop-window-maximized')
          const maximized = getComputedStyle(surface).borderRadius
          const clip = getComputedStyle(surface).clipPath
          root.classList.remove('desktop-window-maximized')
          return { restored, maximized, clip }
        })()
      `)
      if (radiusAudit.restored === '0px' || radiusAudit.maximized !== '0px' || radiusAudit.clip !== 'none') {
        throw new Error(`shuimo window radius audit failed: ${JSON.stringify(radiusAudit)}`)
      }
      await win.webContents.executeJavaScript(`(() => {
        window.__campusInkTestMove = () => new Promise(resolve => {
          let step = 0
          const move = () => {
            window.dispatchEvent(new MouseEvent('mousemove', {
              clientX: 310 + step * 38,
              clientY: 245 + Math.round(Math.sin(step * .72) * 42),
              bubbles: true,
            }))
            step += 1
            if (step < 12) setTimeout(move, 12)
            else resolve()
          }
          move()
        })
        return window.__campusInkTestMove()
      })()`)
      await wait(16)
      fs.writeFileSync(path.join(outputDir, 'shuimo-trail-active.png'), (await win.capturePage()).toPNG())
      await win.webContents.executeJavaScript(`window.dispatchEvent(new MouseEvent('mouseleave')); window.__campusInkTestMove()`)
      await wait(24)
      const trailAudit = await win.webContents.executeJavaScript(`
        (() => {
          const canvas = document.querySelector('.ink-cursor-trail')
          if (!canvas) return { visible: false, painted: 0 }
          const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
          let painted = 0
          let minX = canvas.width
          let maxX = 0
          for (let index = 3; index < pixels.length; index += 4) {
            if (pixels[index] <= 0) continue
            painted += 1
            const x = ((index - 3) / 4) % canvas.width
            minX = Math.min(minX, x)
            maxX = Math.max(maxX, x)
          }
          return { visible: getComputedStyle(canvas).display !== 'none', painted, span: painted ? maxX - minX : 0, width: canvas.width, height: canvas.height, buffer: canvas.dataset.buffer, drops: canvas.dataset.drops, points: canvas.dataset.points, newestAge: canvas.dataset.newestAge, oldestAge: canvas.dataset.oldestAge, travelSpan: canvas.dataset.travelSpan, style: document.documentElement.dataset.style }
        })()
      `)
      if (!trailAudit.visible || trailAudit.painted < 1 || trailAudit.span > 480) throw new Error(`shuimo cursor trail audit failed: ${JSON.stringify(trailAudit)}`)
      await win.webContents.executeJavaScript(`window.dispatchEvent(new MouseEvent('mouseleave')); window.__campusInkTestMove()`)
      await wait(16)
      const fadingBaseline = await win.webContents.executeJavaScript(`(() => {
        const canvas = document.querySelector('.ink-cursor-trail')
        return Number(canvas.dataset.points || 0)
      })()`)
      await wait(480)
      const fadingTrailAudit = await win.webContents.executeJavaScript(`(() => {
        const canvas = document.querySelector('.ink-cursor-trail')
        return { points: Number(canvas.dataset.points || 0), drops: canvas.dataset.drops }
      })()`)
      if (fadingTrailAudit.points < 1 || fadingTrailAudit.points >= fadingBaseline) throw new Error(`shuimo cursor trail did not fade progressively: ${JSON.stringify({ fadingBaseline, fadingTrailAudit })}`)
      await wait(550)
      const clearedTrailAudit = await win.webContents.executeJavaScript(`(() => {
        const canvas = document.querySelector('.ink-cursor-trail')
        if (!canvas) return { painted: -1 }
        const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data
        let painted = 0
        for (let index = 3; index < pixels.length; index += 4) if (pixels[index] > 0) painted += 1
        return { painted, drops: canvas.dataset.drops }
      })()`)
      if (clearedTrailAudit.painted !== 0 || clearedTrailAudit.drops !== '0') throw new Error(`shuimo cursor trail did not clear: ${JSON.stringify(clearedTrailAudit)}`)
      console.log('shuimo window radius audit', JSON.stringify(radiusAudit))
      console.log('shuimo cursor trail audit', JSON.stringify(trailAudit))
      console.log('shuimo fading trail audit', JSON.stringify(fadingTrailAudit))
      console.log('shuimo cleared trail audit', JSON.stringify(clearedTrailAudit))
      if (trailOnly) {
        win.destroy()
        app.quit()
        return
      }
    }
    console.log(`${style} visual audit`, JSON.stringify(audit))
    const image = await win.capturePage()
    fs.writeFileSync(path.join(outputDir, `${style}.png`), image.toPNG())
    if (style === 'aurora' || style === 'anime' || style === 'journal' || style === 'shuimo' || style === 'cyber') {
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
      for (const routePath of ['/board', '/records', '/resumes', '/analysis', '/admin']) {
        await win.loadURL(`${target}${routePath}`)
        await wait(500)
        const routeAudit = await win.webContents.executeJavaScript(`
          ({
            mounted: Boolean(document.querySelector('.main')),
            horizontalOverflow: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) > innerWidth + 2,
            titlebarVisible: (() => { const element = document.querySelector('.desktop-titlebar'); return Boolean(element) && getComputedStyle(element).display !== 'none' })(),
          })
        `)
        if (!routeAudit.mounted || routeAudit.horizontalOverflow || (!webMode && !routeAudit.titlebarVisible)) {
          throw new Error(`${style} ${routePath} audit failed: ${JSON.stringify(routeAudit)}`)
        }
      }
      console.log(`${style} route audit`, 'board, records, resumes, analysis, admin passed')
    }
  }

  if (webMode) {
    win.destroy()
    app.quit()
    return
  }

  for (const style of ['classic', 'pixelium', 'aurora', 'anime', 'journal', 'shuimo', 'cyber']) {
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
          style: document.documentElement.dataset.style,
          fontFamily: getComputedStyle(widget).fontFamily,
          stateIcons: Array.from(document.querySelectorAll('.widget-actions .pixel-icon-btn svg')).map(icon => ({ fill: getComputedStyle(icon).fill, stroke: getComputedStyle(icon).stroke, width: icon.getBoundingClientRect().width })),
          overflowX: document.documentElement.scrollWidth > innerWidth + 2,
          overflowY: document.documentElement.scrollHeight > innerHeight + 2,
        }
      })()
    `)
    console.log(`${style} widget audit`, JSON.stringify(widgetAudit))
    if (!widgetAudit.visible || widgetAudit.overflowX || widgetAudit.overflowY || (style === 'aurora' && !widgetAudit.fontFamily.includes('Zihun Haima')) || (style === 'shuimo' && widgetAudit.style === 'shuimo' && !widgetAudit.fontFamily.includes('Zixiaohun Danqing Xingshu')) || widgetAudit.stateIcons.length !== 2 || widgetAudit.stateIcons.some(icon => icon.fill !== 'none' || icon.stroke === 'none' || icon.width < 15)) {
      throw new Error(`${style} widget audit failed: ${JSON.stringify(widgetAudit)}`)
    }
    fs.writeFileSync(path.join(outputDir, `${style}-widget.png`), (await win.capturePage()).toPNG())
  }

  for (const style of ['aurora', 'anime', 'journal', 'shuimo', 'cyber']) {
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
