from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCRAPER_DIR = Path(__file__).resolve().parent


SUPPLIER_FIELDS = [
    "id",
    "name",
    "category",
    "country",
    "city",
    "description",
    "products",
    "certifications",
    "contactPerson",
    "phone",
    "email",
    "website",
    "employees",
    "annualRevenue",
    "established",
    "capabilities",
    "matchScore",
    "source",
]


@dataclass
class ScrapeRules:
    selectors: dict[str, list[str]] = field(default_factory=dict)
    product_selectors: list[str] = field(default_factory=list)
    capability_selectors: list[str] = field(default_factory=list)
    certification_patterns: list[str] = field(default_factory=list)
    js_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "selectors": self.selectors,
            "product_selectors": self.product_selectors,
            "capability_selectors": self.capability_selectors,
            "certification_patterns": self.certification_patterns,
            "js_required": self.js_required,
        }


class DynamicScraper:
    """AI-assisted supplier scraper with static-first extraction and Selenium fallback."""

    _rules_cache: dict[str, dict[str, Any]] = {}
    _last_request_at: float = 0.0

    def __init__(self, llm=None, request_delay_seconds: float = 2.0):
        self.llm = llm or self._create_llm()
        self.request_delay_seconds = request_delay_seconds
        self.system_context = self._load_system_context()

    def analyze_site(self, url: str) -> dict[str, Any]:
        """Identify page structure and return reusable scrape rules for the domain."""
        domain = self._domain(url)
        if domain in self._rules_cache:
            return self._rules_cache[domain]

        html = self._fetch_static(url)
        rules = self._heuristic_rules(html or "")
        llm_rules = self._llm_rules(url, html or "")
        if llm_rules:
            rules = self._merge_rules(rules, llm_rules)

        if self._looks_js_heavy(html or ""):
            rules["js_required"] = True

        self._rules_cache[domain] = rules
        return rules

    def scrape_with_rules(self, url: str, rules: dict[str, Any]) -> dict[str, Any]:
        """Extract supplier data using generated rules."""
        html = self._fetch_static(url)
        if html and not rules.get("js_required"):
            supplier = self._extract_from_html(url, html, rules)
            if self._has_useful_data(supplier):
                return supplier

        if rules.get("js_required") or self._looks_js_heavy(html or ""):
            supplier = self._scrape_with_selenium(url)
            if self._has_useful_data(supplier):
                return self._normalize_supplier(supplier, url)

        if html:
            return self._extract_from_html(url, html, rules)
        return self._empty_supplier(url)

    def scrape_supplier(self, url: str) -> dict[str, Any]:
        """Full pipeline: analyze site, scrape data, normalize to suppliers.json schema."""
        try:
            rules = self.analyze_site(url)
            supplier = self.scrape_with_rules(url, rules)
            return self._normalize_supplier(supplier, url)
        except Exception:
            return {}

    def _fetch_static(self, url: str) -> str:
        self._rate_limit()
        try:
            import requests

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
            return response.text
        except Exception:
            return ""

    def _extract_from_html(self, url: str, html: str, rules: dict[str, Any]) -> dict[str, Any]:
        try:
            from bs4 import BeautifulSoup
        except Exception:
            return self._extract_with_regex(url, html)

        soup = BeautifulSoup(html, "html.parser")
        for noisy in soup(["script", "style", "noscript", "svg"]):
            noisy.decompose()

        text = self._clean_text(soup.get_text(" "))
        selectors = rules.get("selectors", {})
        supplier = {
            "name": self._first_selector_text(soup, selectors.get("name", [])) or self._meta_content(soup, "og:site_name") or self._title_name(soup),
            "description": self._first_selector_text(soup, selectors.get("description", [])) or self._meta_content(soup, "description"),
            "city": self._first_selector_text(soup, selectors.get("city", [])) or self._extract_city(text),
            "phone": self._first_regex(text, r"(?:(?:\+|00)\d{1,3}[\s()/.-]?)?(?:\d[\s()/.-]?){7,}\d"),
            "email": self._first_regex(text, r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
            "website": url,
            "employees": self._first_regex(text, r"\b\d{1,3}(?:[.,]\d{3})*\+?\s*(?:employees|Mitarbeiter|Besch\u00e4ftigte)\b", re.I),
            "annualRevenue": self._extract_revenue(text),
            "established": self._extract_established(text),
            "products": self._list_from_selectors(soup, rules.get("product_selectors", [])) or self._keyword_list(text, ["adhesive", "seal", "glass", "packaging", "fastener", "rubber", "Klebstoff", "Dichtung", "Glas"]),
            "capabilities": self._list_from_selectors(soup, rules.get("capability_selectors", [])) or self._capability_phrases(text),
            "certifications": self._extract_certifications(text, rules.get("certification_patterns", [])),
        }
        return self._normalize_supplier(supplier, url)

    def _scrape_with_selenium(self, url: str) -> dict[str, Any]:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except Exception:
            return {}

        driver = None
        try:
            self._rate_limit()
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            time.sleep(4)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            html = driver.page_source
            return self._extract_from_html(url, html, self._heuristic_rules(html))
        except Exception:
            return {}
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _llm_rules(self, url: str, html: str) -> dict[str, Any]:
        if not self.llm or not html:
            return {}
        try:
            sample = self._html_sample(html)
            prompt = (
                f"{self.system_context}\n\n"
                "Analyze this supplier/company page and return only JSON scrape rules. "
                "Use this shape: {\"selectors\":{\"name\":[],\"description\":[],\"city\":[]},"
                "\"product_selectors\":[],\"capability_selectors\":[],"
                "\"certification_patterns\":[],\"js_required\":false}.\n"
                f"URL: {url}\nHTML sample:\n{sample}"
            )
            if hasattr(self.llm, "invoke"):
                response = self.llm.invoke(prompt)
                content = getattr(response, "content", response)
            else:
                return {}
            return self._parse_json_object(str(content))
        except Exception:
            return {}

    def _heuristic_rules(self, html: str) -> dict[str, Any]:
        rules = ScrapeRules(
            selectors={
                "name": [
                    "h1",
                    "[class*='company-name']",
                    "[data-test*='company'] h1",
                    "[itemprop='name']",
                ],
                "description": [
                    "[data-test='company-description-full']",
                    "[class*='description']",
                    "[itemprop='description']",
                    "main p",
                    "article p",
                ],
                "city": [
                    "[itemprop='addressLocality']",
                    "[class*='location']",
                    "[class*='address']",
                    "address",
                ],
            },
            product_selectors=[
                "[class*='product']",
                "[data-test*='product']",
                "a[href*='produkt']",
                "a[href*='product']",
            ],
            capability_selectors=[
                "[class*='capabil']",
                "[class*='service']",
                "[class*='expertise']",
                "li",
            ],
            certification_patterns=[
                r"IATF\s*16949",
                r"ISO\s*9001",
                r"ISO\s*14001",
                r"ISO\s*45001",
                r"FSC",
                r"TISAX",
            ],
            js_required=self._looks_js_heavy(html),
        )
        return rules.to_dict()

    def _normalize_supplier(self, supplier: dict[str, Any], url: str) -> dict[str, Any]:
        normalized = self._empty_supplier(url)
        normalized.update({key: supplier.get(key) for key in SUPPLIER_FIELDS if key in supplier})
        normalized["id"] = supplier.get("id") or f"web-{uuid.uuid5(uuid.NAMESPACE_URL, url)}"
        normalized["name"] = self._clean_value(normalized.get("name")) or self._domain(url)
        normalized["description"] = self._clean_value(normalized.get("description")) or ""
        normalized["website"] = supplier.get("website") or url
        normalized["products"] = self._string_list(supplier.get("products"))
        normalized["certifications"] = self._string_list(supplier.get("certifications"))
        normalized["capabilities"] = self._string_list(supplier.get("capabilities"))
        normalized["established"] = self._to_int_or_none(supplier.get("established"))
        normalized["matchScore"] = int(supplier.get("matchScore") or self._quality_score(normalized))
        normalized["source"] = supplier.get("source") or "deep-web"
        return normalized

    def _empty_supplier(self, url: str) -> dict[str, Any]:
        return {
            "id": f"web-{uuid.uuid5(uuid.NAMESPACE_URL, url)}",
            "name": "",
            "category": None,
            "country": None,
            "city": None,
            "description": "",
            "products": [],
            "certifications": [],
            "contactPerson": None,
            "phone": None,
            "email": None,
            "website": url,
            "employees": None,
            "annualRevenue": None,
            "established": None,
            "capabilities": [],
            "matchScore": 50,
            "source": "deep-web",
        }

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self.__class__._last_request_at
        if elapsed < self.request_delay_seconds:
            time.sleep(self.request_delay_seconds - elapsed)
        self.__class__._last_request_at = time.monotonic()

    @staticmethod
    def _load_system_context() -> str:
        path = SCRAPER_DIR / "crawler_instructions.md"
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    @staticmethod
    def _create_llm():
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-key-here":
            return None
        try:
            from langchain_openai import ChatOpenAI

            kwargs: dict[str, Any] = {"model": os.getenv("LLM_MODEL", "gpt-4o"), "temperature": 0}
            base_url = os.getenv("OPENAI_BASE_URL")
            if base_url:
                kwargs["base_url"] = base_url
            return ChatOpenAI(**kwargs)
        except Exception:
            return None

    @staticmethod
    def _domain(url: str) -> str:
        return urlparse(url).netloc.lower().removeprefix("www.")

    @staticmethod
    def _looks_js_heavy(html: str) -> bool:
        if not html:
            return True
        text_len = len(re.sub(r"<[^>]+>", " ", html).strip())
        script_count = html.lower().count("<script")
        root_markers = ("id=\"__next\"", "id=\"root\"", "data-reactroot", "nuxt")
        return text_len < 500 and (script_count > 8 or any(marker in html.lower() for marker in root_markers))

    @staticmethod
    def _merge_rules(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        merged["selectors"] = dict(base.get("selectors", {}))
        for field_name, selectors in override.get("selectors", {}).items():
            merged["selectors"][field_name] = DynamicScraper._dedupe(
                list(selectors or []) + merged["selectors"].get(field_name, [])
            )
        for key in ("product_selectors", "capability_selectors", "certification_patterns"):
            merged[key] = DynamicScraper._dedupe(list(override.get(key) or []) + list(base.get(key) or []))
        if override.get("js_required") is True:
            merged["js_required"] = True
        return merged

    @staticmethod
    def _first_selector_text(soup, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                for element in soup.select(selector):
                    text = DynamicScraper._clean_text(element.get_text(" "))
                    if len(text) >= 2:
                        return text[:500]
            except Exception:
                continue
        return None

    @staticmethod
    def _list_from_selectors(soup, selectors: list[str], limit: int = 8) -> list[str]:
        values = []
        for selector in selectors:
            try:
                for element in soup.select(selector):
                    text = DynamicScraper._clean_text(element.get_text(" "))
                    if 3 <= len(text) <= 120:
                        values.append(text)
            except Exception:
                continue
        return DynamicScraper._dedupe(values)[:limit]

    @staticmethod
    def _extract_with_regex(url: str, html: str) -> dict[str, Any]:
        text = DynamicScraper._clean_text(re.sub(r"<[^>]+>", " ", html))
        return {
            "name": DynamicScraper._domain(url),
            "description": text[:300],
            "phone": DynamicScraper._first_regex(text, r"(?:(?:\+|00)\d{1,3}[\s()/.-]?)?(?:\d[\s()/.-]?){7,}\d"),
            "email": DynamicScraper._first_regex(text, r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
            "website": url,
            "certifications": DynamicScraper._extract_certifications(text, []),
        }

    @staticmethod
    def _extract_certifications(text: str, patterns: list[str]) -> list[str]:
        found = []
        for pattern in patterns or []:
            found.extend(match.group(0).upper().replace("  ", " ") for match in re.finditer(pattern, text, re.I))
        return DynamicScraper._dedupe(found)

    @staticmethod
    def _extract_city(text: str) -> str | None:
        match = re.search(r"\b(?:D-|DE-)?\d{5}\s+([A-Z\u00c4\u00d6\u00dc][A-Za-z\u00c4\u00d6\u00dc\u00e4\u00f6\u00fc\u00df -]{2,40})", text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_revenue(text: str) -> str | None:
        match = re.search(r"((?:€|EUR|CHF|US\$|\$|£)\s?\d+(?:[.,]\d+)?\s?(?:M|B|Mio|Million|Billion|bn|m)\+?)", text, re.I)
        return match.group(1) if match else None

    @staticmethod
    def _extract_established(text: str) -> int | None:
        match = re.search(r"(?:established|founded|gegründet|Gründung)\D{0,30}((?:18|19|20)\d{2})", text, re.I)
        return int(match.group(1)) if match else None

    @staticmethod
    def _keyword_list(text: str, keywords: list[str]) -> list[str]:
        lowered = text.lower()
        return [keyword for keyword in keywords if keyword.lower() in lowered][:8]

    @staticmethod
    def _capability_phrases(text: str) -> list[str]:
        candidates = re.findall(r"\b(?:manufacturing|production|assembly|engineering|extrusion|bonding|sealing|coating|logistics)[^.]{0,80}", text, re.I)
        return DynamicScraper._dedupe(DynamicScraper._clean_text(item) for item in candidates)[:6]

    @staticmethod
    def _meta_content(soup, name: str) -> str | None:
        selectors = [
            f"meta[name='{name}']",
            f"meta[property='{name}']",
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get("content"):
                return DynamicScraper._clean_text(element["content"])
        return None

    @staticmethod
    def _title_name(soup) -> str:
        title = soup.title.get_text(" ") if soup.title else ""
        return DynamicScraper._clean_text(re.split(r"\s[|-]\s", title)[0])

    @staticmethod
    def _first_regex(text: str, pattern: str, flags: int = 0) -> str | None:
        match = re.search(pattern, text, flags)
        return match.group(0).strip() if match else None

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return {}
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _html_sample(html: str) -> str:
        compact = re.sub(r"\s+", " ", html)
        return compact[:12000]

    @staticmethod
    def _has_useful_data(supplier: dict[str, Any]) -> bool:
        return bool(supplier and (supplier.get("name") or supplier.get("email") or supplier.get("phone")))

    @staticmethod
    def _quality_score(supplier: dict[str, Any]) -> int:
        score = 55
        for key in ("description", "phone", "email", "city", "employees", "annualRevenue"):
            if supplier.get(key):
                score += 4
        score += min(12, len(supplier.get("certifications", [])) * 3)
        score += min(8, len(supplier.get("products", [])) * 2)
        return max(0, min(85, score))

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _clean_value(value: Any) -> str:
        return DynamicScraper._clean_text(value) if value is not None else ""

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return DynamicScraper._dedupe(DynamicScraper._clean_text(item) for item in value if item)

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dedupe(values) -> list[str]:
        deduped = []
        seen = set()
        for value in values:
            cleaned = DynamicScraper._clean_text(value)
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                deduped.append(cleaned)
        return deduped
