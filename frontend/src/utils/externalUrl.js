/** Normalize user/imported recruitment links without allowing relative app URLs. */
export function externalHttpUrl(value) {
  let raw = String(value || '').trim()
  if (!raw) return ''
  if (raw.startsWith('//')) raw = 'https:' + raw
  if (!/^[a-z][a-z0-9+.-]*:/i.test(raw)) {
    const looksLikeHost = /^(?:[\w-]+\.)+[a-z]{2,}(?::\d+)?(?:[/?#]|$)/i.test(raw)
      || /^\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:[/?#]|$)/.test(raw)
    if (!looksLikeHost) return ''
    raw = 'https://' + raw
  }
  try {
    const url = new URL(raw)
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) return ''
    return url.href
  } catch (_) {
    return ''
  }
}
