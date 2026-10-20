// 统一 API 客户端：携带 token、错误格式归一化、401 自动登出
import type { ApiErrorBody } from './types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const TOKEN_KEY = 'csaifm_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  code: string
  status: number
  fields?: Record<string, unknown>

  constructor(code: string, message: string, status: number, fields?: Record<string, unknown>) {
    super(message)
    this.code = code
    this.status = status
    this.fields = fields
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError
}

type Query = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, query?: Query): string {
  const url = `${API_BASE}${path}`
  if (!query) return url
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== null && v !== undefined && v !== '') qs.set(k, String(v))
  }
  const s = qs.toString()
  return s ? `${url}?${s}` : url
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null
  try {
    body = (await res.json()) as ApiErrorBody
  } catch {
    // 非 JSON 响应
  }
  const code = body?.detail?.code || `HTTP_${res.status}`
  const message = body?.detail?.message || `请求失败（${res.status}）`
  return new ApiError(code, message, res.status, body?.detail?.fields)
}

export async function request<T>(path: string, options: RequestInit = {}, query?: Query): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(buildUrl(path, query), { ...options, headers })
  if (res.status === 204) return undefined as T
  if (!res.ok) {
    if (res.status === 401) {
      // token 失效/过期：清除并回到登录页
      setToken(null)
      window.dispatchEvent(new CustomEvent('csaifm:unauthorized'))
    }
    throw await parseError(res)
  }
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>(path, { method: 'GET' }, query),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, file: File, field = 'file') => {
    const fd = new FormData()
    fd.append(field, file)
    return request<T>(path, { method: 'POST', body: fd })
  },
}

/** 下载 PDF 为文件（携带 token） */
export async function downloadPdf(path: string, filename: string): Promise<void> {
  const token = getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw await parseError(res)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
