function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

export type FieldErrors = Record<string, string[]>

function flattenFieldErrors(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  const messages = Object.values(data as Record<string, unknown>).flatMap((value) =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [],
  )
  return messages.length > 0 ? messages.join(' ') : null
}

export class ApiError extends Error {
  status: number
  fields?: FieldErrors
  body?: unknown

  constructor(message: string, status: number, fields?: FieldErrors, body?: unknown) {
    super(message)
    this.status = status
    this.fields = fields
    this.body = body
  }
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')

  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie('csrftoken')
    if (csrfToken) headers.set('X-CSRFToken', csrfToken)
    if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' })

  if (response.status === 204) {
    return undefined as T
  }

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const data = isJson ? await response.json() : undefined

  if (!response.ok) {
    const message = data?.detail ?? flattenFieldErrors(data) ?? 'Não foi possível completar a operação.'
    throw new ApiError(message, response.status, isJson ? (data as FieldErrors) : undefined, data)
  }

  return data as T
}

export async function ensureCsrfCookie(): Promise<void> {
  await apiFetch('/api/v1/auth/csrf/')
}
