import { useState } from 'react'
import type { Translation } from '../i18n'
import { SpinnerIcon } from './icons'

export function StepIndicator({
  currentStep,
  steps,
}: {
  currentStep: number
  steps: [string, string, string]
}) {
  const totalSteps = steps.length
  return (
    <div className="flex items-center justify-between">
      {steps.map((label, index) => {
        const stepNum = index + 1
        const isCompleted = stepNum < currentStep || (stepNum === currentStep && currentStep === totalSteps)
        const isInProgress = stepNum === currentStep && currentStep < totalSteps
        const isLast = index === steps.length - 1
        const connectorFilled = stepNum < currentStep || (stepNum === currentStep && currentStep === totalSteps)
        return (
          <div key={label} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-2">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-all duration-300 ${
                  isCompleted || isInProgress ? 'bg-blue-600 text-white' : 'border border-gray-200 bg-gray-100 text-gray-400'
                }`}
              >
                {isCompleted ? (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  stepNum
                )}
              </div>
              <span
                className={`max-w-[140px] text-center text-xs font-medium ${
                  isCompleted ? 'text-blue-600' : isInProgress ? 'text-blue-700' : 'text-gray-400'
                }`}
              >
                {label}
              </span>
            </div>
            {!isLast && (
              <div
                className={`mx-4 mb-6 h-0.5 flex-1 transition-colors duration-300 ${
                  connectorFilled ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function MatchScoreBadge({ score }: { score: number }) {
  const color =
    score >= 95
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
      : score >= 90
        ? 'bg-blue-50 text-blue-700 ring-blue-600/20'
        : 'bg-slate-50 text-slate-600 ring-slate-500/20'
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${score}%` }} />
      </div>
      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset ${color}`}>
        {score}%
      </span>
    </div>
  )
}

export function ExportPrintToolbar({ t }: { t: Translation }) {
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = () => {
    if (isExporting) return
    setIsExporting(true)
    // MOCK export — a real build would stream an .xlsx from the backend.
    setTimeout(() => {
      setIsExporting(false)
      alert(t.common.exportSuccess)
    }, 1500)
  }

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      <button
        type="button"
        onClick={handleExport}
        disabled={isExporting}
        className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-600 shadow-sm transition-all hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isExporting ? (
          <>
            <SpinnerIcon />
            {t.common.exporting}
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 5.25h17.25M3.375 9.75h17.25m-17.25 4.5h17.25m-17.25 4.5h17.25" />
            </svg>
            {t.common.exportExcel}
          </>
        )}
      </button>
      <button
        type="button"
        onClick={() => window.print()}
        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-md shadow-blue-600/20 transition-all hover:bg-blue-700"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18M6.34 18H17.66M6.34 18v-2.25c0-1.036.84-1.875 1.875-1.875h11.25c1.035 0 1.875.84 1.875 1.875V18M9 6.75V4.875C9 3.84 9.84 3 10.875 3h2.25C14.16 3 15 3.84 15 4.875V6.75" />
        </svg>
        {t.common.printPdf}
      </button>
    </div>
  )
}

/** Shared "Start analysis" submit button with spinner. */
export function AnalyzeButton({
  isAnalyzing,
  onClick,
  t,
}: {
  isAnalyzing: boolean
  onClick: () => void
  t: Translation
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isAnalyzing}
      className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition-all hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
    >
      {isAnalyzing ? (
        <>
          <SpinnerIcon />
          {t.common.analyzing}
        </>
      ) : (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
          </svg>
          {t.common.analyze}
        </>
      )}
    </button>
  )
}
