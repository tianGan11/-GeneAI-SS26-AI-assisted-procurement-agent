import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { AuthUser, VaultKey } from '../types'
import { loadJSON, saveJSON, removeKey, STORAGE_KEYS } from '../lib/storage'
import { api, apiEnabled, clearToken, getToken, setToken } from '../lib/api'

interface AuthContextValue {
  user: AuthUser | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  vaultKeys: VaultKey[]
  saveVaultKey: (label: string, secret: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function maskSecret(secret: string): string {
  const last4 = secret.slice(-4)
  return `••••••••${last4}`
}

/** Mock user fabricated from an email — only used when no backend is configured. */
function fabricateUser(email: string): AuthUser {
  const namePart = email.split('@')[0] || 'user'
  return {
    email,
    name: namePart
      .split(/[._-]/)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join(' '),
    company: 'Fuyao Glass Europe',
    role: 'Procurement Manager',
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    // In API mode, a persisted user is only trustworthy if we still hold a token.
    if (apiEnabled && !getToken()) return null
    return loadJSON<AuthUser | null>(STORAGE_KEYS.auth, null)
  })
  const [vaultKeys, setVaultKeys] = useState<VaultKey[]>(() =>
    apiEnabled ? [] : loadJSON<VaultKey[]>(STORAGE_KEYS.vault, []),
  )

  // With a real backend: verify the stored token and refresh the user on load.
  useEffect(() => {
    if (!apiEnabled || !getToken()) return
    api.auth
      .me()
      .then((u) => {
        setUser(u)
        saveJSON(STORAGE_KEYS.auth, u)
      })
      .catch(() => {
        clearToken()
        setUser(null)
        removeKey(STORAGE_KEYS.auth)
      })
  }, [])

  // With a real backend: load the vault for the signed-in user.
  useEffect(() => {
    if (!apiEnabled || !user) return
    api.vault
      .list()
      .then(setVaultKeys)
      .catch(() => {
        /* ignore — vault stays empty */
      })
  }, [user])

  const login = useCallback(async (email: string, password: string) => {
    if (apiEnabled) {
      const { token, user: nextUser } = await api.auth.login(email, password)
      setToken(token)
      setUser(nextUser)
      saveJSON(STORAGE_KEYS.auth, nextUser)
      return
    }
    // MOCK — no backend: any credentials succeed.
    const nextUser = fabricateUser(email)
    setUser(nextUser)
    saveJSON(STORAGE_KEYS.auth, nextUser)
  }, [])

  const logout = useCallback(() => {
    if (apiEnabled) {
      api.auth.logout().catch(() => {
        /* best-effort */
      })
      clearToken()
    }
    setUser(null)
    setVaultKeys([])
    removeKey(STORAGE_KEYS.auth)
  }, [])

  const saveVaultKey = useCallback(async (label: string, secret: string) => {
    if (apiEnabled) {
      const saved = await api.vault.save(label, secret)
      setVaultKeys((prev) => {
        const idx = prev.findIndex((k) => k.label === saved.label)
        return idx >= 0 ? prev.map((k, i) => (i === idx ? saved : k)) : [...prev, saved]
      })
      return
    }
    // MOCK — store masked value in localStorage.
    setVaultKeys((prev) => {
      const masked = maskSecret(secret)
      const idx = prev.findIndex((k) => k.label === label)
      const next: VaultKey =
        idx >= 0
          ? { ...prev[idx], maskedValue: masked, updatedAt: Date.now() }
          : { id: crypto.randomUUID(), label, maskedValue: masked, updatedAt: Date.now() }
      const list = idx >= 0 ? prev.map((k, i) => (i === idx ? next : k)) : [...prev, next]
      saveJSON(STORAGE_KEYS.vault, list)
      return list
    })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, login, logout, vaultKeys, saveVaultKey }),
    [user, login, logout, vaultKeys, saveVaultKey],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
