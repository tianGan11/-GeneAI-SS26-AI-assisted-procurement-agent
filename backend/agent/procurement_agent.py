from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

from agent.parser import IntentParser
from agent.ranker import LLMRanker
from agent.retriever import SupplierRetriever
from web_research.researcher import DuckDuckGoSearchProvider, SearchResult, StaticPageFetcher, WebResearcher
from web_research.idealo_scraper import search_idealo
from web_research.wlw_scraper import search_wlw
from database import query_suppliers_sync, query_products_sync

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
        "deutschepost.de",
        "rechneronline.de",
        "omnicalculator.com",
        "euroshop-online.de",
        "preis.de",
        "bitpanda.com",
        "dockers.com",
        "dockers.eu",
        "dockandbay.com",
        "dockandbay.eu",
        "ebay.de",
        "ebay.com",
        "chip.de",
        "garden-dock.com",
    )
    QUOTE_WEB_STOPWORDS = {
        "supplier", "price", "germany", "b2b", "quote", "quotes", "buy", "shop",
        "online", "standard", "product", "products", "hardware", "office", "search",
        "采购", "供应商", "标准品", "报价", "德国", "价格", "比价",
    }

    def __init__(self):
        self.llm = self._create_llm()
        self.suppliers = query_suppliers_sync()
        self.quotes = query_products_sync()
        self.parser = IntentParser(self.llm)
        chroma_collection = self._create_chroma_collection()
        self.retriever = SupplierRetriever(chroma_collection, self.suppliers, llm=self.llm)
        self.ranker = LLMRanker(self.llm)
        self.quote_search_provider = DuckDuckGoSearchProvider()
        self.quote_page_fetcher = StaticPageFetcher()
        self.web_researcher = WebResearcher(
            search_provider=self.quote_search_provider,
            page_fetcher=self.quote_page_fetcher,
            llm=self.llm,
        )

    async def search_suppliers(self, query: str, progress=None, structured: dict | None = None) -> dict:
        """Full pipeline: parse → local DB → WLW B2B → WebResearcher → merge → rank.

        Pipeline stages:
        1. Parse user intent (LLM)
        2. Search local supplier database (Chroma)
        3. If local results < threshold, search WLW.de B2B directory
        4. If WLW returns < threshold, fall back to WebResearcher (DDG + LLM)
        5. Merge all sources, rank, filter by matchScore >= 60

        structured, when provided, contains B2B-procurement fields from the
        frontend's structured form; these override LLM-parsed intent values.
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

        # ── ✨ Translate to German BEFORE local DB and web search ─────
        # WLW.de and WebResearcher search German sites. Translate the Chinese
        # query to German/English keywords and inject them into intent.keywords
        # so the Chroma retriever and downstream steps all benefit.
        german_supplier_phrase = ""
        if self.llm:
            if progress:
                progress("parse", "正在将中文需求翻译为德语/英语，以便匹配德文供应商数据库...", 22)
            german_kw = await self._llm_search_keywords_async(query)
            if german_kw:
                german_supplier_phrase = german_kw
                de_terms = [t for t in german_kw.split() if len(t) >= 2]
                intent.keywords = list(dict.fromkeys([*de_terms, *(intent.keywords or [])]))
                if progress:
                    progress("parse", f"已翻译为德语搜索词：「{german_supplier_phrase}」。", 26)

        # ── Phase 1: Local database (Chroma) ──────────────────────────
        if progress:
            progress("retrieve", "第一步：检索本地供应商数据库，确认是否已有可复购/可复用供应商...", 30)

        local_candidates = await self.retriever.search(intent, query=query, progress=progress)

        if progress:
            progress("retrieve", f"本地数据库：找到 {len(local_candidates)} 个候选供应商。", 44)

        # ── Phase 2: WLW.de B2B directory (direct scrape) ─────────────
        web_candidates: list[dict] = []
        wlw_phrase = german_supplier_phrase or self._supplier_search_phrase(query, intent)

        if progress:
            progress("web", f"第二步：搜索 WLW.de B2B 供应商目录：「{wlw_phrase}」...", 44)

        try:
            wlw_results = await search_wlw(wlw_phrase, limit=5, timeout=50)
            if progress:
                progress("web", f"WLW.de 返回 {len(wlw_results)} 家供应商。", 50)
            web_candidates = await self._normalize_web_suppliers(wlw_results, intent)
        except Exception as e:
            if progress:
                progress("web", f"WLW.de 搜索失败（{e}），将使用搜索引擎兜底...", 50)
            wlw_results = []

        # ── Phase 3: WebResearcher (DDG + LLM) fallback ────────────────
        if len(wlw_results) < 3:
            if progress:
                progress("web", f"WLW 仅返回 {len(wlw_results)} 家，启动 WebResearcher（DDG搜索+LLM识别）补充...", 52)

            try:
                researcher_results = await self.web_researcher.research(
                    intent, max_suppliers=5, progress=progress
                )
                if progress:
                    progress("web", f"WebResearcher 补充了 {len(researcher_results)} 家候选供应商。", 62)
                web_candidates = self._merge_supplier_candidates(
                    web_candidates,
                    await self._normalize_web_suppliers(researcher_results, intent),
                )
            except Exception as e:
                if progress:
                    progress("web", f"WebResearcher 失败（{e}），仅使用 WLW + 本地数据库结果。", 62)

        # ── Phase 4: Merge all sources ─────────────────────────────────
        all_candidates = self._merge_supplier_candidates(local_candidates, web_candidates)

        local_count = sum(1 for c in all_candidates if c.get("source") in (None, "database"))
        web_count = sum(1 for c in all_candidates if c.get("source") == "web")
        if progress:
            progress("retrieve", f"候选汇总：本地 {local_count} 家 + 网络 {web_count} 家，共 {len(all_candidates)} 家。", 68)

        # ── Phase 5: Rank & filter ─────────────────────────────────────
        if progress:
            progress("rank", "正在根据采购需求对候选供应商进行智能排序和质量过滤...", 82)

        ranked = [
            supplier
            for supplier in await self.ranker.rank_suppliers(query, all_candidates)
            if int(supplier.get("matchScore", 0) or 0) >= 60
        ]

        top = ranked[0]["name"] if ranked else "未找到匹配供应商"
        if progress:
            local_ranked = sum(1 for r in ranked if r.get("source") in (None, "database"))
            web_ranked = sum(1 for r in ranked if r.get("source") == "web")
            progress("rank", f"排序完成！共 {len(ranked)} 家（本地 {local_ranked} + 网络 {web_ranked}），最佳匹配：{top}。", 95)

        return {"intent": intent.model_dump(), "results": ranked}

    # ── Supplier web search helpers ──────────────────────────────────

    @classmethod
    def _supplier_search_phrase(cls, query: str, intent) -> str:
        """Extract a search-friendly phrase from intent for WLW / B2B directory search."""
        keywords = getattr(intent, "keywords", []) or []
        category = getattr(intent, "category", None) or ""
        # Prefer explicit keywords, fall back to category + query words
        if keywords:
            return " ".join([str(k) for k in keywords[:4] if str(k).strip()])
        # Strip constraint words, keep product/business nouns
        cleaned = re.sub(r'[\d\s]*(预算|不超过|以内|欧元|台|个|元)[\d\s]*', ' ', query)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if category and category not in cleaned.lower():
            cleaned = f"{cleaned} {category}"
        return cleaned[:80]

    async def _normalize_web_suppliers(
        self, web_results: list[dict], intent
    ) -> list[dict]:
        """Normalize WLW / WebResearcher output to unified supplier format.

        Ensures every candidate has the fields the ranker expects:
        id, name, website, country, products, matchScore, source, sourceDetail, etc.
        """
        normalized = []
        for item in web_results:
            # Already has the right shape (e.g. from WLW)
            if "name" in item and "website" in item:
                # Ensure source is set
                if "source" not in item:
                    item["source"] = "web"
                if "sourceDetail" not in item:
                    item["sourceDetail"] = item.get("sourceDetail", "web")
                normalized.append(item)
                continue

            # From WebResearcher (may use different keys)
            name = item.get("name") or item.get("company_name") or item.get("title", "")
            website = item.get("website") or item.get("url", "")
            if not name and not website:
                continue
            normalized.append({
                "id": item.get("id", f"web-{abs(hash(website or name)) % 10_000_000}"),
                "name": name or "Web Supplier",
                "website": website,
                "country": item.get("country") or item.get("location", ""),
                "city": item.get("city", ""),
                "description": item.get("description", ""),
                "products": item.get("products") or item.get("matched_products") or [],
                "capabilities": item.get("capabilities") or item.get("supplier_type") or [],
                "certifications": item.get("certifications", []),
                "matchScore": item.get("matchScore") or item.get("score", 60),
                "phone": item.get("phone", ""),
                "email": item.get("email", ""),
                "contactPerson": item.get("contactPerson") or item.get("contact_person", ""),
                "employees": item.get("employees") or item.get("employee_count", ""),
                "source": item.get("source", "web"),
                "sourceDetail": item.get("sourceDetail", "web"),
                "sourceUrls": item.get("sourceUrls") or ([website] if website else []),
                "evidenceSnippets": item.get("evidenceSnippets", []),
                "is_supplier": item.get("is_supplier", True),
                # Extra fields from WLW
                "supplier_type": item.get("supplier_type", []),
                "founding_year": item.get("founding_year"),
                "delivery_range": item.get("delivery_range", ""),
            })
        return normalized

    @staticmethod
    def _merge_supplier_candidates(
        local: list[dict], web: list[dict]
    ) -> list[dict]:
        """Merge local + web supplier candidates, deduplicate by website URL."""
        merged: dict[str, dict] = {}
        for item in [*local, *web]:
            website = (item.get("website") or "").strip().rstrip("/")
            key = website.lower() if website else item.get("id") or item.get("name", "")
            if not key:
                key = str(len(merged))
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            # Prefer the entry with higher matchScore or more evidence
            existing_score = int(existing.get("matchScore", 0) or 0)
            item_score = int(item.get("matchScore", 0) or 0)
            existing_evidence = bool(existing.get("evidenceSnippets") or existing.get("description"))
            item_evidence = bool(item.get("evidenceSnippets") or item.get("description"))
            if item_score > existing_score or (item_score == existing_score and item_evidence and not existing_evidence):
                merged[key] = item
        return list(merged.values())

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

        Pipeline: parse → translate to German → local DB → idealo → DDG → merge → rank.
        Key insight: the database is in German, so we translate the Chinese query to
        German/English keywords FIRST and inject them into intent for all downstream steps.
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

        # ── ✨ STEP 0: Translate to German/English IMMEDIATELY ──────────
        # The database and websites are in German. We must translate the user's
        # Chinese query right away and inject German keywords into intent so
        # ALL downstream steps (local DB filter, web search, LLM filter) benefit.
        german_phrase = ""
        groups = self._quote_required_term_groups(query, intent)
        if not groups and self.llm:
            if progress:
                progress("parse", "正在将中文需求翻译为德语/英语关键词，以便匹配德文数据库和德国电商网站...", 21)
            german_kw = await self._llm_search_keywords_async(query)
            if german_kw:
                german_phrase = german_kw
                # Inject German terms into intent.keywords so local DB filter can use them
                de_terms = [t for t in german_kw.split() if len(t) >= 2]
                intent.keywords = list(dict.fromkeys([*de_terms, *(intent.keywords or [])]))
                if progress:
                    progress("parse", f"已翻译为德语搜索词：「{german_phrase}」，将用于本地数据库匹配和网站搜索。", 24)

        if progress:
            progress("retrieve", "第一步先检索本地标准品/报价数据库，确认是否已有可比价商品...", 28)

        local_candidates = [
            {**quote, "source": quote.get("source", "database"), "sourceDetail": quote.get("sourceDetail", "database")}
            for quote in self.quotes
            if intent.category is None or quote.get("category") == intent.category
        ]
        # When category is unknown, pre-filter by keyword to avoid flooding
        # the pipeline with 200+ irrelevant items (e.g., A4 paper when user
        # searches for "人体工学椅"). The full _is_relevant_quote_item check
        # follows below but this quick gate keeps the candidate list manageable.
        if intent.category is None and len(local_candidates) > 30:
            kw_terms = [t for t in (getattr(intent, "keywords", []) or []) if len(str(t)) >= 2]
            if kw_terms:
                pre_filtered = []
                for quote in local_candidates:
                    text = " ".join(str(quote.get(k, "")) for k in ("product", "vendor", "description") if quote.get(k))
                    if any(str(kw).lower() in text.lower() for kw in kw_terms):
                        pre_filtered.append(quote)
                # Keep at least 10 even if no keyword matches (avoid empty list for common queries)
                if len(pre_filtered) >= 5:
                    local_candidates = pre_filtered
        local_candidates = [
            quote for quote in local_candidates
            if self._is_relevant_quote_item(quote, query, intent)
        ]
        # Sanity check: office supplies rarely exceed 200 EUR per unit
        for quote in local_candidates:
            if quote.get("unitPriceEur") is not None and quote["unitPriceEur"] > 200:
                quote["unitPriceEur"] = None
                quote["unitLabel"] = "需人工核价"

        if progress:
            progress("retrieve", f"本地标准品/报价库已检索完成：找到 {len(local_candidates)} 条本地候选，正在应用前置过滤条件...", 42)

        if progress:
            progress("web", "第二步开始联网搜索 — 先查 idealo.de 比价平台，再补充搜索引擎...", 50)
        
        # ── Determine search phrase (reuse German translation if available) ──
        if german_phrase:
            search_phrase = german_phrase
        else:
            search_phrase = self._quote_search_product_phrase(query, intent)
        
        # Phase A: idealo.de (German price comparison — high-quality structured data)
        idealo_candidates = []
        if progress:
            progress("web", f"正在 idealo.de 搜索：「{search_phrase}」...", 52)
        try:
            idealo_candidates = await search_idealo(search_phrase, limit=4, timeout=35)
        except Exception:
            idealo_candidates = []
        if progress and idealo_candidates:
            progress("web", f"idealo.de 返回 {len(idealo_candidates)} 条比价候选（含商店/价格/评分）。", 55)
        
        # Phase B: DDG web search as fallback/supplement
        web_candidates = await self._search_web_quotes(query, intent, max_results=8, progress=progress, pre_translated_phrase=search_phrase)
        
        # Merge: idealo first (higher quality), then web
        web_candidates = self._merge_quote_candidates(idealo_candidates, web_candidates)
        if progress:
            price_known = sum(1 for item in web_candidates if item.get("unitPriceEur") is not None)
            progress("web", f"网络搜索完成：找到 {len(web_candidates)} 条网络候选，其中 {price_known} 条提取到明确价格，其余标记为需人工核价。", 64)

        all_candidates = self._merge_quote_candidates(local_candidates, web_candidates)
        all_candidates = self._prefer_priced_quote_candidates(all_candidates)

        if progress and len(all_candidates) > 0:
            progress("web", f"正在用 LLM 对 {len(all_candidates)} 条候选做精准产品相关性判断（替代关键词匹配）...", 72)
        all_candidates = await self._llm_filter_relevant_quotes(query, all_candidates, intent, german_search_terms=german_phrase)
        if progress:
            progress("web", f"LLM 相关性过滤完成：保留 {len(all_candidates)} 条真正匹配「{query}」的候选商品。", 78)

        ranked = await self.ranker.rank_quotes(
            query,
            all_candidates,
            min_price=min_price,
            max_price=effective_max_price,
            max_delivery_days=max_delivery_days,
            weights=weights,
        )

        # Fallback: if ranker eliminated everything, return LLM-filtered candidates unsorted
        if len(ranked) == 0 and len(all_candidates) > 0:
            ranked = sorted(all_candidates, key=lambda c: c.get("unitPriceEur") or 999999)[:20]
            if progress:
                progress("rank", f"硬筛选后无候选，已降级为价格排序展示前 {len(ranked)} 条以保持决策表不为空。", 82)
        
        local_ranked = sum(1 for item in ranked if item.get("source") == "database")
        web_ranked = sum(1 for item in ranked if item.get("source") == "web")
        if progress and len(ranked) > 0:
            local_has_price = sum(1 for item in ranked if item.get("source") == "database" and item.get("unitPriceEur") is not None)
            web_has_price = sum(1 for item in ranked if item.get("source") == "web" and item.get("unitPriceEur") is not None)
            progress("rank", f"已根据预算、交付、评价和权重偏好筛选出 {len(ranked)} 条候选（本地 {local_ranked} 条其中 {local_has_price} 有价格，网络 {web_ranked} 条其中 {web_has_price} 有价格），正在生成推荐排序...", 82)

        top = ranked[0].get("vendor") if ranked else "未找到匹配标准品"
        if progress:
            progress("rank", f"标准品比价完成！共 {len(ranked)} 条候选，当前推荐：{top}。", 95)

        return {"intent": intent.model_dump(), "results": ranked}

    async def _search_web_quotes(self, query: str, intent, max_results: int = 8, progress=None, pre_translated_phrase: str = "") -> list[dict]:
        """Search the public web for quote/product candidates and extract real prices.

        Uses targeted site-specific queries for German office-supply shops where
        prices are commonly listed. Runs searches in parallel batches of 3 to cut
        total network wait time by 60-70%.

        pre_translated_phrase: if provided (from caller's LLM translation), use it
        directly instead of re-translating — avoids duplicate LLM calls.
        """
        if pre_translated_phrase:
            product_phrase = pre_translated_phrase
        else:
            product_phrase = self._quote_search_product_phrase(query, intent)
            # For unknown product categories, use LLM to translate into German search terms
            groups = self._quote_required_term_groups(query, intent)
            if not groups and self.llm:
                llm_kw = await self._llm_search_keywords_async(query)
                if llm_kw:
                    product_phrase = llm_kw
                    if progress:
                        progress("web", f"LLM 将需求翻译为德语搜索词：「{product_phrase}」。", 51)
        candidates: list[dict] = []
        if progress:
            progress(
                "web",
                f"Agent 将本次需求转成可搜索的商品短语：「{product_phrase}」，准备优先查德国办公用品电商的商品页和价格片段。",
                52,
            )

        # Parallel helper
        async def _search_one(q: str):
            try:
                return q, await self.quote_search_provider.search(q, max_results=5)
            except Exception:
                return q, []

        # Phase 1: parallel site-specific searches on known German shops
        site_queries = self._quote_site_specific_queries(product_phrase)
        if progress:
            progress("web", f"并行启动 {len(site_queries)} 条网站搜索 + 价格搜索，每批 3 条并发，大幅缩短等待时间。", 53)

        q_idx = 0
        for batch_start in range(0, len(site_queries), 3):
            if q_idx >= 5 and sum(1 for item in candidates if item.get("unitPriceEur") is not None) >= 2:
                break
            batch = site_queries[batch_start:batch_start + 3]
            batch_results = await asyncio.gather(*(_search_one(q) for q in batch))
            for site_query, results in batch_results:
                if not results and not site_query.startswith("site:"):
                    continue
                if progress:
                    progress(
                        "web",
                        f"报价搜索 [{q_idx + 1}/{len(site_queries)}]：{site_query[:60]} -> {len(results)} 条。",
                        53 + int(q_idx * 1.2),
                    )
                more = await self._web_quote_candidates_from_results(results, intent, query, offset=len(candidates), progress=progress)
                candidates = self._merge_quote_candidates(candidates, more)
                q_idx += 1
                if sum(1 for item in candidates if item.get("unitPriceEur") is not None) >= 3:
                    break
            if sum(1 for item in candidates if item.get("unitPriceEur") is not None) >= 3:
                if progress:
                    progress("web", f"已收集足够带价候选 ({sum(1 for item in candidates if item.get('unitPriceEur') is not None)} 条)，提前结束搜索。", 63)
                break

        # Phase 2: extra price-oriented searches if still not enough
        if sum(1 for item in candidates if item.get("unitPriceEur") is not None) < 3:
            extra_queries = self._quote_price_search_queries(query, intent)
            seen_urls = {url for item in candidates for url in item.get("sourceUrls", [])}
            if progress:
                progress("web", "可用价格还不够，Agent 正在追加偏价格意图搜索词（Preis / kaufen / online bestellen）来补价。", 63)
            extra_batch = extra_queries[:2]
            extra_results_list = await asyncio.gather(*(_search_one(q) for q in extra_batch))
            for extra_query, extra_results in extra_results_list:
                fresh = [r for r in extra_results if r.url not in seen_urls]
                if progress:
                    progress("web", f"追加价格搜索：{extra_query[:60]} -> 新URL {len(fresh)} 条。", 69)
                more = await self._web_quote_candidates_from_results(fresh, intent, query, offset=len(candidates), progress=progress)
                candidates = self._merge_quote_candidates(candidates, more)
                seen_urls.update(url for item in more for url in item.get("sourceUrls", []))
                if sum(1 for item in candidates if item.get("unitPriceEur") is not None) >= 3:
                    break
        return candidates
    @classmethod
    def _quote_site_specific_queries(cls, product_phrase: str) -> list[str]:
        """Return queries targeting German e-commerce sites with prices."""
        # Detect if this is likely non-office (appliance, electronics, furniture)
        non_office_signals = ['kaffee', 'maschine', 'vollautomat', 'küche', 'herd', 
                              'kühlschrank', 'wasch', 'trockner', 'fernseher', 'staubsauger',
                              'möbel', 'stuhl', 'tisch', 'lampe', 'leuchte',
                              'iphone', 'smartphone', 'handy', 'telefon', 'laptop', 'notebook',
                              'thinkpad', 'elitebook', 'monitor', 'bildschirm', 'display',
                              'dock', 'docking', 'dockingstation', 'thunderbolt']
        is_non_office = any(s in product_phrase.lower() for s in non_office_signals)
        
        queries = [
            f"{product_phrase} kaufen Preis EUR",
            f"{product_phrase} online shop Deutschland Preis",
            f"{product_phrase} günstig bestellen",
        ]
        lower_phrase = product_phrase.lower()
        industrial_signals = ("festo", "steckanschluss", "anschluss", "pneumatik", "qs", "verschraubung")
        if any(signal in lower_phrase for signal in industrial_signals):
            queries = [
                f"site:festo.com/de/de {product_phrase}",
                f"site:automation24.de {product_phrase}",
                f"site:de.rs-online.com {product_phrase}",
                f"site:conrad.de {product_phrase}",
                f"site:voelkner.de {product_phrase}",
                f"{product_phrase} kaufen Preis EUR",
            ]
        elif is_non_office:
            # Target appliance/electronics/general retailers
            queries = [
                f"{product_phrase} kaufen Preis EUR",
                f"{product_phrase} online shop Deutschland",
                f"site:idealo.de {product_phrase}",
                f"site:notebooksbilliger.de {product_phrase}",
                f"site:cyberport.de {product_phrase}",
                f"site:alternate.de {product_phrase}",
                f"site:mediamarkt.de {product_phrase}",
                f"site:saturn.de {product_phrase}",
                f"site:amazon.de {product_phrase}",
            ]
        else:
            queries = [
                f"site:bueromarkt-ag.de {product_phrase}",
                f"site:schaefer-shop.de {product_phrase}",
                f"site:viking.de {product_phrase}",
                f"site:amazon.de {product_phrase}",
                f"{product_phrase} kaufen Preis EUR",
                f"{product_phrase} günstig bestellen",
            ]
        return queries

    # Track which listing URLs have been parsed to avoid redundant fetches
    _parsed_listing_urls: set[str] = set()

    async def _web_quote_candidates_from_results(
        self,
        results: list[SearchResult],
        intent,
        query: str,
        offset: int = 0,
        progress=None,
    ) -> list[dict]:
        candidates: list[dict] = []
        for idx, result in enumerate(results[:3]):
            host = self._hostname(result.url or "")
            # Deduplicate listing page parses
            listing_products: list[dict] = []
            url_key = (result.url or "").split("?")[0].rstrip("/")
            if url_key not in self._parsed_listing_urls:
                try:
                    listing_products = await self.quote_page_fetcher.fetch_products_from_listing(result.url)
                    if listing_products:
                        self._parsed_listing_urls.add(url_key)
                except Exception:
                    listing_products = []
            
            if listing_products:
                if progress:
                    progress("web", f"从商品列表页解析出 {len(listing_products)} 款单品：{host}。", 67)
                for lp_idx, prod in enumerate(listing_products):
                    vendor = self._vendor_from_host(host)
                    candidates.append({
                        "id": f"web-quote-{offset}-{idx}-{lp_idx}",
                        "vendor": vendor,
                        "platform": host,
                        "product": prod.get("product", result.title),
                        "category": intent.category or "web",
                        "description": "",
                        "matchScore": 76 if prod.get("unitPriceEur") else 58,
                        "unitPriceEur": prod.get("unitPriceEur"),
                        "unitLabel": prod.get("unitLabel", "需人工核价"),
                        "deliveryDays": prod.get("deliveryDays"),
                        "deliveryLabel": prod.get("deliveryLabel", "需确认交期"),
                        "paymentTerm": "prepayment",
                        "paymentLabel": "需确认付款方式",
                        "deliveryMethod": "需确认配送方式",
                        "rating": prod.get("rating", 0),
                        "reviews": prod.get("reviews", 0),
                        "source": "web",
                        "sourceDetail": "listing",
                        "sourceUrls": prod.get("sourceUrls", [result.url])[1:2] or prod.get("sourceUrls", [result.url])[:1],
                        "evidenceSnippets": prod.get("evidenceSnippets", []),
                        "priceConfidence": "extracted" if prod.get("unitPriceEur") else "unknown",
                    })
            else:
                candidate = await self._web_quote_candidate_from_result(result, intent, offset + idx, query, progress=progress)
                if candidate:
                    candidates.append(candidate)
        return candidates

    async def _web_quote_candidate_from_result(self, result: SearchResult, intent, idx: int, query: str, progress=None) -> dict | None:
        url = (result.url or "").strip()
        title = (result.title or "").strip()
        snippet = (result.snippet or "").strip()
        if not url or not title:
            return None
        host = self._hostname(url)
        if not host or self._is_blocked_quote_domain(host):
            return None
        text = f"{title} {snippet}"
        if self._is_quote_noise_result(text, url) or self._is_non_product_quote_page(title, snippet, url, intent):
            return None
        price = self._extract_eur_price(text)
        evidence_text = ""
        source_urls = [url]
        if price is not None and progress:
            progress("web", f"从搜索摘要直接抽到价格：{title[:60]} → € {price:.2f}。", 66)
        if price is None:
            try:
                if progress:
                    progress("web", f"摘要没有明确价格，正在打开商品页核价：{host} / {title[:60]}", 66)
                page = await self.quote_page_fetcher.fetch_page(url)
                if page.text:
                    evidence_text = page.text[:6000]
                    source_urls = [page.url or url]
                    price = self._extract_eur_price(f"{text} {evidence_text}")
                    if price is not None and progress:
                        progress("web", f"已从商品页结构化字段/正文抽到价格：{title[:60]} → € {price:.2f}。", 67)
                    elif progress:
                        progress("web", f"已打开商品页但没有可靠欧元价格：{title[:60]}，该候选会被降权或过滤。", 67)
                elif progress:
                    progress("web", f"商品页未返回可读正文，可能被验证码/反爬拦截：{host}。", 67)
            except Exception:
                evidence_text = ""
        if not self._is_relevant_quote_result(f"{text} {evidence_text}", query, intent, price_found=price is not None):
            return None
        # Sanity check: office supplies rarely exceed 200 EUR per unit
        if price is not None and price > 200:
            price = None
        vendor = self._vendor_from_host(host)
        category = intent.category or "web"
        return {
            "id": f"web-quote-{idx}-{abs(hash(url)) % 10_000_000}",
            "vendor": vendor,
            "platform": host,
            "product": title,
            "category": category,
            "description": snippet,
            "matchScore": 76 if price is not None else 58,
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
            "sourceUrls": source_urls,
            "evidenceSnippets": self._quote_evidence_snippets(evidence_text or snippet),
            "priceConfidence": "extracted" if price is not None else "unknown",
        }

    @classmethod
    def _quote_price_search_queries(cls, query: str, intent) -> list[str]:
        terms = cls._quote_search_product_phrase(query, intent)
        country = getattr(intent, "country", None) or "Germany"
        return [
            f"{terms} Preis €",
            f"{terms} günstig kaufen",
            f"{terms} online bestellen Preis",
            f"{terms} shop {country}",
        ]

    @classmethod
    def _quote_search_product_phrase(cls, query: str, intent) -> str:
        groups = cls._quote_required_term_groups(query, intent)
        if groups:
            preferred: list[str] = []
            for group in groups:
                for alias in (
                    "a4", "kopierpapier", "druckerpapier", "papier",
                    "steckanschluss", "anschluss", "qs", "sicherheitsschuh", "s3",
                    "spülmittel", "thunderbolt", "dock", "dockingstation",
                    "maus", "tastatur", "taschenrechner", "ordner", "heftklammern",
                    "schere", "klebestift", "edding", "post-it", "tesa", "papierkorb",
                    "aktenvernichter", "drucker", "monitor", "laptop", "iphone", "telefon",
                ):
                    if alias in group:
                        preferred.append(alias)
                        break
                else:
                    preferred.append(sorted(group, key=len)[0])
            phrase = " ".join(preferred)
            query_lower = query.lower()
            if any(term in phrase for term in ("laptop", "notebook")) and "thinkpad" in query_lower and "thinkpad" not in phrase:
                phrase = f"thinkpad {phrase}"
            if "monitor" in phrase:
                size = re.search(r'(\d{2})\s*(?:寸|zoll|inch|")', query_lower)
                if size and "zoll" not in phrase and "inch" not in phrase:
                    phrase = f"{size.group(1)} zoll {phrase}"
            if "dock" in phrase:
                extras = []
                for marker in ("hp", "thunderbolt", "usb-c", "usbc"):
                    if marker in query_lower and marker not in phrase:
                        extras.append("usb-c" if marker == "usbc" else marker)
                if extras:
                    phrase = " ".join([*extras, phrase])
            return phrase
        # No known product group matched — strip constraint words, keep product nouns
        terms = sorted(cls._quote_relevance_terms(query, intent), key=len, reverse=True)
        keyword_str = " ".join(terms[:5])
        stripped = cls._strip_constraint_words(keyword_str)
        return stripped or query[:80]

    async def _llm_search_keywords_async(self, query: str) -> str:
        """Use LLM to extract 2-3 search-friendly German keywords from any query."""
        if not self.llm:
            return ""
        prompt = (
            f"Convert this procurement request into 2-3 German search keywords for German e-commerce sites:\n"
            f"{query[:200]}\n\n"
            f"Return ONLY the keywords separated by spaces. No other text.\n"
            f"Example: 'kaffeemaschine vollautomatisch bohnen'"
        )
        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                import asyncio
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return ""
            text = str(getattr(response, "content", response)).strip()[:100]
            import re
            cleaned = re.sub(r'[^a-zA-Z0-9\s\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]', '', text)
            return cleaned.strip()
        except Exception:
            return ""

    @staticmethod
    def _strip_constraint_words(text: str) -> str:
        """Remove budget/quantity/constraint noise, keep product-signal words."""
        import re
        # Remove numbers with units
        text = re.sub(r'\d+\s*(台|个|欧元|元|预算|eur|st|stück|blatt)', '', text, flags=re.I)
        # Remove constraint phrases
        for phrase in ['预算', '适用于', '支持', '不限', '以内', '以上', '以下', '预算', '不超过']:
            text = text.replace(phrase, ' ')
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:100]

    @classmethod
    def _is_quote_noise_result(cls, text: str, url: str = "") -> bool:
        lowered = f"{text} {url}".lower()
        noise_markers = (
            "stückpreis rechner", "unit price calculator", "preis je menge", "omnicalculator",
            "briefmarke", "briefversand", "grossbrief", "großbrief",
            "alles für 1€", "alles fuer 1", "katalog", "aktionen",
            "berechnen", "calculator",
            "kopien ", "copy shop", "posterdruck",
            "0,05", "0.05 €",
            "kurs in euro", "live kurs", "crypto", "kryptowährung", "bitpanda",
            "men's and women's", "chinos", "khakis", "clothing", "dockers®",
        )
        return any(marker in lowered for marker in noise_markers)


    @classmethod
    def _term_in_text(cls, term: str, text: str) -> bool:
        term = str(term or "").lower().strip()
        if not term:
            return False
        if re.search(r"[\u4e00-\u9fff]", term):
            return term in text
        # Latin tokens need boundaries so dock != dockers and phone != headphone.
        return re.search(rf"(?<![a-z0-9äöüß]){re.escape(term)}(?![a-z0-9äöüß])", text, re.I) is not None

    @classmethod
    def _any_term_in_text(cls, terms, text: str) -> bool:
        return any(cls._term_in_text(str(term), text) for term in terms)

    @classmethod
    def _is_non_product_quote_page(cls, title: str, snippet: str, url: str, intent=None) -> bool:
        """Reject obvious non-product pages without killing useful shop/category leads.

        Trusted German procurement shops often expose category/listing URLs such as
        "Ordner günstig kaufen" or "Spülmittel 1 Liter". Those are acceptable quote
        leads when the text matches the product gate. We only reject clearly unrelated
        sites/pages (crypto, clothing brands, generic store homepages, broad accessory
        categories).
        """
        host = cls._hostname(url)
        text = f"{title} {snippet} {url}".lower()
        if cls._is_blocked_quote_domain(host):
            return True
        if host == "bing.com" and "aclick" in url.lower():
            return True

        trusted_hosts = (
            "bueromarkt-ag.de", "schaefer-shop.de", "viking.de", "amazon.de",
            "idealo.de", "otto.de", "mediamarkt.de", "saturn.de", "billiger.de",
            "notebooksbilliger.de", "cyberport.de", "alternate.de", "conrad.de", "voelkner.de", "reichelt.de",
            "rs-online.com", "de.rs-online.com", "distrelec.de", "automation24.de",
            "festo.com",
        )
        trusted = any(host == h or host.endswith(f".{h}") for h in trusted_hosts)
        trusted_search_noise = (
            "suchergebnis auf amazon",
            "dockingstationen online kaufen",
            "idealo – die nr. 1",
            "idealo - die nr. 1",
            "die nr. 1 im preisvergleich",
            "amazon.de: traditional",
            "amazon.de: mini",
            "thinkpad-angebote",
            "laptop-angebote",
            "sale/thinkpad",
        )
        if trusted and any(marker in text for marker in trusted_search_noise):
            return True
        if trusted:
            # Let product-level required/negative gates decide for trusted commerce sites.
            return False

        hard_noise = (
            "kurs in euro", "live kurs", "crypto", "kryptowährung", "bitpanda",
            "men's and women's", "chinos", "khakis", "clothing", "dockers®",
            "dock & bay", "handtücher", "towels", "schwimmdock",
        )
        if any(marker in text for marker in hard_noise):
            return True

        broad_page_markers = (
            "suchergebnis", "search results", "all - ", "collections",
            "computertechnik & zubehör", "monitore webcams & zubehör",
            "traditional laptops", "mini iphone",
        )
        if any(marker in text for marker in broad_page_markers):
            return True

        # Generic category/store pages without price and without a concrete product model are weak.
        if re.search(r"\b(all|alle|store|zubehör|accessories)\b", text) and not re.search(r"€|eur|[0-9]+,[0-9]{2}|[a-z]+[- ]?[0-9]", text):
            return True
        return False

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

        required_groups = cls._quote_required_term_groups(query, intent)
        if required_groups:
            if cls._quote_negative_term_hit(haystack, query, intent):
                return False
            return all(cls._any_term_in_text(group, haystack) for group in required_groups)

        # No known product group — with German keywords now injected into intent,
        # we can be stricter: priced results must match at least one term (>=2 chars).
        # This prevents irrelevant local DB items (e.g., A4 paper) from passing
        # when the user searches for "人体工学椅".
        if price_found:
            for term in terms:
                if len(term) >= 2 and cls._term_in_text(term, haystack):
                    return True
            # No term match — likely irrelevant even if priced
            return False

        # For unpriced results, require some keyword overlap
        overlap = sum(1 for term in terms if cls._term_in_text(term, haystack))
        return overlap >= max(1, len(terms) // 3)


    @classmethod
    def _quote_negative_term_hit(cls, haystack: str, query: str, intent=None) -> bool:
        """Reject known sibling/accessory false positives before ranking."""
        text = f"{query} {' '.join(str(k) for k in (getattr(intent, 'keywords', []) or []))}".lower()
        category = getattr(intent, "category", None)
        if category == "paper" or any(marker in text for marker in ("打印纸", "复印纸", "kopierpapier", "druckerpapier")):
            return any(bad in haystack for bad in ("ordner", "etikett", "laminier", "trennstreifen", "folder", "binder", "label", "folie"))
        if category == "laptop" or any(marker in text for marker in ("笔记本", "laptop", "notebook", "thinkpad", "elitebook")):
            return any(bad in haystack for bad in (
                "dock", "docking", "headset", "monitor", "display", "phone", "iphone",
                "laptophülle", "laptoptasche", "laptopständer", "laptop stand", "sleeve", "hülle", "tasche",
                "lüfter", "fan", "cooler", "kühler"
            ))
        if category == "monitor" or any(marker in text for marker in ("显示器", "monitor", "bildschirm", "display")):
            return any(bad in haystack for bad in ("dock", "docking", "headset", "papier", "paper", "monitorarm", "monitor-ständer", "ständer", "webcam", "kamera"))
        if category == "accessory" and any(marker in text for marker in ("dock", "thunderbolt", "扩展坞")):
            if any(bad in haystack for bad in ("bitpanda", "kurs in euro", "dockers", "chinos", "khakis", "clothing", "nintendo", "kamera", "piranha", "handtuch")):
                return True
            return not cls._any_term_in_text(("dock", "docking", "dockingstation", "扩展坞"), haystack)
        if category == "phone" or any(marker in text for marker in ("iphone", "smartphone", "手机", "智能手机")):
            return any(bad in haystack for bad in ("android", "player", "ladegerät", "charger", "adapter", "kabel", "cable", "hülle", "case", "powerbank"))
        if category == "equipment" and any(marker in text for marker in ("接头", "anschluss", "fitting", "qs")):
            if any(bad in haystack for bad in ("steckdose", "steckschlüssel", "ratschen", "verlängerungskabel", "schuko", "usb-steckdose")):
                return True
            return any(bad in haystack for bad in ("schalldämpfer", "drossel", "rückschlagventil", "ventil")) and not any(ok in haystack for ok in ("anschluss", "steck", "qs", "fitting"))
        if category == "safetyShoes" or any(marker in text for marker in ("安全鞋", "sicherheitsschuh", "s3")):
            return "s3" in text and "s1" in haystack and "s3" not in haystack
        if category == "cleaning" and any(marker in text for marker in ("洗洁精", "spülmittel", "dish soap")):
            return any(bad in haystack for bad in ("schwamm", "schwämme", "wc-reiniger", "toilettenpapier", "spülmaschinensalz", "klarspüler")) and "spülmittel" not in haystack
        if category == "office" and any(marker in text for marker in ("文件夹", "ordner", "folder")):
            return any(bad in haystack for bad in ("etikett", "label", "laminier", "folie", "kopierpapier", "druckerpapier"))
        return False

    @classmethod
    def _quote_relevance_terms(cls, query: str, intent) -> set[str]:
        lowered_query = query.lower()
        raw_terms = re.findall(r"[a-zA-Z0-9\u4e00-\u9fffäöüÄÖÜß]{2,}", lowered_query)
        for group in cls._quote_required_term_groups(query, intent):
            raw_terms.extend(group)
        for field in ("category", "country"):
            value = getattr(intent, field, None)
            if value:
                raw_terms.extend(re.findall(r"[a-zA-Z0-9\u4e00-\u9fffäöüÄÖÜß]{2,}", str(value).lower()))
        for keyword in getattr(intent, "keywords", []) or []:
            keyword_lower = str(keyword).lower()
            raw_terms.extend(re.findall(r"[a-zA-Z0-9\u4e00-\u9fffäöüÄÖÜß]{2,}", keyword_lower))
            for group in cls._quote_required_term_groups(str(keyword), intent=None):
                raw_terms.extend(group)
        return {term for term in raw_terms if term not in cls.QUOTE_WEB_STOPWORDS and (len(term) >= 2 or term == "a4")}

    @classmethod
    def _quote_required_term_groups(cls, query: str, intent=None) -> list[set[str]]:
        """Concrete product concepts that must match for quote comparisons.

        This is deliberately product-level rather than category-level: if the user
        asks for mouse, keyboard, calculator, A4 paper, etc., a cheap item from the
        same broad hardware/office category should not be shown.
        """
        pieces = [query or ""]
        if intent is not None:
            pieces.extend(str(keyword) for keyword in getattr(intent, "keywords", []) or [])
        text = " ".join(pieces).lower()
        groups: list[set[str]] = []

        def add_if(markers: tuple[str, ...], aliases: set[str]) -> None:
            if any(marker in text for marker in markers):
                if not any(aliases == existing for existing in groups):
                    groups.append(aliases)

        add_if(("a4",), {"a4"})
        add_if(("a4纸", "a4紙", "打印纸", "复印纸", "paper", "papier", "kopierpapier", "druckerpapier"), {"纸", "紙", "paper", "papier", "kopierpapier", "druckerpapier"})
        add_if(("鼠标", "滑鼠", "mouse", "maus"), {"鼠标", "滑鼠", "mouse", "maus"})
        add_if(("键盘", "鍵盤", "keyboard", "tastatur"), {"键盘", "鍵盤", "keyboard", "tastatur"})
        add_if(("计算器", "計算器", "calculator", "taschenrechner"), {"计算器", "計算器", "calculator", "taschenrechner"})
        add_if(("文件夹", "資料夾", "folder", "ordner", "schnellhefter"), {"文件夹", "資料夾", "folder", "ordner", "schnellhefter"})
        add_if(("订书钉", "訂書釘", "heftklammer", "staple"), {"订书钉", "訂書釘", "heftklammer", "heftklammern", "staple", "staples"})
        add_if(("剪刀", "scissors", "schere"), {"剪刀", "scissors", "schere"})
        add_if(("胶水", "膠水", "glue", "kleber", "klebestift"), {"胶水", "膠水", "glue", "kleber", "klebestift"})
        add_if(("马克笔", "麥克筆", "记号笔", "marker", "edding"), {"马克笔", "麥克筆", "记号笔", "marker", "whiteboard-marker", "permanentmarker", "edding"})
        add_if(("便利贴", "便签", "便條", "post-it", "haftnotiz"), {"便利贴", "便签", "便條", "post-it", "postit", "haftnotiz", "haftnotizen"})
        add_if(("胶带", "膠帶", "tape", "klebefilm", "tesa"), {"胶带", "膠帶", "tape", "klebefilm", "tesa"})
        add_if(("垃圾桶", "纸篓", "papierkorb", "bin"), {"垃圾桶", "纸篓", "papierkorb", "bin", "waste bin"})
        add_if(("碎纸机", "碎紙機", "shredder", "aktenvernichter", "schredder", "reißwolf", "reibwolf"), {"碎纸机", "碎紙機", "shredder", "aktenvernichter", "schredder", "reißwolf", "reibwolf", "paper shredder"})
        add_if(("打印机", "印表機", "drucker", "printer", "multifunktionsdrucker"), {"打印机", "印表機", "drucker", "printer", "multifunktionsdrucker", "laserdrucker", "tintenstrahldrucker"})
        add_if(("显示器", "顯示器", "monitor", "bildschirm", "display"), {"显示器", "顯示器", "monitor", "bildschirm", "display", "screen"})
        add_if(("笔记本", "筆記本", "laptop", "notebook", "thinkpad"), {"笔记本", "筆記本", "laptop", "notebook", "thinkpad", "arbeitslaptop"})
        add_if(("电话", "電話", "telefon", "phone", "handy"), {"电话", "電話", "telefon", "phone", "handy", "schnurlostelefon", "voip-telefon"})
        add_if(("iphone", "smartphone", "手机", "智能手机"), {"iphone", "smartphone", "handy", "phone", "手机", "galaxy"})
        add_if(("dock", "docking", "扩展坞", "dockingstation"), {"dock", "docking", "dockingstation", "扩展坞"})
        add_if(("耳机", "headset", "kopfhörer", "earpod"), {"耳机", "headset", "kopfhörer", "earpod", "headphone"})
        add_if(("安全鞋", "sicherheitsschuh", "sicherheitsschuhe", "schutzschuh"), {"安全鞋", "sicherheitsschuh", "sicherheitsschuhe", "schutzschuh"})
        add_if(("s3",), {"s3"})
        add_if(("洗洁精", "spülmittel", "geschirrspülmittel", "dish soap"), {"洗洁精", "spülmittel", "geschirrspülmittel", "dish soap"})
        add_if(("气动接头", "steckanschluss", "anschluss", "fitting", "verschraubung"), {"steckanschluss", "anschluss", "verschraubung", "fitting", "kupplung", "接头"})
        add_if(("festo",), {"festo"})
        add_if(("qs",), {"qs"})
        add_if(("工作站", "workstation", "zbook", "desktop"), {"工作站", "workstation", "zbook", "desktop", "arbeitsstation"})
        return groups

    @classmethod
    def _is_relevant_quote_item(cls, quote: dict, query: str, intent) -> bool:
        text = " ".join(
            str(value)
            for value in [
                quote.get("vendor"),
                quote.get("platform"),
                quote.get("product"),
                quote.get("description"),
            ]
            if value
        )
        url = (quote.get("sourceUrls") or [""])[0]
        if cls._is_non_product_quote_page(str(quote.get("product") or ""), str(quote.get("description") or ""), url, intent):
            return False
        return cls._is_relevant_quote_result(text, query, intent, price_found=quote.get("unitPriceEur") is not None)


    async def _llm_filter_relevant_quotes(self, query: str, candidates: list[dict], intent, german_search_terms: str = "") -> list[dict]:
        """LLM judges which candidates actually match the user's specific product need.

        Products from parsed listing pages pass through directly — they were found
        via site-specific targeted searches and already priced. We keep ALL listing
        products (not just keyword-matched ones) because the search query already
        targeted the right product category.

        LLM only filters candidates from other sources (search snippets, single pages).
        When german_search_terms is provided, it's included in the LLM prompt to help
        match German product names against the user's Chinese query.
        """
        if not candidates:
            return []
        
        listing_all = [c for c in candidates if c.get('sourceDetail') == 'listing']
        other_products = [c for c in candidates if c.get('sourceDetail') != 'listing']
        
        # Listing pages can still contain sibling accessories (e.g. laptop sleeves,
        # chargers, monitor arms). Keep only products passing the same product-level
        # relevance gate; this is safer than trusting the listing page wholesale.
        listing_products = [c for c in listing_all if self._is_relevant_quote_item(c, query, intent)]
        
        if not other_products:
            return listing_products
        
        if not self.llm:
            return listing_products + [c for c in other_products if self._is_relevant_quote_item(c, query, intent)]

        # Extract product keywords from query for the LLM prompt
        product_keywords = ' '.join([str(k) for k in getattr(intent, 'keywords', []) or []]) or query[:120]
        
        # Include German search terms so LLM can match German product names
        context_note = ""
        if german_search_terms:
            context_note = f"\nNote: products were searched with German keywords: \"{german_search_terms}\". "
            context_note += "A German product name matching these German keywords IS relevant even if its name doesn't contain Chinese words."
        
        # Build summary for LLM — cap at 20 to avoid 2-minute inference time
        items = []
        for i, c in enumerate(other_products[:20]):
            items.append(
                f"[{i}] {c.get('product','')} | vendor={c.get('vendor','')} "
                f"| platform={c.get('platform','')} | price=€{c.get('unitPriceEur','?')}"
            )

        prompt = (
            f"User needs: {product_keywords}{context_note}\n\n"
            f"Candidates to check:\n" + "\n".join(items) + "\n\n"
            "For each candidate, decide if it IS the type of product the user needs. "
            "MATCH if it's the same product (e.g., shredder=shredder, paper=paper). "
            "REJECT if it's a different product (e.g., shredder oil is NOT a shredder).\n\n"
            "Return a JSON array of indices (the numbers in brackets) that MATCH. "
            "Example: [0, 3, 5]\n"
            "Return ONLY the JSON array, nothing else."
        )

        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                import asyncio
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return listing_products + [c for c in other_products if self._is_relevant_quote_item(c, query, intent)]

            content_text = str(getattr(response, "content", response))
            import re, json
            match = re.search(r'\[.*?\]', content_text, re.S)
            if not match:
                return listing_products + [c for c in other_products if self._is_relevant_quote_item(c, query, intent)]
            indices = json.loads(match.group(0))
            kept = [
                other_products[i]
                for i in indices
                if isinstance(i, int)
                and 0 <= i < len(other_products)
                and self._is_relevant_quote_item(other_products[i], query, intent)
            ]
            return listing_products + kept
        except Exception:
            return listing_products + [c for c in other_products if self._is_relevant_quote_item(c, query, intent)]

    @classmethod
    def _extract_eur_price(cls, text: str) -> float | None:
        patterns = [
            r'"price"\s*:\s*"?([0-9][0-9.,]*(?:[.,][0-9]{2})?)"?[^{}]{0,160}"priceCurrency"\s*:\s*"?EUR"?',
            r'"priceCurrency"\s*:\s*"?EUR"?[^{}]{0,160}"price"\s*:\s*"?([0-9][0-9.,]*(?:[.,][0-9]{2})?)"?',
            r'(?:data-price|content|amount)\s*=\s*["\']([0-9][0-9.,]*(?:[.,][0-9]{2})?)["\'][^<>]{0,120}(?:EUR|€)',
            r"€\s*([0-9][0-9.,]*(?:[.,][0-9]{2})?)",
            r"€\s*([0-9][0-9.,]*)\s*(?:[-–]|,–)",
            r"([0-9][0-9.,]*(?:[.,][0-9]{2})?)\s*(?:EUR|Euro|€)",
            r"([0-9][0-9.,]*)\s*(?:[-–]|,–)\s*(?:EUR|Euro|€)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = cls._parse_price_number(match.group(1))
            if value is not None and 0.08 < value < 100000:
                return value
        return None

    @staticmethod
    def _parse_price_number(raw: str) -> float | None:
        value = raw.strip().strip(".,;:").replace(" ", "")
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
            urls = item.get("sourceUrls") or []
            # Listing page products each have a unique product link; use ID as key
            if item.get("sourceDetail") == "listing":
                key = item.get("id", str(len(merged)))
            else:
                key = str(urls[0] if urls else item.get("id") or item.get("vendor") or len(merged))
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            existing_has_price = existing.get("unitPriceEur") is not None
            item_has_price = item.get("unitPriceEur") is not None
            if item_has_price and not existing_has_price:
                merged[key] = item
            elif item_has_price == existing_has_price and item.get("matchScore", 0) > existing.get("matchScore", 0):
                merged[key] = item
        return list(merged.values())

    @staticmethod
    def _prefer_priced_quote_candidates(candidates: list[dict]) -> list[dict]:
        """Avoid a deliverable table full of '需人工核价' when priced rows exist.
        Keep listing products (from verified product pages) even without price."""
        listing_items = [item for item in candidates if item.get("sourceDetail") == "listing"]
        other_items = [item for item in candidates if item.get("sourceDetail") != "listing"]
        priced_other = [item for item in other_items if item.get("unitPriceEur") is not None]
        if priced_other:
            return priced_other + listing_items
        return candidates

    @staticmethod
    def _quote_evidence_snippets(text: str) -> list[str]:
        lines = [line.strip() for line in re.split(r"[\n。]", text or "") if len(line.strip()) > 20]
        return lines[:3]

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
    def _delivery_time_to_days(delivery_time: Optional[str]) -> Optional[int]:
        mapping = {
            "within3": 3,
            "within7": 7,
            "unlimited": None,
            None: None,
        }
        return mapping.get(delivery_time)
