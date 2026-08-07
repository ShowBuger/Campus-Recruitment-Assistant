const DB_NAME = 'campus-skin-resources'
const DB_VERSION = 1
const STORE_NAME = 'resources'
const SHUIMO_KEY = 'shuimo-font-20260802-3'
const SHUIMO_MARKER = `skin_resource_${SHUIMO_KEY}`
const SHUIMO_URL = '/static/themes/shuimo/fonts/zihun-longyin-shoushu.ttf?v=20260802-3'
const ANIME_KEY = 'anime-font-20260802-2'
const ANIME_MARKER = `skin_resource_${ANIME_KEY}`
const ANIME_URL = '/static/themes/anime/fonts/zihun-buding.ttf?v=20260802-2'
const CYBER_KEY = 'cyber-font-20260802-1'
const CYBER_MARKER = `skin_resource_${CYBER_KEY}`
const CYBER_URL = '/static/themes/cyber/fonts/zihun-bionic.ttf?v=20260802-1'
const AURORA_KEY = 'aurora-bundle-20260802-2'
const AURORA_MARKER = `skin_resource_${AURORA_KEY}`
const AURORA_FONT_KEY = `${AURORA_KEY}-font`
const AURORA_VIDEO_KEY = 'aurora-bundle-20260802-1-video'
const AURORA_FONT_URL = '/static/themes/aurora/fonts/zihun-haima.ttf?v=20260802-2'
const AURORA_VIDEO_URL = '/static/themes/aurora/city-night.mp4?v=20260802-1'
const AURORA_FONT_BYTES = 1784504
const AURORA_VIDEO_BYTES = 44482101
const LEGACY_AURORA_MARKER = 'skin_resource_aurora-bundle-20260802-1'
const LEGACY_AURORA_FONT_KEY = 'aurora-bundle-20260802-1-font'
const LEGACY_ANIME_KEY = 'anime-font-20260802-1'
const LEGACY_ANIME_MARKER = `skin_resource_${LEGACY_ANIME_KEY}`
const LEGACY_SHUIMO_KEY = 'shuimo-font-20260802-1'
const LEGACY_SHUIMO_MARKER = `skin_resource_${LEGACY_SHUIMO_KEY}`

const resources = {
  shuimo: { key: SHUIMO_KEY, marker: SHUIMO_MARKER, url: SHUIMO_URL, family: 'Zihun Longyin Shoushu' },
  anime: { key: ANIME_KEY, marker: ANIME_MARKER, url: ANIME_URL, family: 'Zihun Buding' },
  cyber: { key: CYBER_KEY, marker: CYBER_MARKER, url: CYBER_URL, family: 'Zihun Bionic' },
  auroraFont: { key: AURORA_FONT_KEY, marker: AURORA_MARKER, url: AURORA_FONT_URL, family: 'Zihun Haima' },
}
const installedFonts = new Map()
const installedFontUrls = new Map()
let auroraVideoUrl = ''

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('无法打开本地资源库'))
  })
}

async function readResource(key) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readonly')
    const request = transaction.objectStore(STORE_NAME).get(key)
    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error || new Error('读取本地资源失败'))
    transaction.oncomplete = () => db.close()
  })
}

async function writeResource(key, value) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).put(value, key)
    transaction.oncomplete = () => { db.close(); resolve() }
    transaction.onerror = () => { db.close(); reject(transaction.error || new Error('保存本地资源失败')) }
  })
}

async function deleteResource(key) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).delete(key)
    transaction.oncomplete = () => { db.close(); resolve() }
    transaction.onerror = () => { db.close(); reject(transaction.error || new Error('清理旧资源失败')) }
  })
}

async function clearLegacyAnimeResource() {
  try { localStorage.removeItem(LEGACY_ANIME_MARKER) } catch (_) {}
  try { await deleteResource(LEGACY_ANIME_KEY) } catch (_) {}
}

async function clearLegacyShuimoResource() {
  try { localStorage.removeItem(LEGACY_SHUIMO_MARKER) } catch (_) {}
  try { await deleteResource(LEGACY_SHUIMO_KEY) } catch (_) {}
}

async function clearLegacyAuroraFontResource() {
  try { localStorage.removeItem(LEGACY_AURORA_MARKER) } catch (_) {}
  try { await deleteResource(LEGACY_AURORA_FONT_KEY) } catch (_) {}
}

async function installFont(resource, blob) {
  if (installedFonts.has(resource.key)) return true
  const fontUrl = URL.createObjectURL(blob)
  try {
    const font = new FontFace(resource.family, `url(${fontUrl}) format('truetype')`, { style: 'normal', weight: '400' })
    await font.load()
    document.fonts.add(font)
    installedFonts.set(resource.key, font)
    installedFontUrls.set(resource.key, fontUrl)
    return true
  } catch (error) {
    URL.revokeObjectURL(fontUrl)
    throw error
  }
}

function hasResourceMarker(resource) {
  try { return localStorage.getItem(resource.marker) === '1' } catch (_) { return false }
}

async function restoreResource(resource) {
  if (installedFonts.has(resource.key)) return true
  if (!hasResourceMarker(resource)) return false
  try {
    const blob = await readResource(resource.key)
    if (!(blob instanceof Blob) || !blob.size) throw new Error('本地字体资源不存在')
    await installFont(resource, blob)
    return true
  } catch (_) {
    try { localStorage.removeItem(resource.marker) } catch (_) {}
    return false
  }
}

async function downloadResource(resource, onProgress) {
  const response = await fetch(resource.url, { cache: 'no-store' })
  if (!response.ok || !response.body) throw new Error(`资源下载失败（HTTP ${response.status}）`)
  const total = Number(response.headers.get('content-length')) || 0
  const reader = response.body.getReader()
  const chunks = []
  let received = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    received += value.byteLength
    onProgress?.({ received, total, percent: total ? received / total * 100 : 0 })
  }
  const blob = new Blob(chunks, { type: 'font/ttf' })
  await installFont(resource, blob)
  await writeResource(resource.key, blob)
  try { localStorage.setItem(resource.marker, '1') } catch (_) {}
  onProgress?.({ received, total: total || received, percent: 100 })
  return { received, total: total || received }
}

async function fetchBlob(url, type, onProgress) {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok || !response.body) throw new Error(`资源下载失败（HTTP ${response.status}）`)
  const reader = response.body.getReader()
  const chunks = []
  let received = 0
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    received += value.byteLength
    onProgress?.(received)
  }
  return new Blob(chunks, { type })
}

function installAuroraVideo(blob) {
  if (auroraVideoUrl) URL.revokeObjectURL(auroraVideoUrl)
  auroraVideoUrl = URL.createObjectURL(blob)
  window.dispatchEvent(new CustomEvent('aurora-resource-ready', { detail: { videoUrl: auroraVideoUrl } }))
}

export async function restoreAuroraResource() {
  if (!hasResourceMarker({ marker: AURORA_MARKER })) return false
  try {
    const [fontBlob, videoBlob] = await Promise.all([readResource(AURORA_FONT_KEY), readResource(AURORA_VIDEO_KEY)])
    if (!(fontBlob instanceof Blob) || !fontBlob.size || !(videoBlob instanceof Blob) || !videoBlob.size) throw new Error('雨幕流光本地资源不完整')
    await installFont(resources.auroraFont, fontBlob)
    installAuroraVideo(videoBlob)
    await clearLegacyAuroraFontResource()
    return true
  } catch (_) {
    try { localStorage.removeItem(AURORA_MARKER) } catch (_) {}
    return false
  }
}

export async function downloadAuroraResource(onProgress) {
  let videoBlob = null
  try { videoBlob = await readResource(AURORA_VIDEO_KEY) } catch (_) {}
  const reuseVideo = videoBlob instanceof Blob && videoBlob.size > 0
  const downloadTotal = AURORA_FONT_BYTES + (reuseVideo ? 0 : AURORA_VIDEO_BYTES)
  let fontReceived = 0
  const fontBlob = await fetchBlob(AURORA_FONT_URL, 'font/ttf', received => {
    fontReceived = received
    onProgress?.({ received, total: downloadTotal, percent: received / downloadTotal * 100 })
  })
  if (!reuseVideo) {
    videoBlob = await fetchBlob(AURORA_VIDEO_URL, 'video/mp4', received => {
      const combined = fontReceived + received
      onProgress?.({ received: combined, total: downloadTotal, percent: combined / downloadTotal * 100 })
    })
  }
  await installFont(resources.auroraFont, fontBlob)
  installAuroraVideo(videoBlob)
  await writeResource(AURORA_FONT_KEY, fontBlob)
  if (!reuseVideo) await writeResource(AURORA_VIDEO_KEY, videoBlob)
  try { await navigator.storage?.persist?.() } catch (_) {}
  try { localStorage.setItem(AURORA_MARKER, '1') } catch (_) {}
  await clearLegacyAuroraFontResource()
  onProgress?.({ received: downloadTotal, total: downloadTotal, percent: 100 })
  return { received: downloadTotal, total: downloadTotal }
}

export function hasAuroraResourceMarker() { return hasResourceMarker({ marker: AURORA_MARKER }) }
export function getAuroraVideoUrl() { return auroraVideoUrl }

export function hasShuimoResourceMarker() { return hasResourceMarker(resources.shuimo) }
export function hasAnimeResourceMarker() { return hasResourceMarker(resources.anime) }
export function hasCyberResourceMarker() { return hasResourceMarker(resources.cyber) }
export async function restoreShuimoResource() {
  await clearLegacyShuimoResource()
  return restoreResource(resources.shuimo)
}
export function restoreCyberResource() { return restoreResource(resources.cyber) }
export async function restoreAnimeResource() {
  await clearLegacyAnimeResource()
  return restoreResource(resources.anime)
}
export async function downloadShuimoResource(onProgress) {
  const result = await downloadResource(resources.shuimo, onProgress)
  await clearLegacyShuimoResource()
  return result
}
export function downloadCyberResource(onProgress) { return downloadResource(resources.cyber, onProgress) }
export async function downloadAnimeResource(onProgress) {
  const result = await downloadResource(resources.anime, onProgress)
  await clearLegacyAnimeResource()
  return result
}
