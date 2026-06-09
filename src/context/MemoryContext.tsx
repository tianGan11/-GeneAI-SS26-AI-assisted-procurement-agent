import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { ConversationRecord, FeedbackRecord } from '../types'
import { loadJSON, saveJSON, STORAGE_KEYS } from '../lib/storage'
import { api, apiEnabled } from '../lib/api'
import { useAuth } from './AuthContext'

interface MemoryContextValue {
  conversations: ConversationRecord[]
  /** Logs a query + all inputs; resolves to the new record's id. */
  remember: (record: Omit<ConversationRecord, 'id' | 'timestamp' | 'feedback'>) => Promise<string>
  attachFeedback: (conversationId: string, feedback: FeedbackRecord) => Promise<void>
  /** Deletes a single conversation by id. */
  remove: (conversationId: string) => Promise<void>
  clearAll: () => Promise<void>
}

const MemoryContext = createContext<MemoryContextValue | null>(null)

export function MemoryProvider({ children }: { children: ReactNode }) {
  // MemoryProvider sits inside AuthProvider, so it can react to sign-in/out.
  const { user } = useAuth()
  const [conversations, setConversations] = useState<ConversationRecord[]>(() =>
    apiEnabled ? [] : loadJSON<ConversationRecord[]>(STORAGE_KEYS.conversations, []),
  )

  const persist = useCallback((list: ConversationRecord[]) => {
    if (!apiEnabled) saveJSON(STORAGE_KEYS.conversations, list)
  }, [])

  // With a real backend: (re)load conversations whenever the user changes.
  useEffect(() => {
    if (!apiEnabled) return
    if (!user) {
      setConversations([])
      return
    }
    let alive = true
    api.conversations
      .list()
      .then((list) => {
        if (alive) setConversations(list)
      })
      .catch(() => {
        /* ignore — list stays empty */
      })
    return () => {
      alive = false
    }
  }, [user])

  const remember = useCallback<MemoryContextValue['remember']>(
    async (record) => {
      if (apiEnabled) {
        const created = await api.conversations.create(record)
        setConversations((prev) => [created, ...prev])
        return created.id
      }
      const id = crypto.randomUUID()
      const full: ConversationRecord = { ...record, id, timestamp: Date.now() }
      setConversations((prev) => {
        const next = [full, ...prev]
        persist(next)
        return next
      })
      return id
    },
    [persist],
  )

  const attachFeedback = useCallback<MemoryContextValue['attachFeedback']>(
    async (conversationId, feedback) => {
      if (apiEnabled) {
        const updated = await api.conversations.attachFeedback(conversationId, feedback)
        setConversations((prev) => prev.map((c) => (c.id === conversationId ? updated : c)))
        return
      }
      setConversations((prev) => {
        const next = prev.map((c) => (c.id === conversationId ? { ...c, feedback } : c))
        persist(next)
        return next
      })
    },
    [persist],
  )

  const remove = useCallback<MemoryContextValue['remove']>(
    async (conversationId) => {
      if (apiEnabled) await api.conversations.remove(conversationId)
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== conversationId)
        persist(next)
        return next
      })
    },
    [persist],
  )

  const clearAll = useCallback<MemoryContextValue['clearAll']>(async () => {
    if (apiEnabled) await api.conversations.clear()
    setConversations([])
    persist([])
  }, [persist])

  const value = useMemo<MemoryContextValue>(
    () => ({ conversations, remember, attachFeedback, remove, clearAll }),
    [conversations, remember, attachFeedback, remove, clearAll],
  )

  return <MemoryContext.Provider value={value}>{children}</MemoryContext.Provider>
}

export function useMemory(): MemoryContextValue {
  const ctx = useContext(MemoryContext)
  if (!ctx) throw new Error('useMemory must be used within MemoryProvider')
  return ctx
}
