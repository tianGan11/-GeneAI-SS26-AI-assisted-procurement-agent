import { useMemo, useState } from 'react'
import type { Translation } from '../i18n'
import type {
  ComparisonItem,
  ConversationRecord,
  DeliveryOptionKey,
  FactorWeights,
  FeedbackRecord,
} from '../types'
import { MOCK_COMPARISON } from '../data/comparison'
import { api, apiEnabled } from '../lib/api'
import { useMemory } from '../context/MemoryContext'
import { StepIndicator, MatchScoreBadge, ExportPrintToolbar, AnalyzeButton } from '../components/shared'
import { FeedbackModal } from '../components/FeedbackModal'
import { WeightControl } from '../components/WeightControl'

const DELIVERY_KEYS: DeliveryOptionKey[] = ['unlimited', 'within3', 'within7']

// Default importance: price-led, then delivery, then reviews.
const DEFAULT_WEIGHTS: FactorWeights = { price: 40, delivery: 35, rating: 25 }

/** A quote plus its user-weighted decision score (0–100). */
type ScoredItem = ComparisonItem & { score: number }

interface RankOptions {
  minPrice: string
  maxPrice: string
  deliveryTime: DeliveryOptionKey
  weights: FactorWeights
}

/** Normalize a value to 0–1; higher is always better. */
function normalize(value: number, min: number, max: number, higherIsBetter: boolean): number {
  if (max === min) return 1
  const t = (value - min) / (max - min)
  return higherIsBetter ? t : 1 - t
}

/**
 * Apply hard filters (price range + delivery time), then rank by the
 * user-weighted composite score over price / delivery / reviews.
 * Pure function — used both for rendering and for logging to memory.
 */
function rankItems(items: ComparisonItem[], { minPrice, maxPrice, deliveryTime, weights }: RankOptions): ScoredItem[] {
  const min = minPrice ? Number(minPrice) : -Infinity
  const max = maxPrice ? Number(maxPrice) : Infinity
  const deliveryCap = deliveryTime === 'within3' ? 3 : deliveryTime === 'within7' ? 7 : Infinity

  const filtered = items.filter(
    (r) => r.unitPriceEur >= min && r.unitPriceEur <= max && r.deliveryDays <= deliveryCap,
  )
  if (filtered.length === 0) return []

  const prices = filtered.map((r) => r.unitPriceEur)
  const days = filtered.map((r) => r.deliveryDays)
  const ratings = filtered.map((r) => r.rating)
  const minP = Math.min(...prices)
  const maxP = Math.max(...prices)
  const minD = Math.min(...days)
  const maxD = Math.max(...days)
  const minR = Math.min(...ratings)
  const maxR = Math.max(...ratings)

  const wp = weights.price / 100
  const wd = weights.delivery / 100
  const wr = weights.rating / 100

  return filtered
    .map<ScoredItem>((r) => {
      const sPrice = normalize(r.unitPriceEur, minP, maxP, false)
      const sDelivery = normalize(r.deliveryDays, minD, maxD, false)
      const sRating = normalize(r.rating, minR, maxR, true)
      const score = Math.round((wp * sPrice + wd * sDelivery + wr * sRating) * 100)
      return { ...r, score }
    })
    .sort((a, b) => b.score - a.score || a.unitPriceEur - b.unitPriceEur)
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

export function ComparisonModule({
  t,
  restore,
}: {
  t: Translation
  /** When set, the module opens pre-filled with this past conversation. */
  restore: ConversationRecord | null
}) {
  const c = t.comparison
  const { remember, attachFeedback } = useMemory()
  const init = restore?.restore

  const [requirement, setRequirement] = useState(init?.query ?? '')
  const [minPrice, setMinPrice] = useState(init?.minPrice ?? '')
  const [maxPrice, setMaxPrice] = useState(init?.maxPrice ?? '')
  const [deliveryTime, setDeliveryTime] = useState<DeliveryOptionKey>(init?.deliveryTime ?? 'unlimited')
  const [weights, setWeights] = useState<FactorWeights>(init?.weights ?? DEFAULT_WEIGHTS)
  const [items, setItems] = useState<ComparisonItem[]>(apiEnabled ? [] : MOCK_COMPARISON)
  const [currentStep, setCurrentStep] = useState(0)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [searchError, setSearchError] = useState(false)
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null)
  // Reopening a past conversation re-links feedback to that same record.
  const [activeConversationId, setActiveConversationId] = useState<string | null>(restore?.id ?? null)

  const rows = useMemo<ScoredItem[]>(
    () => rankItems(items, { minPrice, maxPrice, deliveryTime, weights }),
    [items, minPrice, maxPrice, deliveryTime, weights],
  )

  // Top of the ranked list is the recommended pick.
  const recommendedId = rows.length > 0 ? rows[0].id : null

  // Builds the memory record for the current query + all entered inputs.
  const buildRecord = (ranked: ScoredItem[]) => ({
    module: 'comparison' as const,
    query: requirement.trim() || '(no text — filter browse)',
    filters: {
      [c.budget]: `${minPrice || '0'} – ${maxPrice || '∞'} €`,
      [c.delivery]: c.deliveryOptions[deliveryTime],
      [c.weightTitle]: `${c.weightPrice} ${weights.price}% · ${c.weightDelivery} ${weights.delivery}% · ${c.weightRating} ${weights.rating}%`,
    },
    restore: { query: requirement, minPrice, maxPrice, deliveryTime, weights },
    resultCount: ranked.length,
    candidateNames: ranked.map((row) => row.vendor),
  })

  const handleAnalyze = async () => {
    setIsAnalyzing(true)
    setCurrentStep(1)
    setTimeout(() => setCurrentStep(2), 700)
    setTimeout(() => setCurrentStep(3), 1400)

    let list = items
    if (apiEnabled) {
      setSearchError(false)
      try {
        const res = await api.comparison.search(requirement, {
          minPrice: minPrice ? Number(minPrice) : undefined,
          maxPrice: maxPrice ? Number(maxPrice) : undefined,
          deliveryTime,
        })
        list = res.results
      } catch {
        list = []
        setSearchError(true)
      }
      setItems(list)
    } else {
      // Keep the step animation visible in mock mode.
      await new Promise((r) => setTimeout(r, 1800))
    }

    setIsAnalyzing(false)
    const ranked = rankItems(list, { minPrice, maxPrice, deliveryTime, weights })
    setActiveConversationId(await remember(buildRecord(ranked)))
  }

  const handleFeedbackSubmit = async (feedback: FeedbackRecord) => {
    // Lazily create a conversation if feedback is given before running analysis.
    const id = activeConversationId ?? (await remember(buildRecord(rows)))
    setActiveConversationId(id)
    await attachFeedback(id, feedback)
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

        <div className="mt-4 rounded-lg bg-gray-50 px-4 py-3.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{c.weightTitle}</p>
          <p className="mb-3 mt-0.5 text-xs text-slate-400">{c.weightHint}</p>
          <WeightControl weights={weights} onChange={setWeights} t={t} />
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
            <ExportPrintToolbar
              t={t}
              filename="fuyao-quote-comparison.xlsx"
              sheetName="Comparison"
              columns={[
                c.colVendor,
                c.colPlatform,
                c.colProduct,
                c.colScore,
                c.colPrice,
                c.colDelivery,
                c.colPayment,
                c.colDeliveryMethod,
                c.colRating,
              ]}
              rows={rows.map((r) => [
                r.vendor,
                r.platform,
                r.product,
                `${r.score}%`,
                r.unitLabel,
                r.deliveryLabel,
                r.paymentLabel,
                r.deliveryMethod,
                `${r.rating.toFixed(1)} (${r.reviews})`,
              ])}
            />
          </div>
        </div>

        {searchError ? (
          <div className="flex items-center justify-center rounded-lg border border-dashed border-red-200 bg-red-50 py-12 text-sm text-red-500">
            {t.common.searchError}
          </div>
        ) : (
          <ComparisonTable rows={rows} recommendedId={recommendedId} t={t} onSelect={(name) => setFeedbackFor(name)} />
        )}
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
  rows: ScoredItem[]
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
    <div className="cmp-print overflow-x-auto rounded-lg border border-slate-200 print:overflow-visible">
      <table className="min-w-[1200px] w-full border-collapse text-left text-sm align-middle print:min-w-0">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className={`sticky left-0 z-20 min-w-[240px] border-r border-gray-100 bg-slate-50 shadow-[2px_0_5px_rgba(0,0,0,0.03)] ${HEAD_CELL}`}>
              {c.colVendor}
            </th>
            <th className={`min-w-[140px] ${HEAD_CELL}`}>{c.colScore}</th>
            <th className={`min-w-[110px] ${HEAD_CELL}`}>{c.colPrice}</th>
            <th className={`min-w-[120px] ${HEAD_CELL}`}>{c.colDelivery}</th>
            <th className={`min-w-[160px] ${HEAD_CELL}`}>{c.colPayment}</th>
            <th className={`min-w-[150px] ${HEAD_CELL}`}>{c.colDeliveryMethod}</th>
            <th className={`min-w-[120px] ${HEAD_CELL}`}>{c.colRating}</th>
            <th className={`min-w-[110px] print:hidden ${HEAD_CELL}`}>{c.colAction}</th>
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
                  <MatchScoreBadge score={row.score} />
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
                <td className="px-4 py-4 align-middle print:hidden">
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
