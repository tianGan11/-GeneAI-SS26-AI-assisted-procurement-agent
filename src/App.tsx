import { useState } from 'react'
import type { ConversationRecord, Language, ModuleId } from './types'
import { translations } from './i18n'
import { loadJSON, saveJSON, STORAGE_KEYS } from './lib/storage'
import { AuthProvider, useAuth } from './context/AuthContext'
import { MemoryProvider } from './context/MemoryContext'
import { Sidebar } from './components/Sidebar'
import { TopNavbar } from './components/TopNavbar'
import { LoginPage } from './modules/LoginPage'
import { SourcingModule } from './modules/SourcingModule'
import { ComparisonModule } from './modules/ComparisonModule'
import { MemoryModule } from './modules/MemoryModule'
import { SettingsPage } from './modules/SettingsPage'

function Workspace({
  language,
  setLanguage,
}: {
  language: Language
  setLanguage: (lang: Language) => void
}) {
  const { user } = useAuth()
  const [activeModule, setActiveModule] = useState<ModuleId>('sourcing')
  // A conversation queued to reopen inside its source module (from Memory).
  const [restore, setRestore] = useState<ConversationRecord | null>(null)
  const t = translations[language]

  // Manual navigation starts the module fresh; opening from Memory restores it.
  const goToModule = (id: ModuleId) => {
    setRestore(null)
    setActiveModule(id)
  }
  const openConversation = (conv: ConversationRecord) => {
    setRestore(conv)
    setActiveModule(conv.module)
  }

  if (!user) {
    return <LoginPage t={t} language={language} onLanguageChange={setLanguage} />
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-slate-100 print:h-auto print:overflow-visible">
      <TopNavbar
        moduleTitle={t.module[activeModule].title}
        subtitle={t.module[activeModule].subtitle}
        language={language}
        onLanguageChange={setLanguage}
        t={t}
      />
      <div className="flex min-h-0 flex-1 overflow-hidden print:overflow-visible">
        <Sidebar active={activeModule} onChange={goToModule} t={t} />
        <main className="min-w-0 flex-1 overflow-y-auto bg-slate-100 p-8 print:overflow-visible print:p-0">
          {activeModule === 'sourcing' && (
            <SourcingModule t={t} restore={restore?.module === 'sourcing' ? restore : null} />
          )}
          {activeModule === 'comparison' && (
            <ComparisonModule t={t} restore={restore?.module === 'comparison' ? restore : null} />
          )}
          {activeModule === 'memory' && (
            <MemoryModule t={t} language={language} onOpen={openConversation} />
          )}
          {activeModule === 'settings' && <SettingsPage t={t} language={language} />}
        </main>
      </div>
    </div>
  )
}

function App() {
  const [language, setLanguageState] = useState<Language>(() =>
    loadJSON<Language>(STORAGE_KEYS.language, 'en'),
  )

  const setLanguage = (lang: Language) => {
    setLanguageState(lang)
    saveJSON(STORAGE_KEYS.language, lang)
  }

  return (
    <AuthProvider>
      <MemoryProvider>
        <Workspace language={language} setLanguage={setLanguage} />
      </MemoryProvider>
    </AuthProvider>
  )
}

export default App
