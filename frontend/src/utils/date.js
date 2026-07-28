const CHINA_OFFSET_MS = 8 * 3600000

/**
 * Format a UTC+8 midnight millisecond timestamp as "MM-DD".
 * Returns "—" when ts is falsy or NaN.
 */
export function fmtDateChina(ts) {
  if (!ts) return '—'
  const d = new Date(ts + CHINA_OFFSET_MS)
  if (isNaN(d)) return '—'
  return String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0')
}

/**
 * Format a UTC+8 midnight millisecond timestamp as "YYYY-MM-DD".
 * Returns empty string when ts is falsy or NaN.
 */
export function fmtDateFullChina(ts) {
  if (!ts) return ''
  const d = new Date(ts + CHINA_OFFSET_MS)
  if (isNaN(d)) return ''
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0')
}

/**
 * Convert a UTC+8 midnight millisecond timestamp to a "YYYY-MM-DD" string
 * suitable for `<input type="date">` value binding.
 * Returns empty string when ts is falsy or NaN.
 */
export function inputDateChina(ts) {
  if (!ts) return ''
  const d = new Date(ts + CHINA_OFFSET_MS)
  if (isNaN(d)) return ''
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0')
}

/**
 * Convert a UTC+8 midnight millisecond timestamp to a Date object
 * at midnight (local timezone) for calendar grouping.
 * Returns null when ts is falsy or NaN.
 */
export function calendarDateChina(ts) {
  if (!ts) return null
  const d = new Date(ts + CHINA_OFFSET_MS)
  if (isNaN(d)) return null
  return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
}

/**
 * Board dwell time calculation using UTC+8 timestamp.
 * Returns { text, days }.
 */
export function boardDwellChina(ts) {
  if (!ts) return { text: '—', days: -1 }
  // Use midnight-equivalent UTC date from the CST timestamp
  const d = new Date(ts + CHINA_OFFSET_MS)
  if (isNaN(d)) return { text: '—', days: -1 }
  const enteredDay = new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const DAY_MS = 86400000
  const days = Math.floor((today - enteredDay) / DAY_MS)
  if (days < 0) return { text: '0 天', days: 0 }
  return { text: days < 30 ? days + ' 天' : Math.floor(days / 30) + ' 个月', days }
}
