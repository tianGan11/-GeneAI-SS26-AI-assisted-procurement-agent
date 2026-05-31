import { useState } from 'react'
import type { Translation } from '../i18n'
import type { FeedbackRecord } from '../types'
import { StarRating } from './StarRating'

export function FeedbackModal({
  options,
  defaultChosen,
  t,
  onSubmit,
  onClose,
}: {
  options: string[]
  defaultChosen?: string
  t: Translation
  onSubmit: (feedback: FeedbackRecord) => void
  onClose: () => void
}) {
  const [chosen, setChosen] = useState(defaultChosen ?? options[0] ?? '')
  const [quality, setQuality] = useState(0)
  const [logistics, setLogistics] = useState(0)
  const [priceSat, setPriceSat] = useState(0)
  const [service, setService] = useState(0)
  const [comment, setComment] = useState('')
  const [done, setDone] = useState(false)

  const handleSubmit = () => {
    onSubmit({
      chosenName: chosen,
      quality,
      logistics,
      priceSatisfaction: priceSat,
      service,
      comment: comment.trim(),
      submittedAt: Date.now(),
    })
    setDone(true)
    setTimeout(onClose, 1200)
  }

  const ratingRows: { label: string; value: number; set: (v: number) => void }[] = [
    { label: t.feedback.quality, value: quality, set: setQuality },
    { label: t.feedback.logistics, value: logistics, set: setLogistics },
    { label: t.feedback.priceSat, value: priceSat, set: setPriceSat },
    { label: t.feedback.service, value: service, set: setService },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl">
        {done ? (
          <div className="flex flex-col items-center justify-center px-8 py-16 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <p className="text-base font-medium text-slate-800">{t.feedback.thanks}</p>
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{t.feedback.title}</h2>
                <p className="mt-0.5 text-sm text-slate-500">{t.feedback.subtitle}</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                aria-label={t.common.close}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="max-h-[60vh] space-y-5 overflow-y-auto px-6 py-5">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  {t.feedback.whichChosen}
                </label>
                <select
                  value={chosen}
                  onChange={(e) => setChosen(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                >
                  {options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-3 rounded-lg bg-slate-50 px-4 py-4">
                {ratingRows.map((row) => (
                  <div key={row.label} className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">{row.label}</span>
                    <StarRating value={row.value} onChange={row.set} />
                  </div>
                ))}
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  {t.feedback.comment}
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={3}
                  placeholder={t.feedback.commentPlaceholder}
                  className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
              >
                {t.common.cancel}
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition-colors hover:bg-blue-700"
              >
                {t.feedback.submit}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
