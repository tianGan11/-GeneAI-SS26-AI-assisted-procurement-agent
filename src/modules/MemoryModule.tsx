import { useEffect, useMemo, useState } from 'react'
import type { ConversationRecord, Language } from '../types'
import type { Translation } from '../i18n'
import { useMemory } from '../context/MemoryContext'
import { apiEnabled } from '../lib/api'
import { MemoryIcon, SearchIcon } from '../components/icons'
import { StarRating } from '../components/StarRating'
import { ConfirmDialog } from '../components/ConfirmDialog'

/** Time filter options. */
type TimeFilter = 'all' | '7d' | '30d' | '1y'

/** Module filter: 'all' shows both. */
type ModuleFilter = 'all' | 'sourcing' | 'comparison'

/** What a pending confirmation targets: one record (by id) or everything. */
type PendingDelete = { type: 'one'; id: string } | { type: 'all' } | null

function formatTime(ts: number, language: Language): string {
  return new Date(ts).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Return timestamp (ms) threshold for a given time filter, or 0 for 'all'. */
function timeCutoff(filter: TimeFilter): number {
  const now = Date.now()
  switch (filter) {
    case '7d':
      return now - 7 * 24 * 60 * 60 * 1000
    case '30d':
      return now - 30 * 24 * 60 * 60 * 1000
    case '1y':
      return now - 365 * 24 * 60 * 60 * 1000
    default:
      return 0
  }
}

export function MemoryModule({
  t,
  language,
  onOpen,
}: {
  t: Translation
  language: Language
  /** Reopen a past conversation in its source module. */
  onOpen: (conv: ConversationRecord) => void
}) {
  const { conversations, remove, clearAll, reloadConvs } = useMemory()
  const m = t.memory
  const [pending, setPending] = useState<PendingDelete>(null)

  // ── Filter state ──────────────────────────────────────────────────────
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('all')
  const [moduleFilter, setModuleFilter] = useState<ModuleFilter>('all')
  const [keyword, setKeyword] = useState('')

  // When the backend is enabled, re-fetch from the server when the time range changes.
  useEffect(() => {
    if (!apiEnabled) return
    void reloadConvs(timeFilter === 'all' ? 'all' : timeFilter)
  }, [timeFilter, reloadConvs])

  // ── Client-side filtering (used in mock mode, or for keyword/module filter) ─
  const filtered = useMemo(() => {
    const cutoff = timeCutoff(timeFilter)
    const kw = keyword.trim().toLowerCase()

    return conversations.filter((conv) => {
      // Time filter
      if (cutoff > 0 && conv.timestamp < cutoff) return false

      // Module filter
      if (moduleFilter !== 'all' && conv.module !== moduleFilter) return false

      // Keyword search (query text + filter values + candidate names)
      if (kw) {
        const haystack = [
          conv.query,
          ...Object.values(conv.filters),
          ...(conv.candidateNames ?? []),
          conv.module,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        if (!haystack.includes(kw)) return false
      }

      return true
    })
  }, [conversations, timeFilter, moduleFilter, keyword])

  // ── Filter button helper ──────────────────────────────────────────────
  const timeBtn = (value: TimeFilter, label: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setTimeFilter(value)}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        timeFilter === value
          ? 'bg-blue-600 text-white shadow-sm'
          : 'border border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:text-blue-600'
      }`}
    >
      {label}
    </button>
  )

  const moduleBtn = (value: ModuleFilter, label: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setModuleFilter(value)}
      className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
        moduleFilter === value
          ? value === 'sourcing'
            ? 'bg-blue-600 text-white shadow-sm'
            : value === 'comparison'
              ? 'bg-violet-600 text-white shadow-sm'
              : 'bg-slate-700 text-white shadow-sm'
          : 'border border-slate-200 bg-white text-slate-500 hover:border-blue-200 hover:text-blue-600'
      }`}
    >
      {label}
    </button>
  )

  const handleConfirm = () => {
    if (pending?.type === 'one') void remove(pending.id)
    else if (pending?.type === 'all') void clearAll()
    setPending(null)
  }

  return (
    <div className="space-y-5">
      {/* ── Filter bar ──────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        {/* Keyword search */}
        <div className="relative min-w-0 flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder={m.searchPlaceholder}
            className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-3 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>

        {/* Clear all button */}
        {conversations.length > 0 && (
          <button
            type="button"
            onClick={() => setPending({ type: 'all' })}
            className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            {m.clearAll}
          </button>
        )}
      </div>

      {/* Time + module filter pills */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Time filters */}
        <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white p-1.5 shadow-sm">
          {timeBtn('all', m.timeFilterAll)}
          {timeBtn('7d', m.timeFilter7d)}
          {timeBtn('30d', m.timeFilter30d)}
          {timeBtn('1y', m.timeFilter1y)}
        </div>

        {/* Module filters */}
        <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white p-1.5 shadow-sm">
          {moduleBtn('all', m.moduleFilterAll)}
          {moduleBtn('sourcing', m.moduleSourcing)}
          {moduleBtn('comparison', m.moduleComparison)}
        </div>

        {/* Result count badge */}
        <span className="text-xs text-slate-400">
          {filtered.length}/{conversations.length}
        </span>
      </div>

      {/* ── Conversation list ──────────────────────────────────────── */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400">
            <MemoryIcon className="h-7 w-7" />
          </div>
          <p className="max-w-md text-sm text-slate-500">
            {keyword || timeFilter !== 'all' || moduleFilter !== 'all'
              ? t.common.empty
              : m.empty}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((conv) => (
            <div
              key={conv.id}
              role="button"
              tabIndex={0}
              onClick={() => onOpen(conv)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onOpen(conv)
                }
              }}
              className="group cursor-pointer rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        conv.module === 'sourcing'
                          ? 'bg-blue-50 text-blue-700'
                          : 'bg-violet-50 text-violet-700'
                      }`}
                    >
                      {t.nav[conv.module]}
                    </span>
                    <span className="text-xs text-slate-400">{formatTime(conv.timestamp, language)}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-800">{conv.query}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="rounded-md bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-500">
                    {m.resultsCol}: {conv.resultCount}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 opacity-0 transition-opacity group-hover:opacity-100">
                    {m.reopen}
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </span>
                  <button
                    type="button"
                    aria-label={m.delete}
                    title={m.delete}
                    onClick={(e) => {
                      e.stopPropagation()
                      setPending({ type: 'one', id: conv.id })
                    }}
                    className="rounded-md p-1.5 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-600"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </button>
                </div>
              </div>

              {Object.keys(conv.filters).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(conv.filters).map(([key, val]) => (
                    <span key={key} className="rounded-md border border-slate-200 px-2 py-0.5 text-xs text-slate-500">
                      {key}: <span className="text-slate-700">{val}</span>
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-3 border-t border-slate-100 pt-3">
                {conv.feedback ? (
                  <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                    <span className="text-sm text-slate-600">
                      {m.chose}: <span className="font-semibold text-slate-900">{conv.feedback.chosenName}</span>
                    </span>
                    <RatingChip label={t.feedback.quality} value={conv.feedback.quality} />
                    <RatingChip label={t.feedback.logistics} value={conv.feedback.logistics} />
                    <RatingChip label={t.feedback.priceSat} value={conv.feedback.priceSatisfaction} />
                    <RatingChip label={t.feedback.service} value={conv.feedback.service} />
                    {conv.feedback.comment && (
                      <span className="text-xs italic text-slate-400">“{conv.feedback.comment}”</span>
                    )}
                  </div>
                ) : (
                  <span className="text-xs text-slate-400">{m.noFeedback}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {pending && (
        <ConfirmDialog
          title={pending.type === 'all' ? m.clearTitle : m.deleteTitle}
          message={pending.type === 'all' ? m.confirmClear : m.confirmDelete}
          confirmLabel={pending.type === 'all' ? m.clearAll : m.delete}
          cancelLabel={t.common.cancel}
          onConfirm={handleConfirm}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  )
}

function RatingChip({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
      {label}
      <StarRating value={value} readOnly size="sm" />
    </span>
  )
}
