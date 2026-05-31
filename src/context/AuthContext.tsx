import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { AuthUser, VaultKey } from '../types'
import { loadJSON, saveJSON, removeKey, STORAGE_KEYS } from '../lib/storage'

interface AuthContextValue {
  user: AuthUser | null
  login: (email: string) => void
  logout: () => void
  vaultKeys: VaultKey[]
  saveVaultKey: (label: string, secret: string) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function maskSecret(secret: string): string {
  const last4 = secret.slice(-4)
  return `••••••••${last4}`
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() =>
    loadJSON<AuthUser | null>(STORAGE_KEYS.auth, null),
  )
  const [vaultKeys, setVaultKeys] = useState<VaultKey[]>(() =>
    loadJSON<VaultKey[]>(STORAGE_KEYS.vault, []),
  )

  const login = useCallback((email: string) => {
    // MOCK auth — in production this hits an IdP and returns a session token.
    const namePart = email.split('@')[0] || 'user'
    const nextUser: AuthUser = {
      email,
      name: namePart
        .split(/[._-]/)
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join(' '),
      company: 'Fuyao Glass Europe',
      role: 'Procurement Manager',
    }
    setUser(nextUser)
    saveJSON(STORAGE_KEYS.auth, nextUser)
  }, [])

  const logout = useCallback(() => {
    setUser(null)
    removeKey(STORAGE_KEYS.auth)
  }, [])

  const saveVaultKey = useCallback((label: string, secret: string) => {
    setVaultKeys((prev) => {
      const masked = maskSecret(secret)
      const existingIdx = prev.findIndex((k) => k.label === label)
      const next: VaultKey =
        existingIdx >= 0
          ? { ...prev[existingIdx], maskedValue: masked, updatedAt: Date.now() }
          : { id: crypto.randomUUID(), label, maskedValue: masked, updatedAt: Date.now() }
      const list = existingIdx >= 0 ? prev.map((k, i) => (i === existingIdx ? next : k)) : [...prev, next]
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
