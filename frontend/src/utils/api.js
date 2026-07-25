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
    if (res.status === 401) { setToken(''); throw new Error('登录已过期') }
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  if (opts.raw) return res
  return res.json()
}

// Convenience wrappers
export const get = (path, opts) => api('GET', path, null, opts)
export const post = (path, body, opts) => api('POST', path, body, opts)
export const del = (path, opts) => api('DELETE', path, null, opts)
