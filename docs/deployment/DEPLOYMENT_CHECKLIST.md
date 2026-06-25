# 🚀 ProcureAI 上线检查清单

> 更新时间：2026-06-16 | 负责人：简博约

---

## 1. 后端部署（你来做 — 3分钟）

### Render 部署

1. 打开 https://render.com → 用 GitHub 登录
2. 右上角点 **New +** → **Web Service**
3. 搜索并选择仓库：`tianGan11/-GeneAI-SS26-AI-assisted-procurement-agent`
4. Render 自动检测到 `render.yaml`，确认以下配置：
   - **Root Directory**：`backend`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 点 **Deploy Web Service**（免费额度够用）
6. 等 5-8 分钟构建完成，拿到 URL，比如：
   ```
   https://procureai-backend.onrender.com
   ```
7. 在 Render 面板 → Environment → 添加：
   ```
   OPENAI_API_KEY = sk-你的真实Key
   ```
   （不填也能跑，填了 AI 评分更准）

### 验证

```bash
curl https://procureai-backend.onrender.com/api/health
# 返回 {"status":"ok"} 即成功
```

---

## 2. 前端对接（告诉前端同学 — 1分钟）

> **发到群里给前端同学：**

```
后端已部署，URL: https://procureai-backend.onrender.com

请在 Vercel 项目设置里加一条环境变量然后重新部署：

VITE_API_BASE_URL = https://procureai-backend.onrender.com

加完后前端会自动从 Mock 数据切换到真实后端，
不需要改任何前端代码。
```

### 前端同学操作步骤

1. 打开 Vercel 项目面板
2. **Settings** → **Environment Variables**
3. 添加：
   ```
   Key:   VITE_API_BASE_URL
   Value: https://procureai-backend.onrender.com
   ```
4. 点 **Save** → 重新部署（Vercel 会自动触发）
5. 部署完访问前端页面，搜索"德国玻璃胶"看是否返回真实结果

---

## 3. 训练数据（你去找福耀采购 — 每人5分钟）

### 带什么去

- 你已经做好的 Agent（可以演示 "搜德国玻璃胶 → 返回 Henkel"）
- 一张纸或手机 Notes

### 问每个人这三个问题

```
1. 你最近一次采购，搜的什么条件？
   例："德国挡水条，IATF认证必须，两周内到货，预算€10/m"

2. 最后选了哪家供应商？
   例：Cooper Standard

3. 为什么选它？
   例："交期稳定、本地服务好，虽然贵一点"
```

### 目标

收集 **30-50 条**（每人 5-10 条）。格式我帮你整理，你只管记录。

### 拿到数据后告诉我

我把数据跑 DSPy 训练，Agent 评分会更准。

---

## 4. API Key 配置（你来做 — 1分钟）

### 为什么需要

现在没 Key 也能跑（规则引擎），但填了 Key 后 LLM 会：
- 更准地理解复杂需求（中英德混合）
- 更聪明地打分（知道"紧急"优先交期）
- 动态爬虫的网站分析更智能

### 用哪个

| 选择 | 成本 | 推荐 |
|------|------|:--:|
| OpenAI GPT-4o | $0.01-0.05/次搜索 | 🥇 |
| DeepSeek | 超便宜 | 🥈 |
| 不填 | 免费，规则引擎 | 🥉 |

### 操作

在 Render 面板 → Environment Variables → 填入：
```
OPENAI_API_KEY = sk-你的Key
LLM_MODEL = gpt-4o
```
然后重新部署。

如果用 DeepSeek：
```
OPENAI_API_KEY = sk-你的DeepSeekKey
OPENAI_BASE_URL = https://api.deepseek.com/v1
LLM_MODEL = deepseek-chat
```

---

## 5. 数据库切换（告诉数据库同学 — 等他们建表后）

### 数据库同学要做的事

`backend/database.py` 里已经定义好了两张表，照这个建：

```sql
-- suppliers 表
CREATE TABLE suppliers (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    category VARCHAR,
    country VARCHAR,
    city VARCHAR,
    address VARCHAR,
    contact_person VARCHAR,
    phone VARCHAR,
    email VARCHAR,
    website VARCHAR,
    employees VARCHAR,
    annual_revenue VARCHAR,
    established INT,
    capabilities TEXT[],
    certifications TEXT[]
);

-- products 表
CREATE TABLE products (
    id VARCHAR PRIMARY KEY,
    supplier_id VARCHAR REFERENCES suppliers(id),
    sku VARCHAR,
    name VARCHAR NOT NULL,
    unit_price_eur FLOAT,
    stock INT,
    delivery_days INT,
    delivery_label VARCHAR,
    payment_term VARCHAR,
    payment_label VARCHAR,
    delivery_method VARCHAR,
    rating FLOAT,
    reviews INT
);
```

建好后告诉我 `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD`，我把 `.env` 配置好，后端自动切换。

### 切换方法

```bash
# backend/.env 里填入：
DB_HOST=xxx
DB_PORT=5432
DB_NAME=procureai
DB_USER=procureai
DB_PASSWORD=xxx
```

然后 `database.py` 里的 `# TODO` 取消注释就行。

---

## 6. 爬虫数据补充（告诉爬虫同学 — 现在可以做）

### 同学要做的事

1. 写好的爬虫（`wlw_selenium_scraper.py`）已经放在 `backend/scraper/` 里
2. 输出格式按 `backend/SCRAPER_SCHEMA.md` 来（我发过）
3. 爬出来的 JSON 放到 `backend/data/scraped/` 目录下
4. 运行合并命令：
   ```bash
   cd backend
   python merge_scraped.py data/scraped/wlw_results.json
   ```
   自动去重、更新、淘汰 90 天没更新的数据

### 定时运行

公司服务器上设 cron：
```bash
0 3 * * * /opt/procureai/backend/cron_scraper.sh
```
每天凌晨 3 点自动爬 + 合并。

---

## 7. PR Review（告诉王旨/1FanYang1 — 现在就可以）

### PR 链接

https://github.com/tianGan11/-GeneAI-SS26-AI-assisted-procurement-agent/pull/new/feature/backend-agent

### 跟组员说

> 我的后端 AI Agent 在 `feature/backend-agent`，已完成：
> - 11 品类自然语言搜索
> - 报价对比 + 硬过滤
> - LLM 动态爬虫模块
> - 24 家供应商 + 36 条报价
> - 全部 API 端点（auth/vault/conversations/sourcing/comparison）
> - 前端对接只需设一条环境变量
>
> 麻烦 Review 一下，没问题就 merge 进 main 🙏

---

## 📊 完成检查表

| # | 任务 | 负责人 | 状态 |
|---|------|--------|:--:|
| 1 | Render 部署 | 你 | ⬜ |
| 2 | 前端设 VITE_API_BASE_URL | 前端同学 | ⬜ |
| 3 | 找采购收集训练数据 | 你 | ⬜ |
| 4 | 填 API Key | 你 | ⬜ |
| 5 | 数据库建表 | 数据库同学 | ⬜ |
| 6 | 爬虫跑起来 | 爬虫同学 | ⬜ |
| 7 | PR Review | 王旨/1FanYang1 | ⬜ |
