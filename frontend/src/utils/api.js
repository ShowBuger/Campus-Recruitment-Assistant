const BASE = ''
let _token = localStorage.getItem('rb_token') || ''

export function setToken(t) { _token = t; t ? localStorage.setItem('rb_token', t) : localStorage.removeItem('rb_token') }
export function getToken() { return _token }

export async function api(method, path, body, opts = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (_token) headers['Authorization'] = `Bearer ${_token}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: opts.timeout ? AbortSignal.timeout(opts.timeout) : undefined
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    if (res.status === 401) {
      // 区分：auth/me 返回"登录已过期"，login 返回"用户名或密码错误"
      if (String(data.detail || '').includes('登录已过期')) {
        setToken('')
        throw new Error('登录已过期')
      }
    }
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  if (opts.raw) return res
  return res.json()
}

// Convenience wrappers
export const get = (path, opts) => api('GET', path, null, opts)
export const post = (path, body, opts) => api('POST', path, body, opts)
export const del = (path, opts) => api('DELETE', path, null, opts)
