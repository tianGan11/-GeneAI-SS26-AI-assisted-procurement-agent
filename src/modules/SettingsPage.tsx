import { useState } from 'react'
import type { Language } from '../types'
import type { Translation } from '../i18n'
import { useAuth } from '../context/AuthContext'
import { ShieldIcon } from '../components/icons'

function formatTime(ts: number, language: Language): string {
  return new Date(ts).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-GB', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const SUGGESTED_KEYS = ['AI Search Provider', 'Pricing Data API', 'ERP Connector']

export function SettingsPage({ t, language }: { t: Translation; language: Language }) {
  const { user, vaultKeys, saveVaultKey } = useAuth()
  const s = t.settings
  const [label, setLabel] = useState(SUGGESTED_KEYS[0])
  const [secret, setSecret] = useState('')
  const [justSaved, setJustSaved] = useState(false)

  const handleSave = () => {
    if (!label.trim() || !secret.trim()) return
    saveVaultKey(label.trim(), secret.trim())
    setSecret('')
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 1500)
  }

  return (
    <div className="max-w-3xl space-y-6">
      {/* Account */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">{s.accountTitle}</h2>
        <dl className="mt-4 grid grid-cols-1 gap-y-3 sm:grid-cols-2">
          <Row label={s.name} value={user?.name ?? '—'} />
          <Row label={t.login.email} value={user?.email ?? '—'} />
          <Row label={s.company} value={user?.company ?? '—'} />
          <Row label={s.role} value={user?.role ?? '—'} />
        </dl>
      </section>

      {/* Key vault */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
            <ShieldIcon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">{s.vaultTitle}</h2>
            <p className="mt-0.5 text-sm text-slate-500">{s.vaultDesc}</p>
          </div>
        </div>

        <div className="mt-5 rounded-lg bg-slate-50 p-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[180px] flex-1">
              <label className="mb-1.5 block text-sm text-slate-600">{s.keyLabel}</label>
              <input
                list="suggested-keys"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30"
              />
              <datalist id="suggested-keys">
                {SUGGESTED_KEYS.map((k) => (
                  <option key={k} value={k} />
                ))}
              </datalist>
            </div>
            <div className="min-w-[200px] flex-1">
              <label className="mb-1.5 block text-sm text-slate-600">{s.keyValue}</label>
              <input
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder={s.keyPlaceholder}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30"
              />
            </div>
            <button
              type="button"
              onClick={handleSave}
              disabled={!label.trim() || !secret.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {justSaved ? t.common.saved : s.addKey}
            </button>
          </div>
        </div>

        <div className="mt-5">
          {vaultKeys.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-200 py-6 text-center text-sm text-slate-400">
              {s.noKeys}
            </p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
              {vaultKeys.map((key) => (
                <li key={key.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{key.label}</p>
                    <p className="font-mono text-xs text-slate-400">{key.maskedValue}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                      <ShieldIcon className="h-3 w-3" />
                      {s.encrypted}
                    </span>
                    <span className="text-xs text-slate-400">
                      {s.updated} {formatTime(key.updatedAt, language)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-700">{value}</dd>
    </div>
  )
}
