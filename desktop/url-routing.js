'use strict'

function parseHttpUrl(rawUrl) {
  try {
    const parsed = new URL(String(rawUrl || '').trim())
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
    return parsed
  } catch {
    return null
  }
}

function normalizeHttpUrl(rawUrl) {
  const value = String(rawUrl || '').trim()
  if (!value) return null
  const absolute = parseHttpUrl(value.startsWith('//') ? `https:${value}` : value)
  if (absolute) return absolute.toString()
  if (/^[./?#]/.test(value) || /\s/.test(value)) return null
  try {
    const parsed = new URL(`https://${value}`)
    if (!parsed.hostname.includes('.') || parsed.username || parsed.password) return null
    return parsed.toString()
  } catch {
    return null
  }
}

function isAppUrl(rawUrl, appOrigin) {
  const parsed = parseHttpUrl(rawUrl)
  return Boolean(parsed && parsed.origin === appOrigin)
}

function externalUrlFromNavigation(rawUrl, appOrigin) {
  const parsed = parseHttpUrl(rawUrl)
  if (!parsed) return null
  if (parsed.origin !== appOrigin) return parsed.toString()

  // A bare job domain in href (for example jobs.example.com/campus) is
  // resolved by Chromium as /jobs.example.com/campus on the app origin.
  // Recover it before Electron creates a second application window.
  const candidate = parsed.pathname.replace(/^\/+/, '') + parsed.search + parsed.hash
  return normalizeHttpUrl(candidate)
}

module.exports = { externalUrlFromNavigation, isAppUrl, normalizeHttpUrl }
