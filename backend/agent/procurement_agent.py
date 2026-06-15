from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from agent.parser import IntentParser
from agent.ranker import LLMRanker
from agent.retriever import SupplierRetriever


BASE_DIR = Path(__file__).resolve().parents[1]


class ProcurementAgent:
    def __init__(self):
        self.llm = self._create_llm()
        self.suppliers = self._load_json(BASE_DIR / "data" / "suppliers.json")
        self.quotes = self._load_json(BASE_DIR / "data" / "quotes.json")
        self.parser = IntentParser(self.llm)
        chroma_collection = self._create_chroma_collection()
        self.retriever = SupplierRetriever(chroma_collection, self.suppliers)
        self.ranker = LLMRanker(self.llm)

    async def search_suppliers(self, query: str) -> dict:
        """Full pipeline: parse → retrieve → rank → return"""
        intent = await self.parser.parse(query)
        candidates = await self.retriever.search(intent)
        ranked = await self.ranker.rank_suppliers(query, candidates)
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
