import type { Language } from '../types'

export function LanguageToggle({
  language,
  onChange,
}: {
  language: Language
  onChange: (lang: Language) => void
}) {
  return (
    <div className="flex items-center rounded-md border border-slate-200 bg-slate-50 p-0.5 text-xs font-semibold">
      <button
        type="button"
        onClick={() => onChange('en')}
        className={`rounded px-2.5 py-1 transition-all duration-200 ${
          language === 'en' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        EN
      </button>
      <span className="px-0.5 text-slate-300">/</span>
      <button
        type="button"
        onClick={() => onChange('zh')}
        className={`rounded px-2.5 py-1 transition-all duration-200 ${
          language === 'zh' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        CN
      </button>
    </div>
  )
}
