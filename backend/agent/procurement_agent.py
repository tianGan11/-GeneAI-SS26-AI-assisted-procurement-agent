from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from agent.parser import IntentParser
from agent.ranker import LLMRanker
from agent.retriever import SupplierRetriever
from web_research.researcher import DuckDuckGoSearchProvider, SearchResult
from database import query_suppliers_sync
from database import query_products_sync

BASE_DIR = Path(__file__).resolve().parents[1]


class ProcurementAgent:
    QUOTE_WEB_BLOCKED_DOMAINS = (
        "temu.com",
        "play.google.com",
        "chromewebstore.google.com",
        "kimi.com",
        "claude.com",
        "gemini.google.com",
        "tinypng.com",
        "stitch.withgoogle.com",
        "google.com",
        "youtube.com",
        "facebook.com",
        "instagram.com",
        "pinterest.com",
        "wikipedia.org",
        "reddit.com",
        "linkedin.com",
    )
    QUOTE_WEB_STOPWORDS = {
        "supplier", "price", "germany", "b2b", "quote", "quotes", "buy", "shop",
        "online", "standard", "product", "products", "hardware", "office", "search",
        "采购", "供应商", "标准品", "报价", "德国", "价格", "比价",
    }

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
        self.quote_search_provider = DuckDuckGoSearchProvider()

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
            progress("parse", f"已理解需求：品类「{category}」、目标地区「{country}」、{budget_detail}。", 18)

        if progress:
            progress("retrieve", f"第一步先检索本地供应商数据库，确认是否已有可复购/可复用供应商...", 24)

        candidates = await self.retriever.search(intent, query=query, progress=progress)

        if progress:
            progress("retrieve", f"已收集到 {len(candidates)} 个候选供应商，正在进行质量过滤和相关性匹配...", 68)

        if progress:
            progress("rank", "正在根据您的采购需求对候选供应商进行智能排序...", 82)

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
        weights: Optional[dict] = None,
        progress=None,
    ) -> dict:
        """Full pipeline for standard-product quote comparison.

        The comparison Agent mirrors supplier sourcing: parse the full request,
        search the local standard-product/quote database first, apply hard
        filters, then let the ranker/LLM prepare a decision-ready shortlist.
        """
        if progress:
            progress("parse", "正在解析标准品比价需求，合并自然语言、前置过滤条件和权重偏好...", 10)

        intent = await self.parser.parse(query)
        max_delivery_days = self._delivery_time_to_days(delivery_time) or intent.max_delivery_days
        effective_max_price = max_price if max_price is not None else intent.max_price
        category = intent.category or "all standard products"
        delivery_label = f"{max_delivery_days} 天内" if max_delivery_days else "不限时效"
        weight_text = ""
        if weights:
            weight_text = (
                f"；权重：价格 {weights.get('price', 40)}%、"
                f"交付 {weights.get('delivery', 35)}%、评价 {weights.get('rating', 25)}%"
            )

        if progress:
            budget_detail = f"€{min_price or 0}–€{effective_max_price}" if effective_max_price else f"最低 €{min_price}" if min_price else "未设置预算"
            progress("parse", f"已理解需求：品类「{category}」、预算「{budget_detail}」、交付「{delivery_label}」{weight_text}。", 18)

        if progress:
            progress("retrieve", "第一步先检索本地标准品/报价数据库，确认是否已有可比价商品...", 24)

        local_candidates = [
            {**quote, "source": quote.get("source", "database"), "sourceDetail": quote.get("sourceDetail", "database")}
            for quote in self.quotes
            if intent.category is None or quote.get("category") == intent.category
        ]

        if progress:
            progress("retrieve", f"本地标准品/报价库已检索完成：找到 {len(local_candidates)} 条本地候选，正在应用前置过滤条件...", 42)

        if progress:
            progress("web", "第二步开始联网搜索标准品报价/商品候选，用于补充本地报价库没有覆盖的结果...", 50)
        web_candidates = await self._search_web_quotes(query, intent, max_results=8)
        if progress:
            price_known = sum(1 for item in web_candidates if item.get("unitPriceEur") is not None)
            progress("web", f"网络搜索完成：找到 {len(web_candidates)} 条网络候选，其中 {price_known} 条提取到明确价格，其余标记为需人工核价。", 64)

        all_candidates = self._merge_quote_candidates(local_candidates, web_candidates)

        ranked = await self.ranker.rank_quotes(
            query,
            all_candidates,
            min_price=min_price,
            max_price=effective_max_price,
            max_delivery_days=max_delivery_days,
            weights=weights,
        )

        local_ranked = sum(1 for item in ranked if item.get("source") == "database")
        web_ranked = sum(1 for item in ranked if item.get("source") == "web")
        if progress:
            progress("rank", f"已根据预算、交付、评价和权重偏好筛选出 {len(ranked)} 条候选（本地 {local_ranked} 条，网络 {web_ranked} 条），正在生成推荐排序...", 82)

        top = ranked[0].get("vendor") if ranked else "未找到匹配标准品"
        if progress:
            progress("rank", f"标准品比价完成！共 {len(ranked)} 条候选，当前推荐：{top}。", 95)

        return {"intent": intent.model_dump(), "results": ranked}

    async def _search_web_quotes(self, query: str, intent, max_results: int = 8) -> list[dict]:
        """Search the public web for quote/product candidates without fabricating prices.

        Web candidates are supplemental. If the search snippet does not contain a
        clear EUR price, unitPriceEur stays None and the UI shows "needs manual
        price check" rather than pretending it is cheap.
        """
        search_query = f"{query} supplier price Germany B2B"
        try:
            results = await self.quote_search_provider.search(search_query, max_results=max_results)
        except Exception:
            results = []
        candidates: list[dict] = []
        for idx, result in enumerate(results):
            candidate = self._web_quote_candidate_from_result(result, intent, idx, query)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _web_quote_candidate_from_result(self, result: SearchResult, intent, idx: int, query: str) -> dict | None:
        url = (result.url or "").strip()
        title = (result.title or "").strip()
        snippet = (result.snippet or "").strip()
        if not url or not title:
            return None
        host = self._hostname(url)
        if not host or self._is_blocked_quote_domain(host):
            return None
        text = f"{title} {snippet}"
        price = self._extract_eur_price(text)
        if not self._is_relevant_quote_result(text, query, intent, price_found=price is not None):
            return None
        vendor = self._vendor_from_host(host)
        category = intent.category or "web"
        return {
            "id": f"web-quote-{idx}-{abs(hash(url)) % 10_000_000}",
            "vendor": vendor,
            "platform": host,
            "product": title,
            "category": category,
            "description": snippet,
            "matchScore": 64,
            "unitPriceEur": price,
            "unitLabel": f"€ {price:.2f}" if price is not None else "需人工核价",
            "deliveryDays": None,
            "deliveryLabel": "需确认交期",
            "paymentTerm": "prepayment",
            "paymentLabel": "需确认付款方式",
            "deliveryMethod": "需确认配送方式",
            "rating": 0,
            "reviews": 0,
            "source": "web",
            "sourceDetail": "web-search",
            "sourceUrls": [url],
            "evidenceSnippets": [snippet] if snippet else [],
            "priceConfidence": "extracted" if price is not None else "unknown",
        }

    @classmethod
    def _is_blocked_quote_domain(cls, host: str) -> bool:
        host = host.lower()
        return any(host == domain or host.endswith(f".{domain}") for domain in cls.QUOTE_WEB_BLOCKED_DOMAINS)

    @classmethod
    def _is_relevant_quote_result(cls, text: str, query: str, intent, price_found: bool = False) -> bool:
        haystack = text.lower()
        terms = cls._quote_relevance_terms(query, intent)
        if not terms:
            return price_found
        overlap = sum(1 for term in terms if term in haystack)
        # A priced result still needs at least one domain/query signal; otherwise
        # generic search noise such as AI tools or app stores can pollute quotes.
        return overlap >= 1

    @classmethod
    def _quote_relevance_terms(cls, query: str, intent) -> set[str]:
        raw_terms = re.findall(r"[a-zA-Z0-9äöüÄÖÜß]{3,}", query.lower())
        for field in ("category", "country"):
            value = getattr(intent, field, None)
            if value:
                raw_terms.extend(re.findall(r"[a-zA-Z0-9äöüÄÖÜß]{3,}", str(value).lower()))
        for keyword in getattr(intent, "keywords", []) or []:
            raw_terms.extend(re.findall(r"[a-zA-Z0-9äöüÄÖÜß]{3,}", str(keyword).lower()))
        return {term for term in raw_terms if term not in cls.QUOTE_WEB_STOPWORDS and len(term) >= 3}

    @classmethod
    def _extract_eur_price(cls, text: str) -> float | None:
        patterns = [
            r"€\s*([0-9][0-9.,]*(?:[.,][0-9]{2})?)",
            r"([0-9][0-9.,]*(?:[.,][0-9]{2})?)\s*(?:EUR|Euro|€)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = cls._parse_price_number(match.group(1))
            if value is not None and 0 < value < 100000:
                return value
        return None

    @staticmethod
    def _parse_price_number(raw: str) -> float | None:
        value = raw.strip().replace(" ", "")
        if not value:
            return None
        dot = value.rfind(".")
        comma = value.rfind(",")
        if dot != -1 and comma != -1:
            # Last separator is decimal, the other is thousands: 1.234,56 / 1,234.56
            if dot > comma:
                value = value.replace(",", "")
            else:
                value = value.replace(".", "").replace(",", ".")
        elif comma != -1:
            parts = value.split(",")
            if len(parts[-1]) == 2:
                value = "".join(parts[:-1]).replace(",", "") + "." + parts[-1]
            else:
                value = value.replace(",", "")
        elif dot != -1:
            parts = value.split(".")
            if len(parts) > 2 and len(parts[-1]) == 2:
                value = "".join(parts[:-1]) + "." + parts[-1]
            elif len(parts) > 2:
                value = "".join(parts)
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _hostname(url: str) -> str:
        try:
            from urllib.parse import urlparse
            return (urlparse(url).netloc or "").replace("www.", "")
        except Exception:
            return ""

    @staticmethod
    def _vendor_from_host(host: str) -> str:
        base = host.split(":", 1)[0].split(".")[0]
        return base.replace("-", " ").replace("_", " ").title() or host

    @staticmethod
    def _merge_quote_candidates(local_candidates: list[dict], web_candidates: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for item in [*local_candidates, *web_candidates]:
            key = str(item.get("id") or item.get("sourceUrls") or item.get("vendor") or len(merged))
            merged[key] = item
        return list(merged.values())

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
