import type { Language } from '../types'
import type { Translation } from '../i18n'
import { useMemory } from '../context/MemoryContext'
import { MemoryIcon } from '../components/icons'
import { StarRating } from '../components/StarRating'

function formatTime(ts: number, language: Language): string {
  return new Date(ts).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function MemoryModule({ t, language }: { t: Translation; language: Language }) {
  const { conversations, clearAll } = useMemory()
  const m = t.memory

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{m.subtitle}</p>
        {conversations.length > 0 && (
          <button
            type="button"
            onClick={() => {
              if (window.confirm(m.confirmClear)) clearAll()
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            {m.clearAll}
          </button>
        )}
      </div>

      {conversations.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-16 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400">
            <MemoryIcon className="h-7 w-7" />
          </div>
          <p className="max-w-md text-sm text-slate-500">{m.empty}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {conversations.map((conv) => (
            <div key={conv.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
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
                <span className="shrink-0 rounded-md bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-500">
                  {m.resultsCol}: {conv.resultCount}
                </span>
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
