# 🏢 ProcureAI: AI-Assisted Procurement Agent

[English](#english-version) | [中文版](#chinese-version)

![Deployment Status](https://img.shields.io/badge/Status-Live_on_Vercel-success)
![React](https://img.shields.io/badge/Frontend-React_%2B_Vite-blue)
![Tailwind](https://img.shields.io/badge/Styling-Tailwind_CSS-38B2AC)

---

<a name="english-version"></a>
## 🇬🇧 English Version

### 📖 Project Overview
This project is an intelligent procurement decision assistant (**ProcureAI Agent**) custom-developed for European manufacturing enterprises (with Fuyao Europe as the business background). 
The system aims to automate supplier sourcing and quote comparisons using AI, transforming natural language requirements into structured decision data. By integrating global web data and a localized multi-language UI, it significantly boosts the efficiency and compliance of multinational procurement teams.

### ✨ Core Features
- **🤖 Natural Language Parsing:** Input procurement needs in natural language (e.g., specifications, budget, delivery requirements).
- **📊 Structured Decision Workspace:** Automatically extracts and generates a multi-dimensional comparison table including match scores, unit prices, lead times, and payment methods.
- **⚙️ Hard Filters:** Combines AI flexibility with strict business logic, allowing upfront absolute budget limits and delivery deadlines.
- **🌍 Deep Localization:** - Supports EN / CN UI bilingual hot-switching.
  - Core procurement data remains in its original European language (German/English) to prevent translation distortion.
- **📑 One-Click Reporting:** Export comparison results to Excel or generate PDF prints for filing and approval.

### 🚀 Getting Started
1. Clone the repository:
   ```bash
   git clone [https://github.com/tianGan11/--GeneAI-SS26-AI-assisted-procurement-agent.git](https://github.com/tianGan11/--GeneAI-SS26-AI-assisted-procurement-agent.git)
2. Install dependencies:
   ```bash
   cd --GeneAI-SS26-AI-assisted-procurement-agent
   npm install
3. Start the local development server:
   ```bash
   npm run dev

### 🤝 Team Workflow (Feature Branch Workflow)
To ensure the stability of our Vercel production environment, all team members must strictly adhere to the following rules:
1. No Direct Pushes to Main: Direct commits to the main branch are strictly prohibited.
2. Branch Naming Convention: Always create a new branch from main before developing:
  - Features: feature/xxx (e.g., feature/api-integration)
  - UI Tweaks: ui/xxx (e.g., ui/table-alignment)
  - Bug Fixes: fix/xxx (e.g., fix/language-toggle)
3. Pull Requests (PR): Once development is complete, submit a PR on GitHub. Code must be reviewed by at least one other team member before merging into main.

<a name="chinese-version"></a>
## 🇨🇳 中文版

### 📖 项目简介
本项目为针对欧洲制造企业（以 Fuyao Europe 为业务背景）定制开发的**智能采购辅助智能体 (ProcureAI Agent)**。
系统致力于通过 AI 自动化处理供应商寻源与报价比对，将自然语言需求转化为结构化的决策数据。通过对接全网数据与本地化多语言 UI，大幅提升跨国采购团队的决策效率与合规性。

### ✨ 核心功能
- **🤖 自然语言解析：** 支持用自然语言输入采购需求（如：规格、预算、交付要求）。
- **📊 结构化决策工作台：** 自动抓取并生成包含匹配度、单价、交期、付款方式等关键业务维度的多维对比表。
- **⚙️ 业务硬约束过滤 (Hard Filters)：** 结合 AI 的灵活性与真实业务的严谨性，支持前置设定绝对预算上限与交期红线。
- **🌍 深度本地化 (Localization)：** - 支持 EN / CN 界面双语热切换。
  - 核心采购数据保持欧洲本地语言（德语/英语）原文防失真。
- **📑 一键报表闭环：** 支持比价结果一键导出 Excel 或生成 PDF 打印留档。

### 🚀 本地运行指南
1. 克隆项目到本地：
   ```bash
   git clone https://github.com/tianGan11/--GeneAI-SS26-AI-assisted-procurement-agent.git
2. 进入项目目录并安装依赖：
   ```bash
   cd --GeneAI-SS26-AI-assisted-procurement-agent
   npm install
3. 启动本地开发服务器：
   ```bash
   npm run dev

### 🤝 团队协作规范
本项目采用 Feature Branch Workflow (功能分支工作流)，请全组严格遵守以下规定以保障 Vercel 线上环境的稳定：
1. 绝对禁止直接推送到 main 分支。
2. 开发新功能前，必须基于最新 main 创建个人分支，命名规范：
  - Features: feature/xxx (e.g., feature/api-integration)
  - UI Tweaks: ui/xxx (e.g., ui/table-alignment)
  - Bug Fixes: fix/xxx (e.g., fix/language-toggle)
3. Pull Request (PR) 审查： 开发完成后，在 GitHub 提交 PR，至少需要另一名组员 Review 代码无误后，方可 Merge 合并入主分支。
