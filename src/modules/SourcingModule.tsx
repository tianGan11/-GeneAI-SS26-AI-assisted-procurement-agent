import { useEffect, useRef, useState } from 'react'
import type { Translation } from '../i18n'
import type { Supplier, ConversationRecord, FeedbackRecord } from '../types'
import { MOCK_SUPPLIERS } from '../data/suppliers'
import { api, apiEnabled, type SourcingJob, type SourcingStructuredFields } from '../lib/api'
import { useMemory } from '../context/MemoryContext'
import { StepIndicator, ExportPrintToolbar, AnalyzeButton, RestoredBanner } from '../components/shared'
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
  // Defensive joins — real (scraped) data may be missing any of these fields.
  const location = [supplier.city, supplier.country].filter(Boolean).join(', ')
  const established = supplier.established ? ` · ${s.cardEstablished} ${supplier.established}` : ''
  const contact = [supplier.contactPerson, supplier.phone].filter(Boolean).join(' · ')
  const contactSub = [supplier.email, supplier.website].filter(Boolean).join(' · ')
  const capabilities = supplier.capabilities ?? []
  const certifications = supplier.certifications ?? []
  const evidenceSnippets = supplier.evidenceSnippets ?? []
  const sourceUrls = supplier.sourceUrls ?? []

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-900">{supplier.name}</h3>
          {(location || established) && (
            <p className="mt-0.5 text-sm text-slate-500">
              {location}
              {established}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span
            title={`${s.sourceLabel}: ${isDatabaseSupplier(supplier) ? s.localDatabaseTag : s.webSearchTag}`}
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
              isDatabaseSupplier(supplier)
                ? 'bg-amber-50 text-amber-700 ring-amber-600/20'
                : 'bg-sky-50 text-sky-700 ring-sky-600/20'
            }`}
          >
            {isDatabaseSupplier(supplier) ? s.localDatabaseTag : s.webSearchTag}
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
            {Math.round(supplier.matchScore)}% {s.match}
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        <Field label={s.cardAddress} value={supplier.address || location} />
        <Field label={s.cardContact} value={contact} sub={contactSub} />
        <Field label={s.cardEmployees} value={supplier.employees} />
        <Field label={s.cardRevenue} value={supplier.annualRevenue} />
      </div>

      {capabilities.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardCapabilities}</p>
          <div className="flex flex-wrap gap-1.5">
            {capabilities.map((cap) => (
              <span key={cap} className="rounded-md bg-blue-50 px-2 py-1 text-xs text-blue-700">
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {evidenceSnippets.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardEvidence}</p>
          <div className="space-y-1.5">
            {evidenceSnippets.slice(0, 3).map((snippet, idx) => (
              <p key={`${supplier.id}-evidence-${idx}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
                {snippet}
              </p>
            ))}
          </div>
        </div>
      )}

      {sourceUrls.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardSources}</p>
          <div className="flex flex-wrap gap-1.5">
            {sourceUrls.slice(0, 4).map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="max-w-full truncate rounded-md border border-blue-100 bg-blue-50 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100"
              >
                {url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          {certifications.length > 0 && (
            <>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">{s.cardCerts}</p>
              <div className="flex flex-wrap gap-1.5">
                {certifications.map((cert) => (
                  <span key={cert} className="rounded-md border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
                    {cert}
                  </span>
                ))}
              </div>
            </>
          )}
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

function Field({ label, value, sub }: { label: string; value?: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm text-slate-700">{value || '—'}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

type SearchStatus = 'idle' | 'running' | 'success' | 'empty' | 'error'

function isDatabaseSupplier(supplier: Supplier): boolean {
  return supplier.source === 'database' || supplier.repurchasePriority === 'database'
}

function AgentProgressPanel({ job, t }: { job: SourcingJob | null; t: Translation }) {
  const copy = t.sourcing.agentProgress
  const backendProgress = job?.progress ?? 0
  const [displayedProgress, setDisplayedProgress] = useState(0)
  const events = job?.events ?? []
  const isRunning = job?.status !== 'failed' && job?.status !== 'completed'
  const progress = Math.round(displayedProgress)
  const statusLabel = job?.status === 'failed' ? copy.failedTitle : copy.runningTitle
  const eventListRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!job) return
    const timer = window.setInterval(() => {
      setDisplayedProgress((prev) => {
        if (job.status === 'completed') return Math.min(100, prev + 4)
        if (job.status === 'failed') return Math.max(prev, backendProgress)
        // Smooth, mostly linear visual progress: do not jump to backend event percentages.
        // Cap below completion until the backend really finishes. 0.28 per 200ms ≈ 84%/minute.
        return Math.min(92, prev + 0.28)
      })
    }, 200)
    return () => window.clearInterval(timer)
  }, [backendProgress, job])

  useEffect(() => {
    const list = eventListRef.current
    if (!list) return
    list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
  }, [events.length, job?.status])

  return (
    <section className="overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-br from-white via-blue-50/70 to-indigo-50/60 shadow-sm print:hidden">
      <div className="border-b border-white/70 px-6 py-5 backdrop-blur">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-sm font-bold text-white shadow-lg shadow-blue-200">
              {isRunning ? (
                <span className="relative flex h-5 w-5 items-center justify-center" aria-label="Agent is working">
                  <span className="absolute h-5 w-5 animate-ping rounded-full bg-white/50" />
                  <span className="h-3 w-3 animate-pulse rounded-full bg-white" />
                </span>
              ) : (
                'AI'
              )}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-500">{copy.eyebrow}</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">{statusLabel}</h2>
              {isRunning && (
                <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-blue-100/80 px-2.5 py-1 text-xs font-semibold text-blue-700 ring-1 ring-blue-200">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-60" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-blue-600" />
                  </span>
                  {copy.activeLabel}
                </div>
              )}
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">{copy.description}</p>
            </div>
          </div>
          <div className="rounded-2xl bg-white/85 px-4 py-3 text-right shadow-sm ring-1 ring-blue-100">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{copy.progress}</p>
            <p className="text-2xl font-semibold text-blue-700">{progress}%</p>
          </div>
        </div>

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white ring-1 ring-blue-100">
          <div className="relative h-full overflow-hidden rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }}>
            {isRunning && <span className="absolute inset-0 animate-pulse bg-white/30" />}
          </div>
        </div>
      </div>

      <div className="p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{copy.thoughtLogLabel}</p>
        <div ref={eventListRef} className="mt-3 max-h-64 space-y-2.5 overflow-auto pr-1">
          {events.length === 0 ? (
            <p className="text-sm leading-6 text-slate-500 italic">{copy.emptyText}</p>
          ) : (
            events.map((event) => (
              <div
                key={`${event.timestamp}-${event.phase}-${event.message}`}
                className="flex items-start gap-2.5 rounded-xl bg-white/80 px-3.5 py-2.5 shadow-sm ring-1 ring-inset ring-blue-100"
              >
                <span className="mt-0.5 text-xs text-slate-400 tabular-nums">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </span>
                <p className="text-sm leading-6 text-slate-700">{event.message}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </section>
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

  // ═══════════════════════════════════════════════════════════════════════════
  // Debug logging — detects unexpected page reloads.
  // ═══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    try {
      const nav = performance.getEntriesByType?.('navigation')?.[0] as PerformanceNavigationTiming | undefined
      console.log(`[SourcingModule] MOUNTED (type=${nav?.type ?? 'unknown'})`, {
        restore: !!restore,
      })
    } catch {
      console.log(`[SourcingModule] MOUNTED (perf API unavailable)`)
    }
  }, [restore])

  // Cleanup any stale sessionStorage artifacts from previous versions.
  useEffect(() => {
    try {
      ;['_sourcing_save', '_sourcing_save_v2', '_sourcing_reloading', '_sourcing_analyzing', '_sourcing_convId']
        .forEach(k => sessionStorage.removeItem(k))
    } catch { /* ignore */ }
  }, [])

  // ── State initializers ────────────────────────────────────────────────
  // Every time this module mounts, it starts FRESH — no cache, no persistence.
  // Only the `restore` prop (from Memory module → conversation history) can
  // pre-fill state.

  const savedResults = Array.isArray(restore?.resultsSnapshot)
    ? (restore.resultsSnapshot as unknown as Supplier[])
    : undefined
  const savedRestore = restore?.restore

  const [query, setQuery] = useState(savedRestore?.query ?? '')
  const [results, setResults] = useState<Supplier[]>(
    savedResults ?? (apiEnabled ? [] : MOCK_SUPPLIERS)
  )
  const [currentStep, setCurrentStep] = useState(savedResults || !apiEnabled ? 3 : 0)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [hasRun, setHasRun] = useState(!!savedResults || !apiEnabled)
  const [searchStatus, setSearchStatus] = useState<SearchStatus>(
    savedResults ? 'success' : apiEnabled ? 'idle' : 'success'
  )
  const [searchJob, setSearchJob] = useState<SourcingJob | null>(null)
  const [searchError, setSearchError] = useState(false)
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    restore?.id ?? null
  )
  const hasOnlyWebResults = results.length > 0 && results.every((supplier) => !isDatabaseSupplier(supplier))

  // ── Structured fields state (双模输入表单) ──────────────────────────────
  const [structProductName, setStructProductName] = useState(savedRestore?.productName ?? '')
  const [structQuantity, setStructQuantity] = useState(savedRestore?.quantity ?? '')
  const [structUnit, setStructUnit] = useState(savedRestore?.unit ?? 'pcs')
  const [structBrand, setStructBrand] = useState(savedRestore?.brand ?? '')
  const [structCategory, setStructCategory] = useState(savedRestore?.structuredCategory ?? '')
  const [structCountry, setStructCountry] = useState(savedRestore?.structuredCountry ?? '')
  const [structCerts, setStructCerts] = useState(savedRestore?.structuredCerts ?? '')

  /** Append structured info to the NL query for backward compat / mock mode. */
  const buildEnhancedQuery = () => {
    if (!structProductName && !structQuantity && !structBrand && !structCategory && !structCountry && !structCerts)
      return query
    const parts: string[] = []
    if (structProductName) parts.push(`Product: ${structProductName}`)
    if (structQuantity) parts.push(`Quantity: ${structQuantity} ${structUnit}`)
    if (structBrand) parts.push(`Brand: ${structBrand}`)
    if (structCategory) parts.push(`Category: ${structCategory}`)
    if (structCountry) parts.push(`Target Country: ${structCountry}`)
    if (structCerts) parts.push(`Certifications: ${structCerts}`)
    return `${query}\n---\n${parts.join('\n')}`
  }

  const getStructuredPayload = (): SourcingStructuredFields | undefined => {
    const structured: SourcingStructuredFields = {
      productName: structProductName || undefined,
      quantity: structQuantity || undefined,
      unit: structUnit || undefined,
      brand: structBrand || undefined,
      category: structCategory || undefined,
      country: structCountry || undefined,
      certifications: structCerts || undefined,
    }
    return Object.values(structured).some(Boolean) ? structured : undefined
  }

  /** Human-readable filter summary for the memory card. */
  const buildFilterSummary = (): Record<string, string> => {
    const s: Record<string, string> = {}
    const add = (k: string, v: string) => { if (v) s[k] = v }
    add(t.sourcing.productName, structProductName)
    if (structQuantity) add(t.sourcing.quantity, `${structQuantity} ${structUnit}`)
    add(t.sourcing.brand, structBrand)
    add(t.sourcing.structuredCategory, structCategory)
    add(t.sourcing.structuredCountry, structCountry)
    add(t.sourcing.structuredCerts, structCerts)
    return s
  }

  // Builds the memory record for the current query + all entered inputs.
  const buildRecord = (list: Supplier[]) => {
    const enhancedQuery = buildEnhancedQuery()
    const structured = getStructuredPayload()
    return {
      module: 'sourcing' as const,
      query: query.trim() || '(no text — browse all suppliers)',
      filters: buildFilterSummary(),
      restore: {
        query,
        productName: structProductName || undefined,
        quantity: structQuantity || undefined,
        unit: structUnit || undefined,
        brand: structBrand || undefined,
        structuredCategory: structCategory || undefined,
        structuredCountry: structCountry || undefined,
        structuredCerts: structCerts || undefined,
      },
      requestSnapshot: { query, enhancedQuery, structured: structured ?? null },
      resultCount: list.length,
      candidateNames: list.map((r) => r.name),
      resultsSnapshot: list as unknown as Record<string, unknown>[],
    }
  }

  const pollSearchJob = async (jobId: string): Promise<SourcingJob> => {
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1500))
      const job = await api.sourcing.getJob(jobId)
      setSearchJob(job)

      if (job.progress >= 35 && job.progress < 75) setCurrentStep(2)
      if (job.progress >= 75) setCurrentStep(3)
      if (job.status === 'completed' || job.status === 'failed') return job
    }
  }

  const handleAnalyze = async () => {
    console.log(`[SourcingModule] handleAnalyze STARTED`, { query: query.slice(0, 60) })
    const enhancedQuery = buildEnhancedQuery()
    const structured = getStructuredPayload()
    setIsAnalyzing(true)
    setHasRun(false)
    setSearchStatus('running')
    setSearchJob(null)
    setSearchError(false)
    setResults([])
    setCurrentStep(1)

    let list: Supplier[]
    try {
      if (apiEnabled) {
        try {
          // Preferred path: async job with live "Agent Thinking" progress (SSE).
          // Send both enhanced text and structured fields; older backends ignore unknown structured payloads.
          const created = await api.sourcing.createJob(enhancedQuery, structured)
          setSearchJob(created)
          console.log(`[SourcingModule] Job created:`, created.jobId)
          let finished: SourcingJob
          try {
            finished = await api.sourcing.streamJob(created.jobId, (job) => {
              setSearchJob(job)
              if (job.progress >= 35 && job.progress < 75) setCurrentStep(2)
              if (job.progress >= 75) setCurrentStep(3)
            })
          } catch {
            // Some deployment proxies buffer or close long-lived streams. Keep the
            // stable polling path as a fallback so the UX still progresses.
            finished = await pollSearchJob(created.jobId)
          }
          console.log(`[SourcingModule] Job finished:`, { status: finished.status, results: finished.results?.length })
          list = finished.results ?? []
          if (finished.status === 'failed') {
            setResults(list)
            setSearchError(true)
            setSearchStatus('error')
          } else {
            setResults(list)
            setSearchStatus(list.length > 0 ? 'success' : 'empty')
          }
        } catch {
          // Backend has no job endpoints yet (older deploy → 404). Fall back to the
          // plain synchronous search so results still load (without live progress).
          setSearchJob(null)
          const res = await api.sourcing.search(enhancedQuery, structured)
          list = res.results ?? []
          setResults(list)
          setSearchStatus(list.length > 0 ? 'success' : 'empty')
        }
      } else {
        // Keep the step animation visible in mock mode.
        await new Promise((r) => setTimeout(r, 1800))
        list = MOCK_SUPPLIERS
        setResults(list)
        setSearchStatus('success')
      }
      setHasRun(true)
      console.log(`[SourcingModule] Results set, saving to memory...`, { resultCount: list.length })
      // Save to conversation memory independently — a failure here must NOT
      // clear already-fetched results.
      try {
        const convId = await remember(buildRecord(list))
        console.log(`[SourcingModule] remember() succeeded:`, convId)
        setActiveConversationId(convId)
      } catch (e) {
        console.warn(`[SourcingModule] Failed to save conversation to memory; search results unaffected.`, e)
      }
      console.log(`[SourcingModule] handleAnalyze SUCCESS, hasRun=true`)
    } catch (e) {
      console.error(`[SourcingModule] handleAnalyze CATCH:`, e)
      setSearchError(true)
      setSearchStatus('error')
      setHasRun(true)
    } finally {
      setIsAnalyzing(false)
      setCurrentStep(3)
    }
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

        {/* ── Structured form (双模输入) ───────────────────────────────── */}
        <div className="mt-6 border-t border-slate-200 pt-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {t.sourcing.structuredLabel}
          </p>
          <p className="mb-4 mt-0.5 text-xs text-slate-400">{t.sourcing.structuredHint}</p>

          <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Product Name */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.productName}</label>
              <input
                type="text"
                value={structProductName}
                onChange={(e) => setStructProductName(e.target.value)}
                placeholder={t.sourcing.productNamePlaceholder}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            {/* Quantity + Unit */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.quantity}</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={structQuantity}
                  onChange={(e) => setStructQuantity(e.target.value)}
                  placeholder={t.sourcing.quantityPlaceholder}
                  className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
                <select
                  value={structUnit}
                  onChange={(e) => setStructUnit(e.target.value)}
                  className="w-20 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="pcs">{t.sourcing.units.pcs}</option>
                  <option value="kg">{t.sourcing.units.kg}</option>
                  <option value="m">{t.sourcing.units.m}</option>
                  <option value="set">{t.sourcing.units.set}</option>
                </select>
              </div>
            </div>

            {/* Brand */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.brand}</label>
              <input
                type="text"
                value={structBrand}
                onChange={(e) => setStructBrand(e.target.value)}
                placeholder={t.sourcing.brandPlaceholder}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            {/* Category */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.structuredCategory}</label>
              <select
                value={structCategory}
                onChange={(e) => setStructCategory(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="">{t.sourcing.categoryAll}</option>
                {Object.entries(t.sourcing.categories).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>

            {/* Country */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.structuredCountry}</label>
              <input
                type="text"
                value={structCountry}
                onChange={(e) => setStructCountry(e.target.value)}
                placeholder={t.sourcing.countryPlaceholder}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>

            {/* Certifications */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.sourcing.structuredCerts}</label>
              <input
                type="text"
                value={structCerts}
                onChange={(e) => setStructCerts(e.target.value)}
                placeholder={t.sourcing.certsPlaceholder}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              />
            </div>
          </div>
        </div>
        {/* ── End structured form ────────────────────────────────────────── */}

        <div className="mt-4 flex justify-end">
          <AnalyzeButton isAnalyzing={isAnalyzing} onClick={handleAnalyze} t={t} />
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white px-8 py-6 shadow-sm print:hidden">
        <StepIndicator currentStep={currentStep} steps={t.steps} />
      </section>

      {searchJob && searchStatus !== 'idle' && <AgentProgressPanel key={searchJob.jobId} job={searchJob} t={t} />}

      {hasRun && (
        <section className="space-y-4">
          {savedResults && <RestoredBanner t={t} />}
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
                t.sourcing.sourceLabel,
                t.sourcing.match,
              ]}
              rows={results.map((r) => [
                r.name,
                r.established ?? '',
                [r.city, r.country].filter(Boolean).join(', '),
                r.address ?? '',
                [r.contactPerson, r.phone].filter(Boolean).join(' · '),
                r.email ?? '',
                r.website ?? '',
                r.employees ?? '',
                r.annualRevenue ?? '',
                (r.capabilities ?? []).join('; '),
                (r.certifications ?? []).join('; '),
                isDatabaseSupplier(r) ? t.sourcing.localDatabaseTag : t.sourcing.webSearchTag,
                `${Math.round(r.matchScore)}%`,
              ])}
            />
          </div>

          {!searchError && hasOnlyWebResults && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-3 text-sm font-medium text-amber-800 shadow-sm print:hidden">
              {t.sourcing.allWebNotice}
            </div>
          )}

          {searchError ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-red-200 bg-red-50 p-12 text-red-500">
              <SearchIcon className="mb-3 h-7 w-7" />
              <p className="text-sm">{t.common.searchError}</p>
            </div>
          ) : results.length === 0 ? (
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
