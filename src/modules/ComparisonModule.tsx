import { useMemo, useState } from 'react'
import type { Translation } from '../i18n'
import type { ComparisonItem, ComparisonSortKey, FeedbackRecord } from '../types'
import { MOCK_COMPARISON } from '../data/comparison'
import { useMemory } from '../context/MemoryContext'
import { StepIndicator, MatchScoreBadge, ExportPrintToolbar, AnalyzeButton } from '../components/shared'
import { FeedbackModal } from '../components/FeedbackModal'

type DeliveryOptionKey = 'unlimited' | 'within3' | 'within7'
const DELIVERY_KEYS: DeliveryOptionKey[] = ['unlimited', 'within3', 'within7']
const SORT_KEYS: ComparisonSortKey[] = ['match', 'price', 'delivery', 'payment']

// On-account (挂帐) ranks first when sorting by payment term.
const PAYMENT_PRIORITY: Record<ComparisonItem['paymentTerm'], number> = {
  onAccount: 0,
  prepayment: 1,
  card: 2,
}

function PriceInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  return (
    <div className="relative w-28">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-400">€</span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-slate-200 bg-white py-1.5 pl-7 pr-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30"
      />
    </div>
  )
}

export function ComparisonModule({ t }: { t: Translation }) {
  const c = t.comparison
  const { remember, attachFeedback } = useMemory()

  const [requirement, setRequirement] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [deliveryTime, setDeliveryTime] = useState<DeliveryOptionKey>('unlimited')
  const [sortKey, setSortKey] = useState<ComparisonSortKey>('match')
  const [currentStep, setCurrentStep] = useState(3)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)

  // Apply hard filters (price range + delivery time), then sort.
  const rows = useMemo(() => {
    const min = minPrice ? Number(minPrice) : -Infinity
    const max = maxPrice ? Number(maxPrice) : Infinity
    const deliveryCap = deliveryTime === 'within3' ? 3 : deliveryTime === 'within7' ? 7 : Infinity

    const filtered = MOCK_COMPARISON.filter(
      (r) => r.unitPriceEur >= min && r.unitPriceEur <= max && r.deliveryDays <= deliveryCap,
    )

    const sorted = [...filtered].sort((a, b) => {
      switch (sortKey) {
        case 'price':
          return a.unitPriceEur - b.unitPriceEur
        case 'delivery':
          return a.deliveryDays - b.deliveryDays
        case 'payment':
          return PAYMENT_PRIORITY[a.paymentTerm] - PAYMENT_PRIORITY[b.paymentTerm] || a.unitPriceEur - b.unitPriceEur
        case 'match':
        default:
          return b.matchScore - a.matchScore
      }
    })
    return sorted
  }, [minPrice, maxPrice, deliveryTime, sortKey])

  const recommendedId = useMemo(() => {
    if (rows.length === 0) return null
    return rows.reduce((best, r) => (r.matchScore > best.matchScore ? r : best), rows[0]).id
  }, [rows])

  // Builds the memory record for the current query + all entered inputs.
  const buildRecord = () => ({
    module: 'comparison' as const,
    query: requirement.trim() || '(no text — filter browse)',
    filters: {
      [c.budget]: `${minPrice || '0'} – ${maxPrice || '∞'} €`,
      [c.delivery]: c.deliveryOptions[deliveryTime],
      [c.sortLabel]: c.sortOptions[sortKey],
    },
    resultCount: rows.length,
    candidateNames: rows.map((r) => r.vendor),
  })

  const handleAnalyze = () => {
    setIsAnalyzing(true)
    setCurrentStep(1)
    setTimeout(() => setCurrentStep(2), 700)
    setTimeout(() => setCurrentStep(3), 1400)
    setTimeout(() => {
      setIsAnalyzing(false)
      setActiveConversationId(remember(buildRecord()))
    }, 1800)
  }

  const handleFeedbackSubmit = (feedback: FeedbackRecord) => {
    // Lazily create a conversation if feedback is given before running analysis.
    const id = activeConversationId ?? remember(buildRecord())
    setActiveConversationId(id)
    attachFeedback(id, feedback)
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden">
        <label className="mb-2 block text-sm font-medium text-slate-700">{c.inputLabel}</label>
        <textarea
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          rows={3}
          placeholder={c.placeholder}
          className="w-full resize-none rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        />
        <p className="mt-1.5 text-xs text-slate-400">{c.hint}</p>

        <div className="mt-4 rounded-lg bg-gray-50 px-4 py-3.5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">{c.hardFilters}</p>
          <div className="flex flex-wrap items-start gap-8">
            <div>
              <label className="mb-2 block text-sm text-slate-600">{c.budget}</label>
              <div className="flex items-center gap-2">
                <PriceInput value={minPrice} onChange={setMinPrice} placeholder={c.minPrice} />
                <span className="text-sm text-slate-400">—</span>
                <PriceInput value={maxPrice} onChange={setMaxPrice} placeholder={c.maxPrice} />
              </div>
            </div>
            <div>
              <label className="mb-2 block text-sm text-slate-600">{c.delivery}</label>
              <div className="flex flex-wrap gap-2">
                {DELIVERY_KEYS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setDeliveryTime(key)}
                    className={`rounded-full px-3 py-1 text-sm transition-colors duration-200 ${
                      deliveryTime === key
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    {c.deliveryOptions[key]}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <AnalyzeButton isAnalyzing={isAnalyzing} onClick={handleAnalyze} t={t} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white px-8 py-6 shadow-sm print:hidden">
        <StepIndicator currentStep={currentStep} steps={t.steps} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:border-0 print:shadow-none">
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{c.tableTitle}</h2>
            <p className="mt-0.5 text-sm text-slate-500">{t.common.resultsFound(rows.length)}</p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="flex items-center gap-2 print:hidden">
              <label className="text-xs font-medium text-slate-500">{c.sortLabel}</label>
              <select
                value={sortKey}
                onChange={(e) => setSortKey(e.target.value as ComparisonSortKey)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30"
              >
                {SORT_KEYS.map((key) => (
                  <option key={key} value={key}>
                    {c.sortOptions[key]}
                  </option>
                ))}
              </select>
            </div>
            <ExportPrintToolbar t={t} />
          </div>
        </div>

        <ComparisonTable rows={rows} recommendedId={recommendedId} t={t} onSelect={(name) => setFeedbackFor(name)} />
      </section>

      {feedbackFor && (
        <FeedbackModal
          options={rows.map((r) => r.vendor)}
          defaultChosen={feedbackFor}
          t={t}
          onSubmit={handleFeedbackSubmit}
          onClose={() => setFeedbackFor(null)}
        />
      )}
    </div>
  )
}

const HEAD_CELL = 'px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500'

function ComparisonTable({
  rows,
  recommendedId,
  t,
  onSelect,
}: {
  rows: ComparisonItem[]
  recommendedId: string | null
  t: Translation
  onSelect: (vendor: string) => void
}) {
  const c = t.comparison
  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 py-12 text-sm text-slate-400">
        {t.common.empty}
      </div>
    )
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-[1200px] w-full border-collapse text-left text-sm align-middle">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className={`sticky left-0 z-20 min-w-[240px] border-r border-gray-100 bg-slate-50 shadow-[2px_0_5px_rgba(0,0,0,0.03)] ${HEAD_CELL}`}>
              {c.colVendor}
            </th>
            <th className={`min-w-[140px] ${HEAD_CELL}`}>{c.colMatch}</th>
            <th className={`min-w-[110px] ${HEAD_CELL}`}>{c.colPrice}</th>
            <th className={`min-w-[120px] ${HEAD_CELL}`}>{c.colDelivery}</th>
            <th className={`min-w-[160px] ${HEAD_CELL}`}>{c.colPayment}</th>
            <th className={`min-w-[150px] ${HEAD_CELL}`}>{c.colDeliveryMethod}</th>
            <th className={`min-w-[120px] ${HEAD_CELL}`}>{c.colRating}</th>
            <th className={`min-w-[110px] ${HEAD_CELL}`}>{c.colAction}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((row) => {
            const highlight = row.id === recommendedId
            const stickyBg = highlight ? 'bg-blue-50' : 'bg-white'
            return (
              <tr key={row.id} className={`transition-colors hover:bg-slate-50/80 ${highlight ? 'bg-blue-50/40' : ''}`}>
                <td className={`sticky left-0 z-10 min-w-[240px] border-r border-gray-100 px-4 py-4 align-middle shadow-[2px_0_5px_rgba(0,0,0,0.03)] ${stickyBg}`}>
                  <div className="mb-0.5 flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{row.vendor}</p>
                    {highlight && (
                      <span className="shrink-0 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold uppercase text-white">
                        {c.recommended}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">{row.platform}</p>
                  <p className="mt-1 text-sm text-gray-500">{row.product}</p>
                </td>
                <td className="px-4 py-4 align-middle">
                  <MatchScoreBadge score={row.matchScore} />
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="whitespace-nowrap text-sm font-semibold text-slate-900">{row.unitLabel}</span>
                </td>
                <td className="px-4 py-4 align-middle text-sm text-gray-600">{row.deliveryLabel}</td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm text-gray-600">{row.paymentLabel}</span>
                  {row.paymentTerm === 'onAccount' && (
                    <span className="ml-1.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                      {c.paymentTerms.onAccount}
                    </span>
                  )}
                </td>
                <td className="px-4 py-4 align-middle text-sm text-gray-600">{row.deliveryMethod}</td>
                <td className="px-4 py-4 align-middle">
                  <span className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">{row.rating.toFixed(1)}</span>
                    <span className="text-amber-400">★</span>
                    <span className="text-slate-500">({row.reviews})</span>
                  </span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <button
                    type="button"
                    onClick={() => onSelect(row.vendor)}
                    className="whitespace-nowrap rounded-md border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-600 transition-colors hover:bg-blue-50 print:hidden"
                  >
                    {t.common.giveFeedback}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
