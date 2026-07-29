const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  /** 前端判断当前是否在 Electron 桌面环境 */
  isElectron: true,

  /** 发送系统原生通知 */
  notify(title, body) {
    const { Notification } = require('electron')
    if (Notification.isSupported()) {
      const n = new Notification({ title, body, icon: 'assets/icon.png' })
      n.show()
    }
  },

  /** 获取应用版本号 */
  getAppVersion() {
    return process.env.npm_package_version || '1.0.0'
  },

  /** 在系统浏览器中打开链接 */
  openExternal(url) {
    const { shell } = require('electron')
    shell.openExternal(url)
  },

  /** 获取当前平台 */
  platform: process.platform,
})
