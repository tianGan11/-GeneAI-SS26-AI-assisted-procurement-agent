// ---------------------------------------------------------------------------
// Shared domain types for the Fuyao procurement SaaS shell.
// NOTE: This is a front-end-only prototype. Everything below is wired to mock
// JSON data; the shapes are designed so a real backend can drop in later.
// ---------------------------------------------------------------------------

export type Language = 'en' | 'zh'

export type ModuleId = 'sourcing' | 'comparison' | 'memory' | 'settings'

// --- Auth ------------------------------------------------------------------

export interface AuthUser {
  email: string
  name: string
  company: string
  role: string
}

/** A secret stored in the (mock) cloud key vault. Value is never shown raw. */
export interface VaultKey {
  id: string
  label: string
  /** Last 4 chars only, for display. The full value is treated as write-only. */
  maskedValue: string
  updatedAt: number
}

// --- Sourcing (supplier discovery) -----------------------------------------

export type SupplierCategoryKey =
  | 'waterDeflector' // 挡水条
  | 'glassAdhesive' // 玻璃胶 / urethane
  | 'rubberSeal' // 密封条 / weatherstrip
  | 'glassRaw' // 玻璃原片 / float glass
  | 'hardware' // 五金件 / mounting hardware
  | 'packaging' // 包装材料
  | 'cleaning'
  | 'office'
  | 'safetyShoes'
  | 'firstAid'
  | 'equipment'
  | string

export interface Supplier {
  id: string
  name: string
  category: SupplierCategoryKey
  /** Detail fields below are optional: real (scraped) data may not have them. */
  country?: string
  city?: string
  address?: string
  contactPerson?: string
  phone?: string
  email?: string
  website?: string
  /** Headcount band, e.g. "250–500". */
  employees?: string
  /** Annual revenue band, e.g. "€ 80M–120M". */
  annualRevenue?: string
  established?: number
  capabilities?: string[]
  certifications?: string[]
  /** URLs fetched during deep supplier research. */
  sourceUrls?: string[]
  /** Short text snippets supporting the extracted supplier profile. */
  evidenceSnippets?: string[]
  /** 0–100 relevance to the query. */
  matchScore: number
}

// --- Comparison (standard-product price benchmarking) ----------------------

export type PaymentTermKey = 'onAccount' | 'prepayment' | 'card'

export interface ComparisonItem {
  id: string
  vendor: string
  platform: string
  product: string
  matchScore: number
  /** Numeric unit price in EUR — used for sorting. */
  unitPriceEur: number
  /** Original localized price label, e.g. "€ 2.180 / Stk." */
  unitLabel: string
  /** Numeric lead time in days — used for sorting. */
  deliveryDays: number
  deliveryLabel: string
  paymentTerm: PaymentTermKey
  paymentLabel: string
  deliveryMethod: string
  rating: number
  reviews: number
}

export type DeliveryOptionKey = 'unlimited' | 'within3' | 'within7'

/** User-set ranking weights (percentages that always sum to 100). */
export interface FactorWeights {
  price: number
  delivery: number
  rating: number
}

// --- Memory + feedback -----------------------------------------------------

export interface FeedbackRecord {
  /** Name of the chosen supplier / vendor. */
  chosenName: string
  /** 0–5 stars each. */
  quality: number
  logistics: number
  priceSatisfaction: number
  service: number
  comment: string
  submittedAt: number
}

/** Raw input values needed to re-run / reopen a past conversation. */
export interface ConversationRestore {
  query: string
  minPrice?: string
  maxPrice?: string
  deliveryTime?: DeliveryOptionKey
  weights?: FactorWeights
}

/** One logged query + everything the user typed for it. */
export interface ConversationRecord {
  id: string
  module: Extract<ModuleId, 'sourcing' | 'comparison'>
  query: string
  /** Human-readable filter summary for display in the memory list. */
  filters: Record<string, string>
  /** Raw input values so the conversation can be reopened in its module. */
  restore?: ConversationRestore
  resultCount: number
  /** Names of the candidates returned, so feedback can reference them. */
  candidateNames: string[]
  timestamp: number
  feedback?: FeedbackRecord
}
