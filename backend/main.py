"""
ProcureAI Backend — FastAPI
接收前端请求，调用 Agent 和数据库，返回结果
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from agent_interface import run_sourcing_agent, run_comparison_agent

app = FastAPI(title="ProcureAI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://*.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════
# 数据模型（对应前端 types.ts）
# ═══════════════════════════════════════════════════════

class FactorWeights(BaseModel):
    price: float = 40
    delivery: float = 35
    rating: float = 25

class ComparisonRequest(BaseModel):
    query: str                              # 用户自然语言输入
    min_price: Optional[float] = None       # 硬约束：最低价格
    max_price: Optional[float] = None       # 硬约束：最高价格
    delivery_option: str = "unlimited"      # unlimited | within3 | within7
    weights: FactorWeights = FactorWeights()

class SourcingRequest(BaseModel):
    query: str                              # 用户自然语言输入
    category: Optional[str] = None         # 可选品类过滤


# ═══════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════

@app.post("/api/comparison/analyze")
async def analyze_quotes(req: ComparisonRequest):
    """
    报价比对接口
    前端 ComparisonModule 的 handleAnalyze() 调用这里
    """
    try:
        result = await run_comparison_agent(
            query=req.query,
            min_price=req.min_price,
            max_price=req.max_price,
            delivery_option=req.delivery_option,
            weights=req.weights.model_dump(),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sourcing/search")
async def search_suppliers(req: SourcingRequest):
    """
    供应商寻源接口
    前端 SourcingModule 的 handleAnalyze() 调用这里
    """
    try:
        result = await run_sourcing_agent(
            query=req.query,
            category=req.category,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """健康检查，部署后确认服务存活"""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
