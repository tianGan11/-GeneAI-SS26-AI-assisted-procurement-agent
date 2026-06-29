// ---------------------------------------------------------------------------
// Tiny localStorage wrapper. Stands in for a real backend / cloud store.
// Everything persisted here would, in production, live server-side behind auth.
// ---------------------------------------------------------------------------

export function loadJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function saveJSON<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // ignore quota / serialization errors in this prototype
  }
}

export function removeKey(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore
  }
}

export const STORAGE_KEYS = {
  auth: 'fuyao.auth.user',
  language: 'fuyao.lang',
  conversations: 'fuyao.memory.conversations',
  vault: 'fuyao.vault.keys',
} as const
