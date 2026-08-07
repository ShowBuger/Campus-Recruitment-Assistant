const DESKTOP_APP_ID = 'campus-recruitment-assistant'

export function isDesktopRuntime() {
  const bridge = window.electronAPI
  return bridge?.appId === DESKTOP_APP_ID && bridge?.isElectron === true
}

export function hasDesktopTitlebar() {
  return isDesktopRuntime() && window.electronAPI?.customTitlebar === true
}
