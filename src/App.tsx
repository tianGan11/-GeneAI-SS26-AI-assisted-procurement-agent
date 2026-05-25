import { useState } from 'react'

type Language = 'en' | 'zh'
type MenuId = 'sourcing' | 'comparison'
type DeliveryOptionKey = 'unlimited' | 'within3' | 'within7'

interface ComparisonRow {
  id: string
  vendor: string
  platform: string
  product: string
  matchScore: number
  unitPrice: string
  deliveryCycle: string
  paymentMethod: string
  deliveryMethod: string
  rating: number
  reviews: string
  highlight?: boolean
}

/** EU-sourced procurement records — original EN/DE text, never translated with UI language */
const COMPARISON_DATA: ComparisonRow[] = [
  {
    id: '1',
    vendor: 'Bechtle AG',
    platform: 'Bechtle Online Shop',
    product: 'Cisco ISR 4331 — Enterprise Router (Generalüberholt)',
    matchScore: 96,
    unitPrice: '€ 2.180 / Stk.',
    deliveryCycle: '3–5 Werktage',
    paymentMethod: 'Invoice (Rechnung 30 Tage)',
    deliveryMethod: 'DHL Express',
    rating: 4.8,
    reviews: '124 reviews',
    highlight: true,
  },
  {
    id: '2',
    vendor: 'Saturn Business',
    platform: 'MediaMarktSaturn Pro',
    product: 'Ubiquiti UniFi Dream Machine Pro — Gateway & Controller',
    matchScore: 91,
    unitPrice: '€ 1.950 / unit',
    deliveryCycle: '5–7 business days',
    paymentMethod: 'Credit Card / PayPal',
    deliveryMethod: 'UPS Standard',
    rating: 4.6,
    reviews: '89 reviews',
  },
  {
    id: '3',
    vendor: 'Axesso Systems GmbH',
    platform: 'ITscope B2B Marketplace',
    product: 'HPE Aruba Instant On AP22 (5-Pack) — WLAN Access Point',
    matchScore: 88,
    unitPrice: '€ 2.320 / Stk.',
    deliveryCycle: '7–10 Werktage',
    paymentMethod: 'Prepayment (Vorkasse)',
    deliveryMethod: 'Freight Forwarding (Spedition)',
    rating: 4.5,
    reviews: '56 Bewertungen',
  },
]

interface Translations {
  sidebar: {
    modules: string
    sourcing: string
    comparison: string
    tagline: string
  }
  header: {
    subtitle: string
  }
  modules: Record<MenuId, string>
  steps: [string, string, string]
  comparison: {
    inputTitle: string
    inputDesc: string
    placeholder: string
    hint: string
    analyze: string
    analyzing: string
    hardFiltersTitle: string
    hardFiltersEn: string
    budgetLabel: string
    budgetLabelEn: string
    deliveryLabel: string
    deliveryLabelEn: string
    minPlaceholder: string
    maxPlaceholder: string
    deliveryOptions: Record<DeliveryOptionKey, string>
    tableTitle: string
    tableSubtitle: string
    analysisComplete: string
    tableVendor: string
    tableMatch: string
    tablePrice: string
    tableDelivery: string
    tablePayment: string
    tableDeliveryMethod: string
    tableRating: string
    tableAction: string
    recommended: string
    viewDetails: string
    exportExcel: string
    exporting: string
    exportSuccessAlert: string
    printPdf: string
  }
  sourcing: {
    title: string
    description: string
  }
}

const translations: Record<Language, Translations> = {
  en: {
    sidebar: {
      modules: 'Modules',
      sourcing: 'Supplier Sourcing',
      comparison: 'Quote Comparison',
      tagline: 'Intelligent procurement decision assistant',
    },
    header: {
      subtitle: 'AI-powered structured procurement analysis & benchmarking',
    },
    modules: {
      sourcing: 'Supplier Sourcing',
      comparison: 'Quote Comparison',
    },
    steps: [
      'Understand requirements',
      'Search suppliers globally',
      'Generate structured comparison',
    ],
    comparison: {
      inputTitle: 'Procurement requirement',
      inputDesc: 'Describe your needs in natural language — AI will parse and benchmark across the web',
      placeholder:
        'Enter your procurement needs, e.g.: We need to purchase a batch of enterprise-grade routers...',
      hint: 'Include specs, quantity, budget, delivery requirements, and other key details',
      analyze: 'Start analysis',
      analyzing: 'Analyzing...',
      hardFiltersTitle: 'Pre-filter conditions',
      hardFiltersEn: '(Hard Filters)',
      budgetLabel: 'Budget limit',
      budgetLabelEn: '(Budget Limit)',
      deliveryLabel: 'Delivery time',
      deliveryLabelEn: '(Delivery Time)',
      minPlaceholder: 'Min',
      maxPlaceholder: 'Max',
      deliveryOptions: {
        unlimited: 'No limit',
        within3: 'Within 3 business days',
        within7: 'Within 7 business days',
      },
      tableTitle: 'Decision comparison table',
      tableSubtitle: 'Found 3 suppliers — ranked by match score and total cost',
      analysisComplete: 'Analysis complete',
      tableVendor: 'Vendor / Platform',
      tableMatch: 'Product match',
      tablePrice: 'Unit price',
      tableDelivery: 'Lead time',
      tablePayment: 'Payment Method',
      tableDeliveryMethod: 'Delivery Method',
      tableRating: 'Rating',
      tableAction: 'Action',
      recommended: 'Top pick',
      viewDetails: 'View details',
      exportExcel: 'Export Excel',
      exporting: 'Exporting...',
      exportSuccessAlert: 'Excel report exported successfully!',
      printPdf: 'Print / Download PDF',
    },
    sourcing: {
      title: 'Supplier Sourcing',
      description:
        'This module is under construction. Switch to Quote Comparison to explore the full workflow.',
    },
  },
  zh: {
    sidebar: {
      modules: '功能模块',
      sourcing: '供应商寻源',
      comparison: '标准品比价',
      tagline: '智能采购决策助手',
    },
    header: {
      subtitle: '基于 AI 的结构化采购分析与比价',
    },
    modules: {
      sourcing: '供应商寻源',
      comparison: '标准品比价',
    },
    steps: ['理解采购需求', '全网检索供应商', '生成结构化对比'],
    comparison: {
      inputTitle: '采购需求输入',
      inputDesc: '用自然语言描述您的采购需求，AI 将自动解析并全网比价',
      placeholder: '请输入采购需求，例如：需要采购一批企业级路由器...',
      hint: '支持描述规格、数量、预算、交付要求等关键信息',
      analyze: '开始分析',
      analyzing: '分析中...',
      hardFiltersTitle: '前置条件过滤',
      hardFiltersEn: '(Hard Filters)',
      budgetLabel: '价格区间',
      budgetLabelEn: '(Budget Limit)',
      deliveryLabel: '配送时效',
      deliveryLabelEn: '(Delivery Time)',
      minPlaceholder: '最低',
      maxPlaceholder: '最高',
      deliveryOptions: {
        unlimited: '不限时效',
        within3: '3个工作日内',
        within7: '7个工作日内',
      },
      tableTitle: '决策对比表',
      tableSubtitle: '已检索 3 家供应商，按匹配度与综合成本排序',
      analysisComplete: '分析完成',
      tableVendor: '供应商 / 平台',
      tableMatch: '产品匹配度',
      tablePrice: '单价',
      tableDelivery: '交货周期',
      tablePayment: '付款方式',
      tableDeliveryMethod: '配送方式',
      tableRating: '用户评分',
      tableAction: '操作',
      recommended: '推荐',
      viewDetails: '查看详情',
      exportExcel: '导出 Excel',
      exporting: '导出中...',
      exportSuccessAlert: 'Excel 报表导出成功！',
      printPdf: '打印 / 下载 PDF',
    },
    sourcing: {
      title: '供应商寻源',
      description: '该模块正在建设中。请切换至「标准品比价」体验完整工作流。',
    },
  },
}

const FUYAO_LOGO_SRC = '/fuyao-europe-logo.png'
const SIDEBAR_WIDTH_CLASS = 'w-[260px]'

const DELIVERY_OPTION_KEYS: DeliveryOptionKey[] = ['unlimited', 'within3', 'within7']

const MENU_ICONS: Record<MenuId, React.ReactNode> = {
  sourcing: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  ),
  comparison: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  ),
}

function LanguageToggle({
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
          language === 'en'
            ? 'bg-white text-blue-600 shadow-sm'
            : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        EN
      </button>
      <span className="px-0.5 text-slate-300">/</span>
      <button
        type="button"
        onClick={() => onChange('zh')}
        className={`rounded px-2.5 py-1 transition-all duration-200 ${
          language === 'zh'
            ? 'bg-white text-blue-600 shadow-sm'
            : 'text-slate-400 hover:text-slate-600'
        }`}
      >
        CN
      </button>
    </div>
  )
}

function UserRatingDisplay({ rating, reviews }: { rating: number; reviews: string }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-sm text-slate-700">
      <span className="font-semibold text-slate-900">{rating.toFixed(1)}</span>
      <span className="text-amber-400">★</span>
      <span className="text-slate-500">({reviews})</span>
    </span>
  )
}

function MatchScoreBadge({ score }: { score: number }) {
  const color =
    score >= 95
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
      : score >= 90
        ? 'bg-blue-50 text-blue-700 ring-blue-600/20'
        : 'bg-slate-50 text-slate-600 ring-slate-500/20'

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-blue-600 transition-all"
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset ${color}`}>
        {score}%
      </span>
    </div>
  )
}

function Sidebar({
  activeMenu,
  onMenuChange,
  t,
}: {
  activeMenu: MenuId
  onMenuChange: (id: MenuId) => void
  t: Translations
}) {
  const menuItems: { id: MenuId; label: string }[] = [
    { id: 'sourcing', label: t.sidebar.sourcing },
    { id: 'comparison', label: t.sidebar.comparison },
  ]

  return (
    <aside
      className={`relative z-10 flex ${SIDEBAR_WIDTH_CLASS} shrink-0 flex-col overflow-y-auto bg-slate-900 text-slate-300 shadow-[4px_0_10px_rgba(0,0,0,0.1)] print:hidden`}
    >
      <nav className="flex-1 space-y-1 px-3 py-4">
        <p className="mb-2 px-3 text-[11px] font-medium uppercase tracking-wider text-slate-500">
          {t.sidebar.modules}
        </p>
        {menuItems.map((item) => {
          const isActive = activeMenu === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onMenuChange(item.id)}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-900/30'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <span className={isActive ? 'text-white' : 'text-slate-500'}>{MENU_ICONS[item.id]}</span>
              {item.label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

function TopNavbar({
  moduleTitle,
  subtitle,
  language,
  onLanguageChange,
}: {
  moduleTitle: string
  subtitle: string
  language: Language
  onLanguageChange: (lang: Language) => void
}) {
  return (
    <header className="flex w-full shrink-0 items-center bg-white shadow-sm print:hidden">
      <div className={`flex shrink-0 items-center px-5 py-4 ${SIDEBAR_WIDTH_CLASS}`}>
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
        <div className="flex shrink-0 items-center">
          <LanguageToggle language={language} onChange={onLanguageChange} />
        </div>
      </div>
    </header>
  )
}

function StepIndicator({ currentStep, steps }: { currentStep: number; steps: [string, string, string] }) {
  const totalSteps = steps.length

  return (
    <div className="flex items-center justify-between">
      {steps.map((label, index) => {
        const stepNum = index + 1
        const isCompleted =
          stepNum < currentStep || (stepNum === currentStep && currentStep === totalSteps)
        const isInProgress = stepNum === currentStep && currentStep < totalSteps
        const isPending = stepNum > currentStep
        const isLast = index === steps.length - 1
        const connectorFilled =
          stepNum < currentStep || (stepNum === currentStep && currentStep === totalSteps)

        return (
          <div key={label} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-2">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition-all duration-300 ${
                  isCompleted
                    ? 'bg-blue-600 text-white'
                    : isInProgress
                      ? 'bg-blue-600 text-white'
                      : isPending
                        ? 'border border-gray-200 bg-gray-100 text-gray-400'
                        : 'bg-gray-100 text-gray-400'
                }`}
              >
                {isCompleted ? (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                ) : (
                  stepNum
                )}
              </div>
              <span
                className={`max-w-[140px] text-center text-xs font-medium ${
                  isCompleted ? 'text-blue-600' : isInProgress ? 'text-blue-700' : 'text-gray-400'
                }`}
              >
                {label}
              </span>
            </div>
            {!isLast && (
              <div
                className={`mx-4 mb-6 h-0.5 flex-1 transition-colors duration-300 ${
                  connectorFilled ? 'bg-blue-600' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

function ExportPrintToolbar({ t }: { t: Translations['comparison'] }) {
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = () => {
    if (isExporting) return
    setIsExporting(true)
    setTimeout(() => {
      setIsExporting(false)
      alert(t.exportSuccessAlert)
    }, 2000)
  }

  const handlePrint = () => {
    window.print()
  }

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      <button
        type="button"
        onClick={handleExport}
        disabled={isExporting}
        className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-medium text-blue-600 shadow-sm transition-all hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {isExporting ? (
          <>
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {t.exporting}
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 5.25h17.25M3.375 9.75h17.25m-17.25 4.5h17.25m-17.25 4.5h17.25" />
            </svg>
            {t.exportExcel}
          </>
        )}
      </button>
      <button
        type="button"
        onClick={handlePrint}
        className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-md shadow-blue-600/20 transition-all hover:bg-blue-700"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18M6.34 18H17.66M6.34 18v-2.25c0-1.036.84-1.875 1.875-1.875h11.25c1.035 0 1.875.84 1.875 1.875V18M9 6.75V4.875C9 3.84 9.84 3 10.875 3h2.25C14.16 3 15 3.84 15 4.875V6.75" />
        </svg>
        {t.printPdf}
      </button>
    </div>
  )
}

const STICKY_COL_HEAD =
  'sticky left-0 z-20 min-w-[240px] border-r border-gray-100 bg-slate-50 px-4 py-3.5 text-left align-middle shadow-[2px_0_5px_rgba(0,0,0,0.03)]'

function ComparisonTable({ data, t }: { data: ComparisonRow[]; t: Translations['comparison'] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-[1200px] w-full border-collapse text-left text-sm align-middle">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50">
            <th className={`${STICKY_COL_HEAD} text-xs font-semibold uppercase tracking-wider text-slate-500`}>
              {t.tableVendor}
            </th>
            <th className="min-w-[140px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tableMatch}
            </th>
            <th className="min-w-[110px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tablePrice}
            </th>
            <th className="min-w-[120px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tableDelivery}
            </th>
            <th className="min-w-[160px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tablePayment}
            </th>
            <th className="min-w-[150px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tableDeliveryMethod}
            </th>
            <th className="min-w-[130px] px-4 py-3.5 align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tableRating}
            </th>
            <th className="min-w-[100px] px-4 py-3.5 text-left align-middle text-xs font-semibold uppercase tracking-wider text-slate-500">
              {t.tableAction}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {data.map((row) => {
            const stickyCellBg = row.highlight ? 'bg-blue-50' : 'bg-white'

            return (
              <tr
                key={row.id}
                className={`transition-colors hover:bg-slate-50/80 ${
                  row.highlight ? 'bg-blue-50/40' : ''
                }`}
              >
                <td
                  className={`sticky left-0 z-10 min-w-[240px] border-r border-gray-100 px-4 py-4 align-middle shadow-[2px_0_5px_rgba(0,0,0,0.03)] ${stickyCellBg}`}
                >
                  <div className="min-w-0">
                    <div className="mb-0.5 flex items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900">{row.vendor}</p>
                      {row.highlight && (
                        <span className="shrink-0 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold uppercase text-white">
                          {t.recommended}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500">{row.platform}</p>
                    <p className="mt-1 text-sm text-gray-500">{row.product}</p>
                  </div>
                </td>
                <td className="px-4 py-4 align-middle">
                  <MatchScoreBadge score={row.matchScore} />
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm font-semibold whitespace-nowrap text-slate-900">{row.unitPrice}</span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm text-gray-600">{row.deliveryCycle}</span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm text-gray-600">{row.paymentMethod}</span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <span className="text-sm text-gray-600">{row.deliveryMethod}</span>
                </td>
                <td className="px-4 py-4 align-middle">
                  <UserRatingDisplay rating={row.rating} reviews={row.reviews} />
                </td>
                <td className="px-4 py-4 text-left align-middle">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 whitespace-nowrap rounded-md py-1.5 text-sm font-medium text-blue-600 transition-colors hover:bg-blue-50 print:hidden"
                  >
                    {t.viewDetails}
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function PriceInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <div className="relative w-28">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-slate-400">
        €
      </span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-slate-200 bg-white py-1.5 pl-7 pr-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400/30"
      />
    </div>
  )
}

function HardFilters({
  minPrice,
  maxPrice,
  deliveryTime,
  onMinPriceChange,
  onMaxPriceChange,
  onDeliveryTimeChange,
  t,
}: {
  minPrice: string
  maxPrice: string
  deliveryTime: DeliveryOptionKey
  onMinPriceChange: (value: string) => void
  onMaxPriceChange: (value: string) => void
  onDeliveryTimeChange: (value: DeliveryOptionKey) => void
  t: Translations['comparison']
}) {
  return (
    <div className="mt-4 rounded-lg bg-gray-50 px-4 py-3.5">
      <div className="flex flex-wrap items-start gap-8">
        <div>
          <label className="mb-2 block text-sm text-slate-600">
            {t.budgetLabel}{' '}
            <span className="text-slate-400">{t.budgetLabelEn}</span>
          </label>
          <div className="flex items-center gap-2">
            <PriceInput value={minPrice} onChange={onMinPriceChange} placeholder={t.minPlaceholder} />
            <span className="text-sm text-slate-400">—</span>
            <PriceInput value={maxPrice} onChange={onMaxPriceChange} placeholder={t.maxPlaceholder} />
          </div>
        </div>
        <div>
          <label className="mb-2 block text-sm text-slate-600">
            {t.deliveryLabel}{' '}
            <span className="text-slate-400">{t.deliveryLabelEn}</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {DELIVERY_OPTION_KEYS.map((key) => {
              const isSelected = deliveryTime === key
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => onDeliveryTimeChange(key)}
                  className={`rounded-full px-3 py-1 text-sm transition-colors duration-200 ${
                    isSelected
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  {t.deliveryOptions[key]}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

function QuoteComparisonContent({ t }: { t: Translations }) {
  const c = t.comparison
  const [requirement, setRequirement] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [deliveryTime, setDeliveryTime] = useState<DeliveryOptionKey>('unlimited')
  const [currentStep, setCurrentStep] = useState(3)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleAnalyze = () => {
    setIsAnalyzing(true)
    setCurrentStep(1)
    setTimeout(() => setCurrentStep(2), 800)
    setTimeout(() => setCurrentStep(3), 1600)
    setTimeout(() => setIsAnalyzing(false), 2000)
  }

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden">
        <textarea
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
          rows={4}
          placeholder={c.hint}
          className="w-full resize-none rounded-lg border border-slate-200 bg-slate-50/50 px-4 py-3 text-sm text-slate-800 placeholder:text-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        />

        <HardFilters
          minPrice={minPrice}
          maxPrice={maxPrice}
          deliveryTime={deliveryTime}
          onMinPriceChange={setMinPrice}
          onMaxPriceChange={setMaxPrice}
          onDeliveryTimeChange={setDeliveryTime}
          t={c}
        />

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-600/25 transition-all hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isAnalyzing ? (
              <>
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {c.analyzing}
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                </svg>
                {c.analyze}
              </>
            )}
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white px-8 py-6 shadow-sm print:hidden">
        <StepIndicator currentStep={currentStep} steps={t.steps} />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:border-0 print:shadow-none">
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{c.tableTitle}</h2>
            <p className="mt-0.5 text-sm text-slate-500">{c.tableSubtitle}</p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-600/20 print:hidden">
              {c.analysisComplete}
            </span>
            <ExportPrintToolbar t={c} />
          </div>
        </div>
        <ComparisonTable data={COMPARISON_DATA} t={c} />
      </section>
    </div>
  )
}

function SourcingPlaceholder({ t }: { t: Translations }) {
  return (
    <section className="flex min-h-[400px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center shadow-sm">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      </div>
      <p className="max-w-md text-sm text-slate-500">{t.sourcing.description}</p>
    </section>
  )
}

function App() {
  const [language, setLanguage] = useState<Language>('en')
  const [activeMenu, setActiveMenu] = useState<MenuId>('comparison')
  const t = translations[language]

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-slate-100">
      <TopNavbar
        moduleTitle={t.modules[activeMenu]}
        subtitle={t.header.subtitle}
        language={language}
        onLanguageChange={setLanguage}
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar activeMenu={activeMenu} onMenuChange={setActiveMenu} t={t} />

        <main className="min-w-0 flex-1 overflow-y-auto bg-slate-100 p-8 print:p-4">
          {activeMenu === 'comparison' ? (
            <QuoteComparisonContent t={t} />
          ) : (
            <SourcingPlaceholder t={t} />
          )}
        </main>
      </div>
    </div>
  )
}

export default App
