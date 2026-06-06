"""
ProcureAI Backend — FastAPI 骨架
对接前端 ComparisonModule 和 SourcingModule
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="ProcureAI Backend", version="0.1.0")

# ── CORS：允许前端本地开发服务器访问 ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",          # 前端本地开发
        "https://*.vercel.app",           # 前端 Vercel 部署（改成你们的域名）
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型（严格对应前端 types.ts，字段名不能改）
# ═══════════════════════════════════════════════════════════════════════════════

# ── Comparison 相关 ───────────────────────────────────────────────────────────

class FactorWeights(BaseModel):
    price: float = 40
    delivery: float = 35
    rating: float = 25

class ComparisonRequest(BaseModel):
    query: str                              # 用户自然语言输入
    min_price: Optional[float] = None       # 硬约束：最低价格（€）
    max_price: Optional[float] = None       # 硬约束：最高价格（€）
    delivery_option: str = "unlimited"      # "unlimited" | "within3" | "within7"
    weights: FactorWeights = FactorWeights()

class ComparisonItem(BaseModel):
    id: str
    vendor: str
    platform: str
    product: str
    matchScore: int           # 0–100，LLM 评分
    unitPriceEur: float       # 纯数字，前端用于排序和过滤
    unitLabel: str            # 展示字符串，如 "€ 2.180 / Stk."
    deliveryDays: int         # 纯数字，前端用于过滤
    deliveryLabel: str        # 展示字符串，如 "3–5 Werktage"
    paymentTerm: str          # "onAccount" | "prepayment" | "card"
    paymentLabel: str         # 展示字符串
    deliveryMethod: str
    rating: float
    reviews: int

class ComparisonResponse(BaseModel):
    items: list[ComparisonItem]

# ── Sourcing 相关 ─────────────────────────────────────────────────────────────

class SourcingRequest(BaseModel):
    query: str                        # 如 "500x TS705a, <1 week delivery, IATF认证"
    category: Optional[str] = None    # 可选：前端传品类关键词辅助过滤

class SupplierResult(BaseModel):
    # 对应前端 types.ts 的 Supplier 接口
    id: str
    name: str
    category: str
    country: str
    city: str
    address: str
    contactPerson: str
    phone: str
    email: str
    website: str
    employees: str        # 区间字符串，如 "250–500"
    annualRevenue: str    # 如 "€ 80M–120M"
    established: int
    capabilities: list[str]
    certifications: list[str]
    matchScore: int       # 0–100，LLM 评分

class SourcingResponse(BaseModel):
    suppliers: list[SupplierResult]


# ═══════════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/comparison/analyze", response_model=ComparisonResponse)
async def analyze_quotes(req: ComparisonRequest):
    """
    报价比对主接口 — 对应前端 ComparisonModule 的 handleAnalyze()

    实现路线图（按顺序）：
      阶段1 [现在]  : 返回 mock 数据，验证前后端连通
      阶段2 [W3-W4] : LLM 解析 req.query，提取 SKU/数量/规格
      阶段3 [W3-W4] : 用解析结果查 DB + 调爬虫工具抓取报价
      阶段4 [W5-W6] : 硬过滤（价格区间/交期）+ LLM 打 matchScore
      阶段5 [W5-W6] : 排序后返回真实数据
    """
    # ── 阶段1：mock 数据（结构和前端 MOCK_COMPARISON 完全一致）──────────────
    mock_items = [
        ComparisonItem(
            id="vendor-001",
            vendor="Bechtle AG",
            platform="Bechtle Online Shop",
            product="Cisco ISR 4331 — Enterprise Router (Generalüberholt)",
            matchScore=96,
            unitPriceEur=2180.0,
            unitLabel="€ 2.180 / Stk.",
            deliveryDays=4,
            deliveryLabel="3–5 Werktage",
            paymentTerm="onAccount",
            paymentLabel="Invoice (Rechnung 30 Tage)",
            deliveryMethod="DHL Express",
            rating=4.8,
            reviews=124,
        ),
        ComparisonItem(
            id="vendor-002",
            vendor="Saturn Business",
            platform="MediaMarktSaturn Pro",
            product="Ubiquiti UniFi Dream Machine Pro — Gateway & Controller",
            matchScore=91,
            unitPriceEur=1950.0,
            unitLabel="€ 1.950 / unit",
            deliveryDays=6,
            deliveryLabel="5–7 business days",
            paymentTerm="card",
            paymentLabel="Credit Card / PayPal",
            deliveryMethod="UPS Standard",
            rating=4.6,
            reviews=89,
        ),
        ComparisonItem(
            id="vendor-003",
            vendor="Axesso Systems GmbH",
            platform="ITscope B2B Marketplace",
            product="HPE Aruba Instant On AP22 (5-Pack) — WiFi Access Point",
            matchScore=88,
            unitPriceEur=2320.0,
            unitLabel="€ 2.320 / Stk.",
            deliveryDays=8,
            deliveryLabel="7–10 Werktage",
            paymentTerm="prepayment",
            paymentLabel="Prepayment (Vorkasse)",
            deliveryMethod="Freight Forwarding (Spedition)",
            rating=4.5,
            reviews=56,
        ),
    ]
    return ComparisonResponse(items=mock_items)


@app.post("/api/sourcing/search", response_model=SourcingResponse)
async def search_suppliers(req: SourcingRequest):
    """
    供应商寻源接口 — 对应前端 SourcingModule 的 handleAnalyze()

    实现路线图：
      阶段1 [现在]  : 返回 mock 数据，验证连通
      阶段2 [W3-W4] : LLM 解析 req.query，提取品类/规格/MOQ/认证要求
      阶段3 [W3-W4] : 查 PostgreSQL supplier 表（历史供应商）
      阶段4 [W5-W6] : Web 搜索工具扩展候选 + LLM 评分排序
    """
    # ── 阶段1：mock 数据（结构和前端 MOCK_SUPPLIERS 一致）────────────────────
    mock_suppliers = [
        SupplierResult(
            id="sup-001",
            name="Freudenberg Sealing Technologies GmbH",
            category="rubberSeal",
            country="Germany",
            city="Weinheim",
            address="Höhnerweg 2-4, 69469 Weinheim, Germany",
            contactPerson="Klaus Bauer",
            phone="+49 6201 80-0",
            email="procurement@freudenberg-et.com",
            website="www.freudenberg-et.com",
            employees="10,000+",
            annualRevenue="€ 2B+",
            established=1849,
            capabilities=["Rubber Seals", "Gaskets", "Vibration Control", "Custom Molding"],
            certifications=["IATF 16949", "ISO 14001", "ISO 9001"],
            matchScore=94,
        ),
        SupplierResult(
            id="sup-002",
            name="Sika Automotive GmbH",
            category="glassAdhesive",
            country="Germany",
            city="Hamburg",
            address="Reichsbahnstraße 99, 22525 Hamburg, Germany",
            contactPerson="Anna Müller",
            phone="+49 40 54002-0",
            email="automotive@sika.com",
            website="www.sika.com/automotive",
            employees="5,000–10,000",
            annualRevenue="€ 500M–1B",
            established=1910,
            capabilities=["PVB Lamination", "Urethane Adhesives", "Glass Bonding", "NVH Solutions"],
            certifications=["IATF 16949", "ISO 9001", "VDA 6.1"],
            matchScore=89,
        ),
    ]
    return SourcingResponse(suppliers=mock_suppliers)


@app.get("/health")
async def health():
    """健康检查，部署后用来确认服务是否存活"""
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════════════════
# 本地运行：python main.py
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)