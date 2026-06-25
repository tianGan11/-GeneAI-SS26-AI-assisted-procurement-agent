from __future__ import annotations

import asyncio
import json
import re
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.parser import ProcurementIntent
from web_research.researcher import SearchResult, WebResearcher


class FakeSearchProvider:
    def __init__(self, by_query: dict[str, list[SearchResult]] | None = None):
        self.by_query = by_query or {}
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 8) -> list[SearchResult]:
        self.queries.append(query)
        value = self.by_query.get(query, [])
        if value and isinstance(value[0], list):
            batch = value.pop(0)
            return batch[:max_results]
        return value[:max_results]


class FakePageFetcher:
    async def fetch_text(self, url: str) -> str:
        fixtures = {
            "https://www.viking.de/": "Viking Bürobedarf A4 Papier Ordner Druckerzubehör Deutschland B2B supplier",
            "https://www.office.com/": "Microsoft Office 365 login sign in Outlook",
            "https://www.otto-office.com/de/": "OTTO Office Bürobedarf Bürotechnik Büromöbel Kopierpapier Deutschland",
        }
        return fixtures.get(url, "")


class DeepFakePageFetcher:
    def __init__(self):
        self.fetched: list[str] = []

    async def fetch_page(self, url: str):
        self.fetched.append(url)
        from web_research.researcher import PageSnapshot
        fixtures = {
            "https://supplier.example/": PageSnapshot(
                url="https://supplier.example/",
                text="Example Office GmbH B2B supplier for office products.",
                links=[
                    "https://supplier.example/products",
                    "https://supplier.example/contact",
                    "https://supplier.example/impressum",
                    "https://supplier.example/blog",
                ],
            ),
            "https://supplier.example/products": PageSnapshot(
                url="https://supplier.example/products",
                text="Products: A4 copy paper, file folders, binders, printer supplies, office stationery wholesale.",
                links=[],
            ),
            "https://supplier.example/contact": PageSnapshot(
                url="https://supplier.example/contact",
                text="Contact sales team: sales@supplier.example Tel +49 30 1234567 Berlin Germany.",
                links=[],
            ),
            "https://supplier.example/impressum": PageSnapshot(
                url="https://supplier.example/impressum",
                text="Example Office GmbH, Hauptstrasse 1, 10115 Berlin, Germany. Geschäftsführer Max Muster.",
                links=[],
            ),
            "https://supplier.example/blog": PageSnapshot(
                url="https://supplier.example/blog",
                text="Blog article about office productivity tips.",
                links=[],
            ),
        }
        return fixtures.get(url, PageSnapshot(url=url, text="", links=[]))

    async def fetch_text(self, url: str) -> str:
        page = await self.fetch_page(url)
        return page.text


class StubLLM:
    """LLM that simulates procurement-friendly responses for testing."""
    def __init__(self, mode: str = "supplier"):
        self.mode = mode
        self.calls: list[str] = []

    async def ainvoke(self, prompt: str):
        self.calls.append(prompt)
        if "Generate" in prompt and "search queries" in prompt.lower() or "DuckDuckGo" in prompt:
            return _FakeResponse("\n".join([
                "site:wlw.de Bürobedarf A4 Papier Ordner Lieferant Deutschland",
                "site:europages.de A4 Papier Ordner Deutschland Bürobedarf",
                "site:lieferanten.de A4 Papier Ordner Bürobedarf",
                "A4 Papier Ordner Lieferant Deutschland B2B Großhandel -Amazon -eBay -Pinterest",
                "office supplies wholesaler Germany A4 paper folders B2B -amazon -ebay",
            ]))
        if "evaluating web search results" in prompt.lower() or "supplier page" in prompt.lower():
            return _FakeResponse(json.dumps([
                {"index": 1, "is_supplier": True, "reason": "Office supplier company"},
                {"index": 2, "is_supplier": True, "reason": "Bürobedarf B2B supplier"},
            ]))
        if "Extract a B2B procurement supplier" in prompt:
            if "viking" in prompt.lower():
                return _FakeResponse(json.dumps({
                    "name": "Viking Office Deutschland",
                    "description": "German office supplies wholesale supplier for A4 paper, folders, printer supplies.",
                    "products": ["A4 Papier", "Ordner", "Druckerzubehör"],
                    "capabilities": ["Office supplies", "Bürobedarf", "B2B wholesale"],
                    "country": "Germany",
                    "city": "Berlin",
                    "certifications": [],
                }))
            if "otto" in prompt.lower():
                return _FakeResponse(json.dumps({
                    "name": "OTTO Office",
                    "description": "German office supplies, technology and furniture B2B supplier.",
                    "products": ["Kopierpapier", "Ordner", "Büromaterial"],
                    "capabilities": ["Office supplies", "Bürotechnik"],
                    "country": "Germany",
                    "city": "Hamburg",
                    "certifications": [],
                }))
        return _FakeResponse("{}")


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class WebResearcherTest(unittest.TestCase):
    def test_rule_query_planning_targets_b2b_directories(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier"])
        researcher = WebResearcher(search_provider=FakeSearchProvider(), page_fetcher=FakePageFetcher())

        queries = researcher._rule_plan_queries(intent)
        joined = "\n".join(queries).lower()

        self.assertGreaterEqual(len(queries), 5)
        self.assertIn("site:wlw.de", joined)
        self.assertIn("site:europages", joined)
        self.assertIn("-amazon", joined)
        self.assertIn("-ebay", joined)
        self.assertNotIn("automotive supplier", joined)

    def test_research_with_llm_driven_pipeline_yields_real_suppliers(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "Papier", "Ordner"])
        provider = FakeSearchProvider({
            "site:wlw.de Bürobedarf A4 Papier Ordner Lieferant Deutschland": [
                SearchResult(title="Office 365 login", url="https://www.office.com/", snippet="Microsoft login"),
                SearchResult(title="Viking Office Deutschland Bürobedarf", url="https://www.viking.de/", snippet="A4 Papier Ordner supplier"),
                SearchResult(title="OTTO Office Bürobedarf", url="https://www.otto-office.com/de/", snippet="Kopierpapier Büromaterial"),
            ],
            "site:europages.de A4 Papier Ordner Deutschland Bürobedarf": [
                SearchResult(title="Viking Office Deutschland Bürobedarf", url="https://www.viking.de/", snippet="A4 Papier Ordner supplier"),
            ],
            "site:lieferanten.de A4 Papier Ordner Bürobedarf": [],
            "A4 Papier Ordner Lieferant Deutschland B2B Großhandel -Amazon -eBay -Pinterest": [
                SearchResult(title="Viking Office Deutschland Bürobedarf", url="https://www.viking.de/", snippet="A4 Papier Ordner supplier"),
            ],
            "office supplies wholesaler Germany A4 paper folders B2B -amazon -ebay": [
                SearchResult(title="OTTO Office Bürobedarf", url="https://www.otto-office.com/de/", snippet="Kopierpapier Büromaterial"),
            ],
        })
        researcher = WebResearcher(
            search_provider=provider,
            page_fetcher=FakePageFetcher(),
            llm=StubLLM(),
        )

        suppliers = asyncio.run(researcher.research(intent, max_suppliers=5))

        names = [s["name"] for s in suppliers]
        websites = [s["website"] for s in suppliers]

        # Non-supplier domains should be excluded
        self.assertNotIn("https://www.office.com/", websites)
        # Office fallback suppliers should fill any gaps
        self.assertGreaterEqual(len(suppliers), 4)
        # All results should be in the right category
        for s in suppliers:
            self.assertEqual(s["category"], "office")

    def test_blocked_domains_are_filtered(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["Ordner"])
        # Test that blocked domains are excluded by _url_ok
        researcher = WebResearcher()
        blocked_urls = [
            "https://www.amazon.de/HERMA-Ordner/dp/B09MQY2PT7",
            "https://de.pinterest.com/pin/258323728618087480/",
            "https://www.ebay.de/itm/123",
            "https://www.tiktok.com/@office_supplies",
            "https://www.instagram.com/office_supplier/",
        ]
        for url in blocked_urls:
            self.assertFalse(researcher._url_ok(url), url)

        supplier_url = "https://www.viking.de/"
        self.assertTrue(researcher._url_ok(supplier_url))

    def test_noisy_page_detection(self):
        researcher = WebResearcher()
        self.assertTrue(researcher._is_noisy_page("captcha verification required"))
        self.assertTrue(researcher._is_noisy_page("access denied by bot detection"))
        self.assertTrue(researcher._is_noisy_page(""))  # too short to be useful text
        self.assertFalse(researcher._is_noisy_page("German office-supplies supplier for paper and folders"))

    def test_rule_fallback_without_llm_still_works(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["Bürobedarf"])
        provider = FakeSearchProvider({
            "site:wlw.de Bürobedarf Lieferant office": [
                SearchResult("Bürobedarf Müller GmbH - Lieferant", "https://www.europages.de/BUEROBEDARF-MUELLER/000000.html", "Bürobedarf Lieferant Deutschland"),
            ],
            "site:europages.de Bürobedarf Deutschland office": [
                SearchResult("Papier Großhandel Schmidt KG", "https://www.europages.de/papier/", "Großhandel Papier Deutschland"),
            ],
        })
        researcher = WebResearcher(search_provider=provider, page_fetcher=FakePageFetcher())
        queries = researcher._rule_plan_queries(intent)
        # FakeSearchProvider only returns results for queries that match its keys
        # so we only provide results for the first two queries
        provider.by_query = {
            queries[0]: [SearchResult("Müller Bürobedarf GmbH", "https://www.europages.de/", "Bürobedarf Lieferant")],
            queries[1]: [SearchResult("Schmidt Papier KG", "https://www.europages.de/", "Papier Großhandel")],
        }
        suppliers = asyncio.run(researcher.research(intent, max_suppliers=3))
        # Without LLM, should still get office fallback suppliers
        self.assertGreaterEqual(len(suppliers), 3)
        for s in suppliers:
            self.assertEqual(s["category"], "office")
    def test_deep_supplier_research_fetches_product_contact_and_impressum_pages(self):
        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "paper", "folders"])
        fetcher = DeepFakePageFetcher()
        researcher = WebResearcher(search_provider=FakeSearchProvider(), page_fetcher=fetcher)
        events: list[tuple[str, str, int]] = []

        evidence = asyncio.run(researcher._build_deep_evidence(
            SearchResult("Example Office GmbH", "https://supplier.example/", "A4 paper folders supplier"),
            intent,
            progress=lambda phase, message, pct: events.append((phase, message, pct)),
            index=1,
            total=1,
        ))

        self.assertIn("https://supplier.example/products", fetcher.fetched)
        self.assertIn("https://supplier.example/contact", fetcher.fetched)
        self.assertIn("https://supplier.example/impressum", fetcher.fetched)
        self.assertNotIn("https://supplier.example/blog", fetcher.fetched)
        self.assertIn("A4 copy paper", evidence.text)
        self.assertIn("sales@supplier.example", evidence.text)
        self.assertIn("Hauptstrasse 1", evidence.text)
        self.assertIn("sales@supplier.example", evidence.email_candidates)
        self.assertIn("+49 30 1234567", evidence.phone_candidates)
        self.assertGreaterEqual(len(evidence.source_urls), 3)
        self.assertTrue(any("深挖" in message or "官网" in message for _, message, _ in events))
    def test_research_adds_rule_queries_when_llm_queries_return_too_few_results(self):
        class SparseLLM(StubLLM):
            async def ainvoke(self, prompt: str):
                self.calls.append(prompt)
                if "Generate" in prompt and "search queries" in prompt.lower() or "DuckDuckGo" in prompt:
                    return _FakeResponse('site:wlw.de "overly exact no results"')
                if "Extract a B2B procurement supplier" in prompt:
                    return _FakeResponse(json.dumps({
                        "name": "Fallback Query Office Supplier",
                        "description": "Supplier found through rule fallback query.",
                        "products": ["A4 paper", "folders"],
                        "capabilities": ["B2B wholesale"],
                        "country": "Germany",
                    }))
                if "evaluating web search results" in prompt.lower() or "supplier page" in prompt.lower():
                    return _FakeResponse(json.dumps([{"index": 0, "is_supplier": True, "reason": "real supplier"}]))
                return _FakeResponse("{}")

        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "paper", "folders"])
        provider = FakeSearchProvider()
        researcher = WebResearcher(search_provider=provider, page_fetcher=FakePageFetcher(), llm=SparseLLM())
        rule_queries = researcher._rule_plan_queries(intent)
        provider.by_query = {
            rule_queries[0]: [SearchResult("Fallback Query Office Supplier", "https://www.viking.de/", "A4 paper folder wholesaler")]
        }

        suppliers = asyncio.run(researcher.research(intent, max_suppliers=3))

        self.assertIn(rule_queries[0], provider.queries)
        self.assertTrue(any(s["name"] == "Fallback Query Office Supplier" for s in suppliers))

    def test_research_backfills_when_llm_filter_is_too_strict(self):
        class OverStrictFilterLLM(StubLLM):
            async def ainvoke(self, prompt: str):
                self.calls.append(prompt)
                if "Generate" in prompt and "search queries" in prompt.lower() or "DuckDuckGo" in prompt:
                    return _FakeResponse("site:wlw.de office paper folders supplier Germany")
                if "evaluating web search results" in prompt.lower() or "supplier page" in prompt.lower():
                    return _FakeResponse(json.dumps([{"index": 0, "is_supplier": True, "reason": "only one despite many good candidates"}]))
                if "Extract a B2B procurement supplier" in prompt:
                    match = re.search(r"Source: (https?://[^\s]+)", prompt)
                    url = match.group(1) if match else "https://unknown.example/"
                    name = url.split("//", 1)[1].split(".", 1)[0].title() + " Office GmbH"
                    return _FakeResponse(json.dumps({
                        "name": name,
                        "description": "Office supplies wholesaler for A4 paper and folders.",
                        "products": ["A4 paper", "folders"],
                        "capabilities": ["B2B wholesale"],
                        "country": "Germany",
                    }))
                return _FakeResponse("{}")

        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "paper", "folders"])
        query = "site:wlw.de office paper folders supplier Germany"
        provider = FakeSearchProvider({
            query: [
                SearchResult(f"Supplier {idx} GmbH Bürobedarf", f"https://supplier{idx}.example/", "A4 paper folders wholesaler Germany")
                for idx in range(10)
            ]
        })
        researcher = WebResearcher(search_provider=provider, page_fetcher=FakePageFetcher(), llm=OverStrictFilterLLM())

        suppliers = asyncio.run(researcher.research(intent, max_suppliers=6))

        web_suppliers = [s for s in suppliers if s.get("source") != "web-research-fallback"]
        self.assertGreaterEqual(len(web_suppliers), 6)

    def test_research_retries_empty_search_once_to_reduce_result_flapping(self):
        class SimpleLLM(StubLLM):
            async def ainvoke(self, prompt: str):
                self.calls.append(prompt)
                if "Generate" in prompt and "search queries" in prompt.lower() or "DuckDuckGo" in prompt:
                    return _FakeResponse("site:wlw.de retry office supplier Germany")
                if "evaluating web search results" in prompt.lower() or "supplier page" in prompt.lower():
                    return _FakeResponse(json.dumps([{"index": 0, "is_supplier": True, "reason": "supplier after retry"}]))
                if "Extract a B2B procurement supplier" in prompt:
                    return _FakeResponse(json.dumps({
                        "name": "Retry Supplier GmbH",
                        "description": "Supplier found after retry.",
                        "products": ["A4 paper"],
                        "capabilities": ["B2B wholesale"],
                        "country": "Germany",
                    }))
                return _FakeResponse("{}")

        intent = ProcurementIntent(category="office", country="Germany", keywords=["A4", "paper"])
        query = "site:wlw.de retry office supplier Germany"
        provider = FakeSearchProvider({
            query: [[], [SearchResult("Retry Supplier GmbH", "https://retry.example/", "A4 paper supplier Germany")]]
        })
        researcher = WebResearcher(search_provider=provider, page_fetcher=FakePageFetcher(), llm=SimpleLLM())

        suppliers = asyncio.run(researcher.research(intent, max_suppliers=3))

        self.assertGreaterEqual(provider.queries.count(query), 2)
        self.assertTrue(any(s["name"] == "Retry Supplier GmbH" for s in suppliers))

    def test_merge_prioritizes_deep_research_evidence_over_fallback(self):
        merged = WebResearcher.merge_supplier_lists(
            [{
                "name": "Real Crawled Supplier",
                "website": "https://real.example/",
                "matchScore": 68,
                "source": "web-research-llm",
                "sourceUrls": ["https://real.example/", "https://real.example/contact"],
                "evidenceSnippets": ["A4 paper and folders wholesale supplier"],
            }],
            [{
                "name": "Seed Fallback Supplier",
                "website": "https://fallback.example/",
                "matchScore": 75,
                "source": "web-research-fallback",
            }],
        )

        self.assertEqual(merged[0]["name"], "Real Crawled Supplier")


if __name__ == "__main__":
    unittest.main()
