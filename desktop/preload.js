const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', Object.freeze({
  isElectron: true,
  customTitlebar: true,
  platform: process.platform,
  getAppVersion: () => ipcRenderer.invoke('desktop:get-version'),
  checkForUpdates: () => ipcRenderer.invoke('desktop:check-for-updates'),
  showWidget: type => ipcRenderer.invoke('desktop:widget-show', type),
  getWidgetState: type => ipcRenderer.invoke('desktop:widget-state', type),
  widgetAction: (type, action) => ipcRenderer.invoke('desktop:widget-action', type, action),
  showMainWindow: () => ipcRenderer.invoke('desktop:show-main'),
  windowControl: action => ipcRenderer.invoke('desktop:window-control', action),
  onWindowState: callback => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, state) => callback(state)
    ipcRenderer.on('desktop-window-state', listener)
    return () => ipcRenderer.removeListener('desktop-window-state', listener)
  },
  openExternal: url => ipcRenderer.invoke('desktop:open-external', url),
  notify: (title, body) => ipcRenderer.send('desktop:notify', title, body),
  onUpdateStatus: callback => {
    if (typeof callback !== 'function') return () => {}
    const listener = (_event, status) => callback(status)
    ipcRenderer.on('desktop-update-status', listener)
    return () => ipcRenderer.removeListener('desktop-update-status', listener)
  },
}))
