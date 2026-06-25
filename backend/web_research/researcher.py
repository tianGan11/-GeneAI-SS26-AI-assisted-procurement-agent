from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from agent.parser import ProcurementIntent


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]: ...


class PageFetcher(Protocol):
    async def fetch_text(self, url: str) -> str: ...


class DuckDuckGoSearchProvider:
    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            def run() -> list[SearchResult]:
                with DDGS(timeout=12) as ddgs:
                    rows = list(ddgs.text(query, max_results=max_results))
                return [
                    SearchResult(
                        title=row.get("title") or "Web supplier",
                        url=row.get("href") or row.get("url") or "",
                        snippet=row.get("body") or "",
                    )
                    for row in rows
                    if row.get("href") or row.get("url")
                ]

            return await asyncio.to_thread(run)
        except Exception:
            return []


class StaticPageFetcher:
    async def fetch_text(self, url: str) -> str:
        try:
            import requests
            from bs4 import BeautifulSoup

            def run() -> str:
                response = requests.get(
                    url,
                    timeout=12,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                )
                if response.status_code >= 400:
                    return ""
                soup = BeautifulSoup(response.text, "html.parser")
                for noisy in soup(["script", "style", "noscript", "svg"]):
                    noisy.decompose()
                return WebResearcher.clean_text(soup.get_text(" "))

            return await asyncio.to_thread(run)
        except Exception:
            return ""


class WebResearcher:
    """Agent-like web research for procurement supplier discovery.

    Pipeline:
    1. Plan multiple category-aware search queries.
    2. Collect and de-duplicate search results.
    3. Filter software/login/noise pages.
    4. Fetch lightweight page text when useful.
    5. Normalize candidates to the same supplier schema used by the backend.
    6. Add category fallback suppliers when public search is blocked/noisy.
    """

    BLOCKED_TERMS = (
        "office 365", "microsoft 365",
        "login", "sign in", "signin", "konto anmelden", "software download",
    )
    BLOCKED_DOMAINS = (
        "microsoft.com", "office.com", "outlook.com",
        # Consumer marketplaces / social/product discovery pages are not supplier candidates.
        "amazon.de", "amazon.com", "ebay.de", "ebay.com", "etsy.com", "aliexpress.com", "temu.com",
        "alibaba.com", "dhgate.com", "made-in-china.com", "globalsources.com",
        "pinterest.com", "facebook.com", "linkedin.com", "instagram.com", "youtube.com", "wikipedia.org",
        "stock.adobe.com", "adobe.com", "bing.com", "foreign.mingluji.com",
        "fortunebusinessinsights.com", "deutschepost.de",
        "scribd.com", "fliphtml5.com", "reverso.net", "context.reverso.net",
        "monoskop.org", "sostrenegrene.com", "efiliale.de", "idealo.de",
        "yumpu.com", "dokumen.pub", "staples.com",
    )
    BLOCKED_FILE_EXTENSIONS = (".pdf", ".doc", ".docx", ".ppt", ".pptx")
    NOISY_MARKERS = (
        "request unsuccessful", "incapsula incident", "distil_referrer", "use strict",
        "function(t)", "sessionstorage", "splide.defaults", "captcha", "access denied",
        "bot detection", "enable javascript", "cloudflare ray id",
    )
    B2B_DOMAINS = (
        "wlw.de", "wer-liefert-was.de", "europages.de", "europages.com", "kompass.com",
        "industrystock.de", "directindustry.com", "directindustry.de", "thomasnet.com",
    )
    B2B_MARKETPLACE_ROOT_DOMAINS = ("europages.de", "europages.com", "kompass.com", "wlw.de", "wer-liefert-was.de")

    CATEGORY_TERMS: dict[str, list[str]] = {
        "office": [
            "Bürobedarf Großhandel Lieferant Deutschland A4 Papier Ordner",
            "office supplies wholesaler Germany paper folders printer supplies",
            "Büromaterial Lieferant Deutschland Kopierpapier Druckerzubehör",
        ],
        "cleaning": [
            "Reinigungsmittel Großhandel Lieferant Deutschland",
            "cleaning supplies wholesaler Germany B2B",
        ],
        "firstAid": [
            "Erste Hilfe Bedarf Lieferant Deutschland Verbandkasten Pflaster",
            "first aid supplies supplier Germany B2B",
        ],
        "safetyShoes": [
            "Sicherheitsschuhe Lieferant Deutschland S1 S3",
            "safety shoes supplier Germany S1 S3",
        ],
        "glassAdhesive": [
            "Scheibenkleber Glas Klebstoff Lieferant Deutschland IATF",
            "automotive glass adhesive supplier Germany IATF",
        ],
        "rubberSeal": [
            "Dichtungsprofil EPDM Lieferant Deutschland",
            "rubber seal supplier Germany EPDM automotive",
        ],
        "hardware": [
            "Industriebedarf Befestigungstechnik Lieferant Deutschland",
            "hardware fastener supplier Germany B2B",
        ],
        "equipment": [
            "Industriebedarf Ausrüstung Lieferant Deutschland",
            "industrial equipment supplier Germany B2B",
        ],
        "packaging": [
            "Verpackung Karton Lieferant Deutschland Großhandel",
            "packaging supplier Germany B2B carton boxes",
        ],
    }

    OFFICE_POSITIVE_TERMS = (
        "bürobedarf", "buero", "office supplies", "paper", "papier", "ordner",
        "druckerpapier", "kopierpapier", "büromaterial", "buromaterial", "schreibwaren",
        "großhandel", "grosshandel", "supplier", "lieferant", "viking", "otto office",
        "böttcher", "boettcher", "büroshop24", "bueroshop24", "kaiserkraft", "schaefer-shop",
        "rajapack",
    )

    def __init__(self, search_provider: SearchProvider | None = None, page_fetcher: PageFetcher | None = None, llm=None):
        self.search_provider = search_provider or DuckDuckGoSearchProvider()
        self.page_fetcher = page_fetcher or StaticPageFetcher()
        self.llm = llm

    async def research(self, intent: ProcurementIntent, max_suppliers: int = 8) -> list[dict]:
        collected: dict[str, SearchResult] = {}
        for query in self.plan_queries(intent):
            for result in await self.search_provider.search(query, max_results=8):
                key = self.normalized_url_key(result.url) or result.title.lower()
                if key and key not in collected:
                    collected[key] = result
            if len(collected) >= max_suppliers * 2:
                break

        suppliers: list[dict] = []
        for result in collected.values():
            if not self.is_relevant_result(result, intent):
                continue
            supplier = await self.result_to_supplier(result, intent)
            if supplier and not self.is_noisy_or_blocked(supplier.get("description", "")):
                suppliers.append(supplier)
            elif supplier:
                supplier["description"] = result.snippet
                suppliers.append(supplier)
            if len(suppliers) >= max_suppliers:
                break

        suppliers = self.merge_supplier_lists(suppliers, self.fallback_suppliers(intent))
        return suppliers[:max_suppliers]

    def plan_queries(self, intent: ProcurementIntent) -> list[str]:
        country = intent.country or "Germany"
        keywords = " ".join(intent.keywords[:6])
        base_terms = self.CATEGORY_TERMS.get(intent.category or "", [
            "procurement supplier B2B wholesaler Germany",
            "industrial supplier Germany B2B procurement",
        ])
        exclusions = "-microsoft -office365 -outlook -login -signin"
        queries: list[str] = []
        for term in base_terms:
            queries.append(self.clean_text(f"{keywords} {country} {term} {exclusions}"))
        if intent.category == "office":
            queries.extend([
                self.clean_text(f"{keywords} site:wlw.de Bürobedarf Lieferant Deutschland {exclusions}"),
                self.clean_text(f"{keywords} site:europages.de Bürobedarf Deutschland {exclusions}"),
                self.clean_text(f"{keywords} site:kompass.com office supplies Germany {exclusions}"),
            ])
        else:
            category = intent.category or "supplier"
            queries.extend([
                self.clean_text(f"{keywords} site:wlw.de {category} Lieferant Deutschland"),
                self.clean_text(f"{keywords} site:europages.com {category} supplier Germany"),
            ])
        return list(dict.fromkeys(q for q in queries if q))[:8]

    def is_relevant_result(self, result: SearchResult, intent: ProcurementIntent) -> bool:
        text = f"{result.title} {result.url} {result.snippet}".lower()
        if not result.url.startswith(("http://", "https://")):
            return False
        parsed_url = urlparse(result.url)
        if parsed_url.path.lower().endswith(self.BLOCKED_FILE_EXTENSIONS):
            return False
        domain = parsed_url.netloc.lower().removeprefix("www.")
        if not result.url or any(domain == item or domain.endswith(f".{item}") for item in self.BLOCKED_DOMAINS):
            return False
        if any(term in text for term in self.BLOCKED_TERMS):
            return False
        if self.is_generic_marketplace_homepage(result.url, result.title):
            return False
        if self.is_noisy_or_blocked(text):
            return False
        if intent.category == "office":
            return any(term in text for term in self.OFFICE_POSITIVE_TERMS)
        if any(domain == item or domain.endswith(f".{item}") for item in self.B2B_DOMAINS):
            return True
        category_terms = " ".join(self.CATEGORY_TERMS.get(intent.category or "", [])).lower()
        return any(token in text for token in self.tokenize(category_terms)[:12])

    async def result_to_supplier(self, result: SearchResult, intent: ProcurementIntent) -> dict:
        page_text = ""
        if self.should_fetch_page(result.url):
            page_text = await self.page_fetcher.fetch_text(result.url)
        evidence_text = self.clean_text(" ".join(part for part in [result.title, result.snippet, page_text] if part))
        llm_supplier = await self.llm_extract_supplier(evidence_text, result.url, intent)
        if llm_supplier:
            return self.normalize_supplier(llm_supplier, result, intent, source="web-research-llm")
        return self.normalize_supplier({
            "name": self.clean_title(result.title),
            "description": self.best_description(result.snippet, page_text),
            "products": self.extract_products(evidence_text, intent),
            "capabilities": self.extract_capabilities(evidence_text, intent),
        }, result, intent, source="web-research")

    async def llm_extract_supplier(self, text: str, url: str, intent: ProcurementIntent) -> dict | None:
        if not self.llm or not text or self.is_noisy_or_blocked(text):
            return None
        prompt = (
            "Extract a B2B procurement supplier profile from the evidence text. "
            "Return only JSON with keys: name, description, products, capabilities, country, city, certifications. "
            "If this is not a supplier page, return {}.\n"
            f"Category: {intent.category}\nCountry: {intent.country}\nURL: {url}\nEvidence:\n{text[:3500]}"
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
            return parsed if isinstance(parsed, dict) and parsed.get("name") else None
        except Exception:
            return None

    def fallback_suppliers(self, intent: ProcurementIntent) -> list[dict]:
        seeds = self.fallback_supplier_seeds(intent)
        return [
            self.seed_to_supplier(seed, intent)
            for seed in seeds
        ]

    def fallback_supplier_seeds(self, intent: ProcurementIntent) -> list[dict]:
        if intent.category == "office":
            return [
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
        return []

    def seed_to_supplier(self, seed: dict, intent: ProcurementIntent) -> dict:
        result = SearchResult(seed["name"], seed["website"], seed.get("description", ""))
        return self.normalize_supplier(seed, result, intent, source="web-research-fallback")

    def normalize_supplier(self, data: dict, result: SearchResult, intent: ProcurementIntent, source: str) -> dict:
        website = data.get("website") or result.url
        return {
            "id": f"web-{uuid.uuid5(uuid.NAMESPACE_URL, website or result.title)}",
            "name": self.clean_title(data.get("name") or result.title),
            "category": data.get("category") or intent.category,
            "country": data.get("country") or intent.country,
            "city": data.get("city"),
            "description": self.best_description(data.get("description", ""), result.snippet),
            "products": self.ensure_list(data.get("products") or intent.keywords),
            "certifications": self.ensure_list(data.get("certifications") or intent.certifications),
            "contactPerson": None,
            "phone": None,
            "email": None,
            "website": website,
            "employees": None,
            "annualRevenue": None,
            "established": None,
            "capabilities": self.ensure_list(data.get("capabilities") or intent.keywords),
            "matchScore": int(data.get("matchScore") or self.estimate_score(data, result, intent)),
            "source": source,
        }

    def should_fetch_page(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        return bool(url) and not any(term in domain for term in ("microsoft", "office.com", "outlook"))

    def best_description(self, primary: str, fallback: str = "") -> str:
        for text in (primary, fallback):
            cleaned = self.clean_text(text)
            if cleaned and not self.is_noisy_or_blocked(cleaned):
                return cleaned[:420]
        return ""

    def extract_products(self, text: str, intent: ProcurementIntent) -> list[str]:
        products = list(intent.keywords)
        if intent.category == "office":
            for term in ("A4 Papier", "Ordner", "Kopierpapier", "Druckerzubehör", "Bürobedarf"):
                if term.lower() in text.lower() and term not in products:
                    products.append(term)
        return products[:8]

    def extract_capabilities(self, text: str, intent: ProcurementIntent) -> list[str]:
        caps = []
        if intent.category == "office":
            caps.extend(["Office supplies", "Bürobedarf"])
        if "großhandel" in text.lower() or "wholesale" in text.lower():
            caps.append("Wholesale")
        if "b2b" in text.lower():
            caps.append("B2B procurement")
        return list(dict.fromkeys(caps or intent.keywords))[:8]

    def estimate_score(self, data: dict, result: SearchResult, intent: ProcurementIntent) -> int:
        text = f"{data.get('name', '')} {data.get('description', '')} {result.snippet}".lower()
        score = 56
        if intent.category == "office" and any(term in text for term in self.OFFICE_POSITIVE_TERMS):
            score += 14
        if intent.country and intent.country.lower() in text:
            score += 6
        if intent.country == "Germany" and ("deutschland" in text or ".de/" in result.url or result.url.endswith(".de")):
            score += 6
        if any(domain in result.url for domain in self.B2B_DOMAINS):
            score += 5
        if result.url:
            score += 4  # real search hits should outrank static fallback seeds for the same URL
        return max(0, min(100, score))

    def is_noisy_or_blocked(self, text: str) -> bool:
        normalized = (text or "").lower()
        if not normalized:
            return False
        return any(marker in normalized for marker in self.NOISY_MARKERS) or len(normalized) > 1200

    def is_generic_marketplace_homepage(self, url: str, title: str = "") -> bool:
        parsed = urlparse(url or "")
        domain = parsed.netloc.lower().removeprefix("www.")
        path = (parsed.path or "/").strip("/")
        if not any(domain == item or domain.endswith(f".{item}") for item in self.B2B_MARKETPLACE_ROOT_DOMAINS):
            return False
        if path and path.lower() not in {"de", "en", "de/", "en/"}:
            return False
        title_text = (title or "").lower()
        generic_markers = ("marktplatz", "marketplace", "lieferanten und einkäufer", "buyers and sellers")
        return not title_text or any(marker in title_text for marker in generic_markers)

    @staticmethod
    def clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        return text

    @staticmethod
    def clean_title(title: str) -> str:
        title = WebResearcher.clean_text(re.sub(r"\s*[|–-]\s*(Buy|Shop|Online).*$", "", title or "", flags=re.I))
        return title[:120] or "Web supplier"

    @staticmethod
    def ensure_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return [str(value)] if value else []

    @staticmethod
    def normalized_url_key(url: str) -> str:
        parsed = urlparse(url or "")
        if not parsed.netloc:
            return ""
        path = parsed.path.rstrip("/")
        return f"{parsed.netloc.lower().removeprefix('www.')}{path}"

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return re.findall(r"[\w\u4e00-\u9fffäöüÄÖÜß+-]+", (text or "").lower())

    @staticmethod
    def merge_supplier_lists(primary: list[dict], secondary: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        for item in [*primary, *secondary]:
            key = WebResearcher.normalized_url_key(item.get("website", "")) or item.get("id") or item.get("name", "")
            if not key:
                continue
            existing = merged.get(key)
            if not existing or item.get("matchScore", 0) > existing.get("matchScore", 0):
                merged[key] = item
        return sorted(merged.values(), key=lambda item: item.get("matchScore", 0), reverse=True)
