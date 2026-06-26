from __future__ import annotations

import json
import math
import os
from collections import Counter
from typing import Any

from agent.parser import ProcurementIntent
from web_research.researcher import WebResearcher


class SupplierRetriever:
    def __init__(self, chroma_collection, suppliers: list[dict], llm=None):
        self.collection = chroma_collection
        self.suppliers = suppliers
        self.llm = llm
        self._supplier_by_id = {supplier["id"]: supplier for supplier in suppliers}
        self._embedding_model = None
        self._build_collection()

    async def search(self, intent: ProcurementIntent, query: str = "",
                     top_k: int = 10, progress=None) -> list[dict]:
        """
        Search local DB by intent.

        New logic (workflow1 only):
          1. Score ALL local suppliers, count how many have score >= 60.
          2. If >= 10 qualified → return ALL of them (uncapped).
          3. If < 10 → trigger web search.
          4. If web search returns < 5 results → use LLM to generate
             2-3 rephrased queries and re-search.
          5. Merge local + web results, cap at top_k (no padding to 10).
        """
        query_str = self._intent_to_query(intent)
        all_local = self._search_local(query_str, intent, top_k=len(self.suppliers))
        qualified = [s for s in all_local if s.get("matchScore", 0) >= 60]

        # ALWAYS run web search to supplement local results with fresh/current data.
        # Previously we short-circuited when >=10 local suppliers qualified, which
        # caused equipment searches to skip web search entirely → fast but low match quality.
        web_results = await self._web_search(intent, progress=progress)

        # <5 web results → LLM rephrase & re-search with alt queries
        if len(web_results) < 5 and (query or intent.keywords):
            alt_queries = await self._generate_alt_queries(
                query or " ".join(intent.keywords)
            )
            for alt_q in alt_queries:
                alt_intent = ProcurementIntent(
                    category=intent.category,
                    country=intent.country,
                    certifications=intent.certifications,
                    max_price=intent.max_price,
                    max_delivery_days=intent.max_delivery_days,
                    keywords=alt_q.split(),
                )
                more = await self._web_search(alt_intent, progress=progress)
                web_results = self._merge_results(web_results, more)

        merged = self._merge_results(all_local, web_results)
        return merged[:top_k]

    async def _web_search(self, intent: ProcurementIntent, progress=None) -> list[dict]:
        """Run agent-like web research to discover external supplier candidates."""
        researcher = WebResearcher(llm=self.llm)
        return await researcher.research(intent, max_suppliers=8, progress=progress)

    async def _generate_alt_queries(self, query: str) -> list[str]:
        """Use LLM to generate 2-3 rephrased B2B search queries for re-search.

        Called when the first web search round returns < 5 results,
        suggesting the original query phrasing was suboptimal.
        """
        if not self.llm or not query.strip():
            return []

        prompt = (
            "You are a B2B procurement specialist. The following user query "
            "returned very few supplier results from web search.\n\n"
            f"Original query: {query}\n\n"
            "Generate 2-3 ALTERNATIVE search queries in German that rephrase "
            "the same need using different B2B terminology, synonyms, or "
            "industry-specific terms. Focus on German B2B terms "
            "(Lieferant, Großhandel, Hersteller, Einkauf, Bezug, etc.)\n\n"
            "Return ONLY the queries, one per line. No numbering, no explanations."
        )

        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                import asyncio
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return []
            content = str(getattr(response, "content", response))
            queries = []
            for line in content.strip().split("\n"):
                q = line.strip().lstrip("0123456789.-) ").strip()
                if q and len(q) > 10 and not q.startswith("```"):
                    queries.append(q)
            return queries[:3]
        except Exception:
            return []

    def _build_collection(self) -> None:
        """Deferred build — called lazily on first _search_chroma call."""
        self._collection_built = False

    def _ensure_collection(self) -> None:
        """Build ChromaDB collection lazily (avoids blocking init on model download).

        On Render's free tier, downloading sentence-transformers (BAAI/bge-m3, ~2 GB)
        on every cold start causes 502 timeout / OOM.  Skip embedding-based populating
        when the collection is empty and fall through to the lexical-scoring fallback
        in _search_local.
        """
        if self._collection_built:
            return
        self._collection_built = True

        if self.collection is None or not self.suppliers:
            self.collection = None
            return

        # If the collection already has documents we can query it directly.
        try:
            count = self.collection.count()
            if count > 0:
                return
        except Exception:
            pass

        # No pre-existing documents — avoid downloading the embedding model.
        # The lexical-scoring fallback in _search_local handles this case.
        self.collection = None

    def _search_local(self, query: str, intent: ProcurementIntent, top_k: int) -> list[dict]:
        """Score ALL suppliers (not just top_k candidates) for a complete picture.

        Uses chroma embedding similarity when available, falls back to
        lexical cosine similarity for any supplier chroma misses.
        """
        chroma_by_id: dict[str, int] = {}
        chroma_results = self._search_chroma(query, len(self.suppliers))
        if chroma_results:
            chroma_by_id = {s["id"]: score for s, score in chroma_results}

        all_scored = []
        for supplier in self.suppliers:
            base_score = chroma_by_id.get(supplier["id"])
            if base_score is None:
                base_score = self._lexical_score(query, supplier)
            enriched = self._apply_intent_boosts(supplier, intent, base_score)
            all_scored.append(enriched)

        all_scored.sort(key=lambda item: item.get("matchScore", 0), reverse=True)
        return all_scored[:top_k]

    def _search_chroma(self, query: str, top_k: int) -> list[tuple[dict, int]]:
        self._ensure_collection()
        if self.collection is None:
            return []
        try:
            query_embedding = self._embed_documents([query])
            if query_embedding is None:
                return []
            kwargs: dict[str, Any] = {
                "query_embeddings": query_embedding,
                "n_results": min(top_k, len(self.suppliers)),
            }
            results = self.collection.query(**kwargs)
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else []
            output = []
            for idx, supplier_id in enumerate(ids):
                supplier = self._supplier_by_id.get(supplier_id)
                if not supplier:
                    continue
                distance = float(distances[idx]) if idx < len(distances) else 0.0
                score = max(0, min(100, round(100 - distance * 35)))
                output.append((supplier, score))
            return output
        except Exception:
            return []

    def _embed_documents(self, documents: list[str]) -> list[list[float]] | None:
        try:
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer

                model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
                self._embedding_model = SentenceTransformer(model_name)
            return self._embedding_model.encode(documents, normalize_embeddings=True).tolist()
        except Exception:
            return None

    def _apply_intent_boosts(self, supplier: dict, intent: ProcurementIntent, base_score: int) -> dict:
        score = int(base_score)
        quality_prior = int(supplier.get("matchScore", 70))
        if intent.category and supplier.get("category") == intent.category:
            score += 20
        elif intent.category:
            score -= 15
        if intent.country and intent.country != "Europe" and supplier.get("country") == intent.country:
            score += 12
        if intent.certifications:
            supplier_certs = {cert.upper() for cert in supplier.get("certifications", [])}
            if all(cert.upper() in supplier_certs for cert in intent.certifications):
                score += 10
            else:
                score -= 8
        score = round(score * 0.75 + quality_prior * 0.25)
        score = max(0, min(100, score))
        enriched = dict(supplier)
        enriched["matchScore"] = score
        enriched.setdefault("source", "database")
        enriched.setdefault("repurchasePriority", "database")
        return enriched

    def _lexical_score(self, query: str, supplier: dict) -> int:
        query_terms = Counter(self._tokenize(query))
        supplier_terms = Counter(self._tokenize(self._supplier_to_document(supplier)))
        if not query_terms or not supplier_terms:
            return int(supplier.get("matchScore", 0))
        overlap = sum(min(count, supplier_terms[token]) for token, count in query_terms.items())
        norm = math.sqrt(sum(query_terms.values())) * math.sqrt(sum(supplier_terms.values()))
        similarity = overlap / norm if norm else 0
        return round(similarity * 100)

    @staticmethod
    def _merge_results(local_results: list[dict], web_results: list[dict]) -> list[dict]:
        """Merge local + web results, dedup by ID, sort by matchScore (no bonus).

        Web results are scored by their own relevance (LLM-extracted matchScore),
        while local results already have their category/region/cert boosts applied.
        Sorting by raw matchScore ensures the highest-quality results from
        *either* source rise to the top.
        """
        merged: dict[str, dict] = {}
        for item in local_results:
            enriched = dict(item)
            enriched.setdefault("source", "database")
            enriched.setdefault("repurchasePriority", "database")
            merged[enriched["id"]] = enriched
        for item in web_results:
            merged.setdefault(item["id"], item)
        return sorted(merged.values(), key=lambda x: x.get("matchScore", 0), reverse=True)

    @staticmethod
    def _intent_to_query(intent: ProcurementIntent) -> str:
        parts = [
            intent.category or "",
            intent.country or "",
            " ".join(intent.certifications),
            " ".join(intent.keywords),
        ]
        if intent.max_price is not None:
            parts.append(f"max price {intent.max_price} EUR")
        if intent.max_delivery_days is not None:
            parts.append(f"delivery within {intent.max_delivery_days} days")
        return " ".join(part for part in parts if part).strip() or "automotive procurement supplier"

    @staticmethod
    def _supplier_to_document(supplier: dict) -> str:
        fields = [
            supplier.get("name"),
            supplier.get("category"),
            supplier.get("country"),
            supplier.get("city"),
            supplier.get("description"),
            " ".join(supplier.get("products", [])),
            " ".join(supplier.get("certifications", [])),
            " ".join(supplier.get("capabilities", [])),
        ]
        return " ".join(str(field) for field in fields if field)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re

        return re.findall(r"[\w\u4e00-\u9fffäöüÄÖÜß+-]+", text.lower())
