from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field


class RankedItem(BaseModel):
    id: str
    matchScore: int = Field(ge=0, le=100)
    reason: str


class RankingResponse(BaseModel):
    results: list[RankedItem] = Field(default_factory=list)


class LLMRanker:
    def __init__(self, llm):
        from pathlib import Path
        self.llm = llm
        self.optimized_prompt_path = Path(__file__).resolve().parents[1] / "data" / "optimized_prompt.txt"

    async def rank_suppliers(self, query: str, candidates: list[dict]) -> list[dict]:
        """Score each candidate 0-100 based on query relevance. Return sorted by matchScore with reasons."""
        if not candidates:
            return []
        llm_scores = await self._rank_with_llm(query, candidates, "supplier")
        ranked = []
        for candidate in candidates:
            scored = dict(candidate)
            llm_score = llm_scores.get(candidate.get("id"))
            if llm_score:
                scored["matchScore"] = llm_score.matchScore
                scored["reason"] = llm_score.reason
            else:
                scored["matchScore"] = self._heuristic_score(query, candidate)
                scored["reason"] = self._supplier_reason(query, candidate)
            scored["matchScore"] = self._apply_repurchase_bonus(scored)
            ranked.append(scored)
        return sorted(ranked, key=lambda item: item.get("matchScore", 0), reverse=True)

    async def rank_quotes(
        self,
        query: str,
        candidates: list[dict],
        min_price: float = None,
        max_price: float = None,
        max_delivery_days: int = None,
    ) -> list[dict]:
        """Score quotes, apply hard filters, return sorted."""
        filtered = []
        for candidate in candidates:
            unit_price = candidate.get("unitPriceEur")
            delivery_days = candidate.get("deliveryDays")
            if min_price is not None and unit_price is not None and unit_price < min_price:
                continue
            if max_price is not None and unit_price is not None and unit_price > max_price:
                continue
            if max_delivery_days is not None and delivery_days is not None and delivery_days > max_delivery_days:
                continue
            filtered.append(candidate)

        if not filtered:
            return []

        llm_scores = await self._rank_with_llm(query, filtered, "quote")
        ranked = []
        for candidate in filtered:
            scored = dict(candidate)
            llm_score = llm_scores.get(candidate.get("id"))
            if llm_score:
                scored["matchScore"] = llm_score.matchScore
                scored["reason"] = llm_score.reason
            else:
                scored["matchScore"] = self._quote_score(query, candidate, max_delivery_days)
                scored["reason"] = self._quote_reason(candidate)
            ranked.append(scored)
        return sorted(ranked, key=lambda item: item.get("matchScore", 0), reverse=True)

    async def _rank_with_llm(self, query: str, candidates: list[dict], item_type: str) -> dict[str, RankedItem]:
        if self.llm is None or not hasattr(self.llm, "with_structured_output"):
            return {}
        try:
            payload = [
                {
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("vendor"),
                    "category": item.get("category"),
                    "description": item.get("description") or item.get("product"),
                    "certifications": item.get("certifications"),
                    "price": item.get("unitPriceEur"),
                    "deliveryDays": item.get("deliveryDays"),
                    "baseScore": item.get("matchScore"),
                    "source": item.get("source"),
                    "repurchasePriority": item.get("repurchasePriority"),
                }
                for item in candidates
            ]
            system_instruction = ""
            if self.optimized_prompt_path.exists():
                try:
                    with open(self.optimized_prompt_path, "r", encoding="utf-8") as f:
                        system_instruction = f.read().strip() + "\n\n"
                except Exception:
                    pass

            prompt = (
                f"{system_instruction}"
                f"Rank these procurement {item_type} candidates for the query. "
                "Return one result per candidate id with matchScore 0-100 and a concise reason. "
                "For suppliers, candidates with source=database / repurchasePriority=database are existing database suppliers and should receive a modest repurchase preference when relevance is close; do not let this override a clearly much better new web supplier. "
                f"Query: {query}\nCandidates: {payload}"
            )
            structured_llm = self.llm.with_structured_output(RankingResponse, method="function_calling")
            response = await structured_llm.ainvoke(prompt)
            ranking = response if isinstance(response, RankingResponse) else RankingResponse.model_validate(response)
            return {item.id: item for item in ranking.results}
        except Exception:
            return {}

    def _heuristic_score(self, query: str, candidate: dict) -> int:
        text = " ".join(
            str(value)
            for value in [
                candidate.get("name"),
                candidate.get("category"),
                candidate.get("country"),
                candidate.get("description"),
                " ".join(candidate.get("products", [])),
                " ".join(candidate.get("certifications", [])),
                " ".join(candidate.get("capabilities", [])),
            ]
            if value
        ).lower()
        tokens = set(re.findall(r"[\w\u4e00-\u9fffäöüÄÖÜß+-]+", query.lower()))
        overlap = sum(1 for token in tokens if token in text)
        base = int(candidate.get("matchScore", 70))
        return max(0, min(100, base + min(12, overlap * 2)))

    def _quote_score(self, query: str, candidate: dict, max_delivery_days: Optional[int]) -> int:
        score = self._heuristic_score(query, candidate)
        price = float(candidate.get("unitPriceEur") or 0)
        delivery_days = int(candidate.get("deliveryDays") or 99)
        rating = float(candidate.get("rating") or 0)
        if price:
            score += max(0, 8 - int(price))
        if max_delivery_days and delivery_days <= max_delivery_days:
            score += 8
        elif delivery_days <= 3:
            score += 5
        score += round(max(0, rating - 4.0) * 5)
        return max(0, min(100, score))

    @staticmethod
    def _apply_repurchase_bonus(candidate: dict) -> int:
        """Small bonus for known database suppliers when relevance is close.

        Reduced from +12 to +3 so web-researched suppliers with genuinely higher
        relevance can outrank marginal database hits.
        """
        score = int(candidate.get("matchScore", 0))
        if candidate.get("source") == "database" or candidate.get("repurchasePriority") == "database":
            score += 3
        return max(0, min(100, score))

    @staticmethod
    def _supplier_reason(query: str, candidate: dict) -> str:
        strengths = []
        if candidate.get("country"):
            strengths.append(candidate["country"])
        strengths.extend(candidate.get("certifications", [])[:2])
        if candidate.get("capabilities"):
            strengths.append(candidate["capabilities"][0])
        return "Matches the query through " + ", ".join(strengths) if strengths else "Relevant supplier profile."

    @staticmethod
    def _quote_reason(candidate: dict) -> str:
        return (
            f"{candidate.get('unitLabel')} with {candidate.get('deliveryLabel')} delivery "
            f"and {candidate.get('rating')} rating."
        )
