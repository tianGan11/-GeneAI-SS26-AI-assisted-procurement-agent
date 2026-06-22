from __future__ import annotations

import json
import math
import os
import uuid
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from agent.parser import ProcurementIntent


class SupplierRetriever:
    def __init__(self, chroma_collection, suppliers: list[dict]):
        self.collection = chroma_collection
        self.suppliers = suppliers
        self._supplier_by_id = {supplier["id"]: supplier for supplier in suppliers}
        self._embedding_model = None
        self._build_collection()

    async def search(self, intent: ProcurementIntent, top_k: int = 10) -> list[dict]:
        """Search local vector DB by intent. If results < 3 or top score < 60, fallback to web search."""
        query = self._intent_to_query(intent)
        local_results = self._search_local(query, intent, top_k)
        if len(local_results) < 3 or (local_results and local_results[0].get("matchScore", 0) < 60):
            web_results = await self._web_search(intent)
            merged = self._merge_results(local_results, web_results)
            return merged[:top_k]
        return local_results[:top_k]

    async def _web_search(self, intent: ProcurementIntent) -> list[dict]:
        """Use duckduckgo to find suppliers, then return normalized supplier-like records."""
        query = f"{self._intent_to_query(intent)} automotive supplier"
        try:
            from duckduckgo_search import DDGS

            with DDGS(timeout=10) as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception:
            return []

        web_suppliers = []
        dynamic_scraper = None
        deep_scrapes = 0
        for result in results:
            title = result.get("title") or "Web supplier"
            href = result.get("href") or result.get("url") or ""
            body = result.get("body") or ""
            supplier = {
                "id": f"web-{uuid.uuid5(uuid.NAMESPACE_URL, href or title)}",
                "name": title,
                "category": intent.category,
                "country": intent.country,
                "city": None,
                "description": body,
                "products": intent.keywords,
                "certifications": intent.certifications,
                "contactPerson": None,
                "phone": None,
                "email": None,
                "website": href,
                "employees": None,
                "annualRevenue": None,
                "established": None,
                "capabilities": intent.keywords,
                "matchScore": 55,
                "source": "web",
            }
            if href and deep_scrapes < 3 and self._is_b2b_domain(href):
                if dynamic_scraper is None:
                    try:
                        from scraper.dynamic_scraper import DynamicScraper

                        dynamic_scraper = DynamicScraper()
                    except Exception:
                        dynamic_scraper = False
                if dynamic_scraper:
                    deep_scrapes += 1
                    try:
                        scraped_supplier = dynamic_scraper.scrape_supplier(href)
                        supplier = self._merge_web_supplier(supplier, scraped_supplier, intent)
                    except Exception:
                        pass
            web_suppliers.append(supplier)
        return web_suppliers

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
        chroma_results = self._search_chroma(query, top_k)
        if chroma_results:
            return [self._apply_intent_boosts(supplier, intent, score) for supplier, score in chroma_results]

        scored = [
            self._apply_intent_boosts(supplier, intent, self._lexical_score(query, supplier))
            for supplier in self.suppliers
        ]
        return sorted(scored, key=lambda item: item.get("matchScore", 0), reverse=True)[:top_k]

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
        merged: dict[str, dict] = {item["id"]: item for item in local_results}
        for item in web_results:
            merged.setdefault(item["id"], item)
        return sorted(merged.values(), key=lambda item: item.get("matchScore", 0), reverse=True)

    @staticmethod
    def _is_b2b_domain(url: str) -> bool:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        b2b_domains = (
            "wlw.de",
            "wer-liefert-was.de",
            "industrie.de",
            "industrystock.de",
            "directindustry.de",
            "directindustry.com",
            "europages.de",
            "europages.com",
            "kompass.com",
            "thomasnet.com",
            "b2bmarktplatz.de",
            "directory.de",
        )
        return any(domain == item or domain.endswith(f".{item}") for item in b2b_domains)

    @staticmethod
    def _merge_web_supplier(web_supplier: dict, scraped: dict, intent: ProcurementIntent) -> dict:
        """Merge DuckDuckGo summary with deep-scraped data. Scraped data wins."""
        if not scraped or not scraped.get("name"):
            return web_supplier
        merged = dict(web_supplier)
        for field in ("name", "description", "products", "certifications", "capabilities",
                       "phone", "email", "city", "employees", "annualRevenue", "established"):
            if scraped.get(field):
                merged[field] = scraped[field]
        merged["category"] = merged.get("category") or intent.category
        merged["country"] = merged.get("country") or intent.country
        if not merged.get("certifications"):
            merged["certifications"] = intent.certifications
        if not merged.get("products"):
            merged["products"] = intent.keywords
        if not merged.get("capabilities"):
            merged["capabilities"] = intent.keywords
        merged["matchScore"] = max(web_supplier.get("matchScore", 55),
                                   scraped.get("matchScore", 50))
        merged["source"] = "deep-web"
        return merged

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
