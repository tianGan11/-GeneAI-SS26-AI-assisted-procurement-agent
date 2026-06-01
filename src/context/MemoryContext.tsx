import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { ConversationRecord, FeedbackRecord } from '../types'
import { loadJSON, saveJSON, STORAGE_KEYS } from '../lib/storage'

interface MemoryContextValue {
  conversations: ConversationRecord[]
  /** Logs a query + all inputs; returns the new record's id. */
  remember: (record: Omit<ConversationRecord, 'id' | 'timestamp' | 'feedback'>) => string
  attachFeedback: (conversationId: string, feedback: FeedbackRecord) => void
  /** Deletes a single conversation by id. */
  remove: (conversationId: string) => void
  clearAll: () => void
}

const MemoryContext = createContext<MemoryContextValue | null>(null)

export function MemoryProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<ConversationRecord[]>(() =>
    loadJSON<ConversationRecord[]>(STORAGE_KEYS.conversations, []),
  )

  const persist = useCallback((list: ConversationRecord[]) => {
    saveJSON(STORAGE_KEYS.conversations, list)
  }, [])

  const remember = useCallback<MemoryContextValue['remember']>(
    (record) => {
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
    (conversationId, feedback) => {
      setConversations((prev) => {
        const next = prev.map((c) => (c.id === conversationId ? { ...c, feedback } : c))
        persist(next)
        return next
      })
    },
    [persist],
  )

  const remove = useCallback<MemoryContextValue['remove']>(
    (conversationId) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== conversationId)
        persist(next)
        return next
      })
    },
    [persist],
  )

  const clearAll = useCallback(() => {
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
