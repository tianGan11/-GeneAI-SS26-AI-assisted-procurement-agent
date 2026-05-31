import type { ModuleId } from '../types'
import type { Translation } from '../i18n'
import { MODULE_ICONS } from './icons'

const MODULE_ORDER: ModuleId[] = ['sourcing', 'comparison', 'memory', 'settings']

export function Sidebar({
  active,
  onChange,
  t,
}: {
  active: ModuleId
  onChange: (id: ModuleId) => void
  t: Translation
}) {
  return (
    <aside className="relative z-10 flex w-[260px] shrink-0 flex-col overflow-y-auto bg-slate-900 text-slate-300 shadow-[4px_0_10px_rgba(0,0,0,0.1)] print:hidden">
      <nav className="flex-1 space-y-1 px-3 py-4">
        <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">
          {t.nav.modules}
        </p>
        {MODULE_ORDER.map((id) => {
          const isActive = active === id
          const Icon = MODULE_ICONS[id]
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <span className={isActive ? 'text-white' : 'text-slate-500'}>
                <Icon className="h-5 w-5" />
              </span>
              {t.nav[id]}
            </button>
          )
        })}
      </nav>
      <div className="px-5 py-4 text-[11px] text-slate-600">{t.tagline}</div>
    </aside>
  )
}
