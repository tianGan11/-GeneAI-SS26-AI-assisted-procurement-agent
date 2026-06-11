import { useState } from 'react'
import type { Translation } from '../i18n'
import type { Supplier, ConversationRecord, FeedbackRecord } from '../types'
import { MOCK_SUPPLIERS } from '../data/suppliers'
import { api, apiEnabled } from '../lib/api'
import { useMemory } from '../context/MemoryContext'
import { StepIndicator, ExportPrintToolbar, AnalyzeButton } from '../components/shared'
import { FeedbackModal } from '../components/FeedbackModal'
import { SearchIcon } from '../components/icons'

function SupplierCard({
  supplier,
  t,
  onSelect,
}: {
  supplier: Supplier
  t: Translation
  onSelect: () => void
}) {
  const s = t.sourcing
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-900">{supplier.name}</h3>
          <p className="mt-0.5 text-sm text-slate-500">
            {supplier.city}, {supplier.country} · {s.cardEstablished} {supplier.established}
          </p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
          {supplier.matchScore}% {s.match}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        <Field label={s.cardAddress} value={supplier.address} />
        <Field
          label={s.cardContact}
          value={`${supplier.contactPerson} · ${supplier.phone}`}
          sub={`${supplier.email} · ${supplier.website}`}
        />
        <Field label={s.cardEmployees} value={supplier.employees} />
        <Field label={s.cardRevenue} value={supplier.annualRevenue} />
      </div>

      <div className="mt-4 border-t border-slate-100 pt-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardCapabilities}</p>
        <div className="flex flex-wrap gap-1.5">
          {supplier.capabilities.map((cap) => (
            <span key={cap} className="rounded-md bg-blue-50 px-2 py-1 text-xs text-blue-700">
              {cap}
            </span>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardCerts}</p>
          <div className="flex flex-wrap gap-1.5">
            {supplier.certifications.map((cert) => (
              <span key={cert} className="rounded-md border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
                {cert}
              </span>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={onSelect}
          className="rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-600 transition-colors hover:bg-blue-50 print:hidden"
        >
          {t.common.giveFeedback}
        </button>
      </div>
    </div>
  )
}

function Field({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm text-slate-700">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

export function SourcingModule({
  t,
  restore,
}: {
  t: Translation
  /** When set, the module opens pre-filled with this past conversation. */
  restore: ConversationRecord | null
}) {
  const { remember, attachFeedback } = useMemory()
  const [query, setQuery] = useState(restore?.restore?.query ?? '')
  // Mock mode shows the seed suppliers immediately; API mode waits for a search.
  const [results, setResults] = useState<Supplier[]>(apiEnabled ? [] : MOCK_SUPPLIERS)
  const [currentStep, setCurrentStep] = useState(3)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [hasRun, setHasRun] = useState(!apiEnabled)
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null)
  // Reopening a past conversation re-links feedback to that same record.
  const [activeConversationId, setActiveConversationId] = useState<string | null>(restore?.id ?? null)

  // Builds the memory record for the current query + all entered inputs.
  const buildRecord = (list: Supplier[]) => ({
    module: 'sourcing' as const,
    query: query.trim() || '(no text — browse all suppliers)',
    filters: {},
    restore: { query },
    resultCount: list.length,
    candidateNames: list.map((r) => r.name),
  })

  const handleAnalyze = async () => {
    setIsAnalyzing(true)
    setHasRun(true)
    setCurrentStep(1)
    setTimeout(() => setCurrentStep(2), 700)
    setTimeout(() => setCurrentStep(3), 1400)

    let list = results
    if (apiEnabled) {
      try {
        const res = await api.sourcing.search(query)
        list = res.results
      } catch {
        list = []
      }
      setResults(list)
    } else {
      // Keep the step animation visible in mock mode.
      await new Promise((r) => setTimeout(r, 1800))
    }

    setIsAnalyzing(false)
    setActiveConversationId(await remember(buildRecord(list)))
  }

  const handleFeedbackSubmit = async (feedback: FeedbackRecord) => {
    // Lazily create a conversation if feedback is given before running analysis.
    const id = activeConversationId ?? (await remember(buildRecord(results)))
    setActiveConversationId(id)
    await attachFeedback(id, feedback)
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden">
        <label className="mb-2 block text-sm font-medium text-slate-700">{t.sourcing.inputLabel}</label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          placeholder={t.sourcing.placeholder}
          className="w-full resize-none rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        />
        <p className="mt-1.5 text-xs text-slate-400">{t.sourcing.hint}</p>

        <div className="mt-4 flex justify-end">
          <AnalyzeButton isAnalyzing={isAnalyzing} onClick={handleAnalyze} t={t} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white px-8 py-6 shadow-sm print:hidden">
        <StepIndicator currentStep={currentStep} steps={t.steps} />
      </section>

      {hasRun && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-slate-900">
                {t.common.resultsFound(results.length)}
              </h2>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-600/20 print:hidden">
                {t.common.analysisComplete}
              </span>
            </div>
            <ExportPrintToolbar
              t={t}
              filename="fuyao-suppliers.xlsx"
              sheetName="Suppliers"
              columns={[
                t.sourcing.colName,
                t.sourcing.cardEstablished,
                t.sourcing.colLocation,
                t.sourcing.cardAddress,
                t.sourcing.cardContact,
                t.sourcing.colEmail,
                t.sourcing.colWebsite,
                t.sourcing.cardEmployees,
                t.sourcing.cardRevenue,
                t.sourcing.cardCapabilities,
                t.sourcing.cardCerts,
                t.sourcing.match,
              ]}
              rows={results.map((r) => [
                r.name,
                r.established,
                `${r.city}, ${r.country}`,
                r.address,
                `${r.contactPerson} · ${r.phone}`,
                r.email,
                r.website,
                r.employees,
                r.annualRevenue,
                r.capabilities.join('; '),
                r.certifications.join('; '),
                `${r.matchScore}%`,
              ])}
            />
          </div>

          {results.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-12 text-slate-400">
              <SearchIcon className="mb-3 h-7 w-7" />
              <p className="text-sm">{t.common.empty}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              {results.map((supplier) => (
                <SupplierCard
                  key={supplier.id}
                  supplier={supplier}
                  t={t}
                  onSelect={() => setFeedbackFor(supplier.name)}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {feedbackFor && (
        <FeedbackModal
          options={results.map((r) => r.name)}
          defaultChosen={feedbackFor}
          t={t}
          onSubmit={handleFeedbackSubmit}
          onClose={() => setFeedbackFor(null)}
        />
      )}
    </div>
  )
}
