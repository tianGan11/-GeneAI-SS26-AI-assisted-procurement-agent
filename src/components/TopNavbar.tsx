import { useState } from 'react'
import type { Language } from '../types'
import type { Translation } from '../i18n'
import { useAuth } from '../context/AuthContext'
import { LanguageToggle } from './LanguageToggle'

const FUYAO_LOGO_SRC = '/fuyao-europe-logo.png'

export function TopNavbar({
  moduleTitle,
  subtitle,
  language,
  onLanguageChange,
  t,
}: {
  moduleTitle: string
  subtitle: string
  language: Language
  onLanguageChange: (lang: Language) => void
  t: Translation
}) {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const initials = (user?.name ?? 'U')
    .split(' ')
    .map((s) => s.charAt(0))
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="flex w-full shrink-0 items-center bg-white shadow-sm print:hidden">
      <div className="flex w-[260px] shrink-0 items-center px-5 py-4">
        <img
          src={FUYAO_LOGO_SRC}
          alt="Fuyao Europe Logo"
          className="h-9 w-auto max-w-full object-contain object-left"
          width={180}
          height={40}
        />
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-between gap-6 py-4 pl-6 pr-10">
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-slate-900">{moduleTitle}</h1>
          <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-4">
          <LanguageToggle language={language} onChange={onLanguageChange} />
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 rounded-full border border-slate-200 py-1 pl-1 pr-3 transition-colors hover:bg-slate-50"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                {initials}
              </span>
              <span className="hidden text-sm font-medium text-slate-700 sm:block">{user?.name}</span>
            </button>
            {menuOpen && (
              <>
                <button
                  type="button"
                  className="fixed inset-0 z-10 cursor-default"
                  onClick={() => setMenuOpen(false)}
                  aria-hidden
                />
                <div className="absolute right-0 z-20 mt-2 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                  <div className="border-b border-slate-100 px-4 py-3">
                    <p className="text-sm font-semibold text-slate-900">{user?.name}</p>
                    <p className="truncate text-xs text-slate-500">{user?.email}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{user?.company}</p>
                  </div>
                  <button
                    type="button"
                    onClick={logout}
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-slate-600 transition-colors hover:bg-slate-50"
                  >
                    {t.nav.logout}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
