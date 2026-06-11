"""
agent_interface.py
==================
后端调用 Agent 的统一入口。

现在：mock 函数，返回假数据
开会后：把 TODO 换成真实 LangGraph Agent 调用
"""

from typing import Any
from database import query_suppliers, query_products


# ═══════════════════════════════════════════════════════
# Sourcing Agent
# ═══════════════════════════════════════════════════════

async def run_sourcing_agent(
    query: str,
    category: str | None = None,
) -> dict[str, Any]:
    """
    调用供应商寻源 Agent。

    参数：
        query    : 用户自然语言输入，如 "500x TS705a, <1 week, IATF认证"
        category : 可选品类，如 "rubberSeal"

    返回：
        { "suppliers": [...] }

    开会时和 Agent 同学对齐：
        - 他们的文件叫什么
        - ainvoke() 接收什么参数
        - 返回的数据格式
    """

    # ── 阶段1：现在用数据库 mock 数据 ──────────────────────────────────────
    suppliers = await query_suppliers(category=category)
    return {"suppliers": suppliers}

    # ── 阶段2：开会后换成真实 Agent（把上面两行注释掉，取消下面注释）────────
    # from langgraph_agent import sourcing_graph
    # result = await sourcing_graph.ainvoke({
    #     "query": query,
    #     "category": category,
    # })
    # return result


# ═══════════════════════════════════════════════════════
# Comparison Agent
# ═══════════════════════════════════════════════════════

async def run_comparison_agent(
    query: str,
    min_price: float | None = None,
    max_price: float | None = None,
    delivery_option: str = "unlimited",
    weights: dict | None = None,
) -> dict[str, Any]:
    """
    调用报价比对 Agent。

    参数：
        query           : 用户自然语言输入
        min_price       : 最低价格硬约束（€）
        max_price       : 最高价格硬约束（€）
        delivery_option : "unlimited" | "within3" | "within7"
        weights         : { "price": 40, "delivery": 35, "rating": 25 }

    返回：
        { "items": [...] }

    开会时和 Agent 同学对齐：
        - 他们的文件叫什么
        - ainvoke() 接收什么参数
        - 返回的数据格式
    """

    # 把 delivery_option 转换成天数，方便数据库查询
    delivery_cap = {
        "within3": 3,
        "within7": 7,
        "unlimited": 9999,
    }.get(delivery_option, 9999)

    # ── 阶段1：现在用数据库 mock 数据 ──────────────────────────────────────
    items = await query_products(
        max_price=max_price,
        max_delivery_days=delivery_cap,
    )
    return {"items": items}

    # ── 阶段2：开会后换成真实 Agent（把上面两行注释掉，取消下面注释）────────
    # from langgraph_agent import comparison_graph
    # result = await comparison_graph.ainvoke({
    #     "query": query,
    #     "min_price": min_price,
    #     "max_price": max_price,
    #     "delivery_option": delivery_option,
    #     "weights": weights,
    # })
    # return result
