const BASE = ''
let _token = localStorage.getItem('rb_token') || ''

export function setToken(t) { _token = t; t ? localStorage.setItem('rb_token', t) : localStorage.removeItem('rb_token') }
export function getToken() { return _token }

export async function api(method, path, body, opts = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const timeout = opts.timeout || 30_000  // 默认 30s 超时，防止无限等待
  const maxRetries = opts.retries ?? 1    // 默认 1 次重试

  let lastError
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(`${BASE}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(timeout)
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        if (res.status === 401) {
          if (String(data.detail || '').includes('登录已过期')) {
            setToken('')
            throw new Error('登录已过期')
          }
        }
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      if (opts.raw) return res
      return res.json()
    } catch (e) {
      lastError = e
      // 不重试的情况：登录过期、HTTP 错误（4xx/5xx，非网络错误）
      if (e.message === '登录已过期' || /^HTTP \d{3}$/.test(e.message)) throw e
      // AbortError（超时）和网络错误 → 重试
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 500 * (attempt + 1)))  // 递增退避
        continue
      }
    }
  }
  throw lastError
}

// Convenience wrappers
export const get = (path, opts) => api('GET', path, null, opts)
export const post = (path, body, opts) => api('POST', path, body, opts)
export const del = (path, opts) => api('DELETE', path, null, opts)
