# ProcureAI Backend

FastAPI 后端服务，为 Fuyao Glass Europe 提供 AI 辅助采购功能：

- **供应商寻源** — 根据自然语言需求查找匹配的供应商
- **标品比价** — 对标准商品进行报价对比和评分排序
- **对话记忆** — 记录每次搜索历史，支持 reopen 和反馈
- **密钥管理** — 安全存储第三方 API 密钥

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | Python 3.11+ / FastAPI / Pydantic v2 |
| AI Agent | LangChain (ChatOpenAI) |
| 向量检索 | ChromaDB + sentence-transformers (BAAI/bge-m3) |
| 网络搜索兜底 | DuckDuckGo Search |
| 提示词优化 | DSPy (占位，待实现) |

---

## 本地开发

### 前置条件

- Python 3.11+
- pip / venv

### 安装

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd procureai-backend

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，至少设置 OPENAI_API_KEY（可选，无 Key 时走规则降级）
```

### 启动

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后：

| 地址 | 用途 |
|------|------|
| http://localhost:8000/api/health | 健康检查 |
| http://localhost:8000/docs | Swagger 交互式文档 |
| http://localhost:8000/openapi.json | OpenAPI 规范（JSON） |

### 测试登录

```
POST /api/auth/login
{"email": "user@fuyao.com", "password": "password123"}
→ {"token": "mock-xxx", "user": {...}}
```

拿返回的 token 在 Swagger 右上角点 "Authorize" 填入 `Bearer <token>`，之后所有请求自动带认证。

---

## 部署

### 1. 推送到 GitHub

```bash
git init
git add .
git commit -m "init: ProcureAI backend"
git remote add origin <你的仓库地址>
git push -u origin main
```

### 2. 部署到服务器

选择任意平台（如 Railway / Render / 阿里云 / 腾讯云 / 自建服务器）：

| 步骤 | 说明 |
|------|------|
| 连 GitHub 仓库 | 选择你刚推的 `procureai-backend` 仓库 |
| 启动命令 | `uvicorn main:app --host 0.0.0.0 --port 8000` |
| 环境变量 | 参照 `.env.example` 设置 |
| 拿到 URL | 部署完成后获得公网地址，如 `https://procureai-backend.xxx.com` |

### 3. 配置前端

前端同学在 Vercel 项目设置环境变量：

```
VITE_API_BASE_URL=<你的后端公网地址>
```

---

## 项目结构

```
procureai-backend/
├── main.py                 # FastAPI 入口
├── database.py             # 数据库查询（当前返回 mock）
├── agent_interface.py      # Agent 适配层
├── agent/
│   ├── procurement_agent.py  # 主编排器
│   ├── parser.py             # 意图解析（LLM + 规则）
│   ├── retriever.py          # 供应商检索（向量 + 关键词 + 网络）
│   └── ranker.py             # 评分排序（LLM + 启发式）
├── api/
│   ├── auth.py              # 登录 / 登出 / 用户信息
│   ├── sourcing.py          # 供应商寻源接口
│   ├── comparison.py        # 标品比价接口
│   ├── conversations.py     # 对话历史 CRUD
│   └── vault.py             # API 密钥管理
├── data/
│   ├── suppliers.json       # 供应商种子数据
│   └── quotes.json          # 报价种子数据
├── trainer/
│   └── dspy_optimizer.py    # DSPy 优化（占位）
├── docs/
│   └── openapi.yaml         # 全队接口契约
├── .env.example             # 环境变量模板
├── .gitignore
└── requirements.txt
```

---

## API 概览

| 方法 | 路径 | 说明 | 需认证 |
|------|------|------|--------|
| POST | /api/auth/login | 登录获取 token | ❌ |
| GET | /api/auth/me | 当前用户信息 | ✅ |
| POST | /api/auth/logout | 登出 | ✅ |
| POST | /api/sourcing/search | 供应商寻源 | ✅ |
| POST | /api/comparison/search | 标品比价 | ✅ |
| GET | /api/conversations | 历史记录列表 | ✅ |
| POST | /api/conversations | 新建历史记录 | ✅ |
| PATCH | /api/conversations/{id}/feedback | 添加反馈 | ✅ |
| DELETE | /api/conversations/{id} | 删除单条记录 | ✅ |
| DELETE | /api/conversations | 清空所有记录 | ✅ |
| GET | /api/vault/keys | 密钥列表 | ✅ |
| POST | /api/vault/keys | 保存密钥 | ✅ |
| DELETE | /api/vault/keys/{id} | 删除密钥 | ✅ |
| GET | /api/health | 健康检查 | ❌ |

完整契约见 `docs/openapi.yaml`。
