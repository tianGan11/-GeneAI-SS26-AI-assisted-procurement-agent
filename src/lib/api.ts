// ---------------------------------------------------------------------------
// HTTP API client — the single integration seam to the backend.
//
// Toggle: set VITE_API_BASE_URL (e.g. in .env.local or Vercel env).
//   - NOT set  → `apiEnabled` is false → the app keeps using mock data /
//                localStorage exactly as before (offline prototype mode).
//   - set      → every data call goes to the real REST backend.
//
// Endpoints + payload shapes follow docs/PROJECT_TASKS.md (Lane D) and the
// types in src/types.ts. Backend devs: make your API match this and the
// frontend just works — no frontend changes needed.
// ---------------------------------------------------------------------------

import type {
  AuthUser,
  ComparisonItem,
  ConversationRecord,
  DeliveryOptionKey,
  FeedbackRecord,
  Supplier,
  VaultKey,
} from '../types'

const RAW_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined
/** Base URL of the backend, without trailing slash. Empty string = mock mode. */
export const API_BASE = (RAW_BASE ?? '').replace(/\/+$/, '')
/** True when a real backend is configured; false = use mock data. */
export const apiEnabled = API_BASE.length > 0

// --- Auth token (JWT) ------------------------------------------------------

const TOKEN_KEY = 'fuyao.auth.token'
export const getToken = (): string | null => {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}
export const setToken = (token: string): void => {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* ignore */
  }
}
export const clearToken = (): void => {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

// --- Error type ------------------------------------------------------------

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

// --- Core request helper ---------------------------------------------------

async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown } = {},
): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  })

  if (!res.ok) {
    let code = 'HTTP_ERROR'
    let message = `Request failed (${res.status})`
    try {
      const data = (await res.json()) as { error?: { code?: string; message?: string } }
      if (data?.error) {
        code = data.error.code ?? code
        message = data.error.message ?? message
      }
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(message, code, res.status)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function streamRequest<T>(path: string, onEvent: (event: T) => void): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: {
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (!res.ok || !res.body) {
    throw new ApiError(`Stream failed (${res.status})`, 'STREAM_ERROR', res.status)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let latest: T | null = null

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const dataLine = chunk
        .split('\n')
        .find((line) => line.startsWith('data: '))
      if (!dataLine) continue
      latest = JSON.parse(dataLine.slice(6)) as T
      onEvent(latest)
    }
  }

  if (latest === null) {
    throw new ApiError('Stream ended without data', 'STREAM_EMPTY', 0)
  }
  return latest
}

// --- Typed endpoint methods ------------------------------------------------

export interface ComparisonFilters {
  minPrice?: number
  maxPrice?: number
  deliveryTime?: DeliveryOptionKey
}

export interface SourcingJobEvent {
  timestamp: number
  phase: string
  message: string
  progress: number
}

export interface SourcingJob {
  jobId: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  step: string
  events: SourcingJobEvent[]
  intent?: Record<string, unknown> | null
  results: Supplier[]
  error?: string | null
}

/** New-conversation payload: a record without server-generated fields. */
export type NewConversation = Omit<ConversationRecord, 'id' | 'timestamp' | 'feedback'>

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ token: string; user: AuthUser }>('/api/auth/login', {
        method: 'POST',
        body: { email, password },
      }),
    me: () => request<AuthUser>('/api/auth/me'),
    logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  },

  vault: {
    list: () => request<VaultKey[]>('/api/vault/keys'),
    save: (label: string, secret: string) =>
      request<VaultKey>('/api/vault/keys', { method: 'POST', body: { label, secret } }),
    remove: (id: string) => request<void>(`/api/vault/keys/${id}`, { method: 'DELETE' }),
  },

  sourcing: {
    search: (query: string) =>
      request<{ results: Supplier[] }>('/api/sourcing/search', { method: 'POST', body: { query } }),
    createJob: (query: string) =>
      request<SourcingJob>('/api/sourcing/search-jobs', { method: 'POST', body: { query } }),
    getJob: (jobId: string) => request<SourcingJob>(`/api/sourcing/search-jobs/${jobId}`),
    streamJob: (jobId: string, onEvent: (job: SourcingJob) => void) =>
      streamRequest<SourcingJob>(`/api/sourcing/search-jobs/${jobId}/events`, onEvent),
  },

  comparison: {
    search: (query: string, filters: ComparisonFilters) =>
      request<{ results: ComparisonItem[] }>('/api/comparison/search', {
        method: 'POST',
        body: { query, ...filters },
      }),
  },

  conversations: {
    list: () => request<ConversationRecord[]>('/api/conversations'),
    create: (record: NewConversation) =>
      request<ConversationRecord>('/api/conversations', { method: 'POST', body: record }),
    attachFeedback: (id: string, feedback: FeedbackRecord) =>
      request<ConversationRecord>(`/api/conversations/${id}/feedback`, {
        method: 'PATCH',
        body: feedback,
      }),
    remove: (id: string) => request<void>(`/api/conversations/${id}`, { method: 'DELETE' }),
    clear: () => request<void>('/api/conversations', { method: 'DELETE' }),
  },
}
