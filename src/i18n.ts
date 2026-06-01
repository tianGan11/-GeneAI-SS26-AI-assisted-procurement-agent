import type { Language, ModuleId, SupplierCategoryKey, PaymentTermKey, ComparisonSortKey } from './types'

// ---------------------------------------------------------------------------
// Bilingual (EN / 中文) UI strings. Domain text inside mock data stays in its
// original language and is never run through this table.
// ---------------------------------------------------------------------------

export interface Translation {
  appName: string
  tagline: string

  login: {
    title: string
    subtitle: string
    email: string
    emailPlaceholder: string
    password: string
    passwordPlaceholder: string
    signIn: string
    signingIn: string
    sso: string
    demoHint: string
    secured: string
  }

  nav: {
    modules: string
    sourcing: string
    comparison: string
    memory: string
    settings: string
    logout: string
  }

  module: Record<ModuleId, { title: string; subtitle: string }>

  steps: [string, string, string]

  common: {
    analyze: string
    analyzing: string
    resultsFound: (n: number) => string
    analysisComplete: string
    exportExcel: string
    exporting: string
    exportSuccess: string
    printPdf: string
    viewDetails: string
    select: string
    selected: string
    giveFeedback: string
    close: string
    cancel: string
    save: string
    saved: string
    empty: string
  }

  sourcing: {
    inputLabel: string
    placeholder: string
    hint: string
    categoryLabel: string
    categoryAll: string
    categories: Record<SupplierCategoryKey, string>
    cardAddress: string
    cardContact: string
    cardScale: string
    cardEmployees: string
    cardRevenue: string
    cardEstablished: string
    cardCapabilities: string
    cardCerts: string
    match: string
    colName: string
    colLocation: string
    colEmail: string
    colWebsite: string
  }

  comparison: {
    inputLabel: string
    placeholder: string
    hint: string
    hardFilters: string
    budget: string
    delivery: string
    minPrice: string
    maxPrice: string
    deliveryOptions: { unlimited: string; within3: string; within7: string }
    sortLabel: string
    sortOptions: Record<ComparisonSortKey, string>
    tableTitle: string
    colVendor: string
    colPlatform: string
    colProduct: string
    colMatch: string
    colPrice: string
    colDelivery: string
    colPayment: string
    colDeliveryMethod: string
    colRating: string
    colAction: string
    recommended: string
    paymentTerms: Record<PaymentTermKey, string>
  }

  memory: {
    title: string
    subtitle: string
    empty: string
    moduleCol: string
    queryCol: string
    filtersCol: string
    resultsCol: string
    feedbackCol: string
    timeCol: string
    noFeedback: string
    clearAll: string
    confirmClear: string
    chose: string
  }

  feedback: {
    title: string
    subtitle: string
    whichChosen: string
    quality: string
    logistics: string
    priceSat: string
    service: string
    comment: string
    commentPlaceholder: string
    submit: string
    thanks: string
  }

  settings: {
    vaultTitle: string
    vaultDesc: string
    encrypted: string
    keyLabel: string
    keyValue: string
    keyPlaceholder: string
    addKey: string
    updated: string
    never: string
    noKeys: string
    accountTitle: string
    name: string
    company: string
    role: string
  }
}

export const translations: Record<Language, Translation> = {
  en: {
    appName: 'Fuyao Procurement Cloud',
    tagline: 'Intelligent procurement decision assistant',
    login: {
      title: 'Sign in to your workspace',
      subtitle: 'Enterprise procurement intelligence platform',
      email: 'Work email',
      emailPlaceholder: 'you@fuyao-europe.com',
      password: 'Password',
      passwordPlaceholder: 'Enter your password',
      signIn: 'Sign in',
      signingIn: 'Signing in...',
      sso: 'Continue with Enterprise SSO',
      demoHint: 'Demo: any email + password works (prototype, no real backend).',
      secured: 'Secured with end-to-end encryption · SOC 2 · ISO 27001',
    },
    nav: {
      modules: 'Modules',
      sourcing: 'Supplier Sourcing',
      comparison: 'Quote Comparison',
      memory: 'Conversation Memory',
      settings: 'Settings & Keys',
      logout: 'Sign out',
    },
    module: {
      sourcing: {
        title: 'Supplier Sourcing',
        subtitle: 'Find glass & automotive supply-chain suppliers across Europe',
      },
      comparison: {
        title: 'Quote Comparison',
        subtitle: 'AI-powered structured price benchmarking for standard products',
      },
      memory: {
        title: 'Conversation Memory',
        subtitle: 'Every query and input you have made is remembered here',
      },
      settings: {
        title: 'Settings & Keys',
        subtitle: 'Manage your account and securely stored API keys',
      },
    },
    steps: ['Understand requirements', 'Search suppliers', 'Generate structured output'],
    common: {
      analyze: 'Start analysis',
      analyzing: 'Analyzing...',
      resultsFound: (n) => `Found ${n} result${n === 1 ? '' : 's'}`,
      analysisComplete: 'Analysis complete',
      exportExcel: 'Export Excel',
      exporting: 'Exporting...',
      exportSuccess: 'Report exported successfully!',
      printPdf: 'Print / PDF',
      viewDetails: 'Details',
      select: 'Select this',
      selected: 'Selected',
      giveFeedback: 'Select & rate',
      close: 'Close',
      cancel: 'Cancel',
      save: 'Save',
      saved: 'Saved',
      empty: 'No data yet.',
    },
    sourcing: {
      inputLabel: 'What are you sourcing?',
      placeholder:
        'Describe what you need, e.g.: water deflector strips and glass adhesive for windscreen assembly in Germany...',
      hint: 'Mention the part, material, region, volume and any certification needs.',
      categoryLabel: 'Category',
      categoryAll: 'All categories',
      categories: {
        waterDeflector: 'Water deflector strips',
        glassAdhesive: 'Glass adhesive / urethane',
        rubberSeal: 'Rubber seals / weatherstrip',
        glassRaw: 'Raw / float glass',
        hardware: 'Mounting hardware',
        packaging: 'Packaging & racks',
      },
      cardAddress: 'Address',
      cardContact: 'Contact',
      cardScale: 'Scale',
      cardEmployees: 'Employees',
      cardRevenue: 'Annual revenue',
      cardEstablished: 'Established',
      cardCapabilities: 'Core capabilities',
      cardCerts: 'Certifications',
      match: 'match',
      colName: 'Supplier',
      colLocation: 'Location',
      colEmail: 'Email',
      colWebsite: 'Website',
    },
    comparison: {
      inputLabel: 'Procurement requirement',
      placeholder:
        'Enter your procurement needs, e.g.: We need a batch of windscreen adhesive cartridges...',
      hint: 'Include specs, quantity, budget and delivery requirements.',
      hardFilters: 'Pre-filter conditions (Hard Filters)',
      budget: 'Budget limit',
      delivery: 'Delivery time',
      minPrice: 'Min',
      maxPrice: 'Max',
      deliveryOptions: {
        unlimited: 'No limit',
        within3: 'Within 3 business days',
        within7: 'Within 7 business days',
      },
      sortLabel: 'Sort by',
      sortOptions: {
        match: 'Match score',
        price: 'Price: low to high',
        delivery: 'Delivery: fastest first',
        payment: 'Payment: on-account first',
      },
      tableTitle: 'Decision comparison table',
      colVendor: 'Vendor / Platform',
      colPlatform: 'Platform',
      colProduct: 'Product',
      colMatch: 'Product match',
      colPrice: 'Unit price',
      colDelivery: 'Lead time',
      colPayment: 'Payment method',
      colDeliveryMethod: 'Delivery method',
      colRating: 'Rating',
      colAction: 'Action',
      recommended: 'Top pick',
      paymentTerms: {
        onAccount: 'On account',
        prepayment: 'Prepayment',
        card: 'Card / PayPal',
      },
    },
    memory: {
      title: 'Conversation Memory',
      subtitle: 'Every query and input you have made is remembered here',
      empty: 'No conversations yet. Run a search in Sourcing or Comparison.',
      moduleCol: 'Module',
      queryCol: 'Query & inputs',
      filtersCol: 'Filters',
      resultsCol: 'Results',
      feedbackCol: 'Feedback',
      timeCol: 'Time',
      noFeedback: 'No feedback',
      clearAll: 'Clear all',
      confirmClear: 'Clear all remembered conversations?',
      chose: 'Chose',
    },
    feedback: {
      title: 'Share your feedback',
      subtitle: 'Tell us which supplier you chose and how it went.',
      whichChosen: 'Which supplier / vendor did you choose?',
      quality: 'Goods quality',
      logistics: 'Logistics speed',
      priceSat: 'Price satisfaction',
      service: 'Service',
      comment: 'Comment (optional)',
      commentPlaceholder: 'Anything else you want to note about this choice...',
      submit: 'Submit feedback',
      thanks: 'Thanks! Your feedback was recorded.',
    },
    settings: {
      vaultTitle: 'API Key Vault',
      vaultDesc:
        'Keys are stored in your encrypted cloud vault and never displayed in full after saving.',
      encrypted: 'Encrypted at rest',
      keyLabel: 'Key name',
      keyValue: 'Secret value',
      keyPlaceholder: 'Paste API key...',
      addKey: 'Save to vault',
      updated: 'Updated',
      never: 'never',
      noKeys: 'No keys stored yet.',
      accountTitle: 'Account',
      name: 'Name',
      company: 'Company',
      role: 'Role',
    },
  },

  zh: {
    appName: '福耀采购云',
    tagline: '智能采购决策助手',
    login: {
      title: '登录您的工作空间',
      subtitle: '企业级采购智能平台',
      email: '企业邮箱',
      emailPlaceholder: 'you@fuyao-europe.com',
      password: '密码',
      passwordPlaceholder: '请输入密码',
      signIn: '登录',
      signingIn: '登录中...',
      sso: '使用企业 SSO 登录',
      demoHint: '演示：任意邮箱 + 密码均可登录（原型，无真实后端）。',
      secured: '端到端加密保护 · SOC 2 · ISO 27001',
    },
    nav: {
      modules: '功能模块',
      sourcing: '寻找供应商',
      comparison: '标准品比价',
      memory: '对话记忆',
      settings: '设置与密钥',
      logout: '退出登录',
    },
    module: {
      sourcing: {
        title: '寻找供应商',
        subtitle: '检索欧洲玻璃及汽车用品产业链供应商',
      },
      comparison: {
        title: '标准品比价',
        subtitle: '基于 AI 的标准品结构化比价分析',
      },
      memory: {
        title: '对话记忆',
        subtitle: '这里记录您每一次的询问与输入内容',
      },
      settings: {
        title: '设置与密钥',
        subtitle: '管理您的账户与安全存储的 API 密钥',
      },
    },
    steps: ['理解采购需求', '检索供应商', '生成结构化结果'],
    common: {
      analyze: '开始分析',
      analyzing: '分析中...',
      resultsFound: (n) => `已找到 ${n} 条结果`,
      analysisComplete: '分析完成',
      exportExcel: '导出 Excel',
      exporting: '导出中...',
      exportSuccess: '报表导出成功！',
      printPdf: '打印 / PDF',
      viewDetails: '查看详情',
      select: '选择此项',
      selected: '已选择',
      giveFeedback: '选择并评价',
      close: '关闭',
      cancel: '取消',
      save: '保存',
      saved: '已保存',
      empty: '暂无数据。',
    },
    sourcing: {
      inputLabel: '您要寻找什么供应商？',
      placeholder: '请描述需求，例如：用于挡风玻璃装配的挡水条与玻璃胶，区域德国……',
      hint: '可注明零件、材料、区域、用量及认证要求。',
      categoryLabel: '品类',
      categoryAll: '全部品类',
      categories: {
        waterDeflector: '挡水条',
        glassAdhesive: '玻璃胶 / 聚氨酯',
        rubberSeal: '密封条 / 橡胶件',
        glassRaw: '玻璃原片',
        hardware: '安装五金件',
        packaging: '包装与料架',
      },
      cardAddress: '地址',
      cardContact: '联系方式',
      cardScale: '规模',
      cardEmployees: '员工人数',
      cardRevenue: '年营收',
      cardEstablished: '成立年份',
      cardCapabilities: '核心能力',
      cardCerts: '资质认证',
      match: '匹配度',
      colName: '供应商',
      colLocation: '所在地',
      colEmail: '邮箱',
      colWebsite: '网站',
    },
    comparison: {
      inputLabel: '采购需求输入',
      placeholder: '请输入采购需求，例如：需要采购一批挡风玻璃胶……',
      hint: '支持描述规格、数量、预算、交付要求等关键信息。',
      hardFilters: '前置条件过滤 (Hard Filters)',
      budget: '价格区间',
      delivery: '配送时效',
      minPrice: '最低',
      maxPrice: '最高',
      deliveryOptions: {
        unlimited: '不限时效',
        within3: '3 个工作日内',
        within7: '7 个工作日内',
      },
      sortLabel: '排序方式',
      sortOptions: {
        match: '匹配度',
        price: '价格：从低到高',
        delivery: '到货：从快到慢',
        payment: '付款：挂帐优先',
      },
      tableTitle: '决策对比表',
      colVendor: '供应商 / 平台',
      colPlatform: '平台',
      colProduct: '产品',
      colMatch: '产品匹配度',
      colPrice: '单价',
      colDelivery: '交货周期',
      colPayment: '付款方式',
      colDeliveryMethod: '配送方式',
      colRating: '用户评分',
      colAction: '操作',
      recommended: '推荐',
      paymentTerms: {
        onAccount: '挂帐',
        prepayment: '预付款',
        card: '信用卡 / PayPal',
      },
    },
    memory: {
      title: '对话记忆',
      subtitle: '这里记录您每一次的询问与输入内容',
      empty: '暂无对话记录。请在「寻找供应商」或「标准品比价」中发起检索。',
      moduleCol: '模块',
      queryCol: '询问与输入',
      filtersCol: '过滤条件',
      resultsCol: '结果数',
      feedbackCol: '反馈',
      timeCol: '时间',
      noFeedback: '暂无反馈',
      clearAll: '清空全部',
      confirmClear: '确定要清空所有记忆的对话吗？',
      chose: '已选择',
    },
    feedback: {
      title: '分享您的反馈',
      subtitle: '请告诉我们您选择了哪家供应商，以及体验如何。',
      whichChosen: '本次您选择了哪家供应商 / 供货商？',
      quality: '货品质量',
      logistics: '物流速度',
      priceSat: '价格满意度',
      service: '服务',
      comment: '补充说明（选填）',
      commentPlaceholder: '关于本次选择的其他备注……',
      submit: '提交反馈',
      thanks: '感谢！您的反馈已记录。',
    },
    settings: {
      vaultTitle: 'API 密钥保险库',
      vaultDesc: '密钥保存在加密的云端保险库中，保存后不再以明文显示。',
      encrypted: '静态加密存储',
      keyLabel: '密钥名称',
      keyValue: '密钥内容',
      keyPlaceholder: '粘贴 API 密钥……',
      addKey: '保存至保险库',
      updated: '更新于',
      never: '从未',
      noKeys: '尚未存储任何密钥。',
      accountTitle: '账户',
      name: '姓名',
      company: '公司',
      role: '角色',
    },
  },
}
