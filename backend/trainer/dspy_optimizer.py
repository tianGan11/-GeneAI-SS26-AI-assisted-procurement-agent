from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.procurement_agent import ProcurementAgent


class DSPyTrainer:
    def __init__(self, agent: ProcurementAgent):
        self.agent = agent
        self.feedback_examples: list[dict[str, Any]] = []

    def add_feedback(self, query: str, recommended_supplier: str, feedback: dict):
        self.feedback_examples.append(
            {
                "query": query,
                "recommended_supplier": recommended_supplier,
                "feedback": feedback,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def optimize(self) -> dict:
        return {
            "status": "pending",
            "message": "DSPy optimization is not enabled yet. Feedback has been stored for a future training run.",
            "feedback_count": len(self.feedback_examples),
        }
