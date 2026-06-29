from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
# Standalone EUR price extractor to avoid circular import with procurement_agent
def _quick_extract_eur_price(text: str) -> float | None:
    import re
    patterns = [
        r'€\s*([0-9][0-9.,]*(?:[.,][0-9]{2})?)',
        r'€\s*([0-9][0-9.,]*)\s*(?:[-\u2013]|,\u2013)',
        r'([0-9][0-9.,]*(?:[.,][0-9]{2})?)\s*(?:EUR|Euro|€)',
        r'([0-9][0-9.,]*)\s*(?:[-\u2013]|,\u2013)\s*(?:EUR|Euro|€)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _parse_price_number(match.group(1))
        if value is not None and 0.08 < value < 100000:
            return value
    return None

def _parse_price_number(raw: str) -> float | None:
    value = raw.strip().strip(".,;:").replace(" ", "")
    if not value:
        return None
    dot = value.rfind(".")
    comma = value.rfind(",")
    if dot != -1 and comma != -1:
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



from agent.parser import ProcurementIntent


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    text: str
    links: list[str]


@dataclass(frozen=True)
class DeepEvidence:
    text: str
    source_urls: list[str]
    email_candidates: list[str]
    phone_candidates: list[str]


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class PageFetcher(Protocol):
    async def fetch_text(self, url: str) -> str: ...
    async def fetch_page(self, url: str) -> PageSnapshot: ...


class DuckDuckGoSearchProvider:
    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            def run() -> list[SearchResult]:
                with DDGS(timeout=8) as ddgs:
                    rows = list(ddgs.text(query, max_results=max_results))
                # Filter: prefer German (.de) and EU results, reject Asian TLDs
                filtered = []
                for row in rows:
                    url = row.get("href") or row.get("url") or ""
                    from urllib.parse import urlparse as _up
                    tld = (_up(url).netloc or "").split(".")[-1].lower() if url else ""
                    if tld in ("cn", "tw", "jp", "kr", "hk", "ru", "br", "in"):
                        continue  # Skip non-European results
                    filtered.append(row)
                return [
                    SearchResult(
                        title=row.get("title") or "Web supplier",
                        url=row.get("href") or row.get("url") or "",
                        snippet=row.get("body") or "",
                    )
                    for row in filtered
                    if row.get("href") or row.get("url")
                ]

            return await asyncio.to_thread(run)
        except Exception:
            return []


class StaticPageFetcher:
    # Known German B2B/B2C shops that use product listing grids
    PRODUCT_LISTING_DOMAINS = (
        "schaefer-shop.de", "bueromarkt-ag.de", "otto-office.com",
        "viking.de", "bueroshop24.de", "office-discount.de",
        "mcbuero.de", "wrede-store.de", "printus.de",
        "mediamarkt.de", "saturn.de", "otto.de",
        "amazon.de", "idealo.de",
    )

    async def fetch_page(self, url: str) -> PageSnapshot:
        """Fetch a page, bypassing basic bot protection with cloudscraper."""
        try:
            html = await self._fetch_html(url)
            if not html:
                return PageSnapshot(url=url, text="", links=[])
            return self._parse_html(url, html)
        except Exception:
            return PageSnapshot(url=url, text="", links=[])

    async def fetch_products_from_listing(self, url: str) -> list[dict]:
        """If the URL is a product listing page, extract individual products.

        Returns list of dicts with keys: product, unitPriceEur, unitLabel,
        deliveryLabel, sourceUrls, evidenceSnippets, rating, reviews.
        Returns empty list if not a listing page or extraction fails.
        """
        host = ""
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).netloc or "").replace("www.", "")
        except Exception:
            pass
        if not any(d in host for d in self.PRODUCT_LISTING_DOMAINS):
            return []

        try:
            html = await self._fetch_html(url)
            if not html or len(html) < 5000:
                return []
            return self._parse_product_listing(url, html, host)
        except Exception:
            return []

    async def _fetch_html(self, url: str) -> str:
        """Try cloudscraper first, fall back to requests."""
        import requests as req

        def try_cloudscraper():
            try:
                # Only attempt cloudscraper for real domains (skip test/local URLs)
                from urllib.parse import urlparse as _up
                host = (_up(url).netloc or "").lower()
                if not host or 'example' in host or 'localhost' in host or host.endswith('.test'):
                    return None
                import cloudscraper
                scraper = cloudscraper.create_scraper(
                    browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False}
                )
                resp = scraper.get(url, timeout=8)
                if resp.status_code < 500 and len(resp.text) > 500:
                    if '_Incapsula_Resource' not in resp.text and 'Request unsuccessful' not in resp.text:
                        return resp.text
            except Exception:
                pass
            return None

        def try_requests():
            try:
                resp = req.get(
                    url, timeout=8,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                if resp.status_code < 500 and len(resp.text) > 500:
                    return resp.text
            except Exception:
                pass
            return None

        html = await asyncio.to_thread(try_cloudscraper)
        if not html:
            html = await asyncio.to_thread(try_requests)
        return html or ""

    def _parse_html(self, url: str, html: str) -> PageSnapshot:
        soup = BeautifulSoup(html, "html.parser")

        # Product prices in JSON-LD, meta, itemprop, price classes
        structured_fragments: list[str] = []
        for meta in soup.find_all("meta"):
            key = " ".join(
                str(meta.get(attr) or "")
                for attr in ("name", "property", "itemprop")
            ).lower()
            text = str(meta.get("content") or "").strip()
            if text and any(marker in key for marker in ("price", "amount", "currency", "product")):
                structured_fragments.append(text)
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = script.get_text(" ", strip=True)
            if text and any(marker in text.lower() for marker in ("price", "offers", "eur", "€")):
                structured_fragments.append(text[:4000])
        for node in soup.find_all(attrs={"itemprop": re.compile("price|offer", re.I)}):
            value = str(node.get("content") or node.get_text(" ", strip=True) or "").strip()
            if value:
                structured_fragments.append(value)
        for node in soup.find_all(attrs={"class": re.compile("price|preis|amount", re.I)}):
            value = node.get_text(" ", strip=True)
            if value:
                structured_fragments.append(value[:500])

        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            absolute = urljoin(url, href)
            if absolute.startswith(("http://", "https://")):
                links.append(absolute.split("#", 1)[0])

        for noisy in soup(["script", "style", "noscript", "svg"]):
            noisy.decompose()
        visible_text = WebResearcher.clean_text(soup.get_text(" "))
        if structured_fragments:
            visible_text = WebResearcher.clean_text(
                f"{visible_text} " + " ".join(dict.fromkeys(structured_fragments))
            )
        return PageSnapshot(
            url=url,
            text=visible_text,
            links=list(dict.fromkeys(links))[:80],
        )

    def _parse_product_listing(self, url: str, html: str, host: str) -> list[dict]:
        """Parse individual products from a German e-commerce listing grid."""
        soup = BeautifulSoup(html, "html.parser")
        products: list[dict] = []
        seen_titles: set[str] = set()

        for footer in soup.find_all('div', class_=re.compile(r'product-element-footer', re.I)):
            # Extract price from footer
            price_text = ''
            price_eur = None
            for price_tag in footer.find_all(['span', 'div', 'strong', 'p']):
                text = price_tag.get_text(' ', strip=True)
                if re.search(r'[\d.,]+\s*[€ ]|[\d.,]+\s*EUR', text, re.I):
                    price_text = text
                    price_eur = _quick_extract_eur_price(text)
                    break
            if price_eur is None:
                continue

            # Go up to the product card container
            card = footer
            for _ in range(6):
                card = card.parent
                if card is None:
                    break

                # Find the product title
                title = ''
                for tag in card.find_all(['h2', 'h3', 'h4', 'a', 'span']):
                    t = tag.get_text(' ', strip=True)
                    # Filter: at least 20 chars, not pure navigation
                    if len(t) > 20 and not t.startswith('Sortieren') and not t.startswith('Ansicht'):
                        title = t[:200]
                        break

                if title and title not in seen_titles:
                    seen_titles.add(title)

                    # Extract delivery info
                    delivery = ''
                    delivery_days = None
                    for d in card.find_all(string=re.compile(r'lieferbar|Lieferzeit|Tage|sofort', re.I)):
                        delivery = d.strip()[:60]
                        days_match = re.search(r'(\d+)\s*(?:-\s*\d+\s*)?(?:Werktag|Tag|Arbeitstag)', d.strip())
                        if days_match:
                            delivery_days = int(days_match.group(1))
                        break

                    # Extract rating if available
                    rating = 0.0
                    reviews = 0
                    for star_elem in card.find_all(attrs={"class": re.compile(r'star|rating|bewertung', re.I)}):
                        star_text = star_elem.get_text(' ', strip=True)
                        star_match = re.search(r'(\d[\.\d]*)\s*/\s*5', star_text)
                        if star_match:
                            rating = float(star_match.group(1))
                        count_match = re.search(r'\((\d+)\)', star_text)
                        if count_match:
                            reviews = int(count_match.group(1))

                    # Build product links — product-specific URL first, listing page last
                    product_urls = []
                    for a_tag in card.find_all('a', href=True):
                        href = str(a_tag.get('href') or '').strip()
                        if href and href.startswith('/'):
                            absolute = urljoin(url, href)
                            if absolute not in product_urls:
                                product_urls.append(absolute)
                    if not product_urls:
                        product_urls = [url]
                    else:
                        product_urls.append(url)  # listing page as fallback

                    price_label = f'€ {price_eur:.2f}' if price_eur else '需人工核价'
                    products.append({
                        'product': title,
                        'unitPriceEur': price_eur,
                        'unitLabel': price_label,
                        'deliveryDays': delivery_days,
                        'deliveryLabel': delivery or '需确认交期',
                        'rating': rating,
                        'reviews': reviews,
                        'sourceUrls': product_urls[:3],
                        'evidenceSnippets': [f'{title[:100]}'],
                        'priceConfidence': 'extracted' if price_eur else 'unknown',
                    })

                break

        return products

    async def fetch_text(self, url: str) -> str:
        page = await self.fetch_page(url)
        return page.text


# ---------------------------------------------------------------------------
# Pydantic models for LLM structured output
# ---------------------------------------------------------------------------

class SupplierCandidate(BaseModel):
    name: str
    website: str
    country: str = ""
    city: str = ""
    description: str = ""
    products: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    relevance_score: int = Field(ge=0, le=100, default=60)
    is_supplier: bool = True


class RelevanceJudgment(BaseModel):
    is_supplier_page: bool
    confidence: int = Field(ge=0, le=100)
    reason: str = ""


# ---------------------------------------------------------------------------
# WebResearcher — LLM-driven supplier discovery
# ---------------------------------------------------------------------------

class WebResearcher:
    """LLM-driven procurement supplier web research.

    Architecture:
    1. LLM plans context-aware search queries based on the parsed intent.
    2. DDG executes each query; raw results are collected and de-duplicated.
    3. LLM judges which results are actual supplier pages.
    4. LLM extracts structured supplier profiles from selected pages.
    5. Rule-based fallbacks cover categories without enough search hits.
    """

    BLOCKED_DOMAINS = (
        # Consumer marketplaces
        "amazon.de", "amazon.com", "ebay.de", "ebay.com", "ebey.de",
        "etsy.com", "aliexpress.com", "temu.com",
        "alibaba.com", "dhgate.com", "made-in-china.com", "globalsources.com",
        # Social / media
        "pinterest.com", "facebook.com", "instagram.com", "tiktok.com",
        "youtube.com", "wikipedia.org", "linkedin.com",
        # Software / login
        "microsoft.com", "office.com", "outlook.com",
        "adobe.com", "stock.adobe.com", "bing.com",
        # Document / content hosts
        "scribd.com", "fliphtml5.com", "yumpu.com", "dokumen.pub",
        "monoskop.org", "reverso.net", "context.reverso.net",
        # Shopping / comparison
        "idealo.de", "shopicx.de", "shopicx.com",
        # Non-supplier
        "deutschepost.de", "fortunebusinessinsights.com",
        "foreign.mingluji.com", "sostrenegrene.com", "efiliale.de",
        "staples.com", "envato.com", "papercart.ph",
        # Redirect / tracking
        "google.com", "goo.gl", "bit.ly",
    )

    BLOCKED_FILE_EXTENSIONS = (".pdf", ".doc", ".docx", ".ppt", ".pptx")

    CONTENT_PAGE_KEYWORDS = (
        "how to", "guide", "tips", "blog", "news", "article",
        "comparison", "compare", "review", "best of", "top 10",
        "what is", "why you", "should you",
    )

    # High-signal B2B directories — search results from these domains
    # are automatically ranked higher.
    B2B_DIRECTORY_DOMAINS = (
        "wlw.de", "wer-liefert-was.de",
        "europages.de", "europages.com",
        "kompass.com",
        "industrystock.de", "industrystock.com",
        "directindustry.com", "directindustry.de",
        "thomasnet.com",
        "lieferanten.de",
    )

    # wlw/europages search/browse page URL patterns — these show lists of
    # suppliers, not individual supplier profiles, so they should be excluded.
    DIRECTORY_SEARCH_PATH_PATTERNS = (
        "/de/suche/", "/en/search/", "/fr/recherche/",
        "/unternehmen/", "/companies/",
    )

    OFFICE_FALLBACK_SUPPLIERS: list[dict] = [
        {
            "name": "Viking Office Deutschland",
            "website": "https://www.viking.de/",
            "country": "Germany",
            "description": "German office-supplies supplier for paper, folders, printer supplies and general Bürobedarf.",
            "products": ["A4 Papier", "Ordner", "Druckerzubehör", "Bürobedarf"],
            "capabilities": ["Office supplies", "Bürobedarf", "B2B ordering"],
            "matchScore": 72,
        },
        {
            "name": "OTTO Office",
            "website": "https://www.otto-office.com/de/",
            "country": "Germany",
            "description": "Office supplies, office technology and office furniture supplier in Germany.",
            "products": ["Kopierpapier", "Laminierfolien", "Ordner", "Büromaterial"],
            "capabilities": ["Office supplies", "Bürotechnik", "Büromöbel"],
            "matchScore": 71,
        },
        {
            "name": "Böttcher AG Bürobedarf",
            "website": "https://www.bueromarkt-ag.de/",
            "country": "Germany",
            "description": "German Bürobedarf and office-material online supplier.",
            "products": ["Papier", "Ordner", "Etiketten", "Büroartikel"],
            "capabilities": ["Bürobedarf", "Online procurement"],
            "matchScore": 69,
        },
        {
            "name": "büroshop24",
            "website": "https://www.bueroshop24.de/",
            "country": "Germany",
            "description": "German online office-supplies shop for paper, stationery and office equipment.",
            "products": ["Papier", "Schreibwaren", "Bürogeräte"],
            "capabilities": ["Bürobedarf", "Office equipment"],
            "matchScore": 68,
        },
    ]

    def __init__(
        self,
        search_provider: SearchProvider | None = None,
        page_fetcher: PageFetcher | None = None,
        llm: Any = None,
    ):
        self.search_provider = search_provider or DuckDuckGoSearchProvider()
        self.page_fetcher = page_fetcher or StaticPageFetcher()
        self.llm = llm

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def research(self, intent: ProcurementIntent, max_suppliers: int = 8,
                       progress=None) -> list[dict]:
        """LLM-driven supplier discovery pipeline.

        When *progress* is provided, it is called as progress(phase, message, pct)
        whenever a meaningful step completes, so the frontend can display the
        agent's real-time thought process.
        """
        if progress:
            progress("think", "正在通过 LLM 规划 B2B 供应商搜索策略...", 46)

        # 1. LLM plans search queries
        queries = await self._llm_plan_queries(intent)
        if not queries:
            queries = self._rule_plan_queries(intent)

        if progress:
            progress("think", f"LLM 生成了 {len(queries)} 条针对性的 B2B 搜索查询，准备依次执行...", 48)

        # 2. Execute queries, collect results
        collected: dict[str, SearchResult] = {}
        executed_queries: set[str] = set()

        async def execute_query_batch(batch: list[str], start_index: int = 0, label: str = "搜索") -> None:
            nonlocal collected
            total = min(len(batch), 6)
            for idx, query in enumerate(batch[:6]):
                if query in executed_queries:
                    continue
                executed_queries.add(query)
                results = await self._search_with_retry(query, max_results=10)
                new_count = 0
                for result in results:
                    if not self._url_ok(result.url):
                        continue
                    key = self._url_key(result.url) or result.title.lower()
                    if key and key not in collected:
                        collected[key] = result
                        new_count += 1
                if progress:
                    progress("think",
                             f"{label} [{idx+1}/{total}]: {query[:50]}... → 新增 {new_count} 条，累计 {len(collected)} 条",
                             48 + int((start_index + idx) * 3))
                if len(collected) >= max_suppliers * 3:
                    break

        await execute_query_batch(queries, label="搜索")

        if len(collected) < max_suppliers * 2:
            fallback_queries = [q for q in self._rule_plan_queries(intent) if q not in executed_queries]
            if progress and fallback_queries:
                progress("think", f"LLM 查询结果偏少（{len(collected)} 条），追加规则 B2B 查询兜底...", 58)
            await execute_query_batch(fallback_queries, start_index=len(queries), label="兜底搜索")

        results_list = list(collected.values())
        if progress:
            progress("think", f"共收集到 {len(results_list)} 条候选搜索结果，正在用 LLM 判断哪些是真正的供应商页面...", 60)

        # 3. LLM judges which results are real supplier pages
        relevant = await self._llm_filter_relevant(results_list, intent)
        min_relevant = min(len(results_list), max_suppliers * 2)
        if len(relevant) < min_relevant:
            rule_relevant = self._rule_filter_relevant(results_list, intent)
            relevant = self._merge_search_results(relevant, rule_relevant)[:min_relevant]
            if progress:
                progress("think", f"LLM 筛选结果偏少，已用规则信号补足到 {len(relevant)} 条候选，避免同一问题结果数量大幅波动。", 64)

        if progress:
            progress("think", f"LLM 筛选完成：从 {len(results_list)} 条中识别出 {len(relevant)} 条相关供应商", 65)

        # 4. Extract supplier profiles from relevant results
        suppliers: list[dict] = []
        for idx, result in enumerate(relevant[:max_suppliers * 2]):
            if progress and result.title:
                progress("think", f"正在提取供应商信息 [{idx+1}/{min(len(relevant), max_suppliers*2)}]: {result.title[:50]}", 
                         65 + int(idx * 2))
            supplier = await self._result_to_supplier(result, intent, progress=progress, index=idx+1,
                                                     total=min(len(relevant), max_suppliers*2))
            if supplier:
                suppliers.append(supplier)
            if len(suppliers) >= max_suppliers:
                break

        # 5. Merge with category fallback suppliers
        suppliers = self.merge_supplier_lists(suppliers, self._fallback_suppliers(intent))
        return suppliers[:max_suppliers]

    async def _search_with_retry(self, query: str, max_results: int = 10, attempts: int = 2) -> list[SearchResult]:
        last: list[SearchResult] = []
        for attempt in range(attempts):
            try:
                results = await self.search_provider.search(query, max_results=max_results)
            except Exception:
                results = []
            if results:
                return results
            last = results
            if attempt + 1 < attempts:
                await asyncio.sleep(0.25)
        return last

    # ------------------------------------------------------------------
    # LLM query planning
    # ------------------------------------------------------------------

    async def _llm_plan_queries(self, intent: ProcurementIntent) -> list[str]:
        """Ask the LLM to generate targeted B2B search queries."""
        if not self.llm:
            return []

        country = intent.country or "Germany"
        category = intent.category or "general procurement"
        keywords = ", ".join(intent.keywords[:8])

        prompt = (
            "You are a procurement agent. A user needs to find B2B suppliers.\n\n"
            f"Category: {category}\n"
            f"Target country: {country}\n"
            f"Keywords from user query: {keywords}\n"
            f"Budget: €{intent.max_price if intent.max_price else 'not specified'}\n"
            f"Delivery: {intent.max_delivery_days or 'not specified'} days\n\n"
            "Generate 5-6 DuckDuckGo search queries to find REAL B2B suppliers on the web. "
            "Each query should be a complete search string, one per line.\n\n"
            "Rules:\n"
            "- Target B2B directories: site:wlw.de, site:europages.de, site:kompass.com, site:lieferanten.de\n"
            "- Use the target country's language (German for Germany, French for France, etc.)\n"
            "- Include B2B-specific terms: Lieferant, Großhandel, Hersteller, wholesaler, B2B\n"
            "- Exclude consumer/retail noise: -Amazon -eBay -Pinterest\n"
            "- Focus on the specific products/services the user needs\n\n"
            "Return ONLY the queries, one per line. No numbering, no explanations."
        )

        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return []

            content = str(getattr(response, "content", response))
            queries = []
            for line in content.strip().split("\n"):
                q = line.strip().lstrip("0123456789.-) ").strip()
                if q and len(q) > 10:
                    queries.append(q)
            return queries[:6]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # LLM relevance filtering
    # ------------------------------------------------------------------

    async def _llm_filter_relevant(
        self, results: list[SearchResult], intent: ProcurementIntent
    ) -> list[SearchResult]:
        """Ask the LLM to identify which search results are real supplier pages."""
        if not self.llm or not results:
            return self._rule_filter_relevant(results, intent)

        # Build a compact summary of results for the LLM
        lines = []
        for i, r in enumerate(results):
            lines.append(f"[{i}] {r.title}\n    URL: {r.url}\n    Snippet: {r.snippet[:200]}")
        results_text = "\n\n".join(lines)

        prompt = (
            "You are evaluating web search results for a procurement agent. "
            "The agent MUST find B2B suppliers that match the SPECIFIC procurement category below.\n\n"
            f"Procurement category: {intent.category}\n"
            f"Target country: {intent.country or 'Germany'}\n"
            f"User keywords: {', '.join(intent.keywords[:8])}\n\n"
            "For each search result, decide if it is a VALID supplier for THIS category.\n\n"
            "A valid supplier MUST:\n"
            "- Be a manufacturer, wholesaler, or industrial distributor\n"
            "- Offer products/services that MATCH the procurement category\n"
            "- Have a company profile page (not a search results listing)\n\n"
            "REJECT these:\n"
            "- Companies in unrelated categories (e.g., chemicals, plastics, IT for office supplies)\n"
            "- Generic marketplace homepages (europages.de/ or wlw.de/ root)\n"
            "- Search results pages (/de/suche/, /search/ paths)\n"
            "- Blog posts, how-to guides, news, reviews\n"
            "- Social media, PDF documents, login pages\n\n"
            f"Search results:\n{results_text}\n\n"
            "Return a JSON array of objects with keys: index (int), is_supplier (bool), reason (str). "
            "Example: [{\"index\": 0, \"is_supplier\": false, \"reason\": \"Chemical company, not office supplies\"}]"
        )

        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return self._rule_filter_relevant(results, intent)

            content = str(getattr(response, "content", response))
            # Extract JSON array from response
            match = re.search(r"\[.*\]", content, re.S)
            if not match:
                return self._rule_filter_relevant(results, intent)

            judgments = json.loads(match.group(0))
            relevant_indices = {
                j["index"] for j in judgments
                if isinstance(j, dict) and j.get("is_supplier") and j.get("index", -1) < len(results)
            }
            return [r for i, r in enumerate(results) if i in relevant_indices]
        except Exception:
            return self._rule_filter_relevant(results, intent)

    def _rule_filter_relevant(self, results: list[SearchResult], intent: ProcurementIntent) -> list[SearchResult]:
        """Rule-based fallback when LLM is unavailable."""
        relevant = []
        for r in results:
            if not self._url_ok(r.url):
                continue
            # Quick content page detection
            text = f"{r.title} {r.snippet}".lower()
            if any(term in text for term in self.CONTENT_PAGE_KEYWORDS):
                continue
            # B2B domain bonus
            domain = urlparse(r.url).netloc.lower()
            if any(d in domain for d in self.B2B_DIRECTORY_DOMAINS):
                relevant.append(r)
                continue
            # Supplier-like title detection
            supplier_signals = ("gmbh", "ag", "kg", "gmbh & co", "lieferant", "hersteller",
                              "großhandel", "grosshandel", "supplier", "wholesaler", "manufacturer")
            if any(s in text for s in supplier_signals):
                relevant.append(r)
        return relevant[:16]

    @staticmethod
    def _merge_search_results(primary: list[SearchResult], secondary: list[SearchResult]) -> list[SearchResult]:
        merged: dict[str, SearchResult] = {}
        for result in [*primary, *secondary]:
            key = WebResearcher._url_key(result.url) or result.title.lower()
            if key and key not in merged:
                merged[key] = result
        return list(merged.values())

    # ------------------------------------------------------------------
    # LLM supplier extraction (improved)
    # ------------------------------------------------------------------

    async def _result_to_supplier(self, result: SearchResult, intent: ProcurementIntent, progress=None,
                                  index: int = 1, total: int = 1) -> dict | None:
        """Extract a structured supplier profile from a search result."""
        evidence = await self._build_deep_evidence(result, intent, progress=progress, index=index, total=total)

        if self.llm and evidence.text and not self._is_noisy_page(evidence.text):
            llm_result = await self._llm_extract_supplier(evidence.text, result.url, intent, evidence=evidence)
            if llm_result:
                supplier = self._normalize_supplier(llm_result, result, intent, source="web-research-llm")
                supplier["sourceUrls"] = evidence.source_urls
                supplier["evidenceSnippets"] = self._evidence_snippets(evidence.text)
                if evidence.email_candidates and not supplier.get("email"):
                    supplier["email"] = evidence.email_candidates[0]
                if evidence.phone_candidates and not supplier.get("phone"):
                    supplier["phone"] = evidence.phone_candidates[0]
                return supplier

        # Rule-based fallback
        supplier = self._normalize_supplier(
            {
                "name": self._clean_title(result.title),
                "description": self._best_description(result.snippet, evidence.text),
                "products": list(intent.keywords[:5]),
                "capabilities": [intent.category] if intent.category else [],
            },
            result, intent, source="web-research",
        )
        supplier["sourceUrls"] = evidence.source_urls
        supplier["evidenceSnippets"] = self._evidence_snippets(evidence.text)
        if evidence.email_candidates:
            supplier["email"] = evidence.email_candidates[0]
        if evidence.phone_candidates:
            supplier["phone"] = evidence.phone_candidates[0]
        return supplier

    async def _build_deep_evidence(self, result: SearchResult, intent: ProcurementIntent,
                                   progress=None, index: int = 1, total: int = 1) -> DeepEvidence:
        """Fetch the result page plus high-value same-domain pages for richer supplier evidence."""
        if progress:
            progress("think", f"正在深挖供应商官网 [{index}/{total}]: {result.title[:50]}", 66 + min(index, 10))

        first = await self._fetch_page_compat(result.url)
        selected_links = self._select_deep_links(result.url, first.links, intent)
        if progress and selected_links:
            progress("think", f"发现 {len(selected_links)} 个高价值页面（产品/联系/公司信息），继续抓取证据...", 67 + min(index, 10))

        pages = [first]
        if selected_links:
            fetched = await asyncio.gather(*(self._fetch_page_compat(url) for url in selected_links), return_exceptions=True)
            pages.extend(page for page in fetched if isinstance(page, PageSnapshot))

        source_urls: list[str] = []
        chunks = [result.title, result.snippet]
        for page in pages:
            if page.text and self._useful_page_text(page.text):
                source_urls.append(page.url)
                chunks.append(f"Source: {page.url}\n{page.text[:2200]}")

        text = self.clean_text("\n\n".join(chunks))
        emails = self._extract_emails(text)
        phones = self._extract_phones(text)
        return DeepEvidence(
            text=text[:9000],
            source_urls=list(dict.fromkeys(source_urls or [result.url]))[:8],
            email_candidates=emails[:5],
            phone_candidates=phones[:5],
        )

    async def _fetch_page_compat(self, url: str) -> PageSnapshot:
        if hasattr(self.page_fetcher, "fetch_page"):
            try:
                return await self.page_fetcher.fetch_page(url)  # type: ignore[attr-defined]
            except Exception:
                pass
        text = await self.page_fetcher.fetch_text(url)
        return PageSnapshot(url=url, text=text, links=[])

    def _select_deep_links(self, base_url: str, links: list[str], intent: ProcurementIntent) -> list[str]:
        base = urlparse(base_url)
        wanted = (
            "product", "produkte", "sortiment", "catalog", "katalog", "shop",
            "contact", "kontakt", "impressum", "imprint", "about", "company", "unternehmen",
            "office", "buero", "büro", "paper", "papier", "folder", "ordner",
        )
        rejected = ("blog", "news", "career", "jobs", "privacy", "datenschutz", "terms", "login", "cart", "warenkorb")
        scored: list[tuple[int, str]] = []
        for link in links:
            parsed = urlparse(link)
            if parsed.netloc and parsed.netloc.lower() != base.netloc.lower():
                continue
            if not self._url_ok(link):
                continue
            lowered = link.lower()
            if any(term in lowered for term in rejected):
                continue
            score = sum(4 for term in wanted if term in lowered)
            score += sum(2 for kw in intent.keywords[:6] if kw.lower() in lowered)
            if score > 0:
                scored.append((score, link))
        scored.sort(key=lambda x: (-x[0], len(x[1])))
        return list(dict.fromkeys(link for _, link in scored))[:5]

    @staticmethod
    def _extract_emails(text: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))

    @staticmethod
    def _extract_phones(text: str) -> list[str]:
        candidates = re.findall(r"(?:\+\d{1,3}[\s()/.-]*)?(?:\d[\s()/.-]*){6,}\d", text)
        cleaned = [re.sub(r"\s+", " ", c).strip(" .,-/") for c in candidates]
        return list(dict.fromkeys(c for c in cleaned if len(re.sub(r"\D", "", c)) >= 7))

    @staticmethod
    def _evidence_snippets(text: str) -> list[str]:
        lines = [line.strip() for line in re.split(r"[\n.。]", text) if len(line.strip()) > 40]
        return lines[:4]

    async def _llm_extract_supplier(
        self, text: str, url: str, intent: ProcurementIntent, evidence: DeepEvidence | None = None
    ) -> dict | None:
        """LLM extracts structured supplier data from page evidence."""
        prompt = (
            "Extract a B2B procurement supplier profile from the evidence below.\n"
            "Return ONLY a JSON object with these keys:\n"
            "- name: company name (string)\n"
            "- description: what they supply (string, max 200 chars, in the user's language)\n"
            "- products: list of specific products they offer\n"
            "- capabilities: list of their core capabilities (manufacturing, wholesale, etc.)\n"
            "- country: where they are based (string)\n"
            "- city: city name (string or null)\n"
            "- certifications: list of ISO/IATF/etc certifications mentioned\n"
            "- email: best procurement/sales email if present, else null\n"
            "- phone: best sales/contact phone if present, else null\n"
            "- address: street/address if present, else null\n"
            "- evidence_summary: short sentence explaining which pages support this profile\n\n"
            "If this is clearly NOT a supplier page, return {\"not_supplier\": true}.\n\n"
            f"Procurement category: {intent.category}\n"
            f"Target country: {intent.country}\n"
            f"URL: {url}\n"
            f"Fetched source URLs: {', '.join(evidence.source_urls) if evidence else url}\n"
            f"Email candidates: {', '.join(evidence.email_candidates) if evidence else ''}\n"
            f"Phone candidates: {', '.join(evidence.phone_candidates) if evidence else ''}\n\n"
            f"Evidence:\n{text[:8500]}"
        )

        try:
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
            elif hasattr(self.llm, "invoke"):
                response = await asyncio.to_thread(self.llm.invoke, prompt)
            else:
                return None

            content = str(getattr(response, "content", response))
            match = re.search(r"\{.*\}", content, re.S)
            if not match:
                return None
            parsed = json.loads(match.group(0))
            if parsed.get("not_supplier"):
                return None
            return parsed if isinstance(parsed, dict) and parsed.get("name") else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Rule-based query planning (fallback)
    # ------------------------------------------------------------------

    def _rule_plan_queries(self, intent: ProcurementIntent) -> list[str]:
        country = intent.country or "Germany"
        kw = " ".join(intent.keywords[:6])
        category = intent.category or ""
        exclusions = "-amazon -ebay -pinterest -linkedin -youtube -tiktok"
        queries = []

        # Always search B2B directories directly
        if country == "Germany":
            queries.append(f"site:wlw.de {kw} Lieferant {category}")
            queries.append(f"site:europages.de {kw} Deutschland {category}")
            queries.append(f"site:lieferanten.de {kw}")
        queries.append(f"site:kompass.com {kw} {category} supplier {country}")
        queries.append(f"site:industrystock.de {kw} {category}")

        # General web search with B2B terms
        queries.append(f"{kw} {category} supplier {country} B2B wholesale {exclusions}")
        if country == "Germany":
            queries.append(f"{kw} Lieferant Großhandel Deutschland {category} {exclusions}")

        return [q for q in queries if q][:6]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _url_ok(self, url: str) -> bool:
        if not url or not url.startswith(("http://", "https://")):
            return False
        parsed = urlparse(url)
        if parsed.path.lower().endswith(self.BLOCKED_FILE_EXTENSIONS):
            return False
        domain = parsed.netloc.lower().removeprefix("www.")
        if any(domain == bd or domain.endswith(f".{bd}") for bd in self.BLOCKED_DOMAINS):
            return False
        # Exclude B2B directory search/browse listing pages (not individual supplier profiles)
        if any(d in domain for d in self.B2B_DIRECTORY_DOMAINS):
            path_lower = parsed.path.lower()
            if any(pattern in path_lower for pattern in self.DIRECTORY_SEARCH_PATH_PATTERNS):
                return False
        return True

    def _useful_page_text(self, text: str) -> bool:
        normalized = (text or "").lower()
        if not normalized.strip():
            return False
        if any(marker in normalized for marker in ("captcha", "access denied", "bot detection", "enable javascript", "cloudflare ray id")):
            return False
        if self._extract_emails(text) or self._extract_phones(text):
            return True
        useful_markers = (
            "gmbh", "supplier", "lieferant", "großhandel", "wholesale", "products", "produkte",
            "contact", "kontakt", "impressum", "address", "strasse", "straße", "berlin", "germany",
        )
        return len(normalized) >= 30 or any(marker in normalized for marker in useful_markers)

    def _is_noisy_page(self, text: str) -> bool:
        normalized = (text or "").lower()
        noise = ("captcha", "access denied", "bot detection", "enable javascript",
                 "cloudflare ray id", "request unsuccessful")
        return any(marker in normalized for marker in noise) or len(normalized) < 50 or len(normalized) > 12000

    def _fallback_suppliers(self, intent: ProcurementIntent) -> list[dict]:
        if intent.category == "office":
            return [
                self._seed_to_supplier(s, intent)
                for s in self.OFFICE_FALLBACK_SUPPLIERS
            ]
        return []

    def _seed_to_supplier(self, seed: dict, intent: ProcurementIntent) -> dict:
        result = SearchResult(seed["name"], seed["website"], seed.get("description", ""))
        return self._normalize_supplier(seed, result, intent, source="web-research-fallback")

    def _normalize_supplier(
        self, data: dict, result: SearchResult, intent: ProcurementIntent, source: str
    ) -> dict:
        website = data.get("website") or result.url
        score = int(data.get("matchScore") or self._score(data, result, intent))
        return {
            "id": f"web-{uuid.uuid5(uuid.NAMESPACE_URL, website or result.title)}",
            "name": self._clean_title(data.get("name") or result.title),
            "category": data.get("category") or intent.category,
            "country": data.get("country") or intent.country,
            "city": data.get("city"),
            "description": self._best_description(data.get("description", ""), result.snippet),
            "products": self._ensure_list(data.get("products") or intent.keywords),
            "certifications": self._ensure_list(data.get("certifications") or intent.certifications),
            "contactPerson": data.get("contactPerson"),
            "phone": data.get("phone"),
            "email": data.get("email"),
            "website": website,
            "address": data.get("address"),
            "employees": None,
            "annualRevenue": None,
            "established": None,
            "capabilities": self._ensure_list(data.get("capabilities") or []),
            "matchScore": score,
            "source": source,
        }

    def _score(self, data: dict, result: SearchResult, intent: ProcurementIntent) -> int:
        text = f"{data.get('name', '')} {data.get('description', '')} {result.snippet} {result.url}".lower()
        score = 40

        # B2B directory bonus — strongest signal
        for d in self.B2B_DIRECTORY_DOMAINS:
            if d in result.url:
                score += 18
                break

        # Company name signals
        company_signals = ("gmbh", "ag", "kg", "gmbh & co", "limited", "ltd", "sarl", "spa", "bv")
        if any(s in result.title.lower() or s in text for s in company_signals):
            score += 8

        # B2B term signals
        b2b_signals = ("lieferant", "hersteller", "großhandel", "wholesaler", "supplier", "manufacturer")
        if any(s in text for s in b2b_signals):
            score += 6

        # Country match
        if intent.country and intent.country.lower() in text:
            score += 4
        if ".de" in result.url:
            score += 3

        # Has a real description
        desc = data.get("description") or ""
        if len(desc) > 30:
            score += 5

        return max(0, min(100, score))

    @staticmethod
    def _url_key(url: str) -> str:
        parsed = urlparse(url or "")
        if not parsed.netloc:
            return ""
        path = parsed.path.rstrip("/")
        return f"{parsed.netloc.lower().removeprefix('www.')}{path}"

    @staticmethod
    def _clean_title(title: str) -> str:
        title = re.sub(r"\s*[|–-]\s*(Buy|Shop|Online|Kaufen|Bestellen|Jetzt).*$", "", title or "", flags=re.I)
        return (title or "").strip()[:120] or "Web supplier"

    @staticmethod
    def _best_description(primary: str, fallback: str = "") -> str:
        for text in (primary, fallback):
            cleaned = WebResearcher.clean_text(text)
            if cleaned and len(cleaned) > 10:
                return cleaned[:420]
        return ""

    @staticmethod
    def _ensure_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return [str(value)] if value else []

    @staticmethod
    def clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def merge_supplier_lists(primary: list[dict], secondary: list[dict]) -> list[dict]:
        def priority(item: dict) -> tuple[int, int, int]:
            has_evidence = 1 if item.get("sourceUrls") or item.get("evidenceSnippets") else 0
            is_fallback = 1 if item.get("source") == "web-research-fallback" else 0
            return (has_evidence, -is_fallback, int(item.get("matchScore", 0)))

        merged: dict[str, dict] = {}
        for item in [*primary, *secondary]:
            key = WebResearcher._url_key(item.get("website", "")) or item.get("id") or item.get("name", "")
            if not key:
                continue
            existing = merged.get(key)
            if not existing or priority(item) > priority(existing):
                merged[key] = item

        return sorted(merged.values(), key=priority, reverse=True)
