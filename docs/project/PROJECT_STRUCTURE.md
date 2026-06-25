# ProcureAI Project Structure

这个项目现在按“前端 / 后端 API / Agent 决策 / Web Research / 数据与测试”分层：

```text
.
├── src/                         # Frontend（React + Vite）
│   ├── components/              # 通用 UI 组件
│   ├── context/                 # Auth / Memory 等前端状态
│   ├── data/                    # 前端静态展示数据
│   ├── lib/                     # API client、导出、local storage 工具
│   ├── modules/                 # 页面级模块：Sourcing / Comparison / Settings / Login
│   ├── App.tsx
│   └── main.tsx
│
├── public/                      # 前端静态资源
├── presentation/                # 展示/汇报材料
├── docs/                        # API 文档等项目文档
│
├── backend/                     # Backend（FastAPI）
│   ├── api/                     # HTTP 路由层：auth / sourcing / comparison / vault
│   ├── agent/                   # Procurement Agent 决策层
│   │   ├── parser.py            # 用户需求解析成采购 intent
│   │   ├── retriever.py         # 本地供应商检索 + 调用 WebResearcher
│   │   ├── ranker.py            # LLM 排序和解释
│   │   └── procurement_agent.py # parse → retrieve → rank 总管线
│   │
│   ├── web_research/            # 外部网页供应商发现与整理
│   │   ├── researcher.py        # 多 query 搜索、网页清洗、供应商结构化、fallback
│   │   └── __init__.py
│   │
│   ├── scraper/                 # 传统爬虫/动态页面抓取工具
│   ├── trainer/                 # DSPy / 训练数据相关实验脚本
│   ├── data/                    # 后端本地 JSON fallback 数据
│   ├── tests/                   # 后端单元测试
│   ├── database.py              # Supabase 数据读取
│   ├── main.py                  # FastAPI 入口
│   └── requirements.txt
│
├── docs/database/schema.sql      # Supabase schema
├── render.yaml                  # Render 部署配置
├── package.json                 # 前端 npm 脚本
└── README.md
```

## 关键边界

- `src/`：只放前端，不直接写采购 Agent 逻辑。
- `backend/api/`：只处理 HTTP 请求/响应，不做复杂搜索算法。
- `backend/agent/`：只负责采购意图、检索、排序的业务决策。
- `backend/web_research/`：只负责外部网页搜索、过滤、抽取、fallback。
- `backend/scraper/`：保留传统爬虫工具；WebResearcher 可以选择性调用，但不和 Agent 混在一起。

## 推上线时重点文件

Web Research Agent 相关改动主要是：

```text
backend/agent/procurement_agent.py
backend/agent/retriever.py
backend/web_research/__init__.py
backend/web_research/researcher.py
backend/tests/test_web_researcher.py
backend/tests/test_retriever_web_researcher_integration.py
backend/requirements.txt
docs/project/PROJECT_STRUCTURE.md
```
