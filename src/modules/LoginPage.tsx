import { useState } from 'react'
import type { Language } from '../types'
import type { Translation } from '../i18n'
import { useAuth } from '../context/AuthContext'
import { apiEnabled } from '../lib/api'
import { LanguageToggle } from '../components/LanguageToggle'
import { ShieldIcon, SpinnerIcon } from '../components/icons'

export function LoginPage({
  t,
  language,
  onLanguageChange,
}: {
  t: Translation
  language: Language
  onLanguageChange: (lang: Language) => void
}) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const canSubmit = email.includes('@') && password.length > 0 && !submitting

  // On success the user state flips and this whole page unmounts, so we only
  // reset `submitting` on failure.
  const submit = async (emailValue: string, passwordValue: string) => {
    setSubmitting(true)
    setError('')
    try {
      await login(emailValue, passwordValue)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
      setSubmitting(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    void submit(email.trim(), password)
  }

  const handleSso = () => {
    // Mock SSO shortcut (no real IdP wired yet).
    void submit(email.includes('@') ? email.trim() : 'sso.user@fuyao-europe.com', password || 'sso-demo')
  }

  return (
    <div className="flex min-h-screen w-full">
      {/* Brand panel */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-slate-900 p-12 text-white lg:flex">
        <img
          src="/fuyao-europe-logo.png"
          alt="Fuyao Europe"
          className="h-10 w-auto object-contain object-left brightness-0 invert"
        />
        <div>
          <h2 className="text-3xl font-bold leading-tight">{t.appName}</h2>
          <p className="mt-3 max-w-md text-slate-300">{t.login.subtitle}</p>
          <div className="mt-8 flex items-center gap-2 text-sm text-slate-400">
            <ShieldIcon className="h-5 w-5 text-emerald-400" />
            {t.login.secured}
          </div>
        </div>
        <p className="text-xs text-slate-500">© {new Date().getFullYear()} Fuyao Glass Europe</p>
      </div>

      {/* Form panel */}
      <div className="flex w-full flex-col bg-slate-50 lg:w-1/2">
        <div className="flex justify-end p-6">
          <LanguageToggle language={language} onChange={onLanguageChange} />
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-sm">
            <img
              src="/fuyao-europe-logo.png"
              alt="Fuyao Europe"
              className="mb-8 h-9 w-auto object-contain object-left lg:hidden"
            />
            <h1 className="text-2xl font-bold text-slate-900">{t.login.title}</h1>
            <p className="mt-1 text-sm text-slate-500">{t.login.subtitle}</p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.login.email}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t.login.emailPlaceholder}
                  autoComplete="username"
                  className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">{t.login.password}</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t.login.passwordPlaceholder}
                  autoComplete="current-password"
                  className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <SpinnerIcon />
                    {t.login.signingIn}
                  </>
                ) : (
                  t.login.signIn
                )}
              </button>

              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-center text-sm text-red-600">{error}</p>
              )}
            </form>

            {/* Mock-only affordances — hidden once a real backend is wired up. */}
            {!apiEnabled && (
              <>
                <div className="my-5 flex items-center gap-3 text-xs text-slate-400">
                  <span className="h-px flex-1 bg-slate-200" />
                  <span>·</span>
                  <span className="h-px flex-1 bg-slate-200" />
                </div>

                <button
                  type="button"
                  onClick={handleSso}
                  disabled={submitting}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <ShieldIcon className="h-4 w-4 text-blue-600" />
                  {t.login.sso}
                </button>

                <p className="mt-6 text-center text-xs text-slate-400">{t.login.demoHint}</p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
