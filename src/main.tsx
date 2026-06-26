import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'

// ── Global error handlers ──────────────────────────────────────────────────
// React 19 + Vite 8 dev: unhandled promise rejections (from async effects,
// SSE parsing errors, etc.) cause Vite's HMR client to do a full page reload.
// Swallow them here so a malformed event or transient API failure doesn't
// tear down the entire SPA.
window.addEventListener('unhandledrejection', (event) => {
  console.warn('[global] Unhandled promise rejection (suppressed to prevent Vite full reload):', event.reason)
  event.preventDefault()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
