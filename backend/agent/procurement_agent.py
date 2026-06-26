from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from agent.parser import IntentParser
from agent.ranker import LLMRanker
from agent.retriever import SupplierRetriever
from database import query_suppliers_sync
from database import query_products_sync

BASE_DIR = Path(__file__).resolve().parents[1]


class ProcurementAgent:
    def __init__(self):
        self.llm = self._create_llm()
        #self.suppliers = self._load_json(BASE_DIR / "data" / "suppliers.json")
        self.suppliers = query_suppliers_sync()
        #self.quotes = self._load_json(BASE_DIR / "data" / "quotes.json")
        self.quotes = query_products_sync()
        self.parser = IntentParser(self.llm)
        chroma_collection = self._create_chroma_collection()
        self.retriever = SupplierRetriever(chroma_collection, self.suppliers, llm=self.llm)
        self.ranker = LLMRanker(self.llm)

    async def search_suppliers(self, query: str, progress=None, structured: dict | None = None) -> dict:
        """Full pipeline: parse → retrieve → rank → return.

        progress, when provided, is a lightweight callback used by the async
        job API to expose real backend phases to the frontend.
        Each progress call emits a freeform agent thought — the frontend
        prints them as-is without further phase-to-label mapping.

        structured, when provided, contains B2B-procurement fields filled in via
        the frontend's structured form (productName, quantity, category, country,
        certifications, etc.).  These override the LLM-parsed intent values for a
        more reliable double-check.
        """
        if progress:
            progress("parse", "正在解析您的采购需求，提取品类、地区、预算等关键信息...", 10)

        intent = await self.parser.parse(query)

        # ── Apply structured form overrides (double-check) ─────────────
        if structured:
            if structured.get("category"):
                intent.category = structured["category"]
            if structured.get("country"):
                intent.country = structured["country"]
            if structured.get("certifications"):
                certs = [c.strip().upper() for c in structured["certifications"].split(",")]
                intent.certifications = list(dict.fromkeys([*certs, *intent.certifications]))
            # Merge productName, quantity, brand into keywords for richer matching
            sf_keywords = []
            for sf_field in ["productName", "quantity", "brand"]:
                val = structured.get(sf_field)
                if val and val not in sf_keywords:
                    sf_keywords.append(val)
            if structured.get("unit"):
                sf_keywords.append(structured["unit"])
            if sf_keywords:
                intent.keywords = list(dict.fromkeys([*sf_keywords, *intent.keywords]))

        category = intent.category or "general procurement"
        country = intent.country or "any target country"
        max_price = intent.max_price or 0

        if progress:
            budget_detail = f"预算 €{max_price}" if max_price else "未设置预算"
            progress("parse", f"已理解需求：品类「{category}」、目标地区「{country}」、{budget_detail}。", 35)

        if progress:
            progress("retrieve", f"正在检索「{category}」相关的供应商资源，包括本地数据库和外部网页研究...", 45)

        candidates = await self.retriever.search(intent, query=query, progress=progress)

        if progress:
            progress("retrieve", f"已收集到 {len(candidates)} 个候选供应商，正在进行质量过滤和相关性匹配...", 70)

        if progress:
            progress("rank", "正在根据您的采购需求对候选供应商进行智能排序...", 80)

        ranked = await self.ranker.rank_suppliers(query, candidates)

        top = ranked[0]["name"] if ranked else "未找到匹配供应商"
        if progress:
            progress("rank", f"排序完成！共 {len(ranked)} 个候选供应商，最佳匹配：{top}。", 95)

        return {"intent": intent.model_dump(), "results": ranked}

    async def search_quotes(
        self,
        query: str,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        delivery_time: Optional[str] = None,
    ) -> dict:
        """Full pipeline for quote comparison."""
        intent = await self.parser.parse(query)
        max_delivery_days = self._delivery_time_to_days(delivery_time) or intent.max_delivery_days
        candidates = [
            quote
            for quote in self.quotes
            if intent.category is None or quote.get("category") == intent.category
        ]
        ranked = await self.ranker.rank_quotes(
            query,
            candidates,
            min_price=min_price,
            max_price=max_price if max_price is not None else intent.max_price,
            max_delivery_days=max_delivery_days,
        )
        return {"intent": intent.model_dump(), "results": ranked}

    @staticmethod
    def _create_llm():
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-key-here":
            return None
        try:
            from langchain_openai import ChatOpenAI

            kwargs = {
                "model": os.getenv("LLM_MODEL", "gpt-4o"),
                "temperature": 0,
            }
            base_url = os.getenv("OPENAI_BASE_URL")
            if base_url:
                kwargs["base_url"] = base_url
            return ChatOpenAI(**kwargs)
        except Exception:
            return None

    @staticmethod
    def _create_chroma_collection():
        try:
            import chromadb

            persist_dir = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_data"))
            client = chromadb.PersistentClient(path=persist_dir)
            return client.get_or_create_collection(name="suppliers", embedding_function=None)
        except Exception:
            return None

    @staticmethod
    def _load_json(path: Path) -> list[dict]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _delivery_time_to_days(delivery_time: Optional[str]) -> Optional[int]:
        mapping = {
            "within3": 3,
            "within7": 7,
            "unlimited": None,
            None: None,
        }
        return mapping.get(delivery_time)
