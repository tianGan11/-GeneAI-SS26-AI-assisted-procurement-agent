import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  /** Optional custom fallback UI instead of the default error card. */
  fallback?: ReactNode
  /** Callback fired when an error is caught (for logging/reporting). */
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Error boundary — catches render-phase errors so they don't cascade into
 * a blank page or trigger a Vite HMR full-page reload in development.
 *
 * In React 19 + StrictMode + Vite 8, an uncaught error during render or
 * effect cleanup can cause React to tear down the entire tree, which Vite's
 * dev client interprets as "the app crashed" and falls back to a full reload.
 * This boundary prevents that cascade.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[ErrorBoundary] Caught:`, error)
    console.error(`[ErrorBoundary] Component stack:`, errorInfo.componentStack ?? '(none)')
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div className="mx-auto max-w-lg rounded-xl border border-red-200 bg-red-50 p-8 text-center">
          <svg
            className="mx-auto mb-4 h-10 w-10 text-red-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
          <h2 className="text-base font-semibold text-red-800">
            Something went wrong
          </h2>
          <p className="mt-1 text-sm text-red-600">
            {this.state.error?.message ?? 'An unexpected error occurred.'}
          </p>
          <button
            onClick={this.handleReset}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
