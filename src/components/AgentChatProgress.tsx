import { useEffect, useMemo, useRef, useState } from 'react'
import type { Translation } from '../i18n'
import type { SourcingJobEvent } from '../lib/api'

type AgentJobLike = {
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  events: SourcingJobEvent[]
} | null

interface AgentChatProgressProps {
  job: AgentJobLike
  copy: Translation['sourcing']['agentProgress']
}

const PHASE_META: Record<string, { role: string; avatar: string; tone: string }> = {
  queued: { role: 'Agent', avatar: 'AI', tone: 'bg-slate-50 text-slate-700 ring-slate-200' },
  parse: { role: 'Agent', avatar: 'AI', tone: 'bg-blue-50 text-blue-800 ring-blue-100' },
  retrieve: { role: 'Database', avatar: 'DB', tone: 'bg-amber-50 text-amber-800 ring-amber-100' },
  web: { role: 'Search', avatar: '🔎', tone: 'bg-indigo-50 text-indigo-800 ring-indigo-100' },
  think: { role: 'Researcher', avatar: '🧠', tone: 'bg-violet-50 text-violet-800 ring-violet-100' },
  rank: { role: 'Decision', avatar: '✓', tone: 'bg-emerald-50 text-emerald-800 ring-emerald-100' },
  completed: { role: 'Agent', avatar: '✓', tone: 'bg-emerald-50 text-emerald-800 ring-emerald-100' },
  failed: { role: 'System', avatar: '!', tone: 'bg-red-50 text-red-800 ring-red-100' },
}

function metaFor(phase: string) {
  return PHASE_META[phase] ?? { role: 'Agent', avatar: 'AI', tone: 'bg-slate-50 text-slate-700 ring-slate-200' }
}

function summarizeRun(events: SourcingJobEvent[]) {
  const searches = events.filter((event) => /搜索 \[|追加价格搜索|报价搜索/.test(event.message)).length
  const extractedPrices = events.filter((event) => /抽到价格|抽到明确价格/.test(event.message)).length
  const openedPages = events.filter((event) => /打开商品页|正在提取供应商信息|来源页面/.test(event.message)).length
  return { searches, extractedPrices, openedPages }
}

export function AgentChatProgress({ job, copy }: AgentChatProgressProps) {
  const backendProgress = job?.progress ?? 0
  const [displayedProgress, setDisplayedProgress] = useState(0)
  const events = useMemo(() => job?.events ?? [], [job?.events])
  const isRunning = !!job && job.status !== 'failed' && job.status !== 'completed'
  const progress = Math.round(displayedProgress)
  const statusLabel = job?.status === 'failed' ? copy.failedTitle : copy.runningTitle
  const eventListRef = useRef<HTMLDivElement | null>(null)
  const runSummary = useMemo(() => summarizeRun(events), [events])

  // Smooth progress: never exceed backend real progress, catch up ~0.3% per 200ms
  useEffect(() => {
    if (!job) return
    const timer = window.setInterval(() => {
      setDisplayedProgress((prev) => {
        if (job.status === 'completed') return 100
        if (job.status === 'failed') return prev
        return Math.min(backendProgress, prev + 0.3)
      })
    }, 200)
    return () => window.clearInterval(timer)
  }, [backendProgress, job, job?.status])

  // Auto-scroll to latest message
  useEffect(() => {
    const list = eventListRef.current
    if (!list) return
    requestAnimationFrame(() => {
      list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
    })
  }, [events.length, job?.status])

  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm ring-1 ring-slate-100 print:hidden">
      <div className="border-b border-slate-100 bg-gradient-to-br from-slate-950 via-blue-950 to-slate-900 px-6 py-5 text-white">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/12 text-sm font-bold text-white ring-1 ring-white/20 backdrop-blur">
              {isRunning ? (
                <span className="relative flex h-5 w-5 items-center justify-center" aria-label="Agent is working">
                  <span className="absolute h-5 w-5 animate-ping rounded-full bg-sky-300/60" />
                  <span className="h-3 w-3 animate-pulse rounded-full bg-sky-100" />
                </span>
              ) : (
                'AI'
              )}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-200">{copy.eyebrow}</p>
              <h2 className="mt-1 text-lg font-semibold text-white">{statusLabel}</h2>
              {isRunning && (
                <div className="mt-2 inline-flex items-center gap-2 rounded-full bg-sky-400/15 px-2.5 py-1 text-xs font-semibold text-sky-100 ring-1 ring-sky-300/30">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-300 opacity-70" />
                    <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-200" />
                  </span>
                  {copy.activeLabel}
                </div>
              )}
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                小型 Agent 聊天窗口：展示真实搜索、打开页面、抽取证据、过滤和排序过程；不展示模型隐藏草稿。
              </p>
            </div>
          </div>
          <div className="rounded-2xl bg-white/10 px-4 py-3 text-right ring-1 ring-white/15 backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">{copy.progress}</p>
            <p className="text-2xl font-semibold text-white">{progress}%</p>
          </div>
        </div>

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10 ring-1 ring-white/10">
          <div className="relative h-full overflow-hidden rounded-full bg-sky-300 transition-[width] duration-700 ease-out" style={{ width: `${progress}%` }}>
            {isRunning && <span className="absolute inset-0 animate-pulse bg-white/40" />}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
          <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/10">消息 {events.length}</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/10">搜索 {runSummary.searches}</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/10">开页 {runSummary.openedPages}</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1 ring-1 ring-white/10">抽价 {runSummary.extractedPrices}</span>
        </div>
      </div>

      <div className="bg-slate-50/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{copy.thoughtLogLabel}</p>
        <div ref={eventListRef} className="mt-3 max-h-[420px] space-y-3 overflow-auto rounded-2xl border border-slate-200 bg-white p-3 pr-2 shadow-inner">
          {events.length === 0 ? (
            <p className="px-2 py-8 text-center text-sm leading-6 text-slate-500 italic">{copy.emptyText}</p>
          ) : (
            events.map((event) => {
              const meta = metaFor(event.phase)
              return (
                <div key={`${event.timestamp}-${event.phase}-${event.message}`} className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-900 text-[11px] font-bold text-white shadow-sm">
                    {meta.avatar}
                  </div>
                  <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md bg-white px-3.5 py-3 shadow-sm ring-1 ring-slate-200">
                    <div className="mb-1.5 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${meta.tone}`}>{meta.role}</span>
                      <span className="text-[11px] text-slate-400 tabular-nums">{new Date(event.timestamp).toLocaleTimeString()}</span>
                      <span className="text-[11px] text-slate-300">{event.progress}%</span>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{event.message}</p>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    </section>
  )
}
