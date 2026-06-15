# ProcureAI Backend — AI Agent

> 🏗️ 负责模块：简博约 (BoYue Jian)

## 快速启动

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 复制配置（先不填 API Key 也能跑，用规则引擎）
cp .env.example .env

# 启动
python main.py
# → http://localhost:8000
# → 健康检查: http://localhost:8000/api/health
```

## API 接口

| 接口 | 说明 |
|------|------|
| `POST /api/sourcing/search` | 自然语言搜供应商 |
| `POST /api/comparison/search` | 报价对比+过滤 |
| `GET /api/health` | 健康检查 |

## 前端对接

前端设置环境变量 `VITE_API_BASE_URL` 指向后端地址即可自动切换：

```bash
# .env（前端）
VITE_API_BASE_URL=http://localhost:8000   # 本地开发
VITE_API_BASE_URL=https://xxx.onrender.com  # 生产环境
```

设置后前端自动从 Mock 模式切换到真实 API 模式（见 `src/lib/api.ts` 的 `apiEnabled`）。

## 架构

```
用户输入 → FastAPI → Agent Core
                       ├→ 意图解析 (parser.py)
                       ├→ 向量检索 (retriever.py + ChromaDB)
                       ├→ LLM 打分排序 (ranker.py)
                       └→ 网络搜索 fallback (DuckDuckGo)
```

## 数据

- `data/suppliers.json` — 供应商库
- `data/quotes.json` — 报价数据
- `数据文件/` — 福耀真实采购数据（Excel）

## 训练

`trainer/dspy_optimizer.py` — 基于用户反馈自动优化 Agent（开发中）
