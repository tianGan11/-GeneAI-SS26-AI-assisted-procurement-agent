"""Backend entrypoints for calling the procurement agent."""

from typing import Any

from agent.procurement_agent import ProcurementAgent


agent = ProcurementAgent()


# ═══════════════════════════════════════════════════════
# Sourcing Agent
# ═══════════════════════════════════════════════════════

async def run_sourcing_agent(
    query: str,
    category: str | None = None,
) -> dict[str, Any]:
    return await agent.search_suppliers(query)


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
    return await agent.search_quotes(
        query,
        min_price=min_price,
        max_price=max_price,
        delivery_time=delivery_option,
    )
